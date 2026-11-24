import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from test_authz import _request as execution_request

from triage_core.authz import (
    ORIGIN,
    RP_ID,
    AuthzVerificationError,
    CredentialStore,
    EnrolledCredential,
    HumanAuthorizationReceipt,
    b64url_encode,
    compute_challenge,
)
from triage_core.fido2_adapter import verify_receipt as verify_execution_receipt
from triage_core.task_review_receipt import (
    EvidenceBinding,
    ReviewerPolicy,
    ReviewProofError,
    ReviewReceipt,
    ReviewRequest,
    evidence_manifest_digest,
    verify_review_receipt,
)

NOW = datetime(2026, 11, 23, 18, tzinfo=timezone.utc)
BINDING = EvidenceBinding("workspace-a", "task-1", "revision-1", "sha256:" + "a" * 64)
CREDENTIAL_ID = b"synthetic-review-credential"


def enroll_reviewer(credentials, human_id, raw_id):
    pytest.importorskip("fido2")
    from cryptography.hazmat.primitives.asymmetric import ec
    from fido2 import cbor
    from fido2.cose import ES256

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = ES256.from_cryptography_key(private_key.public_key())
    credential = EnrolledCredential(
        human_id=human_id,
        label="Synthetic reviewer",
        credential_id=b64url_encode(raw_id),
        public_key_cose=b64url_encode(cbor.encode(public_key)),
    )
    credentials.add(credential)
    return private_key, credential


def make_reviewer(tmp_path):
    credentials = CredentialStore(str(tmp_path))
    private_key, credential = enroll_reviewer(credentials, "reviewer-a", CREDENTIAL_ID)
    policy = ReviewerPolicy(
        "workspace-a", {"reviewer-a": {credential.credential_id}}, credentials
    )
    return private_key, policy


@pytest.fixture
def reviewer(tmp_path):
    return make_reviewer(tmp_path)


def assertion(
    private_key,
    request,
    *,
    origin=ORIGIN,
    rp_id=RP_ID,
    flags=5,
    credential_id=CREDENTIAL_ID,
    challenge=None,
    **client_fields,
):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    client_data = json.dumps(
        {
            "type": "webauthn.get",
            "challenge": b64url_encode(
                request.challenge() if challenge is None else challenge
            ),
            "origin": origin,
            **client_fields,
        }
    ).encode()
    authenticator_data = sha256(rp_id.encode()).digest() + bytes([flags]) + bytes(4)
    signature = private_key.sign(
        authenticator_data + sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
    )
    return {
        "type": "public-key",
        "id": b64url_encode(credential_id),
        "rawId": b64url_encode(credential_id),
        "response": {
            "clientDataJSON": b64url_encode(client_data),
            "authenticatorData": b64url_encode(authenticator_data),
            "signature": b64url_encode(signature),
        },
    }


def new_request(**changes):
    request = ReviewRequest.create(BINDING, "accepted", "reviewer-a", None, NOW)
    return replace(request, **changes)


def test_manifest_binds_exact_bytes_and_ids_in_canonical_order():
    items = {"output": b"A\r\n", "summary": b"B"}
    manifest = {
        "schema": "triagecore.task_review_evidence.v1",
        "items": [
            {"id": item, "digest": "sha256:" + sha256(content).hexdigest()}
            for item, content in items.items()
        ],
    }
    expected = (
        "sha256:"
        + sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    assert evidence_manifest_digest(items) == expected
    assert evidence_manifest_digest(dict(reversed(list(items.items())))) == expected
    assert evidence_manifest_digest({**items, "output": b"A\n"}) != expected
    assert evidence_manifest_digest({"draft": b"A\r\n", "summary": b"B"}) != expected


@pytest.mark.parametrize("items", [{}, {"../file": b"bytes"}, {"output": "text"}])
def test_manifest_requires_captured_bytes_and_opaque_item_ids(items):
    with pytest.raises((ValueError, TypeError)):
        evidence_manifest_digest(items)


def test_request_round_trips_and_binds_all_variable_fields():
    req = new_request()
    variations = [
        {"evidence": replace(BINDING, scope_id="workspace-b")},
        {"evidence": replace(BINDING, task_id="task-2")},
        {"evidence": replace(BINDING, revision="revision-2")},
        {"evidence": replace(BINDING, digest="sha256:" + "b" * 64)},
        {"decision": "rejected"},
        {"reviewer_id": "reviewer-b"},
        {"event_id": "b2bbcef9-4a1e-480c-a0af-c522a0b0f33a"},
        {"nonce": "b2bbcef9-4a1e-480c-a0af-c522a0b0f33a"},
        {"predecessor_id": "5c7937c1-cc28-4862-8bd8-7d2bc01ef793"},
        {"issued_at": NOW + timedelta(seconds=1)},
        {"expires_at": NOW + timedelta(minutes=4)},
    ]
    wire = req.canonical_bytes()
    assert ReviewRequest.from_bytes(wire) == req
    assert json.loads(wire)["rp_id"] == RP_ID
    assert json.loads(wire)["purpose"] == "human_task_review"
    assert json.loads(wire)["policy"] == "triagecore.task_review_policy.v1"
    assert len(req.challenge()) == 32
    for change in variations:
        assert replace(req, **change).challenge() != req.challenge()


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "unknown"},
        {"purpose": "execution_authorization"},
        {"policy": "unknown"},
        {"decision": "approve"},
        {"reviewer_id": " Reviewer-A "},
        {"event_id": "not-a-uuid"},
        {"rp_id": "other.example"},
        {"issued_at": "2026-11-23T18:00:00"},
        {"expires_at": "2026-11-23T19:00:00.000000+00:00"},
    ],
)
def test_request_rejects_unsupported_or_noncanonical_fields(change):
    raw = json.loads(new_request().canonical_bytes())
    with pytest.raises(ValueError):
        ReviewRequest.from_bytes(
            json.dumps(
                {**raw, **change}, sort_keys=True, separators=(",", ":")
            ).encode()
        )


