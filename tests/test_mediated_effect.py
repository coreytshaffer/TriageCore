"""Tests for the CR-OC-001A mediated single-file effect contract.

Covers all 18 test-contract items. The module under test is pure, so several
tests here exist to prove absence rather than presence: that raw bytes never
survive into a returned object, that no I/O entry point is reachable from any
public path, and that declared context is never presented as authenticated
identity.

No network, subprocess, sleep, randomness, model call, or real file access.
"""

import builtins
import io
import json
import socket
import sqlite3
import subprocess
import hashlib

import pytest

from triage_core.mediated_effect import (
    CONTENT_NOT_UTF8,
    CONTENT_SIZE_EXCEEDED,
    INVALID_BROKER_BINDING,
    INVALID_CLIENT_REQUEST_ID,
    INVALID_CONTENT_SIZE,
    INVALID_DECISION_ID,
    INVALID_DECLARED_CONTEXT,
    INVALID_DIGEST,
    INVALID_FILE_DESCRIPTOR,
    INVALID_OPERATION,
    INVALID_SCHEMA,
    INVALID_TARGET_FILE_ID,
    INVALID_TASK_ID,
    POST_DIGEST_MISMATCH,
    REPLAY_IDEMPOTENT,
    REPLAY_NEW_REQUEST,
    REPLAY_REUSE_MISMATCH,
    SCHEMA_CLIENT_REQUEST,
    SCHEMA_DECLARED_CONTEXT,
    SCHEMA_FILE_DESCRIPTOR,
    SCHEMA_FILE_EFFECT,
    SCHEMA_PLAN_LINKAGE,
    VALIDATION_OK,
    AuthorizedContentEffect,
    DeclaredInvocationContext,
    MediatedClientRequest,
    MediatedContractError,
    MediatedFileDescriptor,
    MediatedPlanLinkage,
    MediatedValidationError,
    RequestBinding,
    _REQUEST_EFFECT_FIELDS,
    assert_linkage_binds,
    assert_request_represents_effect,
    build_authorized_effect,
    build_client_request,
    build_plan_linkage,
    capability_binding_fields,
    classify_request_replay,
    validate_replacement_proposal,
    verify_proposed_bytes,
)
from triage_core.privacy_invariants import assert_persistent_privacy_safe

CONTENT = b"alpha\nbeta\n"
CONTENT_DIGEST = "sha256:" + hashlib.sha256(CONTENT).hexdigest()
PRE_DIGEST = "sha256:" + "1a" * 32
CONFIG_DIGEST = "sha256:" + "2b" * 32
OTHER_DIGEST = "sha256:" + "3c" * 32

TARGET_FILE_ID = "f-7c9e6679742540de944be07fc1f90ae7"
RELPATH = "docs/notes.md"
CLIENT_REQUEST_ID = "req-0e2f1a3b4c5d4e6f8a9b0c1d2e3f4a5b"
BROKER_CONNECTION_ID = "conn-8f14e45fceea4e78b3f41a2b3c4d5e6f"
TASK_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
DECISION_ID = "gd-1234567890abcdef"


def _descriptor(**overrides) -> MediatedFileDescriptor:
    base = dict(
        target_file_id=TARGET_FILE_ID,
        canonical_relpath=RELPATH,
        maximum_size_bytes=4096,
    )
    base.update(overrides)
    return MediatedFileDescriptor(**base)


def _context(**overrides) -> DeclaredInvocationContext:
    base = dict(
        runtime_id="openclaw",
        runtime_version="1.4.2",
        openclaw_config_digest=CONFIG_DIGEST,
        agent_id="agent-a",
        session_id="session-b",
        tool_name="propose_replacement",
        client_request_id=CLIENT_REQUEST_ID,
    )
    base.update(overrides)
    return DeclaredInvocationContext(**base)


def _effect(**overrides) -> AuthorizedContentEffect:
    kwargs = dict(
        expected_pre_digest=PRE_DIGEST,
        proposed_bytes=CONTENT,
        expected_post_digest=CONTENT_DIGEST,
        broker_connection_id=BROKER_CONNECTION_ID,
        client_request_id=CLIENT_REQUEST_ID,
    )
    kwargs.update(overrides)
    return build_authorized_effect(_descriptor(), _context(), **kwargs)


def _request(effect=None) -> MediatedClientRequest:
    return build_client_request(effect or _effect(), task_id=TASK_ID)


# --- 1. Deterministic canonical representation --------------------------------


