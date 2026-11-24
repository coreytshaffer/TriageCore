"""Canonical review evidence and offline proof for human task decisions."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from uuid import UUID, uuid4

from triage_core.authz import (
    CREDENTIALS_SCHEMA,
    RP_ID,
    AuthzError,
    AuthzHardwareUnavailable,
    CredentialStore,
    EnrolledCredential,
    b64url_decode,
    b64url_encode,
    normalize_identity,
)
from triage_core.fido2_adapter import verify_enrolled_assertion

REQUEST_SCHEMA = "triagecore.task_review_request.v1"
RECEIPT_SCHEMA = "triagecore.task_review_receipt.v1"
EVIDENCE_SCHEMA = "triagecore.task_review_evidence.v1"
REVIEW_POLICY = "triagecore.task_review_policy.v1"
REVIEW_PURPOSE = "human_task_review"
CHALLENGE_TTL = timedelta(minutes=5)
DECISIONS = frozenset(
    {"accepted", "accepted_with_minor_edits", "needs_revision", "rejected"}
)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_BASE64URL = re.compile(r"[A-Za-z0-9_-]+")


class ReviewProofError(ValueError):
    """A privacy-safe verification failure reason."""


def validate_review_id(value: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid review identifier")


def _validate_reviewer_id(value: str) -> None:
    validate_review_id(value)
    if normalize_identity(value) != value:
        raise ValueError("noncanonical reviewer identity")


def _validate_event_id(value: str) -> None:
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise ValueError("invalid review event identifier")


def review_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("review timestamp must include a UTC offset")
    return value.astimezone(timezone.utc)


def review_timestamp(value: datetime) -> str:
    return review_utc(value).isoformat(timespec="microseconds")


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _unique_members(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _read_object(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_members)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("invalid review JSON") from None
    if not isinstance(value, dict):
        raise TypeError("review JSON must be an object")
    return value


def _check_base64url(value: str, limit: int) -> bytes:
    if (
        not isinstance(value, str)
        or len(value) > limit
        or not _BASE64URL.fullmatch(value)
    ):
        raise ValueError("invalid assertion field")
    try:
        decoded = b64url_decode(value)
    except ValueError:
        raise ValueError("invalid assertion field") from None
    if b64url_encode(decoded) != value:
        raise ValueError("noncanonical assertion field")
    return decoded


def evidence_manifest_digest(items: Mapping[str, bytes]) -> str:
    """Bind stable item IDs to already captured bytes without persisting the bytes."""
    if not items:
        raise ValueError("review evidence must contain at least one item")
    entries = []
    for item_id, content in items.items():
        validate_review_id(item_id)
        if not isinstance(content, bytes):
            raise TypeError("review evidence items must be bytes")
        entries.append(
            {"id": item_id, "digest": f"sha256:{sha256(content).hexdigest()}"}
        )
    manifest = {
        "schema": EVIDENCE_SCHEMA,
        "items": sorted(entries, key=lambda item: item["id"]),
    }
    return f"sha256:{sha256(_canonical_json(manifest)).hexdigest()}"


@dataclass(frozen=True)
class EvidenceBinding:
    scope_id: str
    task_id: str
    revision: str
    digest: str

    def __post_init__(self) -> None:
        for value in (self.scope_id, self.task_id, self.revision):
            validate_review_id(value)
        if not isinstance(self.digest, str) or not _DIGEST.fullmatch(self.digest):
            raise ValueError("invalid review evidence digest")


@dataclass(frozen=True)
class ReviewRequest:
    evidence: EvidenceBinding
    decision: str
    reviewer_id: str
    event_id: str
    predecessor_id: str | None
    nonce: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, EvidenceBinding):
            raise TypeError("invalid review evidence binding")
        if not isinstance(self.decision, str) or self.decision not in DECISIONS:
            raise ValueError("unsupported review decision")
        _validate_reviewer_id(self.reviewer_id)
        _validate_event_id(self.event_id)
        _validate_event_id(self.nonce)
        if self.predecessor_id is not None:
            _validate_event_id(self.predecessor_id)
            if self.predecessor_id == self.event_id:
                raise ValueError("review event cannot be its own predecessor")
        issued = review_utc(self.issued_at)
        expires = review_utc(self.expires_at)
        if not timedelta(0) < expires - issued <= CHALLENGE_TTL:
            raise ValueError("invalid review challenge window")
        object.__setattr__(self, "issued_at", issued)
        object.__setattr__(self, "expires_at", expires)

    @classmethod
    def create(
        cls,
        evidence: EvidenceBinding,
        decision: str,
        reviewer_id: str,
        predecessor_id: str | None,
        now: datetime,
    ) -> ReviewRequest:
        now = review_utc(now)
        return cls(
            evidence,
            decision,
            reviewer_id,
            str(uuid4()),
            predecessor_id,
            str(uuid4()),
            now,
            now + CHALLENGE_TTL,
        )

    def canonical_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": REQUEST_SCHEMA,
                "purpose": REVIEW_PURPOSE,
                "policy": REVIEW_POLICY,
                "scope_id": self.evidence.scope_id,
                "task_id": self.evidence.task_id,
                "evidence_revision": self.evidence.revision,
                "evidence_digest": self.evidence.digest,
                "event_id": self.event_id,
                "predecessor_id": self.predecessor_id,
                "decision": self.decision,
                "reviewer_id": self.reviewer_id,
                "rp_id": RP_ID,
                "nonce": self.nonce,
                "issued_at": review_timestamp(self.issued_at),
                "expires_at": review_timestamp(self.expires_at),
            }
        )

    def challenge(self) -> bytes:
        return sha256(self.canonical_bytes()).digest()

    @classmethod
    def from_bytes(cls, raw: bytes) -> ReviewRequest:
        values = _read_object(raw)
        try:
            request = cls(
                EvidenceBinding(
                    values["scope_id"],
                    values["task_id"],
                    values["evidence_revision"],
                    values["evidence_digest"],
                ),
                values["decision"],
                values["reviewer_id"],
                values["event_id"],
                values["predecessor_id"],
                values["nonce"],
                datetime.fromisoformat(values["issued_at"]),
                datetime.fromisoformat(values["expires_at"]),
            )
        except (KeyError, TypeError, ValueError):
            raise ValueError("invalid review request") from None
        if request.canonical_bytes() != raw:
            raise ValueError("noncanonical or unsupported review request")
        return request


@dataclass(frozen=True)
class ReviewReceipt:
    request: ReviewRequest
    credential_id: str = field(repr=False)
    client_data_json: str = field(repr=False)
    authenticator_data: str = field(repr=False)
    signature: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.request, ReviewRequest):
            raise TypeError("invalid review receipt request")
        for value, limit in (
            (self.credential_id, 2048),
            (self.client_data_json, 2048),
            (self.authenticator_data, 2048),
            (self.signature, 1024),
        ):
            _check_base64url(value, limit)

    @classmethod
    def from_assertion(
        cls, request: ReviewRequest, assertion: Mapping[str, object]
    ) -> ReviewReceipt:
        try:
            response = assertion["response"]
            if assertion["type"] != "public-key":
                raise ValueError("unexpected assertion type")
            return cls(
                request,
                assertion["rawId"],
                response["clientDataJSON"],
                response["authenticatorData"],
                response["signature"],
            )
        except (KeyError, TypeError, ValueError):
            raise ValueError("invalid review assertion envelope") from None

    def assertion_response(self) -> dict:
        return {
            "type": "public-key",
            "id": self.credential_id,
            "rawId": self.credential_id,
            "response": {
                "clientDataJSON": self.client_data_json,
                "authenticatorData": self.authenticator_data,
                "signature": self.signature,
            },
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(
            {
                "schema": RECEIPT_SCHEMA,
                "request": _read_object(self.request.canonical_bytes()),
                "assertion": self.assertion_response(),
            }
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> ReviewReceipt:
        values = _read_object(raw)
        try:
            request = ReviewRequest.from_bytes(_canonical_json(values["request"]))
            receipt = cls.from_assertion(request, values["assertion"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("invalid review receipt") from None
        if receipt.canonical_bytes() != raw:
            raise ValueError("noncanonical or unsupported review receipt")
        return receipt


@dataclass(frozen=True)
class ReviewerPolicy:
    """Trusted local review grants backed by the existing enrollment registry."""

    scope_id: str
    grants: Mapping[str, Iterable[str]] = field(repr=False)
    credentials: CredentialStore = field(repr=False)

    def __post_init__(self) -> None:
        validate_review_id(self.scope_id)
        checked = {}
        for reviewer, granted in self.grants.items():
            _validate_reviewer_id(reviewer)
            if isinstance(granted, str):
                raise TypeError("invalid reviewer credential grant")
            ids = frozenset(granted)
            for credential_id in ids:
                _check_base64url(credential_id, 2048)
            checked[reviewer] = ids
        object.__setattr__(self, "grants", MappingProxyType(checked))

    def require_reviewer(self, reviewer_id: str) -> None:
        granted = self.grants.get(reviewer_id, ())
        if not granted:
            raise ReviewProofError("review_grant_required")
        for enrolled in self._enrollments():
            if (
                enrolled.human_id == reviewer_id
                and enrolled.credential_id in granted
                and not enrolled.revoked
                and enrolled.rp_id == RP_ID
            ):
                return
        raise ReviewProofError("reviewer_credential_unavailable")

    def _enrollments(self) -> list[EnrolledCredential]:
        try:
            registry = _read_object(Path(self.credentials.path).read_bytes())
            entries = registry.get("credentials")
            if registry.get("schema") != CREDENTIALS_SCHEMA or not isinstance(
                entries, list
            ):
                raise ValueError("unsupported enrollment registry")
            return [EnrolledCredential(**entry) for entry in entries]
        except (AuthzError, OSError, ValueError, TypeError, KeyError):
            raise ReviewProofError("review_policy_unavailable") from None

    def _credential(self, reviewer_id: str, credential_id: str) -> EnrolledCredential:
        if credential_id not in self.grants.get(reviewer_id, ()):
            raise ReviewProofError("review_grant_required")
        matches = [
            item for item in self._enrollments() if item.credential_id == credential_id
        ]
        if len(matches) != 1:
            raise ReviewProofError("credential_enrollment_missing_or_ambiguous")
        enrolled = matches[0]
        if enrolled.revoked:
            raise ReviewProofError("credential_revoked")
        if enrolled.human_id != reviewer_id or enrolled.rp_id != RP_ID:
            raise ReviewProofError("credential_policy_mismatch")
        return enrolled


def verify_review_receipt(
    receipt: ReviewReceipt, policy: ReviewerPolicy, at: datetime
) -> None:
    """Verify at admission time, applying the reviewer and credential policy now."""
    request = receipt.request
    if request.evidence.scope_id != policy.scope_id:
        raise ReviewProofError("review_scope_mismatch")
    if not request.issued_at <= review_utc(at) < request.expires_at:
        raise ReviewProofError("challenge_not_current")

    enrolled = policy._credential(request.reviewer_id, receipt.credential_id)
    try:
        client_data = _read_object(b64url_decode(receipt.client_data_json))
        if (
            client_data.keys() - {"type", "challenge", "origin", "crossOrigin"}
            or client_data.get("crossOrigin", False) is not False
        ):
            raise ValueError("unsupported review client data")
        verify_enrolled_assertion(
            enrolled,
            request.challenge(),
            receipt.assertion_response(),
            user_verification_required=True,
        )
    except AuthzHardwareUnavailable:
        raise ReviewProofError("review_verifier_unavailable") from None
    except (AuthzError, KeyError, TypeError, ValueError):
        raise ReviewProofError("assertion_invalid") from None
