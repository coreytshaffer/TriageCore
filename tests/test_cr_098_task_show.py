import os
import uuid
import tempfile
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

def test_reviewed_task_accepted_decision(capsys):
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        ledger.append_event(task_id, "task_created", {"title": "Test Accepted Task"})
        ledger.append_event(task_id, "review_completed", {"accepted": True, "review_decision": "accepted"})
        
        ledger_path = os.path.join(temp_dir, "ledger.jsonl")
        with patch("triage_core.tc_cli._ledger_path", return_value=ledger.ledger_path):
            tc_task_show(task_id)
            
            captured = capsys.readouterr()
            assert "Accepted: true" in captured.out
            assert "Review decision: accepted" in captured.out
            assert "Status: reviewed" in captured.out

def test_reviewed_task_needs_revision_decision(capsys):
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        ledger.append_event(task_id, "task_created", {"title": "Test Revision Task"})
        ledger.append_event(task_id, "review_completed", {"accepted": False, "review_decision": "needs_revision"})
        
        ledger_path = os.path.join(temp_dir, "ledger.jsonl")
        with patch("triage_core.tc_cli._ledger_path", return_value=ledger.ledger_path):
            tc_task_show(task_id)
            
            captured = capsys.readouterr()
            assert "Accepted: false" in captured.out
            assert "Review decision: needs_revision" in captured.out
            assert "Review decision: rejected" not in captured.out

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