def test_canonical_digest_is_deterministic_and_order_independent():
    first = _effect()
    second = _effect()
    assert first.effect_digest() == second.effect_digest()

    shuffled = dict(reversed(list(first.as_canonical_dict().items())))
    assert AuthorizedContentEffect.from_mapping(shuffled).effect_digest() == (
        first.effect_digest()
    )

    for _ in range(5):
        assert _effect().effect_digest() == first.effect_digest()


def test_canonical_json_is_the_approved_form():
    payload = _effect().as_canonical_dict()
    expected = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    assert (
        "sha256:" + hashlib.sha256(expected).hexdigest() == _effect().effect_digest()
    )


# --- 2. Every bound field changes the scope digest -----------------------------


# ``operation`` and ``schema`` are single-valued, so they cannot be varied to a
# second legal value here; they are covered by test_unknown_operation_fails_closed
# and the cross-domain distinctness test respectively.
@pytest.mark.parametrize(
    "field, value",
    [
        ("target_file_id", "f-different"),
        ("canonical_relpath", "docs/other.md"),
        ("expected_pre_digest", OTHER_DIGEST),
        ("expected_post_digest", OTHER_DIGEST),
        ("content_size_bytes", 99),
        ("declared_context_digest", OTHER_DIGEST),
        ("broker_connection_id", "conn-different"),
        ("client_request_id", "req-different"),
    ],
)
def test_altering_any_bound_field_changes_the_scope_digest(field, value):
    baseline = _effect()
    payload = dict(baseline.as_canonical_dict())
    assert payload[field] != value, "parametrized value must actually differ"
    payload[field] = value
    mutated = AuthorizedContentEffect.from_mapping(payload)
    assert mutated.effect_digest() != baseline.effect_digest()


def test_every_effect_field_participates_in_the_digest():
    payload = _effect().as_canonical_dict()
    assert set(payload) == set(AuthorizedContentEffect.FIELDS)


# --- 3. Declared context and broker binding stay distinct ----------------------


def test_declared_context_and_broker_binding_are_structurally_distinct():
    effect = _effect()
    projection = effect.persistent_projection()

    assert "declared_context_digest" in projection
    assert "broker_connection_id" in projection
    assert projection["declared_context_digest"] != projection["broker_connection_id"]

    # No accessor may present declared context as authenticated identity.
    surface = [name for name in dir(effect) if not name.startswith("_")]
    for name in surface:
        lowered = name.lower()
        assert "authenticated" not in lowered
        assert "verified_identity" not in lowered
    assert not any("authenticated" in key.lower() for key in projection)


def test_declared_context_digest_covers_only_declared_fields():
    context = _context()
    payload = context.as_canonical_dict()
    assert payload["schema"] == SCHEMA_DECLARED_CONTEXT
    assert "broker_connection_id" not in payload


# --- 4. Post-digest verification ----------------------------------------------


def test_proposed_bytes_must_match_the_post_digest():
    with pytest.raises(MediatedValidationError) as error:
        _effect(expected_post_digest=OTHER_DIGEST)
    assert error.value.reason_code == POST_DIGEST_MISMATCH


def test_matching_bytes_are_accepted():
    assert _effect().expected_post_digest == CONTENT_DIGEST


# --- 5. Non-UTF-8 content fails closed ----------------------------------------


def test_non_utf8_content_fails_closed():
    invalid = b"\xff\xfe\x00bad"
    digest = "sha256:" + hashlib.sha256(invalid).hexdigest()
    with pytest.raises(MediatedValidationError) as error:
        _effect(proposed_bytes=invalid, expected_post_digest=digest)
    assert error.value.reason_code == CONTENT_NOT_UTF8


# --- 6. Size limit fails closed -----------------------------------------------


def test_oversized_content_fails_closed():
    oversized = b"x" * 33
    digest = "sha256:" + hashlib.sha256(oversized).hexdigest()
    with pytest.raises(MediatedValidationError) as error:
        build_authorized_effect(
            _descriptor(maximum_size_bytes=32),
            _context(),
            expected_pre_digest=PRE_DIGEST,
            proposed_bytes=oversized,
            expected_post_digest=digest,
            broker_connection_id=BROKER_CONNECTION_ID,
            client_request_id=CLIENT_REQUEST_ID,
        )
    assert error.value.reason_code == CONTENT_SIZE_EXCEEDED


def test_content_exactly_at_the_limit_is_accepted():
    exact = b"y" * 32
    digest = "sha256:" + hashlib.sha256(exact).hexdigest()
    effect = build_authorized_effect(
        _descriptor(maximum_size_bytes=32),
        _context(),
        expected_pre_digest=PRE_DIGEST,
        proposed_bytes=exact,
        expected_post_digest=digest,
        broker_connection_id=BROKER_CONNECTION_ID,
        client_request_id=CLIENT_REQUEST_ID,
    )
    assert effect.content_size_bytes == 32