def test_synthetic_review_uses_explicit_review_grant_and_preserves_proof(reviewer):
    key, policy = reviewer
    req = new_request()
    receipt = ReviewReceipt.from_assertion(req, assertion(key, req, crossOrigin=False))
    restored = ReviewReceipt.from_bytes(receipt.canonical_bytes())
    assert restored == receipt
    verify_review_receipt(restored, policy, NOW)

    no_grant = ReviewerPolicy(policy.scope_id, {}, policy.credentials)
    with pytest.raises(ReviewProofError, match="review_grant_required"):
        verify_review_receipt(receipt, no_grant, NOW)

    policy.credentials.revoke(receipt.credential_id, now=NOW)
    with pytest.raises(ReviewProofError, match="credential_revoked"):
        verify_review_receipt(receipt, policy, NOW)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"flags": 4}, "assertion_invalid"),
        ({"flags": 1}, "assertion_invalid"),
        ({"origin": "https://other.example"}, "assertion_invalid"),
        ({"rp_id": "other.example"}, "assertion_invalid"),
        ({"crossOrigin": True}, "assertion_invalid"),
        ({"extra": "unexpected"}, "assertion_invalid"),
    ],
)
def test_review_requires_local_assertion_presence_and_verification(
    reviewer, kwargs, expected
):
    key, policy = reviewer
    req = new_request()
    receipt = ReviewReceipt.from_assertion(req, assertion(key, req, **kwargs))
    with pytest.raises(ReviewProofError, match=expected):
        verify_review_receipt(receipt, policy, NOW)


def test_review_verification_binds_request_scope_credential_and_window(reviewer):
    key, policy = reviewer
    req = new_request()
    receipt = ReviewReceipt.from_assertion(req, assertion(key, req))
    cases = [
        (
            replace(receipt, request=replace(req, decision="rejected")),
            policy,
            NOW,
            "assertion_invalid",
        ),
        (
            receipt,
            replace(policy, scope_id="workspace-b"),
            NOW,
            "review_scope_mismatch",
        ),
        (receipt, policy, NOW + timedelta(minutes=5), "challenge_not_current"),
        (receipt, policy, NOW - timedelta(seconds=1), "challenge_not_current"),
    ]
    for candidate, trust, clock, reason in cases:
        with pytest.raises(ReviewProofError, match=reason):
            verify_review_receipt(candidate, trust, clock)


def test_receipt_keeps_only_required_assertion_fields(reviewer):
    key, _ = reviewer
    req = new_request()
    wire = assertion(key, req)
    wire["response"]["userHandle"] = "unused-user-handle"
    wire["clientExtensionResults"] = {"unneeded": "test"}
    receipt = ReviewReceipt.from_assertion(req, wire)
    assert b"unused-user-handle" not in receipt.canonical_bytes()
    assert b"clientExtensionResults" not in receipt.canonical_bytes()


@pytest.mark.parametrize("registry", [None, "[]"])
def test_unreadable_enrollment_is_not_an_absent_reviewer(reviewer, registry):
    key, policy = reviewer
    request = new_request()
    receipt = ReviewReceipt.from_assertion(request, assertion(key, request))
    path = Path(policy.credentials.path)
    if registry is None:
        path.unlink()
    else:
        path.write_text(registry, encoding="utf-8")
    with pytest.raises(ReviewProofError, match="review_policy_unavailable"):
        verify_review_receipt(receipt, policy, NOW)


def test_review_and_execution_proofs_are_not_interchangeable(reviewer):
    key, policy = reviewer
    review = new_request()
    execution = execution_request(
        approver_identity_id=review.reviewer_id,
        issued_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(minutes=5)).isoformat(),
    )
    signed_review = assertion(key, review)
    signed_execution = assertion(key, review, challenge=compute_challenge(execution))

    verify_review_receipt(
        ReviewReceipt.from_assertion(review, signed_review), policy, NOW
    )
    with pytest.raises(ReviewProofError, match="assertion_invalid"):
        verify_review_receipt(
            ReviewReceipt.from_assertion(review, signed_execution), policy, NOW
        )

    def execution_receipt(wire):
        return HumanAuthorizationReceipt(
            request=execution,
            credential_id=wire["rawId"],
            assertion_response=wire,
            user_verified=True,
            recorded_at=NOW.isoformat(),
        )

    verify_execution_receipt(
        execution_receipt(signed_execution), policy.credentials, now=NOW
    )
    with pytest.raises(AuthzVerificationError, match="challenge"):
        verify_execution_receipt(
            execution_receipt(signed_review), policy.credentials, now=NOW
        )
