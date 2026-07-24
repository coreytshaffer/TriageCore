from __future__ import annotations

import base64
import builtins
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import triage_core.governed_run_snapshot as snapshot_module
from triage_core.governed_decision import (
    CLASSIFICATION_POLICY_VERSION,
    CONFIGURATION_VERSION,
    POLICY_VERSION,
    ROUTE_POLICY_VERSION,
    VERIFICATION_POLICY_VERSION,
    DecisionPolicyConfiguration,
    build_governed_decision,
    verify_governed_decision_id,
)
from triage_core.governed_run_snapshot import (
    ASSEMBLY_CONTRACT_VERSION,
    CONSTRUCTION_LIMITS_VERSION,
    DECODE_NEWLINE_CONTRACT_VERSION,
    EXECUTION_DATA_SEPARATOR,
    PROFILE_RESOLUTION_VERSION,
    SNAPSHOT_CONTRACT_VERSION,
    ContextModelProfile,
    GovernedRunInputSnapshot,
    SnapshotConstructionLimits,
    SnapshotLimitError,
    SnapshotValidationError,
    SourceBytesInput,
    WorkerSystemMessageBinding,
    build_governed_run_input_snapshot,
    normalize_operator_declarations,
    resolve_context_model_profile,
    sha256_digest,
)


def _limits(**overrides: object) -> SnapshotConstructionLimits:
    values: dict[str, object] = {
        "max_source_count": 8,
        "max_instruction_bytes": 512,
        "max_inline_input_bytes": 512,
        "max_source_bytes_per_source": 1_024,
        "max_total_source_bytes": 4_096,
        "max_normalized_component_bytes_per_source": 2_048,
        "max_total_normalized_component_bytes": 8_192,
        "max_task_data_bytes": 8_704,
        "max_assembled_execution_bytes": 9_224,
        "max_retained_source_bytes_per_source": None,
        "max_total_retained_source_bytes": None,
    }
    values.update(overrides)
    return SnapshotConstructionLimits(**values)


def _profile(
    profile_id: str = "ordinary",
    *,
    context_window_tokens: int = 4_096,
    reserved_output_tokens: int = 512,
    safety_margin_tokens: int = 128,
) -> ContextModelProfile:
    return ContextModelProfile(
        profile_id=profile_id,
        context_window_tokens=context_window_tokens,
        reserved_output_tokens=reserved_output_tokens,
        safety_margin_tokens=safety_margin_tokens,
    )


def _source(path: object, raw: bytes | bytearray | memoryview) -> SourceBytesInput:
    return SourceBytesInput.from_bytes(path, raw, max_bytes=4_096)


def _build(
    *,
    prompt: str = "Review",
    sources: object = (),
    inline_input: str | None = None,
    limits: SnapshotConstructionLimits | None = None,
    retain_source_bytes: bool = False,
    profile: ContextModelProfile | None = None,
) -> GovernedRunInputSnapshot:
    resolved_profile = profile or _profile()
    declarations = normalize_operator_declarations(
        task_id=None,
        declared_privacy="local_only",
        cloud_intent=False,
        resolved_profile=resolved_profile,
    )
    return build_governed_run_input_snapshot(
        prompt=prompt,
        sources=sources,
        inline_input=inline_input,
        declarations=declarations,
        resolved_profile=resolved_profile,
        worker_system_message=WorkerSystemMessageBinding(
            version="worker_system.v1",
            sha256=sha256_digest(b"fixed system message"),
        ),
        limits=limits or _limits(),
        retain_source_bytes=retain_source_bytes,
    )


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        (b"alpha\nbeta\n", b"alpha\nbeta\n"),
        (b"alpha\r\nbeta\r", b"alpha\nbeta\n"),
        (b"alpha\rbeta\r\ngamma\n", b"alpha\nbeta\ngamma\n"),
        (b"\xef\xbb\xbfBOM\r\nkept", b"\xef\xbb\xbfBOM\nkept"),
        ("café 🌲\r\n".encode("utf-8"), "café 🌲\n".encode("utf-8")),
        (b"", b""),
    ],
)
def test_exact_file_normalization_header_and_execution_bytes(
    raw: bytes,
    normalized: bytes,
) -> None:
    path = r".\operator\input.txt"
    snapshot = _build(
        prompt="Summarize é",
        sources=(_source(path, raw),),
        inline_input="tail",
    )
    component = b"\n--- " + path.encode("utf-8") + b" ---\n" + normalized
    task_data = component + b"tail"
    execution = "Summarize é".encode("utf-8") + EXECUTION_DATA_SEPARATOR + task_data

    assert snapshot.sources[0].normalized_component_bytes == component
    assert snapshot.sources[0].normalized_byte_length == len(normalized)
    assert snapshot.task_data_bytes == task_data
    assert snapshot.assembled_execution_bytes == execution
    assert snapshot.assembled_execution_sha256 == sha256_digest(execution)
    assert snapshot.sources[0].decode_newline_contract_version == (
        DECODE_NEWLINE_CONTRACT_VERSION
    )


