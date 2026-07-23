"""Tests for the CR-YK-001 authorization-receipt lane.

Two tiers:

1. Deterministic-core tests: no python-fido2, no hardware, no network.
2. fido2-backed tests: use real python-fido2 2.x WebAuthn data structures
   with a synthetic software credential. These skip cleanly when the
   optional dependency is absent. They prove offline verification behavior
   only — they do NOT prove Windows integration or a physical-YubiKey
   ceremony (that remains a manual checklist in CR-YK-001).

The concurrency test encodes a known limitation as a strict expected
failure: sequential unit tests cannot and do not prove race-safe single use.
"""

import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone

import pytest

from triage_core import fido2_adapter
from triage_core.authz import (
    EVENT_CAPABILITY_CONSUMED,
    EVENT_CAPABILITY_DENIED,
    EVENT_RECEIPT_RECORDED,
    ORIGIN,
    REASON_ALREADY_CONSUMED,
    REASON_DIGEST_MISMATCH,
    REASON_EXPIRED,
    REASON_NOT_FOUND,
    REASON_OK,
    REQUEST_SCHEMA,
    RP_ID,
    STRUCTURAL_FAIL_CHALLENGE,
    STRUCTURAL_FAIL_EXPIRED,
    STRUCTURAL_FAIL_MALFORMED,
    STRUCTURAL_FAIL_ORIGIN,
    STRUCTURAL_FAIL_TYPE,
    AuthorizationRequest,
    AuthzArtifactTamperError,
    AuthzError,
    AuthzHardwareUnavailable,
    AuthzVerificationError,
    CredentialStore,
    EnrolledCredential,
    HumanAuthorizationReceipt,
    b64url_encode,
    build_receipt_ledger_payload,
    compute_challenge,
    consume_capability,
    issue_capability,
    read_receipt_artifact,
    record_receipt,
    verify_receipt_structure,
    write_receipt_artifact,
)
from triage_core.privacy_invariants import assert_persistent_privacy_safe
from triage_core.task_ledger import TaskLedger

NOW = datetime(2026, 8, 5, 15, 5, 0, tzinfo=timezone.utc)

BASE_REQUEST_KWARGS = dict(
    decision_id="gd-1234567890abcdef",
    artifact_byte_digest="sha256:" + "ab" * 32,
    plan_body_digest="sha256:" + "cd" * 32,
    task_id="11111111-2222-3333-4444-555555555555",
    risk_class="high",
    policy_version="cr-yk-001-v1",
    approver_identity_id="human-corey",
    user_verification_required=True,
    scope_digest="sha256:" + "ee" * 32,
    nonce="99999999-8888-7777-6666-555555555555",
    issued_at="2026-08-05T15:00:00+00:00",
    expires_at="2026-08-05T15:10:00+00:00",
)


def _request(**overrides) -> AuthorizationRequest:
    kwargs = dict(BASE_REQUEST_KWARGS)
    kwargs.update(overrides)
    return AuthorizationRequest(**kwargs)


def _wire_assertion(client_data_bytes: bytes) -> dict:
    """Minimal wire-shaped assertion for structural tests (no crypto)."""
    return {
        "id": b64url_encode(b"cred-id"),
        "rawId": b64url_encode(b"cred-id"),
        "type": "public-key",
        "response": {
            "clientDataJSON": b64url_encode(client_data_bytes),
            "authenticatorData": b64url_encode(b"auth-data"),
            "signature": b64url_encode(b"sig"),
        },
    }


def _receipt(request: AuthorizationRequest, challenge_b64: str = None,
             origin: str = ORIGIN, cd_type: str = "webauthn.get",
             client_data_bytes: bytes = None) -> HumanAuthorizationReceipt:
    if client_data_bytes is None:
        challenge = challenge_b64 or b64url_encode(compute_challenge(request))
        client_data_bytes = json.dumps(
            {"type": cd_type, "challenge": challenge, "origin": origin}
        ).encode("utf-8")
    return HumanAuthorizationReceipt(
        request=request,
        credential_id=b64url_encode(b"cred-id"),
        assertion_response=_wire_assertion(client_data_bytes),
        user_verified=True,
        recorded_at="2026-08-05T15:01:00+00:00",
    )


