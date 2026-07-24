from __future__ import annotations

import base64
from dataclasses import FrozenInstanceError, replace
from enum import Enum, IntEnum
from hashlib import sha256
import json
from types import MappingProxyType

import pytest

import triage_core.governed_decision as governed_decision
from triage_core.privacy_invariants import assert_persistent_privacy_safe
from triage_core.governed_decision import (
    CANONICALIZATION_VERSION,
    CLASSIFICATION_POLICY_VERSION,
    CONFIGURATION_VERSION,
    CONTRACT_VERSION,
    IDENTITY_DOMAIN,
    POLICY_VERSION,
    ROUTE_POLICY_VERSION,
    VERIFICATION_POLICY_VERSION,
    DecisionPolicyConfiguration,
    GovernedDecisionError,
    build_governed_decision,
    parse_governed_decision,
    serialize_governed_decision,
    verify_governed_decision_id,
)
from triage_core.governed_run_snapshot import (
    ContextModelProfile,
    GovernedRunInputSnapshot,
    SnapshotConstructionLimits,
    SourceBytesInput,
    WorkerSystemMessageBinding,
    build_governed_run_input_snapshot,
    normalize_operator_declarations,
    sha256_digest,
)


def _digest(value: bytes) -> str:
    return "sha256:" + sha256(value).hexdigest()


def _binding(
    *,
    instruction: bytes = b"Review the bounded input",
    inline: bytes = b"inline value",
    source_components: tuple[bytes, ...] = (
        b"\n--- first.txt ---\nalpha",
        b"\n--- second.txt ---\nbeta",
    ),
    locators: tuple[bytes, ...] = (b"first.txt", b"second.txt"),
    task_id: str | None = None,
    privacy: str = "external_safe",
    cloud_intent: str = "not_requested",
) -> GovernedRunInputSnapshot:
    profile = ContextModelProfile(
        profile_id="generic-8k",
        context_window_tokens=8192,
        reserved_output_tokens=1024,
        safety_margin_tokens=256,
    )
    declarations = normalize_operator_declarations(
        task_id=task_id,
        declared_privacy=privacy,
        cloud_intent=cloud_intent == "requested",
        resolved_profile=profile,
    )
    limits = SnapshotConstructionLimits(
        max_source_count=16,
        max_instruction_bytes=4096,
        max_inline_input_bytes=4096,
        max_source_bytes_per_source=8192,
        max_total_source_bytes=65536,
        max_normalized_component_bytes_per_source=16384,
        max_total_normalized_component_bytes=131072,
        max_task_data_bytes=135168,
        max_assembled_execution_bytes=143360,
    )
    sources = tuple(
        SourceBytesInput(
            path_spelling=locators[index].decode("utf-8"),
            source_bytes=component,
        )
        for index, component in enumerate(source_components)
    )
    return build_governed_run_input_snapshot(
        prompt=instruction.decode("utf-8"),
        sources=sources,
        inline_input=inline.decode("utf-8") if inline else None,
        declarations=declarations,
        resolved_profile=profile,
        worker_system_message=WorkerSystemMessageBinding(
            version="worker_system_message.v1",
            sha256=sha256_digest(b"fixed-system-message"),
        ),
        limits=limits,
    )


def _configuration(**overrides: object) -> DecisionPolicyConfiguration:
    values: dict[str, object] = {
        "configuration_version": CONFIGURATION_VERSION,
        "configuration_sha256": _digest(b"explicit-configuration"),
        "policy_version": POLICY_VERSION,
        "classification_policy_version": CLASSIFICATION_POLICY_VERSION,
        "route_policy_version": ROUTE_POLICY_VERSION,
        "verification_policy_version": VERIFICATION_POLICY_VERSION,
        "estimated_input_tokens": 128,
        "usable_input_tokens": 1024,
        "privacy_preflight": "passed",
        "classification": "docs_update",
        "risk_posture": "low",
        "classification_reason_codes": ("deterministic_classifier_match",),
        "preferred_logical_route": "local_fast",
        "permitted_fallback_envelope": (
            "local_heavy",
            "local_fast",
            "human_handoff",
        ),
        "route_reason_codes": ("policy_selected",),
        "terminal_escalation": "none",
        "ethical_firewall": "clear",
        "human_review": "not_required",
        "escalation_conditions": ("route_unavailable_at_execution",),
        "required_checks": (
            "packet_verification",
            "privacy_preflight",
            "decision_identity_verification",
        ),
    }
    values.update(overrides)
    return DecisionPolicyConfiguration(**values)


