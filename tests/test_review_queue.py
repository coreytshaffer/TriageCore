from types import SimpleNamespace

from triage_core.task_ledger import TaskLedger
from triage_core.review_queue import get_pending_reviews, format_review_queue

def test_review_queue_empty(tmp_path):
    ledger = TaskLedger(str(tmp_path))
    pending = get_pending_reviews(ledger)
    assert len(pending) == 0
    output = format_review_queue(pending)
    assert "Status: empty" in output
    assert "(no pending reviews found)" in output

def test_review_queue_with_items(tmp_path):
    ledger = TaskLedger(str(tmp_path))
    # Add a task that requires review
    ledger.append_event("task-123", "task_classified", {"risk_level": "high"})
    
    # Add a task that does not require review
    ledger.append_event("task-456", "task_classified", {"risk_level": "low"})
    
    pending = get_pending_reviews(ledger)
    assert len(pending) == 1
    assert pending[0].task_id == "task-123"
    
    output = format_review_queue(pending)
    assert "Status: available" in output
    assert "ID: task-123" in output

def test_legacy_observation_leaves_required_review_open(tmp_path):
    ledger = TaskLedger(str(tmp_path))
    ledger.append_event("task-123", "task_classified", {"risk_level": "high"})
    
    pending = get_pending_reviews(ledger)
    assert len(pending) == 1
    
    ledger.append_event("task-123", "review_completed", {"accepted": True})
    
    pending = get_pending_reviews(ledger)
    assert [task.task_id for task in pending] == ["task-123"]
    assert "Review status: unpaired" in format_review_queue(pending)


def test_verified_terminal_decisions_alone_close_queue(tmp_path):
    from triage_core.task_review_service import ReviewState

    states = {
        "accept": ReviewState(status="verified", decision="accepted"),
        "reject": ReviewState(status="verified", decision="rejected"),
        "revise": ReviewState(status="verified", decision="needs_revision"),
        "waiting": ReviewState(status="pending"),
        "changed": ReviewState(status="evidence_changed"),
        "unavailable": ReviewState(status="unavailable", reason="store_unavailable"),
        "undecided": ReviewState(status="no_decision"),
    }
    service = SimpleNamespace(project=lambda task_id, *, include_history: states[task_id])
    ledger = TaskLedger(str(tmp_path), review_service=service)
    for task_id in states:
        ledger.append_event(task_id, "task_classified", {"risk_level": "high"})

    pending = get_pending_reviews(ledger)
    assert {task.task_id for task in pending} == {
        "revise", "waiting", "changed", "unavailable", "undecided"
    }
    output = format_review_queue(pending)
    assert "Review decision: needs_revision" in output
    assert "Review reason: store_unavailable" in output