# --- Challenge derivation -----------------------------------------------------

def test_challenge_deterministic_versioned_and_32_bytes():
    a = compute_challenge(_request())
    b = compute_challenge(_request())
    assert a == b and len(a) == 32
    payload = json.loads(_request().canonical_bytes())
    assert payload["schema"] == REQUEST_SCHEMA
    assert payload["rp_id"] == RP_ID
    assert payload["user_verification_required"] is True


def test_challenge_field_order_independence():
    forward = AuthorizationRequest(**dict(BASE_REQUEST_KWARGS))
    reversed_kwargs = dict(reversed(list(BASE_REQUEST_KWARGS.items())))
    backward = AuthorizationRequest(**reversed_kwargs)
    assert compute_challenge(forward) == compute_challenge(backward)


@pytest.mark.parametrize(
    "override",
    [
        {"artifact_byte_digest": "sha256:" + "ff" * 32},
        {"plan_body_digest": "sha256:" + "aa" * 32},
        {"decision_id": "gd-other"},
        {"nonce": "00000000-0000-0000-0000-000000000000"},
        {"issued_at": "2026-08-05T14:59:00+00:00"},
        {"expires_at": "2026-08-05T15:11:00+00:00"},
        {"approver_identity_id": "human-mallory"},
        {"rp_id": "evil.example"},
        {"user_verification_required": False},
        {"scope_digest": "sha256:" + "11" * 32},
        {"risk_class": "low"},
        {"policy_version": "cr-yk-001-v2"},
    ],
)
def test_challenge_changes_when_bound_field_changes(override):
    assert compute_challenge(_request(**override)) != compute_challenge(_request())


def test_unknown_request_schema_rejected():
    with pytest.raises(AuthzError):
        _request(schema="triagecore.authz.request.v1")


def test_normalization_makes_equivalent_requests_identical():
    baseline = compute_challenge(_request())
    normalized = _request(
        risk_class="  HIGH ",
        policy_version="CR-YK-001-V1",
        approver_identity_id="HUMAN-Corey",
        rp_id="TRIAGECORE.LOCAL",
        issued_at="2026-08-05T15:00:00.000000+00:00",
    )
    assert compute_challenge(normalized) == baseline
    assert normalized.risk_class == "high"
    assert normalized.approver_identity_id == "human-corey"
    assert normalized.rp_id == RP_ID


@pytest.mark.parametrize(
    "override",
    [
        {"risk_class": "critical"},
        {"artifact_byte_digest": "sha256:nothex"},
        {"plan_body_digest": "md5:" + "ab" * 32},
        {"scope_digest": "sha256:short"},
        {"task_id": "has whitespace"},
        {"task_id": "   "},
        {"decision_id": ""},
        {"nonce": "not-a-uuid"},
        {"issued_at": "yesterday"},
        {"approver_identity_id": "***"},
    ],
)
def test_non_canonical_or_invalid_inputs_rejected(override):
    with pytest.raises(AuthzError):
        _request(**override)


# --- Sidecar artifact ---------------------------------------------------------

def test_receipt_artifact_roundtrip_and_tamper_detection(tmp_path):
    receipt = _receipt(_request())
    path = write_receipt_artifact(receipt, ledger_dir=str(tmp_path))
    loaded = read_receipt_artifact(path, expected_digest=receipt.receipt_digest())
    assert loaded.receipt_digest() == receipt.receipt_digest()

    raw = open(path, "r", encoding="utf-8").read()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(raw.replace("human-corey", "human-mallory"))
    with pytest.raises(AuthzArtifactTamperError):
        read_receipt_artifact(path, expected_digest=receipt.receipt_digest())


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_receipt_artifact_permissions_owner_only(tmp_path):
    path = write_receipt_artifact(_receipt(_request()), ledger_dir=str(tmp_path))
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode & 0o077 == 0


# --- Structural verification --------------------------------------------------

def test_structural_passes_for_honest_receipt():
    result = verify_receipt_structure(_receipt(_request()), now=NOW)
    assert result.passed, result.failure_reason