# --- 7. Exact-byte treatment ---------------------------------------------------


@pytest.mark.parametrize(
    "left, right, label",
    [
        (b"a\nb\n", b"a\r\nb\r\n", "newline style"),
        (b"\xef\xbb\xbfabc", b"abc", "BOM presence"),
        ("é".encode("utf-8"), "e\u0301".encode("utf-8"), "unicode normal form"),
    ],
)
def test_byte_variants_are_never_silently_reconciled(left, right, label):
    """Newline style, BOM, and normal form must produce different digests."""
    assert left != right, label
    left_digest = "sha256:" + hashlib.sha256(left).hexdigest()
    right_digest = "sha256:" + hashlib.sha256(right).hexdigest()
    assert left_digest != right_digest, label

    left_effect = _effect(proposed_bytes=left, expected_post_digest=left_digest)
    right_effect = _effect(proposed_bytes=right, expected_post_digest=right_digest)
    assert left_effect.effect_digest() != right_effect.effect_digest()

    # Cross-assignment must fail rather than be reconciled.
    with pytest.raises(MediatedValidationError) as error:
        _effect(proposed_bytes=left, expected_post_digest=right_digest)
    assert error.value.reason_code == POST_DIGEST_MISMATCH


# --- 8. content_size_bytes measures original bytes -----------------------------


def test_content_size_is_the_original_byte_length_not_decoded_length():
    multibyte = "héllo wörld".encode("utf-8")
    assert len(multibyte) != len(multibyte.decode("utf-8"))
    digest = "sha256:" + hashlib.sha256(multibyte).hexdigest()
    effect = _effect(proposed_bytes=multibyte, expected_post_digest=digest)
    assert effect.content_size_bytes == len(multibyte)


def test_bom_is_counted_not_stripped():
    with_bom = b"\xef\xbb\xbfabc"
    digest = "sha256:" + hashlib.sha256(with_bom).hexdigest()
    effect = _effect(proposed_bytes=with_bom, expected_post_digest=digest)
    assert effect.content_size_bytes == 6


# --- 9. A path cannot substitute for a target_file_id --------------------------


@pytest.mark.parametrize(
    "path_like",
    [
        "docs/notes.md",
        "docs\\notes.md",
        "../escape",
        "C:/abs/path",
        "~/home",
        "./relative",
    ],
)
def test_a_path_cannot_substitute_for_a_target_file_id(path_like):
    with pytest.raises(MediatedValidationError) as error:
        _descriptor(target_file_id=path_like)
    assert error.value.reason_code == INVALID_TARGET_FILE_ID


def test_canonical_relpath_is_not_a_resolution_channel():
    """It is bound into the digest, but the module never resolves or opens it."""
    effect = _effect()
    assert effect.canonical_relpath == RELPATH
    assert "canonical_relpath" in effect.as_canonical_dict()
    # Changing only the relpath changes the effect digest: it is integrity-bound.
    payload = dict(effect.as_canonical_dict())
    payload["canonical_relpath"] = "docs/elsewhere.md"
    assert (
        AuthorizedContentEffect.from_mapping(payload).effect_digest()
        != effect.effect_digest()
    )


# --- 10-12. Replay classification ---------------------------------------------


def test_classify_returns_new_request_for_absent_existing():
    assert classify_request_replay(None, _request().binding()) == REPLAY_NEW_REQUEST


def test_classify_returns_idempotent_replay_for_a_matching_pair():
    binding = _request().binding()
    assert classify_request_replay(binding, binding) == REPLAY_IDEMPOTENT


def test_classify_returns_reuse_mismatch_for_a_digest_difference():
    incoming = _request().binding()
    existing = RequestBinding(
        client_request_id=incoming.client_request_id,
        request_digest=OTHER_DIGEST,
    )
    assert classify_request_replay(existing, incoming) == REPLAY_REUSE_MISMATCH


def test_same_request_on_a_different_connection_is_reuse_mismatch():
    """The request digest covers broker_connection_id, so a reconnect differs."""
    first = _request(_effect(broker_connection_id="conn-first"))
    second = _request(_effect(broker_connection_id="conn-second"))
    assert first.client_request_id == second.client_request_id
    assert first.request_digest() != second.request_digest()
    assert (
        classify_request_replay(first.binding(), second.binding())
        == REPLAY_REUSE_MISMATCH
    )


