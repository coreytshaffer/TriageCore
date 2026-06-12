import json

from triage_core.demo_dry_run import format_demo_dry_run, run_demo_dry_run


def test_demo_dry_run_output_includes_all_checkpoints(tmp_path):
    result = run_demo_dry_run(tmp_path, decision="pending")
    output = format_demo_dry_run(result)

    for heading in [
        "Messy Request",
        "TaskPacket Summary",
        "Privacy Check",
        "Route Decision",
        "Scoped Context",
        "Proposed Output",
        "Validation",
        "Human Decision",
        "Ledger Event",
        "Ledger Path",
    ]:
        assert heading in output


def test_demo_dry_run_writes_metadata_only_ledger_event(tmp_path):
    result = run_demo_dry_run(tmp_path, decision="pending")
    ledger_path = tmp_path / "ledger.jsonl"
    records = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(records) == 1
    record = records[0]
    payload = record["payload"]

    assert record["event_type"] == "demo_dry_run"
    assert payload["demo_mode"] == "dry_run"
    assert payload["selected_route"] == "deterministic"
    assert payload["raw_context_included"] is False
    assert payload["validation_status"] == "passed"

    for forbidden_field in [
        "prompt",
        "data",
        "content",
        "raw_prompt",
        "raw_data",
        "raw_content",
        "snippet",
    ]:
        assert forbidden_field not in payload


def test_demo_dry_run_scoped_context_excludes_raw_context(tmp_path):
    result = run_demo_dry_run(tmp_path, decision="pending")

    assert result.scoped_context["raw_context_included"] is False
    assert "raw prompt" in result.scoped_context["forbidden_scope"]
    assert "full context" in result.scoped_context["forbidden_scope"]


def test_demo_dry_run_reject_does_not_finalize(tmp_path):
    result = run_demo_dry_run(tmp_path, decision="reject")

    assert result.human_decision["decision_state"] == "rejected"
    assert result.human_decision["finalized"] is False
    assert result.ledger_event["finalized"] is False


def test_demo_dry_run_validation_failure_blocks_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "triage_core.demo_dry_run.validate_demo_output",
        lambda proposed_output: {
            "validator_name": "deterministic_demo_validator",
            "status": "failed",
            "checks": {"forced_failure": False},
            "passed": False,
        },
    )

    result = run_demo_dry_run(tmp_path, decision="approve")

    assert result.human_decision["decision_state"] == "approval_blocked"
    assert result.human_decision["finalized"] is False
    assert result.ledger_event["validation_status"] == "failed"


def test_demo_dry_run_formatter_includes_key_details(tmp_path):
    result = run_demo_dry_run(tmp_path, decision="approve")
    output = format_demo_dry_run(result)

    assert "selected_route=deterministic" in output
    assert "backend_invoked=False" in output
    assert "raw_context_included=False" in output
    assert "decision_state=approved" in output
