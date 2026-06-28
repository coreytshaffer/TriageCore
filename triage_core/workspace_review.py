import datetime
from triage_core.workspace_board import WorkItem, Status, Priority, GtdList

def is_stale(item: WorkItem, default_stale_days: int = 14) -> bool:
    """Determine if an item is considered stale."""
    if item.kanban.status not in (Status.ACTIVE, Status.REVIEW):
        return False
        
    stale_days = default_stale_days
    compare_date_str = None
    
    if item.review:
        if item.review.stale_after_days is not None:
            stale_days = item.review.stale_after_days
        
        if item.review.last_touched:
            compare_date_str = item.review.last_touched
        elif item.review.last_reviewed:
            compare_date_str = item.review.last_reviewed
            
    # Fallback to github updated_at if no review dates exist
    if not compare_date_str:
        if item.external and item.external.source == "github" and item.external.github and item.external.github.updated_at:
            compare_date_str = item.external.github.updated_at
            
    if compare_date_str:
        try:
            # We support both YYYY-MM-DD and YYYY-MM-DDTHH:MM:SSZ
            # Let's normalize by just string comparison after formatting our threshold
            threshold_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=stale_days)).strftime("%Y-%m-%d")
            
            # Simple string comparison works for ISO 8601 prefixes
            if compare_date_str < threshold_date:
                return True
        except Exception:
            pass
            
    # If no dates available, we don't assume stale
    return False

def is_someday(item: WorkItem) -> bool:
    """Determine if an item is intentionally deferred."""
    if item.kanban.status == Status.PARKED:
        return True
    if item.kanban.priority == Priority.SOMEDAY:
        return True
    if item.gtd and item.gtd.gtd_list == GtdList.SOMEDAY_MAYBE:
        return True
    return False

def render_weekly_review(items: list[WorkItem], stale_after_days: int = 14) -> str:
    """Render a Weekly Review Markdown view."""
    
    active = []
    ready = []
    blocked = []
    done = []
    stale = []
    someday = []
    
    for item in items:
        # Check specific computed states first
        if is_someday(item):
            someday.append(item)
            continue
            
        if item.kanban.status == Status.DONE:
            # In a real system, we'd filter for "recently" done, but we'll show all done for now.
            done.append(item)
            continue
            
        if is_stale(item, default_stale_days=stale_after_days):
            stale.append(item)
            continue
            
        # Standard states
        if item.kanban.status == Status.ACTIVE:
            active.append(item)
        elif item.kanban.status == Status.READY:
            ready.append(item)
        elif item.kanban.status == Status.BLOCKED:
            blocked.append(item)
            
    # Helper to render a list of items
    def render_list(group_items: list[WorkItem]) -> str:
        if not group_items:
            return "- None\n"
        
        lines = []
        for it in group_items:
            lines.append(f"- [{it.id}] {it.title}")
        return "\n".join(lines) + "\n"

    blocks = [
        "Weekly Review",
        "=============\n",
        "Active:",
        render_list(active),
        "Ready:",
        render_list(ready),
        "Waiting / Blocked:",
        render_list(blocked),
        "Done Recently:",
        render_list(done),
        "Stale:",
        render_list(stale),
        "Someday / Parked:",
        render_list(someday)
    ]
    
    return "\n".join(blocks).strip() + "\n"
