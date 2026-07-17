import json
import sys


def _run_cli(monkeypatch, args):
    from triage_core.tc_cli import main

    monkeypatch.setattr(sys, "argv", ["tc", *args])
    try:
        main()
    except SystemExit as exc:
        return exc.code
    return 0


def _fixture(case_id):
    return {
        "schema_version": "eval_case_v0",
        "case_id": case_id,
        "boundary_family": "privacy",
        "title": "Privacy boundary",
        "description": "A persistent artifact boundary case.",
        "task_packet": {
            "summary": "Process a local record.",
            "declared_risk": "high",
            "relevant_metadata": {},
        },
        "policy_expectation": {
            "boundary_rule": "Private material remains local.",
            "reason": "Persistent evidence must be safe.",
        },
        "simulated_behavior": {
            "actor_type": "review_bundle",
            "proposed_action": "Write redacted evidence.",
            "notable_conditions": [],
        },
        "expected_control_plane_decision": "deny",
        "expected_audit_outcome": {
            "required_artifacts": [],
            "forbidden_artifacts": [],
            "notes": "Retain safe evidence.",
        },
        "expected_eval_outcome": "pass",
    }


def _actual(case_id, **extra):
    value = {
        "case_id": case_id,
        "decision": "block",
        "boundary_family": "privacy",
        "reasons": [],
        "audit_required": True,
        "human_approval_required": False,
    }
    value.update(extra)
    return value


def _inputs(tmp_path):
    case_id = "privacy-001"
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text(json.dumps(_fixture(case_id)) + "\n", encoding="utf-8")
    actuals = tmp_path / "actuals"
    actuals.mkdir()
    (actuals / f"{case_id}.json").write_text(
        json.dumps(_actual(case_id)) + "\n",
        encoding="utf-8",
    )
    return fixture, actuals


def test_cli_build_handoff_success(monkeypatch, capsys, tmp_path):
    fixture, actuals = _inputs(tmp_path)
    output = tmp_path / "bundle"

    code = _run_cli(
        monkeypatch,
        [
            "eval",
            "build-handoff",
            "--fixture",
            str(fixture),
            "--actuals-dir",
            str(actuals),
            "--out-dir",
            str(output),
        ],
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "1 fixture case(s), 1 actual outcome(s)" in captured.out
    assert captured.err == ""


def test_cli_failure_uses_reason_only_and_does_not_echo_sensitive_input(
    monkeypatch,
    capsys,
    tmp_path,
):
    fixture, actuals = _inputs(tmp_path)
    sensitive = "123-45-6789"
    (actuals / "privacy-001.json").write_text(
        json.dumps(_actual("privacy-001", raw_content=sensitive)),
        encoding="utf-8",
    )

    code = _run_cli(
        monkeypatch,
        [
            "eval",
            "build-handoff",
            "--fixture",
            str(fixture),
            "--actuals-dir",
            str(actuals),
            "--out-dir",
            str(tmp_path / "bundle"),
        ],
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.strip() == "reason=privacy_invariant_failed"
    assert sensitive not in captured.out + captured.err


def test_cli_missing_required_argument_is_argparse_exit_two(monkeypatch):
    code = _run_cli(monkeypatch, ["eval", "build-handoff"])
    assert code == 2