def test_classify_raises_when_existing_carries_a_different_request_id():
    incoming = _request().binding()
    existing = RequestBinding(
        client_request_id="req-someone-else",
        request_digest=incoming.request_digest,
    )
    with pytest.raises(MediatedContractError):
        classify_request_replay(existing, incoming)


def test_request_binding_is_not_a_canonical_digest_object():
    binding = _request().binding()
    assert not hasattr(binding, "as_canonical_dict")
    assert not hasattr(binding, "digest")


# --- 13. Closed field sets -----------------------------------------------------


@pytest.mark.parametrize(
    "cls, payload_source",
    [
        (MediatedFileDescriptor, lambda: _descriptor().as_canonical_dict()),
        (DeclaredInvocationContext, lambda: _context().as_canonical_dict()),
        (AuthorizedContentEffect, lambda: _effect().as_canonical_dict()),
        (MediatedClientRequest, lambda: _request().as_canonical_dict()),
        (
            MediatedPlanLinkage,
            lambda: build_plan_linkage(
                _effect(), _request(), decision_id=DECISION_ID
            ).as_canonical_dict(),
        ),
    ],
)
def test_canonical_objects_reject_unknown_missing_and_null_fields(cls, payload_source):
    baseline = payload_source()
    assert cls.from_mapping(baseline) is not None

    unknown = dict(baseline)
    unknown["surprise"] = "value"
    with pytest.raises(MediatedValidationError):
        cls.from_mapping(unknown)

    for key in baseline:
        missing = {k: v for k, v in baseline.items() if k != key}
        with pytest.raises(MediatedValidationError):
            cls.from_mapping(missing)

        nulled = dict(baseline)
        nulled[key] = None
        with pytest.raises(MediatedValidationError):
            cls.from_mapping(nulled)


def test_digests_must_be_lowercase_sha256_with_prefix():
    for bad in ["", "sha256:zz", CONTENT_DIGEST.upper(), CONTENT_DIGEST[7:], 42]:
        with pytest.raises(MediatedValidationError) as error:
            _effect(expected_pre_digest=bad)
        assert error.value.reason_code in {INVALID_DIGEST, POST_DIGEST_MISMATCH}


def test_security_bound_identifiers_are_rejected_not_normalized():
    """Whitespace-padded identifiers fail rather than being silently trimmed."""
    with pytest.raises(MediatedValidationError) as error:
        _effect(broker_connection_id=" conn-padded ")
    assert error.value.reason_code == INVALID_BROKER_BINDING

    with pytest.raises(MediatedValidationError) as error:
        _context(agent_id="agent\twith\ttabs")
    assert error.value.reason_code == INVALID_DECLARED_CONTEXT


def test_task_and_decision_ids_stay_case_exact():
    linkage = build_plan_linkage(
        _effect(), _request(), decision_id="GD-MixedCase"
    )
    assert linkage.task_id == TASK_ID
    assert linkage.decision_id == "GD-MixedCase"


def test_unknown_operation_fails_closed():
    payload = dict(_effect().as_canonical_dict())
    payload["operation"] = "append"
    with pytest.raises(MediatedValidationError) as error:
        AuthorizedContentEffect.from_mapping(payload)
    assert error.value.reason_code == INVALID_OPERATION


# --- 14. Cross-domain distinctness ---------------------------------------------


def test_identical_payloads_in_different_domains_digest_differently():
    """The schema discriminator must make domains non-colliding."""
    shared = {"task_id": TASK_ID, "client_request_id": CLIENT_REQUEST_ID}
    from triage_core.mediated_effect import _digest_of  # noqa: PLC0415

    digests = {
        schema: _digest_of({"schema": schema, **shared})
        for schema in (
            SCHEMA_FILE_DESCRIPTOR,
            SCHEMA_DECLARED_CONTEXT,
            SCHEMA_FILE_EFFECT,
            SCHEMA_CLIENT_REQUEST,
            SCHEMA_PLAN_LINKAGE,
        )
    }
    assert len(set(digests.values())) == 5


def test_effect_and_request_digests_differ_for_the_same_proposal():
    effect = _effect()
    request = _request(effect)
    assert effect.effect_digest() != request.request_digest()


# --- 15-16. Persistent projection ----------------------------------------------


def test_projection_never_contains_file_content():
    secret = b"CANARY-SENTINEL-e6f1a2b3 top secret content\n"
    digest = "sha256:" + hashlib.sha256(secret).hexdigest()
    effect = _effect(proposed_bytes=secret, expected_post_digest=digest)

    projection = effect.persistent_projection()

    # No raw byte payload may reach the projection at all, in any field.
    for key, value in projection.items():
        assert not isinstance(value, (bytes, bytearray)), key

    serialized = json.dumps(projection)
    assert "CANARY" not in serialized
    assert "SENTINEL" not in serialized
    assert "top secret" not in serialized

    # The bytes are not reachable from the object at all.
    for value in vars(effect).values():
        assert not isinstance(value, (bytes, bytearray))
    assert b"CANARY" not in repr(effect).encode("utf-8", "ignore")