@pytest.mark.parametrize(
    "receipt_kwargs,expected",
    [
        ({"client_data_bytes": b"\xff\xfenot json"}, STRUCTURAL_FAIL_MALFORMED),
        ({"cd_type": "webauthn.create"}, STRUCTURAL_FAIL_TYPE),
        ({"challenge_b64": b64url_encode(b"\x00" * 32)}, STRUCTURAL_FAIL_CHALLENGE),
        ({"origin": "https://evil.example"}, STRUCTURAL_FAIL_ORIGIN),
    ],
)
def test_structural_rejections(receipt_kwargs, expected):
    result = verify_receipt_structure(_receipt(_request(), **receipt_kwargs), now=NOW)
    assert not result.passed and result.failure_reason == expected


def test_structural_rejects_missing_client_data():
    receipt = _receipt(_request())
    del receipt.assertion_response["response"]["clientDataJSON"]
    result = verify_receipt_structure(receipt, now=NOW)
    assert not result.passed and result.failure_reason == STRUCTURAL_FAIL_MALFORMED


def test_structural_rejects_expired_request():
    result = verify_receipt_structure(_receipt(_request()), now=NOW + timedelta(hours=1))
    assert not result.passed and result.failure_reason == STRUCTURAL_FAIL_EXPIRED


def test_structural_rejects_tampered_request_binding():
    honest = _receipt(_request())
    swapped = HumanAuthorizationReceipt(
        request=_request(artifact_byte_digest="sha256:" + "99" * 32),
        credential_id=honest.credential_id,
        assertion_response=honest.assertion_response,
        user_verified=honest.user_verified,
        recorded_at=honest.recorded_at,
    )
    result = verify_receipt_structure(swapped, now=NOW)
    assert not result.passed and result.failure_reason == STRUCTURAL_FAIL_CHALLENGE


# --- Ledger evidence ----------------------------------------------------------

def test_ledger_payload_privacy_safe_and_metadata_only(tmp_path):
    receipt = _receipt(_request())
    payload = build_receipt_ledger_payload(receipt, "receipts/receipt_x.json")
    assert_persistent_privacy_safe(payload)

    ledger = TaskLedger(ledger_dir=str(tmp_path))
    path = record_receipt(ledger, receipt, ledger_dir=str(tmp_path))
    events = ledger.get_events(receipt.request.task_id)
    recorded = next(e for e in events if e["event_type"] == EVENT_RECEIPT_RECORDED)
    serialized = json.dumps(recorded["payload"])
    assert "clientDataJSON" not in serialized
    assert "signature" not in serialized
    assert recorded["payload"]["receipt_artifact_path"] == path
    assert recorded["payload"]["uv_required"] is True
    assert recorded["payload"]["uv_verified"] is True


# --- Capability lane ----------------------------------------------------------

