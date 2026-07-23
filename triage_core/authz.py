"""FIDO2 security-key-backed human authorization receipts (CR-YK-001).

Deterministic core only: canonical authorization requests, challenge
derivation, receipt sidecar artifacts with tamper detection, structural
(pre-cryptographic) receipt checks, a one-use execution-capability lane, and
a public-credential store with revocation.

Everything that touches python-fido2 lives in ``triage_core.fido2_adapter``.
This module imports no optional dependency and must keep working on every
platform with no authenticator present.

Evidence-honesty vocabulary used throughout:

- A verified receipt is *hardware-backed evidence of possession and user
  interaction* with an enrolled FIDO2 security key.
- "User verification confirmed" is claimed only when the request required UV
  and the authenticator's UV flag was set and checked.
- Nothing here claims non-repudiation, proof of a specific authenticator
  model (attestation is not validated), or protection against an attacker
  who already controls this host or its clock. See the threat-model section
  of CR-YK-001.

Known limitation (documented, not yet solved): capability consumption reads
then appends over a shared JSONL ledger. Two concurrent consumers can both
observe "unconsumed" before either records consumption, so single-use is
enforced only against sequential use. Atomic claiming (e.g. SQLite
``BEGIN IMMEDIATE``) is a CR-DD-012B integration requirement; see
``consume_capability`` and the expected-failure concurrency test.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from triage_core.privacy_invariants import assert_persistent_privacy_safe
from triage_core.task_ledger import TaskLedger

# --- Constants ---------------------------------------------------------------

REQUEST_SCHEMA = "triagecore.authz.request.v2"
RECEIPT_SCHEMA = "triagecore.human_authorization_receipt.v2"
CREDENTIALS_SCHEMA = "triagecore.authz_credentials.v2"

# Local relying-party identity for a CLI-first flow. The origin is never
# served; it exists so WebAuthn client data has a stable, pinned value.
RP_ID = "triagecore.local"
RP_NAME = "TriageCore Governed Authorization"
ORIGIN = "https://triagecore.local"

DEFAULT_REQUEST_TTL_SECONDS = 600
DEFAULT_CAPABILITY_TTL_SECONDS = 600

EVENT_RECEIPT_RECORDED = "human_authorization_receipt"
EVENT_CAPABILITY_ISSUED = "execution_capability_issued"
EVENT_CAPABILITY_CONSUMED = "execution_capability_consumed"
EVENT_CAPABILITY_DENIED = "execution_capability_denied"

# Closed reason vocabularies (house style: no free-text reasons in evidence).
REASON_OK = "ok"
REASON_NOT_FOUND = "capability_not_found"
REASON_ALREADY_CONSUMED = "capability_already_consumed"
REASON_EXPIRED = "capability_expired"
REASON_DIGEST_MISMATCH = "artifact_digest_mismatch"

STRUCTURAL_FAIL_EXPIRED = "request_expired"
STRUCTURAL_FAIL_MALFORMED = "client_data_malformed"
STRUCTURAL_FAIL_TYPE = "client_data_type_mismatch"
STRUCTURAL_FAIL_CHALLENGE = "client_data_challenge_mismatch"
STRUCTURAL_FAIL_ORIGIN = "client_data_origin_mismatch"

AUTHZ_DIR_NAME = "authz"
RECEIPTS_DIR_NAME = "receipts"
CREDENTIALS_FILE_NAME = "credentials.json"


class AuthzError(Exception):
    """Base error for the authorization-receipt lane."""


class AuthzHardwareUnavailable(AuthzError):
    """Optional dependency or platform ceremony support is unavailable."""


class AuthzVerificationError(AuthzError):
    """A receipt failed structural or cryptographic verification."""


class AuthzArtifactTamperError(AuthzError):
    """A sidecar artifact does not match its recorded digest."""


# --- Small helpers -----------------------------------------------------------

def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _canonical_json_bytes(value: Any) -> bytes:
    """Canonical serialization: sorted keys, minimal separators, UTF-8.

    Key sorting makes the digest independent of construction order.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


