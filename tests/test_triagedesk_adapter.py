import os
import tempfile
import pytest
from triage_core import triagedesk_adapter
from triage_core.task_ledger import TaskLedger, TaskRecord
from triage_core.token_budget import TokenBudget

def test_status_snapshot_returns_expected_fields():
    snapshot = triagedesk_adapter.get_status_snapshot()
    assert hasattr(snapshot, "git_status")
    assert hasattr(snapshot, "ledger_path")
    assert hasattr(snapshot, "ledger_exists")
    assert hasattr(snapshot, "ledger_writable")
    assert hasattr(snapshot, "last_event_timestamp")

def test_doctor_snapshot_is_read_only_and_deterministic():
    snapshot1 = triagedesk_adapter.get_doctor_snapshot()
    snapshot2 = triagedesk_adapter.get_doctor_snapshot()
    assert snapshot1.git_branch == snapshot2.git_branch
    assert snapshot1.overall in ("OK", "WARN", "FAIL")

def test_review_queue_snapshot_handles_empty_state(monkeypatch):
    # Mock _get_ledger_path to a non-existent file
    monkeypatch.setattr(triagedesk_adapter, "_get_ledger_path", lambda: "/tmp/non_existent_ledger.jsonl")
    snapshot = triagedesk_adapter.get_review_queue_snapshot()
    assert len(snapshot.pending_tasks) == 0

def test_context_plan_snapshot_handles_fitting_input():
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("Short text")
        tmp_path = f.name
    
    try:
        snapshot = triagedesk_adapter.plan_context_file(tmp_path, "generic-8k")
        assert snapshot.input_path == tmp_path
        assert snapshot.model_profile == "generic-8k"
        assert snapshot.status == "fits"
        assert snapshot.estimated_input_tokens > 0
    finally:
        os.remove(tmp_path)

def test_packet_preview_includes_estimated_budget_status():
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("Task description")
        tmp_path = f.name
    
    try:
        snapshot = triagedesk_adapter.preview_packet(tmp_path, "generic-8k", [])
        assert "## Model Budget" in snapshot.content
        assert snapshot.fits_budget is True
        assert snapshot.estimated_tokens > 0
        assert isinstance(snapshot.budget, TokenBudget)
    finally:
        os.remove(tmp_path)

def test_missing_file_errors_are_clear():
    with pytest.raises(FileNotFoundError, match="File not found"):
        triagedesk_adapter.plan_context_file("missing_file.md", "generic-8k")
        
    with pytest.raises(FileNotFoundError, match="File not found"):
        triagedesk_adapter.preview_packet("missing_file.md", "generic-8k", [])

def test_unknown_model_profile_errors_are_clear():
    with pytest.raises(KeyError, match="Unknown model profile"):
        triagedesk_adapter.plan_context_file("missing_file.md", "unknown-model")

def test_adapter_does_not_import_gui_libraries():
    with open(triagedesk_adapter.__file__, "r") as f:
        content = f.read()
    assert "customtkinter" not in content
    assert "tkinter" not in content