def test_capability_single_use_sequentially(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    receipt = _receipt(_request())
    task_id = receipt.request.task_id
    digest = receipt.request.artifact_byte_digest

    capability_id = issue_capability(ledger, receipt, now=NOW)
    first = consume_capability(ledger, task_id, capability_id, digest, now=NOW)
    assert first.allowed and first.reason_code == REASON_OK

    second = consume_capability(ledger, task_id, capability_id, digest, now=NOW)
    assert not second.allowed and second.reason_code == REASON_ALREADY_CONSUMED

    events = ledger.get_events(task_id)
    assert sum(e["event_type"] == EVENT_CAPABILITY_CONSUMED for e in events) == 1
    assert sum(e["event_type"] == EVENT_CAPABILITY_DENIED for e in events) == 1


def test_capability_denies_expired_missing_and_mismatched(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    receipt = _receipt(_request())
    task_id = receipt.request.task_id
    digest = receipt.request.artifact_byte_digest

    missing = consume_capability(ledger, task_id, "not-a-real-id", digest, now=NOW)
    assert not missing.allowed and missing.reason_code == REASON_NOT_FOUND

    expiring = issue_capability(ledger, receipt, ttl_seconds=60, now=NOW)
    expired = consume_capability(
        ledger, task_id, expiring, digest, now=NOW + timedelta(hours=2)
    )
    assert not expired.allowed and expired.reason_code == REASON_EXPIRED

    fresh = issue_capability(ledger, receipt, now=NOW)
    mismatched = consume_capability(
        ledger, task_id, fresh, "sha256:" + "00" * 32, now=NOW
    )
    assert not mismatched.allowed and mismatched.reason_code == REASON_DIGEST_MISMATCH


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known limitation (CR-YK-001): read-then-append consumption is not "
        "atomic; interleaved consumers can each observe 'unconsumed'. Atomic "
        "claiming is required before CR-DD-012B execution integration."
    ),
)
def test_concurrent_consume_race_documented(tmp_path, monkeypatch):
    """Deterministically interleave two consumers; single-use SHOULD hold."""
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    receipt = _receipt(_request())
    task_id = receipt.request.task_id
    digest = receipt.request.artifact_byte_digest
    capability_id = issue_capability(ledger, receipt, now=NOW)

    # Freeze both consumers' reads at the pre-consumption snapshot, modeling
    # two processes that each read the ledger before either appends.
    snapshot = ledger.get_events(task_id)
    monkeypatch.setattr(ledger, "get_events", lambda _tid: list(snapshot))

    first = consume_capability(ledger, task_id, capability_id, digest, now=NOW)
    second = consume_capability(ledger, task_id, capability_id, digest, now=NOW)
    successes = sum(1 for d in (first, second) if d.allowed)
    assert successes <= 1  # violated today: both consumers are allowed


# --- Credential store ---------------------------------------------------------

def _credential(**overrides) -> EnrolledCredential:
    base = dict(
        human_id="human-corey",
        label="primary yubikey",
        credential_id=b64url_encode(b"cred-1"),
        public_key_cose=b64url_encode(b"cose-public-bytes"),
        enrolled_at="2026-08-01T00:00:00+00:00",
    )
    base.update(overrides)
    return EnrolledCredential(**base)


def test_credential_store_roundtrip_duplicate_and_revocation(tmp_path):
    store = CredentialStore(ledger_dir=str(tmp_path))
    assert store.load() == []
    credential = _credential()
    store.add(credential)
    assert store.find_by_credential_id(credential.credential_id).label == "primary yubikey"
    with pytest.raises(AuthzError):
        store.add(credential)

    store.revoke(credential.credential_id, now=NOW)
    revoked = store.find_by_credential_id(credential.credential_id)
    assert revoked.revoked and revoked.revoked_at.startswith("2026-08-05")
    with pytest.raises(AuthzError):
        store.revoke("missing-id")


def test_credential_store_normalizes_identity_at_every_boundary(tmp_path):
    store = CredentialStore(ledger_dir=str(tmp_path))
    store.add(_credential(human_id="  Operator-A "))
    saved = store.load()[0]
    assert saved.human_id == "operator-a"                       # serialization
    assert store.find_by_human_id(" OPERATOR-A ") == [saved]    # lookup
    store.revoke(saved.credential_id, now=NOW)                  # revocation
    assert store.load()[0].revoked


def test_identity_variants_fold_to_single_governed_identity(tmp_path):
    store = CredentialStore(ledger_dir=str(tmp_path))
    store.add(_credential(human_id="Operator-A", credential_id=b64url_encode(b"key-1")))
    store.add(_credential(human_id="operator-a", credential_id=b64url_encode(b"key-2")))
    assert {c.human_id for c in store.load()} == {"operator-a"}  # one identity
    assert len(store.find_by_human_id("Operator-A")) == 2        # two backup keys


def test_invalid_identity_rejected_at_enrollment():
    with pytest.raises(AuthzError):
        _credential(human_id="***")
    with pytest.raises(AuthzError):
        _credential(human_id="   ")


# --- Adapter availability (dependency / platform) -----------------------------