def _restrict_file_permissions(path: str) -> None:
    """Best-effort owner-only permissions; a no-op where unsupported."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:  # pragma: no cover - platform dependent
        pass


# --- Normalization and validation ---------------------------------------------

_RISK_CLASSES = frozenset({"low", "medium", "high"})
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def normalize_identity(value: str) -> str:
    """Normalize a governed identifier: strip + lowercase.

    Security-bound identifiers must be stable: cosmetic variants ("Corey",
    "corey ", "COREY") fold to one canonical form before any hashing or
    comparison. Display labels are informational, live in the credential
    store, and are never security-bound.
    """
    return (value or "").strip().lower()


def _normalized_timestamp(value: str, field_name: str) -> str:
    try:
        return _isoformat(datetime.fromisoformat(value))
    except ValueError as exc:
        raise AuthzError(f"invalid {field_name} timestamp: {value!r}") from exc


# --- Authorization request and challenge -------------------------------------

@dataclass(frozen=True)
class AuthorizationRequest:
    """Canonical, versioned description of the one action being approved.

    Every field participates in the challenge digest, so changing the bound
    plan, decision, scope, RP, UV policy, approver identity, nonce, or
    validity window invalidates any assertion made over the previous value.

    Construction normalizes before anything is hashed — canonical JSON fixes
    field order, not case or stray whitespace, so "HIGH", "high", and
    "high " must not produce different challenges. Vocabulary and identity
    fields fold to strip+lowercase and are validated against closed
    grammars; ledger-linked identifiers (``task_id``, ``decision_id``) keep
    their case because ledger lookups are case-exact, but reject embedded
    whitespace. Digests must be ``sha256:<64 lowercase hex>``; the nonce
    must be a UUID (stored in canonical form); timestamps round-trip
    through ISO-8601 parsing.

    ``approver_identity_id`` is the *stable registered identifier* of the
    approving human and is security-bound. Human-facing display labels are
    informational only, live in the credential store, and never enter the
    challenge.

    All fields are privacy-safe metadata (digests, identifiers, vocabulary
    values). Never place prompt or file content here.
    """

    decision_id: str
    artifact_byte_digest: str
    plan_body_digest: str
    task_id: str
    risk_class: str                 # "low" | "medium" | "high"
    policy_version: str             # e.g. "cr-yk-001-v1"
    approver_identity_id: str       # stable governed identifier, e.g. "human-corey"
    user_verification_required: bool = True
    scope_digest: str = ""          # execution-scope / policy-decision digest, when available
    rp_id: str = RP_ID
    schema: str = REQUEST_SCHEMA
    nonce: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: str = field(default_factory=lambda: _isoformat(_utc_now()))
    expires_at: str = ""

    def __post_init__(self) -> None:
        if self.schema != REQUEST_SCHEMA:
            raise AuthzError(f"unsupported request schema: {self.schema!r}")

        for name in ("risk_class", "policy_version", "approver_identity_id", "rp_id"):
            object.__setattr__(self, name, normalize_identity(getattr(self, name)))
        for name in ("task_id", "decision_id"):
            stripped = (getattr(self, name) or "").strip()
            object.__setattr__(self, name, stripped)
            if not stripped or any(ch.isspace() for ch in stripped):
                raise AuthzError(f"{name} must be non-empty with no whitespace")

        if self.risk_class not in _RISK_CLASSES:
            raise AuthzError(f"unknown risk_class: {self.risk_class!r}")
        for name in ("policy_version", "approver_identity_id", "rp_id"):
            if not _IDENTIFIER_PATTERN.fullmatch(getattr(self, name)):
                raise AuthzError(f"{name} is not a stable governed identifier")
        for name in ("artifact_byte_digest", "plan_body_digest"):
            if not _DIGEST_PATTERN.fullmatch(getattr(self, name)):
                raise AuthzError(f"{name} must match sha256:<64 lowercase hex>")
        if self.scope_digest and not _DIGEST_PATTERN.fullmatch(self.scope_digest):
            raise AuthzError("scope_digest must be empty or sha256:<64 lowercase hex>")

        try:
            object.__setattr__(self, "nonce", str(uuid.UUID(self.nonce.strip())))
        except (AttributeError, ValueError) as exc:
            raise AuthzError(f"nonce must be a UUID: {self.nonce!r}") from exc

        object.__setattr__(
            self, "issued_at", _normalized_timestamp(self.issued_at, "issued_at")
        )
        if self.expires_at:
            object.__setattr__(
                self,
                "expires_at",
                _normalized_timestamp(self.expires_at, "expires_at"),
            )
        else:
            issued = datetime.fromisoformat(self.issued_at)
            expires = issued.timestamp() + DEFAULT_REQUEST_TTL_SECONDS
            object.__setattr__(
                self,
                "expires_at",
                _isoformat(datetime.fromtimestamp(expires, tz=timezone.utc)),
            )

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(asdict(self))

    def request_digest(self) -> str:
        return _sha256_hex(self.canonical_bytes())

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        moment = now or _utc_now()
        return moment > datetime.fromisoformat(self.expires_at)


def compute_challenge(request: AuthorizationRequest) -> bytes:
    """32-byte WebAuthn challenge.

    challenge = SHA-256(canonical_json(request))

    Versioning and domain separation come from the ``schema`` field inside
    the canonical payload rather than raw byte concatenation, so the bound
    field set is explicit and auditable in the serialized form.
    """
    return hashlib.sha256(request.canonical_bytes()).digest()


# --- Receipt ------------------------------------------------------------------

@dataclass
class HumanAuthorizationReceipt:
    """Request plus the WebAuthn assertion in standard JSON wire format.

    ``assertion_response`` is the W3C AuthenticationResponse JSON mapping
    (``id``/``rawId``/``response.clientDataJSON``/``response.authenticatorData``
    /``response.signature``, websafe-base64 values) exactly as produced by
    python-fido2's serialization, so offline verification can replay it
    through library primitives without bespoke parsing.

    Receipts are sidecar artifacts, never inline ledger content: the ledger
    privacy invariant forbids credential-adjacent keys and value-scans
    strings, and the ledger event stores digests plus privacy-safe metadata
    only. This is a boundary, not a renaming trick.
    """

    request: AuthorizationRequest
    credential_id: str              # b64url, matches assertion_response["rawId"]
    assertion_response: Dict[str, Any]
    user_verified: bool             # authenticator UV flag as observed
    recorded_at: str = field(default_factory=lambda: _isoformat(_utc_now()))

    def to_artifact_dict(self) -> Dict[str, Any]:
        return {
            "schema": RECEIPT_SCHEMA,
            "request": asdict(self.request),
            "credential_id": self.credential_id,
            "assertion_response": self.assertion_response,
            "user_verified": self.user_verified,
            "recorded_at": self.recorded_at,
        }

    def canonical_artifact_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_artifact_dict())

    def receipt_digest(self) -> str:
        return _sha256_hex(self.canonical_artifact_bytes())

    @classmethod
    def from_artifact_dict(cls, raw: Dict[str, Any]) -> "HumanAuthorizationReceipt":
        if raw.get("schema") != RECEIPT_SCHEMA:
            raise AuthzVerificationError(
                f"unknown receipt schema: {raw.get('schema')!r}"
            )
        return cls(
            request=AuthorizationRequest(**raw["request"]),
            credential_id=raw["credential_id"],
            assertion_response=dict(raw["assertion_response"]),
            user_verified=bool(raw["user_verified"]),
            recorded_at=raw["recorded_at"],
        )


def write_receipt_artifact(
    receipt: HumanAuthorizationReceipt,
    ledger_dir: str = ".triagecore",
) -> str:
    """Write the receipt sidecar artifact with restrictive permissions.

    Retention: receipts persist until the operator prunes them; they are
    inputs to offline re-verification, so removal degrades auditability of
    the runs they authorized (documented in CR-YK-001).
    """
    receipts_dir = os.path.join(ledger_dir, AUTHZ_DIR_NAME, RECEIPTS_DIR_NAME)
    os.makedirs(receipts_dir, exist_ok=True)
    digest_fragment = receipt.request.request_digest().split(":", 1)[1][:12]
    path = os.path.join(receipts_dir, f"receipt_{digest_fragment}.json")
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt.to_artifact_dict(), handle, sort_keys=True, indent=2)
        handle.write("\n")
    _restrict_file_permissions(temp_path)
    os.replace(temp_path, path)
    return path


def read_receipt_artifact(
    path: str,
    expected_digest: Optional[str] = None,
) -> HumanAuthorizationReceipt:
    """Load a receipt; verify tamper-evidence when a digest is supplied.

    ``expected_digest`` should come from the ledger's
    ``human_authorization_receipt`` event, closing the loop between the
    append-only record and the sidecar bytes.
    """
    with open(path, "r", encoding="utf-8") as handle:
        receipt = HumanAuthorizationReceipt.from_artifact_dict(json.load(handle))
    if expected_digest is not None and receipt.receipt_digest() != expected_digest:
        raise AuthzArtifactTamperError(
            f"receipt artifact digest mismatch at {path}"
        )
    return receipt


# --- Structural (pre-cryptographic) verification ------------------------------

@dataclass(frozen=True)
class StructuralVerification:
    passed: bool
    failure_reason: str = ""


def _client_data_from_wire(assertion_response: Dict[str, Any]) -> Dict[str, Any]:
    inner = assertion_response.get("response") or {}
    raw = inner.get("clientDataJSON")
    if not isinstance(raw, str):
        raise ValueError("missing clientDataJSON")
    return json.loads(b64url_decode(raw))


def verify_receipt_structure(
    receipt: HumanAuthorizationReceipt,
    now: Optional[datetime] = None,
) -> StructuralVerification:
    """Deterministic checks needing no cryptography and no python-fido2.

    Full verification (RP-ID hash, UP/UV flags, enrolled and non-revoked
    credential, signature) is ``triage_core.fido2_adapter.verify_receipt``,
    which layers python-fido2's server-side checks on top of this.
    """
    if receipt.request.is_expired(now):
        return StructuralVerification(False, STRUCTURAL_FAIL_EXPIRED)

    try:
        client_data = _client_data_from_wire(receipt.assertion_response)
    except (ValueError, json.JSONDecodeError):
        return StructuralVerification(False, STRUCTURAL_FAIL_MALFORMED)

    if client_data.get("type") != "webauthn.get":
        return StructuralVerification(False, STRUCTURAL_FAIL_TYPE)

    expected_challenge = b64url_encode(compute_challenge(receipt.request))
    if client_data.get("challenge") != expected_challenge:
        return StructuralVerification(False, STRUCTURAL_FAIL_CHALLENGE)

    if client_data.get("origin") != ORIGIN:
        return StructuralVerification(False, STRUCTURAL_FAIL_ORIGIN)

    return StructuralVerification(True)


# --- Ledger events ------------------------------------------------------------

def build_receipt_ledger_payload(
    receipt: HumanAuthorizationReceipt,
    artifact_path: str,
) -> Dict[str, Any]:
    """Digest-and-metadata-only payload; must pass the privacy invariant."""
    payload = {
        "receipt_schema": RECEIPT_SCHEMA,
        "receipt_digest": receipt.receipt_digest(),
        "request_digest": receipt.request.request_digest(),
        "decision_id": receipt.request.decision_id,
        "artifact_byte_digest": receipt.request.artifact_byte_digest,
        "plan_body_digest": receipt.request.plan_body_digest,
        "scope_digest": receipt.request.scope_digest,
        "approver_identity_id": receipt.request.approver_identity_id,
        "risk_class": receipt.request.risk_class,
        "policy_version": receipt.request.policy_version,
        "rp_id": receipt.request.rp_id,
        "nonce": receipt.request.nonce,
        "uv_required": receipt.request.user_verification_required,
        "uv_verified": receipt.user_verified,
        "receipt_artifact_path": artifact_path,
        "request_expires_at": receipt.request.expires_at,
    }
    assert_persistent_privacy_safe(
        payload, artifact_name="human_authorization_receipt payload"
    )
    return payload


def record_receipt(
    ledger: TaskLedger,
    receipt: HumanAuthorizationReceipt,
    ledger_dir: str = ".triagecore",
) -> str:
    """Write the sidecar artifact and the metadata-only ledger event."""
    artifact_path = write_receipt_artifact(receipt, ledger_dir=ledger_dir)
    payload = build_receipt_ledger_payload(receipt, artifact_path)
    ledger.append_event(receipt.request.task_id, EVENT_RECEIPT_RECORDED, payload)
    return artifact_path


# --- One-use execution capability ---------------------------------------------

@dataclass(frozen=True)
class CapabilityDecision:
    allowed: bool
    reason_code: str
    capability_id: str = ""


def issue_capability(
    ledger: TaskLedger,
    receipt: HumanAuthorizationReceipt,
    ttl_seconds: int = DEFAULT_CAPABILITY_TTL_SECONDS,
    now: Optional[datetime] = None,
) -> str:
    """Issue a one-use capability bound to the receipt's artifact digest.

    Callers must fully verify the receipt (structural + fido2_adapter) before
    issuing. ``now`` is injectable for deterministic tests.
    """
    capability_id = str(uuid.uuid4())
    expires = (now or _utc_now()).timestamp() + ttl_seconds
    payload = {
        "capability_id": capability_id,
        "receipt_digest": receipt.receipt_digest(),
        "decision_id": receipt.request.decision_id,
        "artifact_byte_digest": receipt.request.artifact_byte_digest,
        "approver_identity_id": receipt.request.approver_identity_id,
        "expires_at": _isoformat(datetime.fromtimestamp(expires, tz=timezone.utc)),
        "single_use": True,
    }
    assert_persistent_privacy_safe(
        payload, artifact_name="execution_capability_issued payload"
    )
    ledger.append_event(receipt.request.task_id, EVENT_CAPABILITY_ISSUED, payload)
    return capability_id


def consume_capability(
    ledger: TaskLedger,
    task_id: str,
    capability_id: str,
    artifact_byte_digest: str,
    now: Optional[datetime] = None,
) -> CapabilityDecision:
    """Consume the capability; every outcome is a ledger event.

    CONCURRENCY LIMITATION (documented, unresolved in this slice): this is a
    read-then-append sequence over a shared JSONL file with no lock. Two
    concurrent consumers can both observe the capability as unconsumed and
    both record consumption, so single-use holds against sequential use
    only. The sequential unit tests do not demonstrate race safety, and an
    expected-failure test in tests/test_authz.py encodes the gap. Atomic
    claiming (single-writer lock or SQLite ``BEGIN IMMEDIATE`` claim table)
    is required before CR-DD-012B wires this into execution.

    Denials are evidence too: not_found, already_consumed, expired, and
    digest_mismatch all append EVENT_CAPABILITY_DENIED with the reason code.
    """
    moment = now or _utc_now()
    issued: Optional[Dict[str, Any]] = None
    for event in ledger.get_events(task_id):
        etype = event.get("event_type")
        payload = event.get("payload", {})
        if payload.get("capability_id") != capability_id:
            continue
        if etype == EVENT_CAPABILITY_ISSUED:
            issued = payload
        elif etype == EVENT_CAPABILITY_CONSUMED:
            return _deny(ledger, task_id, capability_id, REASON_ALREADY_CONSUMED)

    if issued is None:
        return _deny(ledger, task_id, capability_id, REASON_NOT_FOUND)
    if moment > datetime.fromisoformat(issued["expires_at"]):
        return _deny(ledger, task_id, capability_id, REASON_EXPIRED)
    if issued["artifact_byte_digest"] != artifact_byte_digest:
        return _deny(ledger, task_id, capability_id, REASON_DIGEST_MISMATCH)

    payload = {
        "capability_id": capability_id,
        "artifact_byte_digest": artifact_byte_digest,
        "reason_code": REASON_OK,
    }
    ledger.append_event(task_id, EVENT_CAPABILITY_CONSUMED, payload)
    return CapabilityDecision(True, REASON_OK, capability_id)


def _deny(
    ledger: TaskLedger,
    task_id: str,
    capability_id: str,
    reason_code: str,
) -> CapabilityDecision:
    ledger.append_event(
        task_id,
        EVENT_CAPABILITY_DENIED,
        {"capability_id": capability_id, "reason_code": reason_code},
    )
    return CapabilityDecision(False, reason_code, capability_id)


# --- Credential store ---------------------------------------------------------

@dataclass
class EnrolledCredential:
    """Public credential material only. Never PINs, private keys, or secrets.

    ``human_id`` is a stable governed identifier with the same normalization
    contract as ``AuthorizationRequest.approver_identity_id``: construction
    normalizes (strip + lowercase) and validates, so enrollment, lookup,
    revocation, serialization, and verification all operate on one canonical
    form. Cosmetic variants ("Operator-A", "operator-a") therefore resolve
    to the same governed identity and cannot enroll as distinct ones.
    ``label`` is informational display text and is never security-bound.
    """

    human_id: str
    label: str
    credential_id: str          # b64url
    public_key_cose: str        # b64url of CBOR-encoded COSE public key
    aaguid: str = "00" * 16     # hex; zeros when the authenticator omits it
    rp_id: str = RP_ID
    enrolled_at: str = field(default_factory=lambda: _isoformat(_utc_now()))
    revoked: bool = False
    revoked_at: str = ""

    def __post_init__(self) -> None:
        self.human_id = normalize_identity(self.human_id)
        if not _IDENTIFIER_PATTERN.fullmatch(self.human_id):
            raise AuthzError("human_id is not a stable governed identifier")
        self.rp_id = normalize_identity(self.rp_id)


class CredentialStore:
    """Registry at .triagecore/authz/credentials.json (public material only).

    Enroll at least two credentials per human so a backup key is part of the
    architecture. Revocation is a tombstone, not a deletion: revoked entries
    stay listed so historical receipts remain attributable while new
    verifications reject them.
    """

    def __init__(self, ledger_dir: str = ".triagecore"):
        self.path = os.path.join(ledger_dir, AUTHZ_DIR_NAME, CREDENTIALS_FILE_NAME)

    def load(self) -> List[EnrolledCredential]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return [EnrolledCredential(**item) for item in raw.get("credentials", [])]

    def save(self, credentials: List[EnrolledCredential]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        temp_path = self.path + ".tmp"
        body = {
            "schema": CREDENTIALS_SCHEMA,
            "credentials": [asdict(item) for item in credentials],
        }
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(body, handle, sort_keys=True, indent=2)
            handle.write("\n")
        _restrict_file_permissions(temp_path)
        os.replace(temp_path, self.path)

    def add(self, credential: EnrolledCredential) -> None:
        credentials = self.load()
        if any(c.credential_id == credential.credential_id for c in credentials):
            raise AuthzError("credential already enrolled")
        credentials.append(credential)
        self.save(credentials)

    def revoke(self, credential_id: str, now: Optional[datetime] = None) -> None:
        credentials = self.load()
        for credential in credentials:
            if credential.credential_id == credential_id:
                credential.revoked = True
                credential.revoked_at = _isoformat(now or _utc_now())
                self.save(credentials)
                return
        raise AuthzError("credential not found")

    def find_by_credential_id(self, credential_id: str) -> Optional[EnrolledCredential]:
        for credential in self.load():
            if credential.credential_id == credential_id:
                return credential
        return None

    def find_by_human_id(self, human_id: str) -> List[EnrolledCredential]:
        """All credentials (incl. revoked) for one governed identity.

        The query is normalized with the same contract as storage, so any
        cosmetic variant of the identifier reaches the same entries.
        """
        wanted = normalize_identity(human_id)
        return [c for c in self.load() if c.human_id == wanted]