def _decision(
    *,
    binding: GovernedRunInputSnapshot | None = None,
    configuration: DecisionPolicyConfiguration | None = None,
):
    return build_governed_decision(
        binding or _binding(),
        configuration or _configuration(),
    )


def _primitive(decision=None) -> dict[str, object]:
    return json.loads(serialize_governed_decision(decision or _decision()))


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_builder_rejects_lookalike_before_invoking_its_binding_method() -> None:
    class SideEffectingLookalike:
        def __init__(self) -> None:
            self.called = False

        def to_decision_binding(self) -> object:
            self.called = True
            raise AssertionError("lookalike callback must not run")

    lookalike = SideEffectingLookalike()
    with pytest.raises(GovernedDecisionError) as exc:
        build_governed_decision(lookalike, _configuration())  # type: ignore[arg-type]

    assert exc.value.code == "invalid_snapshot_type"
    assert lookalike.called is False


def test_public_boundaries_reject_hostile_value_subclasses_without_field_access() -> None:
    class HostileConfiguration(DecisionPolicyConfiguration):
        __slots__ = ("_touched",)

        def __getattribute__(self, name: str) -> object:
            if name == "_touched":
                return object.__getattribute__(self, name)
            object.__setattr__(self, "_touched", True)
            raise AssertionError("hostile configuration field access")

    class HostileDecision(governed_decision.GovernedDecision):
        __slots__ = ("_touched",)

        def __getattribute__(self, name: str) -> object:
            if name == "_touched":
                return object.__getattribute__(self, name)
            object.__setattr__(self, "_touched", True)
            raise AssertionError("hostile decision field access")

    hostile_configuration = object.__new__(HostileConfiguration)
    object.__setattr__(hostile_configuration, "_touched", False)
    hostile_decision = object.__new__(HostileDecision)
    object.__setattr__(hostile_decision, "_touched", False)

    with pytest.raises(GovernedDecisionError) as builder_error:
        build_governed_decision(
            _binding(),
            hostile_configuration,
        )
    assert builder_error.value.code == "invalid_configuration_type"

    with pytest.raises(GovernedDecisionError) as serializer_error:
        serialize_governed_decision(hostile_decision)
    assert serializer_error.value.code == "invalid_decision_type"
    assert verify_governed_decision_id(hostile_decision) is False
    assert object.__getattribute__(hostile_configuration, "_touched") is False
    assert object.__getattribute__(hostile_decision, "_touched") is False


def test_repeated_inputs_produce_identical_canonical_bytes_and_id() -> None:
    first = _decision()
    second = _decision()

    assert first == second
    assert first.decision_id == second.decision_id
    assert serialize_governed_decision(first) == serialize_governed_decision(second)
    assert verify_governed_decision_id(first)
    assert parse_governed_decision(serialize_governed_decision(first)) == first


def test_identity_uses_complete_domain_separated_envelope() -> None:
    decision = _decision()
    complete = _primitive(decision)
    envelope = {
        "identity_domain": IDENTITY_DOMAIN,
        "contract_version": CONTRACT_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "decision_body": complete["decision_body"],
    }
    expected = "sha256:" + sha256(_json_bytes(envelope)).hexdigest()

    assert decision.decision_id == expected
    assert "plan_body_digest" not in serialize_governed_decision(decision).decode()
    assert "artifact_byte_digest" not in serialize_governed_decision(decision).decode()


@pytest.mark.parametrize(
    "replacement",
    [
        _binding(instruction=b"changed"),
        _binding(inline=b"changed"),
        _binding(
            source_components=(
                b"\n--- second.txt ---\nbeta",
                b"\n--- first.txt ---\nalpha",
            ),
            locators=(b"second.txt", b"first.txt"),
        ),
        _binding(
            source_components=(
                b"\n--- first.txt ---\nalpha",
                b"\n--- first.txt ---\nalpha",
            ),
            locators=(b"first.txt", b"first.txt"),
        ),
        _binding(
            source_components=(b"\n--- .\\first.txt ---\nalpha",),
            locators=(b".\\first.txt",),
        ),
        _binding(privacy="public"),
        _binding(cloud_intent="requested"),
    ],
)
def test_execution_significant_snapshot_changes_change_decision_id(
    replacement,
) -> None:
    assert _decision(binding=replacement).decision_id != _decision().decision_id