def test_missing_dependency_yields_controlled_unavailability(monkeypatch):
    def _raise():
        raise AuthzHardwareUnavailable("python-fido2 >= 2.0 is required")

    monkeypatch.setattr(fido2_adapter, "_import_fido2", _raise)
    support = fido2_adapter.ceremony_support()
    assert support.available is False and support.mechanism == "none"
    assert "python-fido2" in support.detail

    store_dir_free_store = CredentialStore(ledger_dir="unused")
    receipt = _receipt(_request())
    # Structural and store checks run dependency-free; the crypto step must
    # surface the controlled error, not an ImportError.
    monkeypatch.setattr(
        store_dir_free_store, "find_by_credential_id", lambda _cid: _credential(
            credential_id=receipt.credential_id
        )
    )
    with pytest.raises(AuthzHardwareUnavailable):
        fido2_adapter.verify_receipt(receipt, store_dir_free_store, now=NOW)


def test_unsupported_platform_reports_unavailable_without_crash(monkeypatch):
    pytest.importorskip("fido2")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(fido2_adapter, "_list_ctap_devices", lambda: [])
    support = fido2_adapter.ceremony_support()
    assert support.available is False
    assert support.mechanism == "none"
    assert "no FIDO2 authenticator" in support.detail


# --- Full verification with real python-fido2 structures ----------------------

def _synthetic(request, *, up=True, uv=True, rp_for_hash=None, origin=ORIGIN,
               tamper_auth=False, tamper_sig=False, wrong_key=False,
               human_id="human-corey"):
    """Build a receipt + enrolled credential from a software ES256 key using
    real python-fido2 WebAuthn data structures. Proves offline verification
    logic only — not hardware or Windows integration."""
    pytest.importorskip("fido2")
    import struct
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from fido2 import cbor as fido2_cbor
    from fido2.cose import ES256
    from fido2.webauthn import (
        AuthenticationResponse,
        AuthenticatorAssertionResponse,
        AuthenticatorData,
        CollectedClientData,
    )
    import hashlib as _hashlib

    private_key = ec.generate_private_key(ec.SECP256R1())
    cose_public = ES256.from_cryptography_key(private_key.public_key())
    credential_id = b"synthetic-credential-0001"

    enrolled = EnrolledCredential(
        human_id=human_id,
        label="synthetic software credential",
        credential_id=b64url_encode(credential_id),
        public_key_cose=b64url_encode(fido2_cbor.encode(cose_public)),
    )

    client_data = CollectedClientData.create(
        type="webauthn.get", challenge=compute_challenge(request), origin=origin
    )
    rp_hash = _hashlib.sha256((rp_for_hash or request.rp_id).encode()).digest()
    flags = (0x01 if up else 0) | (0x04 if uv else 0)
    auth_data = AuthenticatorData(rp_hash + bytes([flags]) + struct.pack(">I", 0))

    signing_key = ec.generate_private_key(ec.SECP256R1()) if wrong_key else private_key
    signature = signing_key.sign(
        bytes(auth_data) + client_data.hash, ec.ECDSA(hashes.SHA256())
    )
    if tamper_sig:
        signature = signature[:-1] + bytes([signature[-1] ^ 0x01])

    wire = dict(
        AuthenticationResponse(
            raw_id=credential_id,
            response=AuthenticatorAssertionResponse(
                client_data=client_data,
                authenticator_data=auth_data,
                signature=signature,
            ),
        )
    )
    if tamper_auth:
        tampered = bytearray(bytes(auth_data))
        tampered[0] ^= 0x01
        wire["response"]["authenticatorData"] = b64url_encode(bytes(tampered))

    receipt = HumanAuthorizationReceipt(
        request=request,
        credential_id=b64url_encode(credential_id),
        assertion_response=json.loads(json.dumps(wire)),
        user_verified=uv,
        recorded_at="2026-08-05T15:01:00+00:00",
    )
    return receipt, enrolled


def _store_with(tmp_path, enrolled) -> CredentialStore:
    store = CredentialStore(ledger_dir=str(tmp_path))
    store.add(enrolled)
    return store


def test_full_verification_passes_with_zero_counter(tmp_path):
    receipt, enrolled = _synthetic(_request())
    store = _store_with(tmp_path, enrolled)
    result = fido2_adapter.verify_receipt(receipt, store, now=NOW)
    assert result.credential_id == enrolled.credential_id


def test_full_verification_uv_not_required_up_only_passes(tmp_path):
    request = _request(user_verification_required=False)
    receipt, enrolled = _synthetic(request, uv=False)
    store = _store_with(tmp_path, enrolled)
    assert fido2_adapter.verify_receipt(receipt, store, now=NOW)