def test_projection_contains_content_shaped_metadata_only():
    """Content crafted to look like metadata still must not survive."""
    disguised = b'{"expected_pre_digest": "sha256:deadbeef", "secret": "LEAK"}'
    digest = "sha256:" + hashlib.sha256(disguised).hexdigest()
    effect = _effect(proposed_bytes=disguised, expected_post_digest=digest)
    assert "LEAK" not in json.dumps(effect.persistent_projection())


def test_projection_keys_are_exactly_the_contract_set():
    assert set(_effect().persistent_projection()) == {
        "target_file_id",
        "canonical_relpath",
        "expected_pre_digest",
        "expected_post_digest",
        "content_size_bytes",
        "client_request_id",
        "declared_context_digest",
        "broker_connection_id",
        "effect_digest",
    }


def test_projection_passes_the_persistent_privacy_invariant():
    assert_persistent_privacy_safe(
        _effect().persistent_projection(),
        artifact_name="mediated effect projection",
    )


# --- 17. All-or-nothing construction -------------------------------------------


def test_malformed_input_never_yields_a_partially_valid_effect():
    with pytest.raises(MediatedValidationError):
        _effect(expected_pre_digest="not-a-digest")
    with pytest.raises(MediatedValidationError):
        _effect(broker_connection_id="")
    with pytest.raises(MediatedValidationError):
        build_authorized_effect(
            _descriptor(),
            _context(client_request_id="req-mismatched"),
            expected_pre_digest=PRE_DIGEST,
            proposed_bytes=CONTENT,
            expected_post_digest=CONTENT_DIGEST,
            broker_connection_id=BROKER_CONNECTION_ID,
            client_request_id=CLIENT_REQUEST_ID,
        )


def test_validate_returns_closed_reason_codes():
    assert (
        validate_replacement_proposal(
            _descriptor(),
            _context(),
            expected_pre_digest=PRE_DIGEST,
            proposed_bytes=CONTENT,
            expected_post_digest=CONTENT_DIGEST,
            broker_connection_id=BROKER_CONNECTION_ID,
            client_request_id=CLIENT_REQUEST_ID,
        )
        == VALIDATION_OK
    )
    assert (
        validate_replacement_proposal(
            _descriptor(),
            _context(),
            expected_pre_digest=PRE_DIGEST,
            proposed_bytes=CONTENT,
            expected_post_digest=OTHER_DIGEST,
            broker_connection_id=BROKER_CONNECTION_ID,
            client_request_id=CLIENT_REQUEST_ID,
        )
        == POST_DIGEST_MISMATCH
    )


def test_capability_mapping_reuses_computed_digests():
    effect = _effect()
    request = _request(effect)
    linkage = build_plan_linkage(
        effect, request, decision_id=DECISION_ID
    )
    mapped = capability_binding_fields(effect, request, linkage)
    assert mapped["artifact_byte_digest"] == effect.expected_post_digest
    assert mapped["scope_digest"] == effect.effect_digest()
    assert mapped["plan_body_digest"] == linkage.plan_body_digest()


# --- Cross-object binding ------------------------------------------------------
#
# A linkage or capability bundle assembled from an effect and an unrelated
# request produces digests that each look valid while describing two different
# transitions. These tests close that seam. Mismatches between already-validated
# objects are caller-contract defects, so they raise MediatedContractError rather
# than entering the closed validation vocabulary.


def _effect_b():
    """A second, wholly distinct effect."""
    context = _context(client_request_id="req-BBB")
    return build_authorized_effect(
        _descriptor(target_file_id="f-bbb", canonical_relpath="docs/other.md"),
        context,
        expected_pre_digest=OTHER_DIGEST,
        proposed_bytes=b"different content\n",
        expected_post_digest="sha256:"
        + hashlib.sha256(b"different content\n").hexdigest(),
        broker_connection_id="conn-BBB",
        client_request_id="req-BBB",
    )


TASK_B = "8f14e45f-ceea-4e78-b3f4-1a2b3c4d5e6f"


def test_build_plan_linkage_rejects_a_request_from_a_different_effect():
    effect_a = _effect()
    request_b = build_client_request(_effect_b(), task_id=TASK_B)
    with pytest.raises(MediatedContractError):
        build_plan_linkage(effect_a, request_b, decision_id=DECISION_ID)