def test_configuration_changes_change_decision_id_and_order_is_semantic() -> None:
    baseline = _decision()
    reversed_fallbacks = _configuration(
        permitted_fallback_envelope=(
            "human_handoff",
            "local_fast",
            "local_heavy",
        )
    )
    duplicate_fallbacks = _configuration(
        permitted_fallback_envelope=(
            "local_heavy",
            "local_fast",
            "local_fast",
            "human_handoff",
        )
    )

    assert _decision(configuration=reversed_fallbacks).decision_id != baseline.decision_id
    duplicate = _decision(configuration=duplicate_fallbacks)
    parsed = parse_governed_decision(serialize_governed_decision(duplicate))
    assert parsed.policy.permitted_fallback_envelope == (
        "local_heavy",
        "local_fast",
        "local_fast",
        "human_handoff",
    )


def test_policy_collections_are_owned_and_recursively_immutable() -> None:
    fallback_list = ["local_heavy", "human_handoff"]
    check_list = ["packet_verification"]
    configuration = _configuration(
        permitted_fallback_envelope=fallback_list,
        required_checks=check_list,
    )
    fallback_list.append("cloud_primary")
    check_list.append("output_validation")

    assert configuration.permitted_fallback_envelope == (
        "local_heavy",
        "human_handoff",
    )
    assert configuration.required_checks == ("packet_verification",)
    with pytest.raises(FrozenInstanceError):
        configuration.risk_posture = "high"  # type: ignore[misc]
    with pytest.raises(TypeError):
        configuration.required_checks[0] = "output_validation"  # type: ignore[index]


def test_policy_rejects_unbounded_iterators_before_copying() -> None:
    with pytest.raises(GovernedDecisionError) as exc:
        _configuration(
            required_checks=(
                value for value in ("packet_verification",)
            )
        )
    assert exc.value.code == "ordered_collection_invalid"


def test_builder_calculates_budget_and_egress_postures_without_authority() -> None:
    local = _decision(
        binding=_binding(privacy="local_only", cloud_intent="requested"),
        configuration=_configuration(
            estimated_input_tokens=1025,
            usable_input_tokens=1024,
        ),
    )
    body = _primitive(local)["decision_body"]

    assert body["context_budget"]["posture"] == "over_budget"
    assert body["privacy_and_egress"] == {
        "cloud_authorization": "not_granted",
        "cloud_intent": "requested",
        "egress_eligibility": "prohibited",
        "privacy_preflight": "passed",
    }
    assert body["authority_boundary"] == {
        "acceptance_authority": "not_granted",
        "confirmation_authority": "not_granted",
        "decision_id_is_linkage_only": True,
        "egress_authority": "not_granted",
        "execution_authority": "not_granted",
    }


def test_builder_rejects_cloud_route_outside_egress_envelope() -> None:
    with pytest.raises(GovernedDecisionError) as exc:
        _decision(
            binding=_binding(privacy="local_only"),
            configuration=_configuration(
                permitted_fallback_envelope=("cloud_primary",),
            ),
        )
    assert exc.value.code == "cloud_route_outside_egress_envelope"


@pytest.mark.parametrize(
    "configuration",
    [
        _configuration(risk_posture="high"),
        _configuration(privacy_preflight="failed"),
        _configuration(ethical_firewall="triggered"),
        _configuration(preferred_logical_route="human_handoff"),
        _configuration(terminal_escalation="human_only"),
    ],
)
def test_builder_fails_closed_on_missing_required_human_review(
    configuration,
) -> None:
    with pytest.raises(GovernedDecisionError) as exc:
        _decision(configuration=configuration)
    assert exc.value.code == "human_review_posture_inconsistent"


def test_canonical_bytes_use_pinned_json_profile() -> None:
    payload = {"z": "café", "a": "\"\\\b\f\n\r\t\u0000"}
    encoded = governed_decision._canonical_json_bytes(payload)

    assert encoded == (
        b'{"a":"\\"\\\\\\b\\f\\n\\r\\t\\u0000","z":"caf\xc3\xa9"}'
    )
    assert not encoded.endswith(b"\n")
    assert b"\\u00e9" not in encoded


class _TextEnum(str, Enum):
    VALUE = "text"


class _NumberEnum(IntEnum):
    VALUE = 1


