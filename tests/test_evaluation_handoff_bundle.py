import hashlib
import json
from pathlib import Path

import pytest

from triage_core.evaluation_handoff_bundle import (
    EvaluationHandoffBundleError,
    build_evaluation_handoff_bundle,
)


def _fixture_case(case_id="privacy-deny-001", **overrides):
    case = {
        "schema_version": "eval_case_v0",
        "case_id": case_id,
        "boundary_family": "privacy",
        "title": "Privacy boundary",
        "description": "A persistent artifact boundary case.",
        "task_packet": {
            "summary": "Process a local record.",
            "declared_risk": "high",
            "relevant_metadata": {"privacy_mode": "local_only"},
        },
        "policy_expectation": {
            "boundary_rule": "Private material must remain local.",
            "reason": "Persistent artifacts require privacy review.",
        },
        "simulated_behavior": {
            "actor_type": "review_bundle",
            "proposed_action": "Write a redacted result.",
            "notable_conditions": ["persistent artifact"],
        },
        "expected_control_plane_decision": "deny",
        "expected_audit_outcome": {
            "required_artifacts": ["denial evidence"],
            "forbidden_artifacts": ["raw material"],
            "notes": "Retain only privacy-safe evidence.",
        },
        "expected_eval_outcome": "pass",
    }
    case.update(overrides)
    return case


def _actual(case_id, **overrides):
    outcome = {
        "case_id": case_id,
        "decision": "block",
        "boundary_family": "privacy",
        "reasons": ["privacy_boundary"],
        "audit_required": True,
        "human_approval_required": False,
    }
    outcome.update(overrides)
    return outcome


def _write_inputs(tmp_path, case_ids=("privacy-deny-001",), actual_order=None):
    fixture_path = tmp_path / "source.jsonl"
    fixture_bytes = (
        "\n".join(
            json.dumps(_fixture_case(case_id), sort_keys=True) for case_id in case_ids
        )
        + "\n"
    ).encode()
    fixture_path.write_bytes(fixture_bytes)
    actuals_dir = tmp_path / "actuals-source"
    actuals_dir.mkdir()
    actual_bytes = {}
    for case_id in actual_order or case_ids:
        content = (
            json.dumps(_actual(case_id), sort_keys=False, indent=1) + "\n"
        ).encode()
        (actuals_dir / f"{case_id}.json").write_bytes(content)
        actual_bytes[case_id] = content
    return fixture_path, fixture_bytes, actuals_dir, actual_bytes


def _assert_reason(reason, action):
    with pytest.raises(EvaluationHandoffBundleError) as exc_info:
        action()
    assert exc_info.value.reason == reason


def test_build_bundle_is_deterministic_and_copies_inputs_byte_for_byte(tmp_path):
    fixture, fixture_bytes, actuals, actual_bytes = _write_inputs(
        tmp_path,
        case_ids=("routing-002", "privacy-001"),
        actual_order=("privacy-001", "routing-002"),
    )
    first = tmp_path / "bundle-one"
    second = tmp_path / "bundle-two"

    result = build_evaluation_handoff_bundle(fixture, actuals, first)
    build_evaluation_handoff_bundle(fixture, actuals, second)

    assert result.fixture_count == 2
    assert result.actual_count == 2
    assert sorted(
        path.relative_to(first).as_posix()
        for path in first.rglob("*")
        if path.is_file()
    ) == [
        "actuals/privacy-001.json",
        "actuals/routing-002.json",
        "fixtures/safety_boundaries_v0.jsonl",
        "manifest/evaluation_handoff_manifest.json",
    ]
    assert (first / "fixtures/safety_boundaries_v0.jsonl").read_bytes() == fixture_bytes
    for case_id, content in actual_bytes.items():
        assert (first / "actuals" / f"{case_id}.json").read_bytes() == content

    first_manifest_bytes = (
        first / "manifest/evaluation_handoff_manifest.json"
    ).read_bytes()
    assert first_manifest_bytes == (
        second / "manifest/evaluation_handoff_manifest.json"
    ).read_bytes()
    manifest = json.loads(first_manifest_bytes)
    assert manifest["schema_version"] == "evaluation_handoff_manifest.v0"
    assert manifest["bundle_type"] == "evaluation_handoff"
    assert manifest["handoff_contract"] == "evaluation_handoff_contract.v0"
    assert manifest["scoring_owner"] == "external_evaluator"
    assert manifest["triagecore_scored"] is False
    assert manifest["fixture"] == {
        "contract_identifier": "eval_case_v0",
        "path": "fixtures/safety_boundaries_v0.jsonl",
        "sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "case_count": 2,
    }
    assert [entry["case_id"] for entry in manifest["actuals"]["entries"]] == [
        "privacy-001",
        "routing-002",
    ]
    assert "generated_at" not in manifest
    assert "score" not in manifest
    assert "verdict" not in manifest


