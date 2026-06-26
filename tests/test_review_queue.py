import os
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

def test_review_queue_resolved(tmp_path):
    ledger = TaskLedger(str(tmp_path))
    ledger.append_event("task-123", "task_classified", {"risk_level": "high"})
    
    pending = get_pending_reviews(ledger)
    assert len(pending) == 1
    
    # Review completed
    ledger.append_event("task-123", "review_completed", {"accepted": True})
    
    pending = get_pending_reviews(ledger)
    assert len(pending) == 0