class _DictionarySubclass(dict):
    pass


class _ListSubclass(list):
    pass


@pytest.mark.parametrize(
    "invalid",
    [
        1.5,
        float("nan"),
        ("tuple",),
        b"bytes",
        bytearray(b"buffer"),
        memoryview(b"view"),
        {"set"},
        _TextEnum.VALUE,
        _NumberEnum.VALUE,
        MappingProxyType({"key": "value"}),
        _DictionarySubclass(key="value"),
        _ListSubclass(["value"]),
        object(),
        1 << 63,
        -(1 << 63),
    ],
)
def test_canonicalizer_rejects_non_exact_or_unbounded_primitives(
    invalid: object,
) -> None:
    with pytest.raises(GovernedDecisionError) as exc:
        governed_decision._canonical_json_bytes({"value": invalid})
    assert exc.value.code in {"canonical_type_forbidden", "integer_invalid"}


@pytest.mark.parametrize(
    "invalid",
    [
        {1: "integer key"},
        {"é": "non-ASCII key"},
        {"value": "\ud800"},
    ],
)
def test_canonicalizer_rejects_invalid_keys_and_utf8_strings(
    invalid: object,
) -> None:
    with pytest.raises(GovernedDecisionError) as exc:
        governed_decision._canonical_json_bytes(invalid)
    assert exc.value.code in {"canonical_key_invalid", "canonical_string_invalid"}


def test_canonicalizer_rejects_container_cycles_and_shared_aliases() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)
    shared: list[object] = []

    for invalid in (cyclic, {"first": shared, "second": shared}):
        with pytest.raises(GovernedDecisionError) as exc:
            governed_decision._canonical_json_bytes(invalid)
        assert exc.value.code == "canonical_container_alias_forbidden"


def test_canonicalizer_preserves_unicode_code_point_sequences() -> None:
    nfc = governed_decision._canonical_json_bytes({"value": "caf\u00e9"})
    nfd = governed_decision._canonical_json_bytes({"value": "cafe\u0301"})

    assert nfc != nfd
    assert b"\xc3\xa9" in nfc
    assert b"\xcc\x81" in nfd


def test_unicode_task_identifiers_are_not_normalized_before_identity() -> None:
    nfc = _decision(binding=_binding(task_id="caf\u00e9"))
    nfd = _decision(binding=_binding(task_id="cafe\u0301"))

    assert nfc.decision_id != nfd.decision_id
    assert b"caf\xc3\xa9" in serialize_governed_decision(nfc)
    assert b"cafe\xcc\x81" in serialize_governed_decision(nfd)


def test_parser_rejects_duplicate_keys_at_top_and_nested_depth() -> None:
    canonical = serialize_governed_decision(_decision())
    top_duplicate = canonical.replace(
        b"{",
        b'{"identity_domain":"triagecore.governed_decision.identity.v1",',
        1,
    )
    nested_duplicate = canonical.replace(
        b'"classification":{',
        b'"classification":{"category":"docs_update",',
        1,
    )

    for candidate in (top_duplicate, nested_duplicate):
        with pytest.raises(GovernedDecisionError) as exc:
            parse_governed_decision(candidate)
        assert exc.value.code == "duplicate_key"


def test_parser_rejects_float_unknown_missing_and_wrong_integer_type() -> None:
    cases: list[tuple[dict[str, object], str]] = []
    with_float = _primitive()
    with_float["decision_body"]["context_budget"]["estimated_input_tokens"] = 1.5
    cases.append((with_float, "float_forbidden"))
    with_unknown = _primitive()
    with_unknown["decision_body"]["verification"]["extra"] = False
    cases.append((with_unknown, "unknown_field"))
    with_missing = _primitive()
    del with_missing["decision_body"]["verification"]["required_checks"]
    cases.append((with_missing, "missing_field"))
    with_bool = _primitive()
    with_bool["decision_body"]["context_budget"]["estimated_input_tokens"] = True
    cases.append((with_bool, "integer_invalid"))

    for primitive, expected_code in cases:
        with pytest.raises(GovernedDecisionError) as exc:
            parse_governed_decision(_json_bytes(primitive))
        assert exc.value.code == expected_code


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda value: value.update(identity_domain="wrong.domain"),
            "identity_domain_unsupported",
        ),
        (
            lambda value: value.update(contract_version="governed_decision.v2"),
            "contract_version_unsupported",
        ),
        (
            lambda value: value.update(
                canonicalization_version="canonical_json.v2"
            ),
            "canonicalization_version_unsupported",
        ),
        (
            lambda value: value["decision_body"]["normalization"].update(
                snapshot_contract_version="governed_run_input_snapshot.v2"
            ),
            "version_unsupported",
        ),
        (
            lambda value: value["decision_body"]["snapshot_binding"][
                "instruction"
            ].update(sha256="sha256:ABC"),
            "digest_invalid",
        ),
        (
            lambda value: value.update(decision_id="sha256:" + ("0" * 64)),
            "decision_id_mismatch",
        ),
    ],
)
def test_parser_rejects_domain_version_digest_and_identity_tampering(
    mutator,
    expected_code,
) -> None:
    primitive = _primitive()
    mutator(primitive)

    with pytest.raises(GovernedDecisionError) as exc:
        parse_governed_decision(_json_bytes(primitive))
    assert exc.value.code == expected_code