@pytest.mark.parametrize("inline_input", [None, ""])
def test_absent_inline_and_no_sources_have_the_exact_empty_representation(
    inline_input: str | None,
) -> None:
    snapshot = _build(prompt="", sources=(), inline_input=inline_input)

    assert snapshot.instruction_bytes == b""
    assert snapshot.inline_input_present is False
    assert snapshot.inline_input_bytes == b""
    assert snapshot.task_data_bytes == b""
    assert snapshot.assembled_execution_bytes == EXECUTION_DATA_SEPARATOR
    assert snapshot.to_decision_binding().inline_input_posture == "absent"


def test_empty_file_still_contributes_its_verbatim_header() -> None:
    snapshot = _build(sources=(_source("empty.txt", b""),))

    assert snapshot.task_data_bytes == b"\n--- empty.txt ---\n"


def test_inline_input_is_concatenated_without_a_separator() -> None:
    snapshot = _build(
        sources=(_source("a.txt", b"no-final-newline"),),
        inline_input="INLINE",
    )

    assert snapshot.task_data_bytes.endswith(b"no-final-newlineINLINE")
    assert b"no-final-newline\nINLINE" not in snapshot.task_data_bytes


def test_order_duplicates_and_path_spelling_are_execution_significant() -> None:
    first = _source(r".\same.txt", b"A")
    second = _source("same.txt", b"A")
    duplicate = _build(sources=(first, first, second))
    reordered = _build(sources=(second, first, first))

    expected = (
        b"\n--- .\\same.txt ---\nA"
        b"\n--- .\\same.txt ---\nA"
        b"\n--- same.txt ---\nA"
    )
    assert duplicate.task_data_bytes == expected
    assert [source.position for source in duplicate.sources] == [0, 1, 2]
    assert duplicate.sources[0].component_sha256 == duplicate.sources[1].component_sha256
    assert duplicate.sources[0].locator_sha256 != duplicate.sources[2].locator_sha256
    assert duplicate.assembled_execution_bytes != reordered.assembled_execution_bytes
    assert (
        duplicate.to_decision_binding().assembled_execution.sha256
        != reordered.to_decision_binding().assembled_execution.sha256
    )


def test_planning_only_representation_is_not_execution_bytes() -> None:
    snapshot = _build(prompt="P", sources=(), inline_input="D")

    assert snapshot.assembled_execution_bytes == b"P\n\nDATA:\nD"
    assert snapshot.assembled_execution_bytes != b"P\nD"


def test_strict_utf8_decode_failure_returns_no_snapshot() -> None:
    with pytest.raises(SnapshotValidationError, match="strict UTF-8"):
        _build(sources=(_source("bad.txt", b"\xff"),))


def test_source_read_captures_once_and_build_never_reopens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "captured.txt"
    source_path.write_bytes(b"captured\r\nvalue")
    captured = SourceBytesInput.read(source_path, max_bytes=64)
    source_path.write_bytes(b"changed")

    def forbidden_open(*args: object, **kwargs: object) -> object:
        raise AssertionError("snapshot construction reopened a source")

    monkeypatch.setattr(builtins, "open", forbidden_open)
    snapshot = _build(sources=(captured,))

    assert snapshot.task_data_bytes.endswith(b"captured\nvalue")