@pytest.mark.parametrize(
    "synthetic_kwargs,message_fragment",
    [
        ({"up": False}, "User Present"),
        ({"uv": False}, "User verification required"),
        ({"rp_for_hash": "evil.example"}, "RP ID hash"),
        ({"tamper_auth": True}, ""),   # signature no longer covers auth data
        ({"tamper_sig": True}, ""),
        ({"wrong_key": False, "tamper_sig": True}, ""),
        ({"wrong_key": True}, ""),
    ],
)
def test_full_verification_rejections(tmp_path, synthetic_kwargs, message_fragment):
    receipt, enrolled = _synthetic(_request(), **synthetic_kwargs)
    store = _store_with(tmp_path, enrolled)
    with pytest.raises(AuthzVerificationError) as excinfo:
        fido2_adapter.verify_receipt(receipt, store, now=NOW)
    if message_fragment:
        assert message_fragment in str(excinfo.value)


def test_full_verification_rejects_unknown_credential(tmp_path):
    receipt, _enrolled = _synthetic(_request())
    empty_store = CredentialStore(ledger_dir=str(tmp_path))
    with pytest.raises(AuthzVerificationError) as excinfo:
        fido2_adapter.verify_receipt(receipt, empty_store, now=NOW)
    assert str(excinfo.value) == fido2_adapter.VERIFY_FAIL_UNKNOWN_CREDENTIAL


def test_enrolled_identity_and_request_approver_resolve_identically(tmp_path):
    """enroll('OPERATOR-A') + verify(approver=' Operator-A ') → same identity."""
    request = _request(approver_identity_id=" Operator-A ")
    receipt, enrolled = _synthetic(request, human_id="OPERATOR-A")
    store = _store_with(tmp_path, enrolled)
    verified = fido2_adapter.verify_receipt(receipt, store, now=NOW)
    assert verified.human_id == "operator-a"
    assert request.approver_identity_id == "operator-a"


def test_full_verification_rejects_credential_of_different_identity(tmp_path):
    receipt, enrolled = _synthetic(_request())
    enrolled.human_id = "human-someone-else"
    store = _store_with(tmp_path, enrolled)
    with pytest.raises(AuthzVerificationError) as excinfo:
        fido2_adapter.verify_receipt(receipt, store, now=NOW)
    assert str(excinfo.value) == fido2_adapter.VERIFY_FAIL_APPROVER_MISMATCH


def test_full_verification_rejects_revoked_credential(tmp_path):
    receipt, enrolled = _synthetic(_request())
    store = _store_with(tmp_path, enrolled)
    store.revoke(enrolled.credential_id, now=NOW)
    with pytest.raises(AuthzVerificationError) as excinfo:
        fido2_adapter.verify_receipt(receipt, store, now=NOW)
    assert str(excinfo.value) == fido2_adapter.VERIFY_FAIL_REVOKED_CREDENTIAL


def test_full_verification_rejects_wrong_origin_structurally(tmp_path):
    receipt, enrolled = _synthetic(_request(), origin="https://evil.example")
    store = _store_with(tmp_path, enrolled)
    with pytest.raises(AuthzVerificationError) as excinfo:
        fido2_adapter.verify_receipt(receipt, store, now=NOW)
    assert str(excinfo.value) == STRUCTURAL_FAIL_ORIGIN


def test_full_verification_rejects_challenge_mismatch_structurally(tmp_path):
    receipt, enrolled = _synthetic(_request())
    tampered = HumanAuthorizationReceipt(
        request=_request(scope_digest="sha256:" + "77" * 32),
        credential_id=receipt.credential_id,
        assertion_response=receipt.assertion_response,
        user_verified=receipt.user_verified,
        recorded_at=receipt.recorded_at,
    )
    store = _store_with(tmp_path, enrolled)
    with pytest.raises(AuthzVerificationError) as excinfo:
        fido2_adapter.verify_receipt(tampered, store, now=NOW)
    assert str(excinfo.value) == STRUCTURAL_FAIL_CHALLENGE
