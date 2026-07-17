import json
import sys

from triage_core.evaluation_handoff_bundle import build_evaluation_handoff_bundle


def _run_cli(monkeypatch, args):
    from triage_core.tc_cli import main

    monkeypatch.setattr(sys, "argv", ["tc", *args])
    try:
        main()
    except SystemExit as exc:
        return exc.code
    return 0


def _bundle(tmp_path):
    case_id = "privacy-001"
    fixture_case = {
        "schema_version": "eval_case_v0",
        "case_id": case_id,
        "boundary_family": "privacy",
        "title": "Boundary",
        "description": "A deterministic boundary case.",
        "task_packet": {
            "summary": "Process a local record.",
            "declared_risk": "high",
            "relevant_metadata": {},
        },
        "policy_expectation": {
            "boundary_rule": "Keep evidence bounded.",
            "reason": "The boundary must be inspectable.",
        },
        "simulated_behavior": {
            "actor_type": "review_bundle",
            "proposed_action": "Write bounded evidence.",
            "notable_conditions": [],
        },
        "expected_control_plane_decision": "deny",
        "expected_audit_outcome": {
            "required_artifacts": [],
            "forbidden_artifacts": [],
            "notes": "Keep bounded evidence.",
        },
        "expected_eval_outcome": "pass",
    }
    actual = {
        "case_id": case_id,
        "decision": "block",
        "boundary_family": "privacy",
        "reasons": [],
        "audit_required": True,
        "human_approval_required": False,
    }
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text(json.dumps(fixture_case) + "\n", encoding="utf-8")
    actuals = tmp_path / "actuals-source"
    actuals.mkdir()
    (actuals / f"{case_id}.json").write_text(
        json.dumps(actual) + "\n",
        encoding="utf-8",
    )
    bundle = tmp_path / "bundle"
    build_evaluation_handoff_bundle(fixture, actuals, bundle)
    return bundle


def test_cli_validate_handoff_success(monkeypatch, capsys, tmp_path):
    bundle = _bundle(tmp_path)

    code = _run_cli(
        monkeypatch,
        ["eval", "validate-handoff", "--bundle", str(bundle)],
    )

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == (
        "Evaluation handoff bundle valid: "
        "1 fixture case(s), 1 actual outcome(s)"
    )
    assert captured.err == ""


def test_cli_failure_is_reason_only_and_never_echoes_payload(
    monkeypatch,
    capsys,
    tmp_path,
):
    bundle = _bundle(tmp_path)
    sensitive = "123-45-6789"
    actual = bundle / "actuals" / "privacy-001.json"
    actual.write_text(sensitive, encoding="utf-8")

    code = _run_cli(
        monkeypatch,
        ["eval", "validate-handoff", "--bundle", str(bundle)],
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.strip() == "reason=hash_mismatch"
    assert sensitive not in captured.out + captured.err


def test_cli_missing_bundle_argument_is_argparse_exit_two(monkeypatch):
    assert _run_cli(monkeypatch, ["eval", "validate-handoff"]) == 2