def test_source_read_and_byte_capture_fail_at_the_finite_boundary(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bounded.bin"
    path.write_bytes(b"123")

    assert SourceBytesInput.read(path, max_bytes=3).source_bytes == b"123"
    with pytest.raises(SnapshotLimitError):
        SourceBytesInput.read(path, max_bytes=2)
    assert SourceBytesInput.from_bytes("p", b"123", max_bytes=3).source_bytes == b"123"
    with pytest.raises(SnapshotLimitError):
        SourceBytesInput.from_bytes("p", b"123", max_bytes=2)


@pytest.mark.parametrize("invalid", [None, 0, -1, True, float("inf")])
def test_every_mandatory_limit_is_a_positive_finite_integer(
    invalid: object,
) -> None:
    with pytest.raises(SnapshotLimitError):
        _limits(max_instruction_bytes=invalid)


def test_limits_reject_unsupported_and_internally_inconsistent_values() -> None:
    with pytest.raises(SnapshotLimitError):
        _limits(contract_version="other")
    with pytest.raises(SnapshotLimitError):
        _limits(max_source_bytes_per_source=10, max_total_source_bytes=9)
    with pytest.raises(SnapshotLimitError):
        _limits(
            max_normalized_component_bytes_per_source=10,
            max_total_normalized_component_bytes=9,
        )
    with pytest.raises(SnapshotLimitError):
        _limits(max_assembled_execution_bytes=len(EXECUTION_DATA_SEPARATOR) - 1)
    with pytest.raises(SnapshotLimitError):
        _limits(max_retained_source_bytes_per_source=10)
    with pytest.raises(SnapshotLimitError):
        _limits(
            max_retained_source_bytes_per_source=10,
            max_total_retained_source_bytes=9,
        )


def test_explicit_limits_are_mandatory() -> None:
    profile = _profile()
    declarations = normalize_operator_declarations(
        task_id=None,
        declared_privacy="local_only",
        cloud_intent=False,
        resolved_profile=profile,
    )
    with pytest.raises(SnapshotLimitError, match="explicit finite"):
        build_governed_run_input_snapshot(
            prompt="p",
            sources=(),
            inline_input=None,
            declarations=declarations,
            resolved_profile=profile,
            worker_system_message=WorkerSystemMessageBinding(
                "worker_system.v1", sha256_digest(b"system")
            ),
            limits=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value", "fits"),
    [
        ("instruction", "é", 2),
        ("inline", "é", 2),
    ],
)
def test_instruction_and_inline_utf8_bounds_are_inclusive(
    field: str,
    value: str,
    fits: int,
) -> None:
    kwargs = {"prompt": "", "inline_input": None}
    kwargs["prompt" if field == "instruction" else "inline_input"] = value
    limit_name = (
        "max_instruction_bytes"
        if field == "instruction"
        else "max_inline_input_bytes"
    )

    _build(**kwargs, limits=_limits(**{limit_name: fits}))
    with pytest.raises(SnapshotLimitError):
        _build(**kwargs, limits=_limits(**{limit_name: fits - 1}))


def test_raw_source_per_source_and_aggregate_bounds() -> None:
    source = _source("a", b"12")
    _build(
        sources=(source,),
        limits=_limits(max_source_bytes_per_source=2, max_total_source_bytes=2),
    )
    with pytest.raises(SnapshotLimitError):
        _build(
            sources=(source,),
            limits=_limits(max_source_bytes_per_source=1, max_total_source_bytes=2),
        )
    with pytest.raises(SnapshotLimitError):
        _build(
            sources=(source, _source("b", b"34")),
            limits=_limits(max_source_bytes_per_source=2, max_total_source_bytes=3),
        )


def test_component_and_component_aggregate_bounds_are_preallocation_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source("p", b"x")
    component_length = len(b"\n--- p ---\nx")
    exact = _limits(
        max_normalized_component_bytes_per_source=component_length,
        max_total_normalized_component_bytes=component_length,
    )
    _build(sources=(source,), limits=exact)

    called = False

    def forbidden_materialization(*args: object, **kwargs: object) -> bytes:
        nonlocal called
        called = True
        raise AssertionError("component materialized before its bound passed")

    monkeypatch.setattr(
        snapshot_module, "_materialize_component", forbidden_materialization
    )
    with pytest.raises(SnapshotLimitError):
        _build(
            sources=(source,),
            limits=_limits(
                max_normalized_component_bytes_per_source=component_length - 1,
                max_total_normalized_component_bytes=component_length - 1,
            ),
        )
    assert called is False


def test_total_component_task_and_execution_bounds() -> None:
    first = _source("a", b"x")
    second = _source("b", b"y")
    each = len(b"\n--- a ---\nx")
    task = each * 2 + 1
    execution = len(b"P") + len(EXECUTION_DATA_SEPARATOR) + task

    _build(
        prompt="P",
        sources=(first, second),
        inline_input="z",
        limits=_limits(
            max_normalized_component_bytes_per_source=each,
            max_total_normalized_component_bytes=each * 2,
            max_task_data_bytes=task,
            max_assembled_execution_bytes=execution,
        ),
    )
    with pytest.raises(SnapshotLimitError):
        _build(
            prompt="P",
            sources=(first, second),
            inline_input="z",
            limits=_limits(
                max_normalized_component_bytes_per_source=each,
                max_total_normalized_component_bytes=(each * 2) - 1,
            ),
        )
    with pytest.raises(SnapshotLimitError):
        _build(
            prompt="P",
            sources=(first, second),
            inline_input="z",
            limits=_limits(
                max_normalized_component_bytes_per_source=each,
                max_total_normalized_component_bytes=each * 2,
                max_task_data_bytes=task - 1,
            ),
        )
    with pytest.raises(SnapshotLimitError):
        _build(
            prompt="P",
            sources=(first, second),
            inline_input="z",
            limits=_limits(
                max_normalized_component_bytes_per_source=each,
                max_total_normalized_component_bytes=each * 2,
                max_task_data_bytes=task,
                max_assembled_execution_bytes=execution - 1,
            ),
        )


def test_execution_bound_fails_before_component_or_aggregate_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source("p", b"x")

    def forbidden(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("full-size representation allocated before final sizing")

    monkeypatch.setattr(snapshot_module, "_materialize_component", forbidden)
    monkeypatch.setattr(snapshot_module, "_assemble_bytes", forbidden)
    with pytest.raises(SnapshotLimitError, match="assembled execution"):
        _build(
            prompt="P",
            sources=(source,),
            limits=_limits(max_assembled_execution_bytes=8),
        )


def test_checked_length_arithmetic_rejects_overflow() -> None:
    with pytest.raises(SnapshotLimitError, match="overflow"):
        snapshot_module._checked_add(
            snapshot_module._MAX_CHECKED_LENGTH,
            1,
            snapshot_module._MAX_CHECKED_LENGTH,
            "test",
        )


def test_raw_source_retention_is_separately_and_finitely_bounded() -> None:
    source = _source("p", b"raw")
    without_retention = _build(sources=(source,))
    assert without_retention.sources[0].source_bytes is None
    assert without_retention.sources[0].source_sha256 == sha256_digest(b"raw")

    with pytest.raises(SnapshotLimitError, match="retention requires"):
        _build(sources=(source,), retain_source_bytes=True)

    retained = _build(
        sources=(source,),
        retain_source_bytes=True,
        limits=_limits(
            max_retained_source_bytes_per_source=3,
            max_total_retained_source_bytes=3,
        ),
    )
    assert retained.sources[0].source_bytes == b"raw"

    with pytest.raises(SnapshotLimitError):
        _build(
            sources=(source,),
            retain_source_bytes=True,
            limits=_limits(
                max_retained_source_bytes_per_source=2,
                max_total_retained_source_bytes=3,
            ),
        )


def test_total_raw_retention_bound_preserves_duplicate_semantics() -> None:
    source = _source("p", b"12")
    with pytest.raises(SnapshotLimitError):
        _build(
            sources=(source, source),
            retain_source_bytes=True,
            limits=_limits(
                max_retained_source_bytes_per_source=2,
                max_total_retained_source_bytes=3,
            ),
        )


def test_advisory_profile_budget_never_becomes_a_byte_rejection_rule() -> None:
    tiny_advisory_profile = _profile(
        context_window_tokens=3,
        reserved_output_tokens=1,
        safety_margin_tokens=1,
    )
    snapshot = _build(
        prompt="many bytes remain allowed",
        inline_input="despite one usable token",
        profile=tiny_advisory_profile,
    )

    assert snapshot.resolved_profile.usable_input_tokens == 1
    assert len(snapshot.assembled_execution_bytes) > 1


def test_mutable_buffers_lists_and_path_objects_are_not_retained() -> None:
    class MutablePath:
        def __init__(self) -> None:
            self.value = r".\before.txt"
            self.calls = 0

        def __fspath__(self) -> str:
            self.calls += 1
            return self.value

    path = MutablePath()
    raw = bytearray(b"before")
    source = _source(path, raw)
    raw[:] = b"after!"
    path.value = r".\after.txt"
    source_list = [source]
    snapshot = _build(sources=source_list)
    source_list.clear()

    assert path.calls == 1
    assert snapshot.sources[0].path_spelling == r".\before.txt"
    assert snapshot.sources[0].source_sha256 == sha256_digest(b"before")
    assert snapshot.task_data_bytes.endswith(b"before")
    assert len(snapshot.sources) == 1


def test_snapshot_records_and_returned_collections_are_frozen() -> None:
    snapshot = _build(sources=(_source("p", b"x"),))
    binding = snapshot.to_decision_binding()

    assert type(snapshot.sources) is tuple
    assert type(binding.sources) is tuple
    with pytest.raises(FrozenInstanceError):
        snapshot.inline_input_present = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.sources[0].position = 9  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        binding.sources = ()  # type: ignore[misc]


def test_digest_and_assembly_mismatches_fail_closed() -> None:
    snapshot = _build(sources=(_source("p", b"x"),), inline_input="i")

    with pytest.raises(SnapshotValidationError, match="digest/length"):
        replace(snapshot, task_data_sha256=sha256_digest(b"different"))
    with pytest.raises(SnapshotValidationError, match="assembled execution bytes"):
        altered = snapshot.assembled_execution_bytes[:-1] + b"!"
        replace(
            snapshot,
            assembled_execution_bytes=altered,
            assembled_execution_sha256=sha256_digest(altered),
        )
    with pytest.raises(SnapshotValidationError, match="locator digest"):
        replace(snapshot.sources[0], path_spelling="other")


def test_decision_binding_is_privacy_safe_and_matches_decision_api_shape() -> None:
    prompt = "PROMPT-SHALL-NOT-PERSIST"
    path = r"C:\secret\CLIENT-CODENAME.txt"
    content = b"SENSITIVE-MARKER api_key=secret-value"
    inline = "INLINE-SECRET"
    snapshot = _build(
        prompt=prompt,
        sources=(_source(path, content),),
        inline_input=inline,
    )
    binding = snapshot.to_decision_binding()
    rendered = repr(binding).encode("utf-8")

    assert binding.snapshot_contract_version == SNAPSHOT_CONTRACT_VERSION
    assert binding.assembly_contract_version == ASSEMBLY_CONTRACT_VERSION
    assert binding.profile_resolution_version == PROFILE_RESOLUTION_VERSION
    assert binding.instruction.sha256 == sha256_digest(prompt.encode())
    assert binding.task_data.sha256 == snapshot.task_data_sha256
    assert binding.assembled_execution.sha256 == snapshot.assembled_execution_sha256
    assert binding.sources[0].source_sha256 == sha256_digest(content)
    for forbidden in (
        prompt.encode(),
        path.encode(),
        b"CLIENT-CODENAME.txt",
        content,
        inline.encode(),
    ):
        assert forbidden not in rendered
        assert base64.b64encode(forbidden) not in rendered


def test_profile_resolution_is_explicit_deterministic_and_owns_its_result() -> None:
    profile = _profile("canonical")
    profiles = {"ordinary": profile, "alias": profile}

    defaulted = resolve_context_model_profile(
        None,
        default_profile="ordinary",
        profiles=profiles,
    )
    explicit = resolve_context_model_profile(
        "alias",
        default_profile="ordinary",
        profiles=profiles,
    )
    profiles.clear()

    assert defaulted == explicit == profile
    assert defaulted is not profile
    assert defaulted.resolution_version == PROFILE_RESOLUTION_VERSION


def test_profile_resolution_rejects_unknown_and_ambiguous_configuration() -> None:
    profile = _profile("canonical")
    with pytest.raises(SnapshotValidationError, match="unknown default"):
        resolve_context_model_profile(
            "alias",
            default_profile="missing",
            profiles={"alias": profile},
        )
    with pytest.raises(SnapshotValidationError, match="unknown context"):
        resolve_context_model_profile(
            "missing",
            default_profile="ordinary",
            profiles={"ordinary": profile},
        )
    with pytest.raises(SnapshotValidationError, match="ambiguous"):
        resolve_context_model_profile(
            None,
            default_profile="one",
            profiles={
                "one": profile,
                "two": _profile("canonical", context_window_tokens=8_192),
            },
        )


def test_normalized_declarations_are_closed_and_decision_compatible() -> None:
    profile = _profile()
    explicit = normalize_operator_declarations(
        task_id="Task-α.1",
        declared_privacy="external_safe",
        cloud_intent=True,
        resolved_profile=profile,
    )
    implicit = normalize_operator_declarations(
        task_id=None,
        declared_privacy="local_only",
        cloud_intent=False,
        resolved_profile=profile,
    )

    assert explicit.task_id_posture == "explicit"
    assert explicit.task_id == "Task-α.1"
    assert implicit.task_id_posture == "implicit_unassigned"
    with pytest.raises(SnapshotValidationError):
        normalize_operator_declarations(
            task_id="contains spaces",
            declared_privacy="local_only",
            cloud_intent=False,
            resolved_profile=profile,
        )


def test_build_and_profile_resolution_use_no_ambient_or_reopened_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    captured = _source("already-captured", b"value")

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("ambient dependency accessed")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(snapshot_module.os, "fspath", forbidden)
    monkeypatch.setattr(snapshot_module.os, "getenv", forbidden)

    resolved = resolve_context_model_profile(
        None,
        default_profile="ordinary",
        profiles={"ordinary": profile},
    )
    snapshot = _build(sources=(captured,), profile=resolved)

    assert snapshot.sources[0].source_sha256 == sha256_digest(b"value")
    assert snapshot.resolved_profile == profile


def test_contract_versions_and_limit_binding_are_explicit() -> None:
    limits = _limits()
    snapshot = _build(limits=limits)
    binding = snapshot.to_decision_binding()

    assert limits.contract_version == CONSTRUCTION_LIMITS_VERSION
    assert binding.construction_limits_sha256 == limits.sha256
    assert binding.worker_system_message_version == "worker_system.v1"
    assert binding.worker_system_message_sha256 == sha256_digest(
        b"fixed system message"
    )


def test_snapshot_binding_is_consumed_by_the_governed_decision_builder() -> None:
    snapshot = _build(
        prompt="bounded prompt",
        sources=(_source("input.txt", b"bounded content"),),
        inline_input="inline",
    )
    configuration = DecisionPolicyConfiguration(
        configuration_version=CONFIGURATION_VERSION,
        configuration_sha256=sha256_digest(b"explicit configuration"),
        policy_version=POLICY_VERSION,
        classification_policy_version=CLASSIFICATION_POLICY_VERSION,
        route_policy_version=ROUTE_POLICY_VERSION,
        verification_policy_version=VERIFICATION_POLICY_VERSION,
        estimated_input_tokens=32,
        usable_input_tokens=snapshot.resolved_profile.usable_input_tokens,
        privacy_preflight="passed",
        classification="docs_update",
        risk_posture="low",
        classification_reason_codes=("deterministic_classifier_match",),
        preferred_logical_route="local_fast",
        permitted_fallback_envelope=("local_heavy", "human_handoff"),
        route_reason_codes=("policy_selected",),
        terminal_escalation="none",
        ethical_firewall="clear",
        human_review="not_required",
        escalation_conditions=("route_unavailable_at_execution",),
        required_checks=(
            "packet_verification",
            "privacy_preflight",
            "decision_identity_verification",
        ),
    )

    decision = build_governed_decision(snapshot, configuration)

    assert verify_governed_decision_id(decision)
    assert (
        decision.snapshot_binding.assembled_execution.sha256
        == snapshot.assembled_execution_sha256
    )