@pytest.mark.parametrize("field", list(_REQUEST_EFFECT_FIELDS))
def test_every_request_effect_field_is_compared(field):
    """Each bound field must be checked, not just the ones a happy path hits."""
    effect = _effect()
    request = _request(effect)
    payload = dict(request.as_canonical_dict())
    replacement = {
        "client_request_id": "req-other",
        "broker_connection_id": "conn-other",
        "target_file_id": "f-other",
        "canonical_relpath": "docs/other.md",
        "expected_pre_digest": OTHER_DIGEST,
        "expected_post_digest": OTHER_DIGEST,
        "content_size_bytes": 12345,
        "declared_context_digest": OTHER_DIGEST,
    }[field]
    payload[field] = replacement
    tampered = MediatedClientRequest.from_mapping(payload)
    with pytest.raises(MediatedContractError):
        assert_request_represents_effect(effect, tampered)


def test_linkage_task_id_is_derived_from_the_request():
    """No second task_id input, so the two cannot disagree."""
    effect = _effect()
    request = build_client_request(effect, task_id=TASK_B)
    linkage = build_plan_linkage(effect, request, decision_id=DECISION_ID)
    assert linkage.task_id == TASK_B


def test_capability_binding_rejects_a_linkage_for_a_different_effect():
    effect_a = _effect()
    request_a = _request(effect_a)
    linkage_a = build_plan_linkage(effect_a, request_a, decision_id=DECISION_ID)

    effect_b = _effect_b()
    request_b = build_client_request(effect_b, task_id=TASK_B)
    with pytest.raises(MediatedContractError):
        capability_binding_fields(effect_b, request_b, linkage_a)


def test_capability_binding_rejects_a_linkage_carrying_another_request_digest():
    effect = _effect()
    request = _request(effect)
    other_request = build_client_request(_effect_b(), task_id=TASK_B)
    forged = MediatedPlanLinkage(
        task_id=request.task_id,
        decision_id=DECISION_ID,
        client_request_id=effect.client_request_id,
        broker_connection_id=effect.broker_connection_id,
        effect_digest=effect.effect_digest(),
        request_digest=other_request.request_digest(),
    )
    with pytest.raises(MediatedContractError):
        capability_binding_fields(effect, request, forged)


def test_capability_binding_rejects_a_linkage_with_a_foreign_task_id():
    effect = _effect()
    request = _request(effect)
    forged = MediatedPlanLinkage(
        task_id=TASK_B,
        decision_id=DECISION_ID,
        client_request_id=effect.client_request_id,
        broker_connection_id=effect.broker_connection_id,
        effect_digest=effect.effect_digest(),
        request_digest=request.request_digest(),
    )
    with pytest.raises(MediatedContractError):
        capability_binding_fields(effect, request, forged)


def test_the_exact_matching_trio_succeeds():
    effect = _effect()
    request = _request(effect)
    linkage = build_plan_linkage(effect, request, decision_id=DECISION_ID)
    mapped = capability_binding_fields(effect, request, linkage)
    assert mapped["scope_digest"] == effect.effect_digest()
    assert mapped["plan_body_digest"] == linkage.plan_body_digest()
    assert linkage.task_id == request.task_id


# --- Honest reason codes -------------------------------------------------------
#
# A closed code is only useful when it names the condition that actually failed.
# Reporting a real failure under a different code is still a false report.


@pytest.mark.parametrize(
    "label, build, expected",
    [
        ("encoding not utf-8",
         lambda: _descriptor(encoding="latin-1"), INVALID_FILE_DESCRIPTOR),
        ("maximum_size_bytes zero",
         lambda: _descriptor(maximum_size_bytes=0), INVALID_FILE_DESCRIPTOR),
        ("maximum_size_bytes negative",
         lambda: _descriptor(maximum_size_bytes=-1), INVALID_FILE_DESCRIPTOR),
        ("canonical_relpath empty",
         lambda: _descriptor(canonical_relpath=""), INVALID_FILE_DESCRIPTOR),
        ("canonical_relpath wrong type",
         lambda: _descriptor(canonical_relpath=7), INVALID_FILE_DESCRIPTOR),
        ("target_file_id path-like",
         lambda: _descriptor(target_file_id="a/b"), INVALID_TARGET_FILE_ID),
    ],
)
def test_descriptor_reports_its_true_condition(label, build, expected):
    with pytest.raises(MediatedValidationError) as error:
        build()
    assert error.value.reason_code == expected, label