def test_parser_rejects_noncanonical_bom_malformed_utf8_and_lone_surrogate() -> None:
    canonical = serialize_governed_decision(_decision())
    candidates = (
        (b"\xef\xbb\xbf" + canonical, "canonical_bom_forbidden"),
        (canonical + b"\n", "noncanonical_bytes"),
        (canonical.replace(b":", b": ", 1), "noncanonical_bytes"),
        (b"\xff", "canonical_utf8_invalid"),
        (b'{"x":"\\ud800"}', "unknown_field"),
    )
    for candidate, expected_code in candidates:
        with pytest.raises(GovernedDecisionError) as exc:
            parse_governed_decision(candidate)
        assert exc.value.code == expected_code


def test_parser_rejects_unknown_nested_enum_and_bad_ordered_source_position() -> None:
    bad_enum = _primitive()
    bad_enum["decision_body"]["logical_route_policy"][
        "permitted_fallback_envelope"
    ][0] = "invented_route"
    bad_position = _primitive()
    bad_position["decision_body"]["snapshot_binding"]["sources"][0][
        "position"
    ] = 1

    for primitive, expected_code in (
        (bad_enum, "enum_invalid"),
        (bad_position, "source_position_invalid"),
    ):
        with pytest.raises(GovernedDecisionError) as exc:
            parse_governed_decision(_json_bytes(primitive))
        assert exc.value.code == expected_code


def test_decision_serialization_contains_no_supplied_task_material() -> None:
    prompt = "UNIQUE_PROMPT_7f6a"
    inline = "INLINE_SECRET_sk-test-1234"
    content = "SENSITIVE_MARKER_Bo-No-Po-Ti"
    path = r"C:\private\tribal-intake-secret.txt"
    basename = "tribal-intake-secret.txt"
    component = f"\n--- {path} ---\n{content}".encode()
    binding = _binding(
        instruction=prompt.encode(),
        inline=inline.encode(),
        source_components=(component,),
        locators=(path.encode(),),
    )
    canonical = serialize_governed_decision(_decision(binding=binding))

    supplied = (prompt, inline, content, path, basename, component.decode())
    for value in supplied:
        assert value.encode() not in canonical
        assert base64.b64encode(value.encode()) not in canonical
    for forbidden_key in (
        b'"prompt"',
        b'"data"',
        b'"content"',
        b'"path"',
        b'"secret"',
        b'"token"',
        b'"messages"',
    ):
        assert forbidden_key not in canonical
    assert_persistent_privacy_safe(
        json.loads(canonical),
        artifact_name="governed decision",
    )


def test_rejected_values_are_not_echoed_in_errors() -> None:
    supplied_secret = "SECRET_VALUE_MUST_NOT_ECHO"
    with pytest.raises(GovernedDecisionError) as exc:
        _configuration(configuration_version=supplied_secret + "!")
    assert supplied_secret not in str(exc.value)


def test_noncanonical_key_order_is_rejected_even_when_semantics_match() -> None:
    primitive = _primitive()
    reordered = {
        key: primitive[key]
        for key in reversed(tuple(primitive))
    }
    noncanonical = json.dumps(
        reordered,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode()
    assert json.loads(noncanonical) == primitive

    with pytest.raises(GovernedDecisionError) as exc:
        parse_governed_decision(noncanonical)
    assert exc.value.code == "noncanonical_bytes"