def test_manifest_order_is_independent_of_actual_file_creation_order(tmp_path):
    first_root = tmp_path / "first-input"
    second_root = tmp_path / "second-input"
    first_root.mkdir()
    second_root.mkdir()
    case_ids = ("privacy-001", "routing-002")
    first_fixture, _, first_actuals, _ = _write_inputs(
        first_root,
        case_ids=case_ids,
        actual_order=case_ids,
    )
    second_fixture, _, second_actuals, _ = _write_inputs(
        second_root,
        case_ids=case_ids,
        actual_order=tuple(reversed(case_ids)),
    )

    first_output = tmp_path / "first-bundle"
    second_output = tmp_path / "second-bundle"
    build_evaluation_handoff_bundle(first_fixture, first_actuals, first_output)
    build_evaluation_handoff_bundle(second_fixture, second_actuals, second_output)

    assert (
        first_output / "manifest/evaluation_handoff_manifest.json"
    ).read_bytes() == (
        second_output / "manifest/evaluation_handoff_manifest.json"
    ).read_bytes()


def test_missing_actuals_for_fixture_cases_are_allowed(tmp_path):
    fixture, _, actuals, _ = _write_inputs(
        tmp_path,
        case_ids=("privacy-001", "routing-002"),
        actual_order=("privacy-001",),
    )

    result = build_evaluation_handoff_bundle(
        fixture,
        actuals,
        tmp_path / "bundle",
    )

    assert result.fixture_count == 2
    assert result.actual_count == 1


@pytest.mark.parametrize(
    ("reason", "mutate"),
    [
        ("input_missing", lambda fixture, actuals, tmp: fixture.unlink()),
        ("input_not_regular_file", lambda fixture, actuals, tmp: fixture.unlink() or fixture.mkdir()),
        ("actuals_directory_missing", lambda fixture, actuals, tmp: actuals.rename(tmp / "gone")),
        ("actuals_empty", lambda fixture, actuals, tmp: next(actuals.iterdir()).unlink()),
        (
            "unexpected_actuals_entry",
            lambda fixture, actuals, tmp: (actuals / "nested").mkdir(),
        ),
        (
            "actual_invalid_json",
            lambda fixture, actuals, tmp: next(actuals.iterdir()).write_text("{"),
        ),
        (
            "actual_invalid_contract",
            lambda fixture, actuals, tmp: next(actuals.iterdir()).write_text("{}"),
        ),
        (
            "output_exists",
            lambda fixture, actuals, tmp: (tmp / "bundle").mkdir(),
        ),
    ],
)
def test_fail_closed_reasons_leave_no_partial_output(tmp_path, reason, mutate):
    fixture, _, actuals, _ = _write_inputs(tmp_path)
    mutate(fixture, actuals, tmp_path)
    output = tmp_path / "bundle"

    _assert_reason(
        reason,
        lambda: build_evaluation_handoff_bundle(fixture, actuals, output),
    )

    if reason != "output_exists":
        assert not output.exists()