def test_linkage_reports_task_and_decision_ids_separately():
    common = dict(
        client_request_id=CLIENT_REQUEST_ID,
        broker_connection_id=BROKER_CONNECTION_ID,
        effect_digest=OTHER_DIGEST,
        request_digest=OTHER_DIGEST,
    )
    with pytest.raises(MediatedValidationError) as error:
        MediatedPlanLinkage(task_id="", decision_id=DECISION_ID, **common)
    assert error.value.reason_code == INVALID_TASK_ID

    with pytest.raises(MediatedValidationError) as error:
        MediatedPlanLinkage(task_id=TASK_ID, decision_id=" padded ", **common)
    assert error.value.reason_code == INVALID_DECISION_ID


def test_request_reports_task_id_separately_from_client_request_id():
    common = dict(
        broker_connection_id=BROKER_CONNECTION_ID,
        target_file_id=TARGET_FILE_ID,
        canonical_relpath=RELPATH,
        expected_pre_digest=PRE_DIGEST,
        expected_post_digest=CONTENT_DIGEST,
        content_size_bytes=11,
        declared_context_digest=OTHER_DIGEST,
    )
    with pytest.raises(MediatedValidationError) as error:
        MediatedClientRequest(task_id="", client_request_id=CLIENT_REQUEST_ID, **common)
    assert error.value.reason_code == INVALID_TASK_ID

    with pytest.raises(MediatedValidationError) as error:
        MediatedClientRequest(task_id=TASK_ID, client_request_id="", **common)
    assert error.value.reason_code == INVALID_CLIENT_REQUEST_ID


@pytest.mark.parametrize(
    "cls, payload_source",
    [
        (MediatedFileDescriptor, lambda: _descriptor().as_canonical_dict()),
        (DeclaredInvocationContext, lambda: _context().as_canonical_dict()),
        (AuthorizedContentEffect, lambda: _effect().as_canonical_dict()),
        (MediatedClientRequest, lambda: _request().as_canonical_dict()),
    ],
)
def test_wrong_discriminator_reports_invalid_schema(cls, payload_source):
    payload = dict(payload_source())
    payload["schema"] = "triagecore.some_other_object.v1"
    with pytest.raises(MediatedValidationError) as error:
        cls.from_mapping(payload)
    assert error.value.reason_code == INVALID_SCHEMA


def test_malformed_object_shape_reports_invalid_schema():
    payload = dict(_effect().as_canonical_dict())
    payload["surprise"] = 1
    with pytest.raises(MediatedValidationError) as error:
        AuthorizedContentEffect.from_mapping(payload)
    assert error.value.reason_code == INVALID_SCHEMA


def test_bad_content_size_is_distinguished_from_exceeding_the_limit():
    """A malformed size and an oversized payload are different conditions."""
    payload = dict(_effect().as_canonical_dict())
    payload["content_size_bytes"] = -1
    with pytest.raises(MediatedValidationError) as error:
        AuthorizedContentEffect.from_mapping(payload)
    assert error.value.reason_code == INVALID_CONTENT_SIZE

    oversized = b"z" * 40
    with pytest.raises(MediatedValidationError) as error:
        build_authorized_effect(
            _descriptor(maximum_size_bytes=8),
            _context(),
            expected_pre_digest=PRE_DIGEST,
            proposed_bytes=oversized,
            expected_post_digest="sha256:" + hashlib.sha256(oversized).hexdigest(),
            broker_connection_id=BROKER_CONNECTION_ID,
            client_request_id=CLIENT_REQUEST_ID,
        )
    assert error.value.reason_code == CONTENT_SIZE_EXCEEDED


def test_operation_code_is_reserved_for_the_operation_field():
    """invalid_operation must not be borrowed for unrelated failures."""
    payload = dict(_effect().as_canonical_dict())
    payload["operation"] = "append"
    with pytest.raises(MediatedValidationError) as error:
        AuthorizedContentEffect.from_mapping(payload)
    assert error.value.reason_code == INVALID_OPERATION

    # A descriptor problem must not surface as an operation problem.
    with pytest.raises(MediatedValidationError) as error:
        _descriptor(encoding="utf-16")
    assert error.value.reason_code != INVALID_OPERATION


@pytest.mark.parametrize("not_an_effect", [None, {"not": "an effect"}, 42, "effect"])
def test_build_client_request_rejects_a_non_effect_as_a_caller_defect(not_an_effect):
    """No operation field failed, so invalid_operation must not be borrowed."""
    with pytest.raises(MediatedContractError):
        build_client_request(not_an_effect, task_id=TASK_ID)


