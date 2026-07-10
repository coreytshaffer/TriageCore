import json
import sys


def run_cli(monkeypatch, args):
    from triage_core.tc_cli import main

    monkeypatch.setattr(sys, "argv", ["tc", *args])
    try:
        main()
    except SystemExit as exc:
        return exc.code
    return 0


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


def write_jsonl(path, *cases):
    path.write_text(
        "\n".join(json.dumps(case, sort_keys=True) for case in cases),
        encoding="utf-8",
    )
    return str(path)


def test_eval_validate_fixtures_valid_file_exits_zero(monkeypatch, capsys, tmp_path):
    fixture = write_jsonl(
        tmp_path / "eval_cases.jsonl",
        _case(case_id="privacy-deny-001"),
        _case(case_id="routing-deny-001", boundary_family="routing"),
    )

    code = run_cli(monkeypatch, ["eval", "validate-fixtures", "--input", fixture])

    assert code == 0
    assert "Eval fixture validation passed: 2 case(s) checked." in capsys.readouterr().out


def test_eval_validate_fixtures_invalid_file_prints_line_diagnostics(
    monkeypatch,
    capsys,
    tmp_path,
):
    fixture_path = tmp_path / "eval_cases.jsonl"
    fixture_path.write_text(
        json.dumps(_case(case_id="duplicate-001")) + "\n"
        + json.dumps(_case(case_id="duplicate-001", boundary_family="network"))
        + "\n{not json",
        encoding="utf-8",
    )

    code = run_cli(
        monkeypatch,
        ["eval", "validate-fixtures", "--input", str(fixture_path)],
    )

    out = capsys.readouterr().out
    assert code == 1
    assert "Eval fixture validation failed" in out
    assert "reason=invalid_eval_fixture" in out
    assert "line 2: invalid boundary_family: network" in out
    assert "line 2: duplicate case_id: duplicate-001 (first seen on line 1)" in out
    assert "line 3: malformed JSON" in out


def test_eval_validate_fixtures_missing_file_fails_closed(monkeypatch, capsys, tmp_path):
    missing = tmp_path / "missing.jsonl"

    code = run_cli(monkeypatch, ["eval", "validate-fixtures", "--input", str(missing)])

    out = capsys.readouterr().out
    assert code == 1
    assert f"Error: eval fixture file not found: {missing}" in out
    assert "reason=input_not_found" in out