def test_contract_identity_failures_are_closed(tmp_path):
    fixture, _, actuals, _ = _write_inputs(tmp_path)
    source = next(actuals.iterdir())

    source.write_text(json.dumps(_actual("../unsafe")), encoding="utf-8")
    _assert_reason(
        "unsafe_case_id",
        lambda: build_evaluation_handoff_bundle(
            fixture, actuals, tmp_path / "unsafe-output"
        ),
    )

    source.write_text(json.dumps(_actual("privacy-deny-001")), encoding="utf-8")
    source.rename(actuals / "wrong.json")
    _assert_reason(
        "actual_filename_mismatch",
        lambda: build_evaluation_handoff_bundle(
            fixture, actuals, tmp_path / "mismatch-output"
        ),
    )

    (actuals / "wrong.json").write_text(
        json.dumps(_actual("unknown-001")), encoding="utf-8"
    )
    (actuals / "wrong.json").rename(actuals / "unknown-001.json")
    _assert_reason(
        "unknown_case_id",
        lambda: build_evaluation_handoff_bundle(
            fixture, actuals, tmp_path / "unknown-output"
        ),
    )


def test_unsafe_fixture_case_id_is_rejected_even_without_a_matching_actual(tmp_path):
    fixture, _, actuals, _ = _write_inputs(
        tmp_path,
        case_ids=("privacy-deny-001", "../unsafe"),
        actual_order=("privacy-deny-001",),
    )

    _assert_reason(
        "unsafe_case_id",
        lambda: build_evaluation_handoff_bundle(
            fixture, actuals, tmp_path / "bundle"
        ),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("case_id", 7),
        ("decision", False),
        ("boundary_family", []),
        ("reasons", "not-a-list"),
        ("audit_required", "true"),
        ("human_approval_required", 0),
    ],
)
def test_actual_required_field_types_fail_closed(tmp_path, field, value):
    fixture, _, actuals, _ = _write_inputs(tmp_path)
    source = next(actuals.iterdir())
    payload = _actual("privacy-deny-001")
    payload[field] = value
    source.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    _assert_reason(
        "actual_invalid_contract",
        lambda: build_evaluation_handoff_bundle(
            fixture,
            actuals,
            tmp_path / "bundle",
        ),
    )


def test_invalid_fixture_fails_closed_without_output(tmp_path):
    fixture, _, actuals, _ = _write_inputs(tmp_path)
    fixture.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "bundle"

    _assert_reason(
        "fixture_invalid",
        lambda: build_evaluation_handoff_bundle(fixture, actuals, output),
    )
    assert not output.exists()


def test_duplicate_case_id_is_rejected(tmp_path):
    fixture, _, actuals, _ = _write_inputs(tmp_path)
    (actuals / "second.json").write_text(
        json.dumps(_actual("privacy-deny-001")),
        encoding="utf-8",
    )

    _assert_reason(
        "duplicate_case_id",
        lambda: build_evaluation_handoff_bundle(
            fixture, actuals, tmp_path / "bundle"
        ),
    )


def test_privacy_failure_and_write_failure_leave_no_bundle(tmp_path, monkeypatch):
    fixture, _, actuals, _ = _write_inputs(tmp_path)
    source = next(actuals.iterdir())
    source.write_text(
        json.dumps(_actual("privacy-deny-001", raw_content="123-45-6789")),
        encoding="utf-8",
    )
    output = tmp_path / "privacy-output"
    _assert_reason(
        "privacy_invariant_failed",
        lambda: build_evaluation_handoff_bundle(fixture, actuals, output),
    )
    assert not output.exists()

    source.write_text(json.dumps(_actual("privacy-deny-001")), encoding="utf-8")

    def fail_rename(self, target):
        raise OSError("simulated")

    monkeypatch.setattr(Path, "rename", fail_rename)
    output = tmp_path / "write-output"
    _assert_reason(
        "write_failed",
        lambda: build_evaluation_handoff_bundle(fixture, actuals, output),
    )
    assert not output.exists()
    assert not list(tmp_path.glob(".write-output.*"))


def test_output_parent_and_path_conflicts_fail_closed(tmp_path):
    fixture, _, actuals, _ = _write_inputs(tmp_path)
    _assert_reason(
        "output_parent_missing",
        lambda: build_evaluation_handoff_bundle(
            fixture, actuals, tmp_path / "missing" / "bundle"
        ),
    )
    _assert_reason(
        "path_conflict",
        lambda: build_evaluation_handoff_bundle(
            fixture, actuals, actuals / "bundle"
        ),
    )
