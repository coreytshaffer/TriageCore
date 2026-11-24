import os
import uuid
import tempfile
from types import SimpleNamespace
import pytest
from unittest.mock import patch
from triage_core.tc_cli import tc_task_show
from triage_core.task_ledger import TaskLedger

def test_existing_task_timeline_and_metadata(capsys):
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        ledger.append_event(task_id, "task_created", {
            "title": "Build UI Dashboard",
            "description": "Create new component"
        })
        ledger.append_event(task_id, "task_classified", {
            "recommended_profile": "sandbox-only",
            "risk_level": "low"
        })

        ledger_path = os.path.join(temp_dir, "ledger.jsonl")
        
        with patch("triage_core.tc_cli._ledger_path", return_value=pytest.helpers.Path(ledger_path) if hasattr(pytest, "helpers") else ledger.ledger_path):
            tc_task_show(task_id)
            
            captured = capsys.readouterr()
            
            assert f"Task ID: {task_id}" in captured.out
            assert "Title: Build UI Dashboard" in captured.out
            assert "Status: pending" in captured.out
            assert "Accepted: not_recorded" in captured.out
            assert "Review decision: not_recorded" in captured.out
            assert "Ledger events: 2" in captured.out
            assert "Timeline:" in captured.out
            assert "task_created" in captured.out
            assert "task_classified" in captured.out
            assert "Signature verification: not checked by this command; run tc audit --verify-signatures" in captured.out

def test_historical_acceptance_is_not_a_current_decision(capsys):
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        ledger.append_event(task_id, "task_created", {"title": "Test Accepted Task"})
        ledger.append_event(task_id, "review_completed", {"accepted": True, "review_decision": "accepted"})
        
        ledger_path = os.path.join(temp_dir, "ledger.jsonl")
        with patch("triage_core.tc_cli._ledger_path", return_value=ledger.ledger_path):
            tc_task_show(task_id)
            
            captured = capsys.readouterr()
            assert "Accepted: not_recorded" in captured.out
            assert "Review decision: not_recorded" in captured.out
            assert "Review status: unpaired" in captured.out
            assert "Status: pending" in captured.out
            assert "Historical unsigned review observations: 1" in captured.out

def test_historical_revision_cannot_supply_a_binary_label(capsys):
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        ledger.append_event(task_id, "task_created", {"title": "Test Revision Task"})
        ledger.append_event(task_id, "review_completed", {"accepted": False, "review_decision": "needs_revision"})
        
        ledger_path = os.path.join(temp_dir, "ledger.jsonl")
        with patch("triage_core.tc_cli._ledger_path", return_value=ledger.ledger_path):
            tc_task_show(task_id)
            
            captured = capsys.readouterr()
            assert "Accepted: not_recorded" in captured.out
            assert "Review decision: not_recorded" in captured.out
            assert "review_completed | needs_revision" in captured.out

def test_task_show_preserves_prior_receipt_when_current_evidence_changes(tmp_path, monkeypatch, capsys):
    from triage_core import task_review_service
    from triage_core.task_review_service import ReviewHistory, ReviewState

    ledger = TaskLedger(str(tmp_path))
    ledger.append_event("task", "task_created", {"title": "Review receipt history"})
    ledger.append_event("task", "review_completed", {"accepted": False})
    receipt = ReviewHistory("receipt-1", "r1", "accepted", "2026-11-23T00:00:00Z", scope_id="scope-a")
    current = ReviewState(status="verified", decision="accepted", history=(receipt,))
    service = SimpleNamespace(project=lambda task_id, *, include_history: current)
    monkeypatch.setattr(task_review_service, "get_review_service", lambda ledger_dir: service)

    tc_task_show("task", ledger_dir=str(tmp_path))

    output = capsys.readouterr().out
    assert "Review status: verified" in output
    assert "Review decision: accepted" in output
    assert "Accepted: true" in output
    assert "review_completed | rejected" in output

    current = ReviewState(status="evidence_changed", reason="review_evidence_changed", history=(receipt,))
    tc_task_show("task", ledger_dir=str(tmp_path))

    output = capsys.readouterr().out
    assert "Review status: evidence_changed" in output
    assert "Review reason: review_evidence_changed" in output
    assert "Accepted: not_recorded" in output
    assert "receipt-1 | r1 | accepted | scope=scope-a" in output

def test_missing_task_behavior(capsys):
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        # Do not append anything
        ledger_path = os.path.join(temp_dir, "ledger.jsonl")
        with patch("triage_core.tc_cli._ledger_path", return_value=ledger.ledger_path):
            with pytest.raises(SystemExit) as exc:
                tc_task_show(task_id)
                
            assert exc.value.code == 1
            captured = capsys.readouterr()
            assert "Error: task not found" in captured.out
            assert "reason=task_not_found" in captured.out
            assert "Traceback" not in captured.out
            assert "Traceback" not in captured.err

def test_command_is_readonly():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        ledger.append_event(task_id, "task_created", {"title": "Immutable Task"})
        
        ledger_path = os.path.join(temp_dir, "ledger.jsonl")
        
        # Read file bytes before
        with open(ledger.ledger_path, "rb") as f:
            bytes_before = f.read()
            
        with patch("triage_core.tc_cli._ledger_path", return_value=ledger.ledger_path):
            try:
                tc_task_show(task_id)
            except SystemExit:
                pass
                
        # Read file bytes after
        with open(ledger.ledger_path, "rb") as f:
            bytes_after = f.read()
            
        assert bytes_before == bytes_after
