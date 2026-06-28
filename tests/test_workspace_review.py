import datetime
from triage_core.workspace_board import (
    WorkItem, KanbanState, Status, Priority, ClosingFields, ClosingEvidence, 
    ExternalFields, ExternalGithub, GtdFields, GtdList, ReviewFields
)
from triage_core.workspace_review import is_stale, is_someday, render_weekly_review

def test_is_someday():
    # Test PARKED status
    item = WorkItem(id="1", project="p", title="t", type="task", kanban=KanbanState(status=Status.PARKED, priority=Priority.LOW))
    assert is_someday(item) == True
    
    # Test SOMEDAY priority
    item = WorkItem(id="2", project="p", title="t", type="task", kanban=KanbanState(status=Status.BACKLOG, priority=Priority.SOMEDAY))
    assert is_someday(item) == True
    
    # Test SOMEDAY_MAYBE gtd list
    item = WorkItem(id="3", project="p", title="t", type="task", 
                    kanban=KanbanState(status=Status.BACKLOG, priority=Priority.LOW),
                    gtd=GtdFields(next_action="na", gtd_list=GtdList.SOMEDAY_MAYBE))
    assert is_someday(item) == True
    
    # Test regular item
    item = WorkItem(id="4", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.HIGH))
    assert is_someday(item) == False


def test_is_stale():
    # Non-active/review items are never stale
    item = WorkItem(id="1", project="p", title="t", type="task", kanban=KanbanState(status=Status.BACKLOG, priority=Priority.LOW))
    assert is_stale(item) == False
    
    # Active with no evidence and no external github is NOT stale (we need a date to consider it stale)
    item = WorkItem(id="2", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW))
    assert is_stale(item) == False
    
    # Active with evidence is no longer a factor for staleness, so if it has no dates it's not stale
    item = WorkItem(id="3", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                    closing=ClosingFields(evidence=ClosingEvidence(commits=["abc"])))
    assert is_stale(item) == False
    
    recent_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Active with recent github activity is not stale
    item = WorkItem(id="4", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                    external=ExternalFields(source="github", github=ExternalGithub(updated_at=recent_date)))
    assert is_stale(item) == False
    
    # Active with old github activity is stale
    item = WorkItem(id="5", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                    external=ExternalFields(source="github", github=ExternalGithub(updated_at=old_date)))
    assert is_stale(item) == True

    # Active with old github activity but recent review.last_touched is NOT stale
    item = WorkItem(id="6", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                    external=ExternalFields(source="github", github=ExternalGithub(updated_at=old_date)),
                    review=ReviewFields(last_touched=recent_date))
    assert is_stale(item) == False

    # Active with recent github activity but old review.last_reviewed IS stale
    # (review dates override external dates)
    item = WorkItem(id="7", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                    external=ExternalFields(source="github", github=ExternalGithub(updated_at=recent_date)),
                    review=ReviewFields(last_reviewed=old_date))
    assert is_stale(item) == True
    
    # Active with old review date but large stale_after_days is NOT stale
    item = WorkItem(id="8", project="p", title="t", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                    review=ReviewFields(last_touched=old_date, stale_after_days=30))
    assert is_stale(item) == False


def test_render_weekly_review():
    items = [
        WorkItem(id="A", project="p", title="Active Item", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                 closing=ClosingFields(evidence=ClosingEvidence(commits=["abc"]))), # Not stale
        WorkItem(id="R", project="p", title="Ready Item", type="task", kanban=KanbanState(status=Status.READY, priority=Priority.LOW)),
        WorkItem(id="B", project="p", title="Blocked Item", type="task", kanban=KanbanState(status=Status.BLOCKED, priority=Priority.LOW)),
        WorkItem(id="D", project="p", title="Done Item", type="task", kanban=KanbanState(status=Status.DONE, priority=Priority.LOW)),
        WorkItem(id="S1", project="p", title="Stale Item", type="task", kanban=KanbanState(status=Status.ACTIVE, priority=Priority.LOW),
                 review=ReviewFields(last_touched="2000-01-01")),
        WorkItem(id="S2", project="p", title="Someday Item", type="task", kanban=KanbanState(status=Status.PARKED, priority=Priority.LOW)),
    ]
    
    review = render_weekly_review(items)
    
    assert "Active:\n- [A] Active Item\n" in review
    assert "Ready:\n- [R] Ready Item\n" in review
    assert "Waiting / Blocked:\n- [B] Blocked Item\n" in review
    assert "Done Recently:\n- [D] Done Item\n" in review
    assert "Stale:\n- [S1] Stale Item\n" in review
    assert "Someday / Parked:\n- [S2] Someday Item\n" in review
