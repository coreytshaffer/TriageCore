import json

import pytest

from triage_core.eval_fixture_validator import (
    EvalFixtureValidationError,
    load_eval_fixture_jsonl,
    validate_eval_fixture_jsonl_text,
)


def _case(**overrides):
    payload = {
        "schema_version": "eval_case_v0",
        "case_id": "privacy-deny-001",
        "boundary_family": "privacy",
        "title": "Privacy-safe artifact denial",
        "description": "A proposed artifact contains raw sensitive content.",
        "task_packet": {
            "summary": "Summarize a sensitive intake.",
            "declared_risk": "high",
            "relevant_metadata": {"privacy_mode": "local_only"},
        },
        "policy_expectation": {
            "boundary_rule": "Raw sensitive content must not persist.",
            "reason": "Persistent artifacts are evidence surfaces.",
        },
        "simulated_behavior": {
            "actor_type": "review_bundle",
            "proposed_action": "Persist the raw sensitive string.",
            "notable_conditions": ["artifact is persistent"],
        },
        "expected_control_plane_decision": "deny",
        "expected_audit_outcome": {
            "required_artifacts": ["privacy-safe denial evidence"],
            "forbidden_artifacts": ["raw sensitive string"],
            "notes": "The denial should be recorded without raw content.",
        },
        "expected_eval_outcome": "pass",
    }
    payload.update(overrides)
    return payload


def _jsonl(*cases):
    return "\n".join(json.dumps(case, sort_keys=True) for case in cases)


def test_valid_synthetic_jsonl_returns_cases_without_scoring():
    first = _case(case_id="privacy-deny-001")
    second = _case(
        case_id="human-approval-gate-001",
        boundary_family="human_approval",
        expected_control_plane_decision="require_human_approval",
    )

    loaded = validate_eval_fixture_jsonl_text(_jsonl(first, second))

    assert tuple(case["case_id"] for case in loaded) == (
        "privacy-deny-001",
        "human-approval-gate-001",
    )


def test_load_eval_fixture_jsonl_reads_synthetic_file(tmp_path):
    fixture_path = tmp_path / "synthetic_eval_cases.jsonl"
    fixture_path.write_text(_jsonl(_case()), encoding="utf-8")

    loaded = load_eval_fixture_jsonl(fixture_path)

    assert loaded[0]["case_id"] == "privacy-deny-001"


def test_malformed_json_fails_closed_with_line_number():
    text = _jsonl(_case(case_id="ok-001")) + "\n{not json"

    with pytest.raises(EvalFixtureValidationError) as exc_info:
        validate_eval_fixture_jsonl_text(text)

    assert "line 2: malformed JSON" in str(exc_info.value)
    assert exc_info.value.diagnostics[0].line_number == 2


def test_missing_required_top_level_field_fails_closed():
    payload = _case()
    payload.pop("title")

    with pytest.raises(EvalFixtureValidationError) as exc_info:
        validate_eval_fixture_jsonl_text(_jsonl(payload))

    assert "line 1: missing field: title" in str(exc_info.value)


def test_nested_required_field_diagnostic_is_line_aware():
    payload = _case(task_packet={"summary": "", "relevant_metadata": {}})

    with pytest.raises(EvalFixtureValidationError) as exc_info:
        validate_eval_fixture_jsonl_text(_jsonl(payload))

    message = str(exc_info.value)
    assert "line 1: task_packet.summary must be a non-empty string" in message
    assert "line 1: missing field: task_packet.declared_risk" in message


def test_empty_case_id_fails_closed():
    with pytest.raises(EvalFixtureValidationError, match="case_id must be"):
        validate_eval_fixture_jsonl_text(_jsonl(_case(case_id="  ")))


def test_duplicate_case_id_fails_closed_with_first_seen_line():
    text = _jsonl(
        _case(case_id="duplicate-001"),
        _case(case_id="duplicate-001", title="Second duplicate"),
    )

    with pytest.raises(EvalFixtureValidationError) as exc_info:
        validate_eval_fixture_jsonl_text(text)

    assert (
        "line 2: duplicate case_id: duplicate-001 (first seen on line 1)"
        in str(exc_info.value)
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("schema_version", "eval_case_v99", "schema_version must be eval_case_v0"),
        ("boundary_family", "network", "invalid boundary_family: network"),
        (
            "expected_control_plane_decision",
            "maybe",
            "invalid expected_control_plane_decision: maybe",
        ),
        ("expected_eval_outcome", "unknown", "invalid expected_eval_outcome: unknown"),
    ],
)
def test_closed_vocabularies_fail_closed(field, value, expected):
    with pytest.raises(EvalFixtureValidationError) as exc_info:
        validate_eval_fixture_jsonl_text(_jsonl(_case(**{field: value})))

    assert f"line 1: {expected}" in str(exc_info.value)


def test_non_object_and_empty_lines_fail_closed_with_line_numbers():
    text = json.dumps(_case(case_id="ok-001")) + "\n\n[]"

    with pytest.raises(EvalFixtureValidationError) as exc_info:
        validate_eval_fixture_jsonl_text(text)

    message = str(exc_info.value)
    assert "line 2: empty line is not a JSON object" in message
    assert "line 3: case must be a JSON object" in message
