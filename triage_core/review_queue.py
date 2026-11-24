from typing import List
from triage_core.task_ledger import TaskLedger, TaskRecord

def get_pending_reviews(ledger: TaskLedger) -> List[TaskRecord]:
    """Return required reviews without a verified terminal decision."""
    return [
        task
        for task in ledger.get_all_tasks()
        if task.human_review_required and not task.review.is_terminal
    ]

def format_review_queue(pending: List[TaskRecord]) -> str:
    """
    Formats the review queue for console output.
    """
    lines = ["Review Queue\n"]
    
    if not pending:
        lines.append("Status: empty\n")
        lines.append("Items:")
        lines.append("  (no pending reviews found)")
        return "\n".join(lines)
    
    lines.append("Status: available\n")
    lines.append("Items:")
    
    for task in pending:
        task_id = task.task_id or "unknown"
        kind = task.status or "unknown"
        timestamp = task.updated_at or task.created_at or "unknown"
        reason = task.handoff_reason or task.firewall_reason or task.early_stop_reason or "human review required"
        
        lines.append(f"\n* ID: {task_id}")
        lines.append(f"  Type/kind: {kind}")
        lines.append(f"  Created timestamp: {timestamp}")
        lines.append(f"  Reason/status: {reason}")
        lines.append(f"  Review status: {task.review.status}")
        if task.review.status == "verified":
            lines.append(f"  Review decision: {task.review.decision}")
        if task.review.reason:
            lines.append(f"  Review reason: {task.review.reason}")
        if task.legacy_review_observation_count:
            lines.append(
                f"  Historical unsigned review observations: {task.legacy_review_observation_count}"
            )
        
    return "\n".join(lines)
