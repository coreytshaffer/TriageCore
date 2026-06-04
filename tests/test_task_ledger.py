import os
import uuid
import tempfile
from triage_core.task_ledger import TaskLedger

def test_ledger_append_and_read():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        
        # 1. Append task created
        ledger.append_event(task_id, "task_created", {
            "title": "Test Task",
            "description": "A task for testing",
            "target_files": ["main.py"]
        })
        
        # 2. Append classified
        ledger.append_event(task_id, "task_classified", {
            "category": "bugfix",
            "risk_level": "medium",
            "recommended_profile": "workspace-write-with-approval",
            "reasons": ["Uses pip install"]
        })
        
        # 3. Read it back
        record = ledger.get_task(task_id)
        assert record is not None
        assert record.title == "Test Task"
        assert record.risk_level == "medium"
        assert record.permission_profile == "workspace-write-with-approval"
        assert record.human_review_required == True
        assert record.status == "pending"

def test_ledger_get_all_tasks():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        
        t1 = str(uuid.uuid4())
        t2 = str(uuid.uuid4())
        
        ledger.append_event(t1, "task_created", {"title": "Task 1"})
        ledger.append_event(t2, "task_created", {"title": "Task 2"})
        
        tasks = ledger.get_all_tasks()
        assert len(tasks) == 2
        
        titles = [t.title for t in tasks]
        assert "Task 1" in titles
        assert "Task 2" in titles