def test_verify_proposed_bytes_rejects_a_non_positive_limit():
    """Every public entry point must agree on what a valid limit is.

    ``MediatedFileDescriptor`` rejects a zero maximum, so the helper must too --
    otherwise empty content slips through a limit the descriptor would refuse.
    """
    empty_digest = "sha256:" + hashlib.sha256(b"").hexdigest()
    for limit in (0, -1):
        with pytest.raises(MediatedValidationError) as error:
            verify_proposed_bytes(b"", empty_digest, limit)
        assert error.value.reason_code == INVALID_FILE_DESCRIPTOR

    # A valid positive limit still accepts empty content.
    assert verify_proposed_bytes(b"", empty_digest, 1) == 0


def test_every_emitted_reason_code_is_in_the_closed_vocabulary():
    from triage_core.mediated_effect import VALIDATION_REASONS  # noqa: PLC0415

    emitters = [
        lambda: _descriptor(encoding="latin-1"),
        lambda: _descriptor(maximum_size_bytes=0),
        lambda: _descriptor(target_file_id="a/b"),
        lambda: _context(agent_id=""),
        lambda: _effect(expected_pre_digest="nope"),
        lambda: _effect(expected_post_digest=OTHER_DIGEST),
        lambda: _effect(broker_connection_id=""),
    ]
    for emitter in emitters:
        try:
            emitter()
        except MediatedValidationError as error:
            assert error.reason_code in VALIDATION_REASONS


# --- 18. No I/O, demonstrated rather than stated -------------------------------


def _exercise_every_public_path():
    """Touch every public constructor, builder, digest, projection, classifier."""
    descriptor = _descriptor()
    context = _context()
    effect = build_authorized_effect(
        descriptor,
        context,
        expected_pre_digest=PRE_DIGEST,
        proposed_bytes=CONTENT,
        expected_post_digest=CONTENT_DIGEST,
        broker_connection_id=BROKER_CONNECTION_ID,
        client_request_id=CLIENT_REQUEST_ID,
    )
    request = build_client_request(effect, task_id=TASK_ID)
    linkage = build_plan_linkage(
        effect, request, decision_id=DECISION_ID
    )
    outputs = [
        descriptor.digest(),
        context.declared_context_digest(),
        effect.effect_digest(),
        effect.persistent_projection(),
        request.request_digest(),
        linkage.plan_body_digest(),
        capability_binding_fields(effect, request, linkage),
        validate_replacement_proposal(
            descriptor,
            context,
            expected_pre_digest=PRE_DIGEST,
            proposed_bytes=CONTENT,
            expected_post_digest=CONTENT_DIGEST,
            broker_connection_id=BROKER_CONNECTION_ID,
            client_request_id=CLIENT_REQUEST_ID,
        ),
        classify_request_replay(None, request.binding()),
        classify_request_replay(request.binding(), request.binding()),
        MediatedFileDescriptor.from_mapping(descriptor.as_canonical_dict()),
        DeclaredInvocationContext.from_mapping(context.as_canonical_dict()),
        AuthorizedContentEffect.from_mapping(effect.as_canonical_dict()),
        MediatedClientRequest.from_mapping(request.as_canonical_dict()),
        MediatedPlanLinkage.from_mapping(linkage.as_canonical_dict()),
    ]
    return outputs


def test_public_surface_performs_no_io(monkeypatch):
    """Replace representative I/O entry points with exploding stubs.

    This exercises the public surface rather than only inspecting imports, so a
    future change that reaches for I/O fails here rather than passing a source
    scan.
    """

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("mediated_effect attempted I/O")

    monkeypatch.setattr(builtins, "open", explode)
    monkeypatch.setattr(io, "open", explode)
    monkeypatch.setattr(socket, "socket", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(subprocess, "Popen", explode)
    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(sqlite3, "connect", explode)
    for name in ("open", "remove", "mkdir", "makedirs", "stat", "listdir"):
        import os

        monkeypatch.setattr(os, name, explode, raising=False)

    outputs = _exercise_every_public_path()
    assert len(outputs) == 15


def test_module_imports_no_io_or_authority_modules():
    """Supplementary source check; not a substitute for the behavioral test."""
    import triage_core.mediated_effect as module

    source = module.__file__
    with open(source, "r", encoding="utf-8") as handle:
        text = handle.read()

    forbidden = [
        "import os",
        "import socket",
        "import subprocess",
        "import sqlite3",
        "from triage_core.authz",
        "from triage_core.capability_claims",
        "from triage_core.task_ledger",
        "import requests",
        "urllib",
    ]
    for token in forbidden:
        assert token not in text, token
