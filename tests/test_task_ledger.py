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
        assert record.created_at != ""
        assert record.updated_at != ""
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

def test_ledger_tracks_model_evaluation_fields():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {
            "title": "Evaluate local model",
            "description": "Run a benchmark task",
            "target_files": []
        })
        ledger.append_event(task_id, "model_evaluated", {
            "backend_name": "ollama",
            "model": "qwen2.5-coder:7b",
            "timeout_seconds": 30,
            "elapsed_seconds": 2.5,
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "tokens_per_second": 60.0,
            "validator_passed": True
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.backend_name == "ollama"
        assert record.model == "qwen2.5-coder:7b"
        assert record.timeout_seconds == 30
        assert record.elapsed_seconds == 2.5
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.total_tokens == 150
        assert record.tokens_per_second == 60.0
        assert record.validator_passed is True

def test_ledger_tracks_study_id():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {
            "title": "Study benchmark",
            "study_id": "study_001",
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.study_id == "study_001"

def test_ledger_tracks_run_id():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {
            "title": "Study benchmark trial",
            "study_id": "study_001",
            "run_id": "trial_001",
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.study_id == "study_001"
        assert record.run_id == "trial_001"

def test_ledger_tracks_handoff_reason_for_review():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Unsafe task"})
        ledger.append_event(task_id, "handoff_generated", {
            "artifact_path": "triage_tasks/codex_task.md",
            "reason": "Risk level high detected."
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.status == "handoff_generated"
        assert record.handoff_reason == "Risk level high detected."
        assert record.human_review_required is True

def test_ledger_tracks_human_review_minutes_and_completion_timestamp():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Timer Task"})
        ledger.append_event(task_id, "local_draft_generated", {
            "status": "success",
            "duration_seconds": 12.5
        })
        ledger.append_event(task_id, "review_completed", {
            "accepted": True,
            "human_review_minutes": 1.5
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.status == "reviewed"
        assert record.accepted is True
        assert record.human_review_minutes == 1.5
        assert record.completed_at != ""
        assert record.updated_at != ""

def test_ledger_tracks_review_workload():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Review Load Task"})
        ledger.append_event(task_id, "review_completed", {
            "accepted": False,
            "human_review_minutes": 0.75,
            "review_workload": "high"
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.status == "reviewed"
        assert record.accepted is False
        assert record.review_workload == "high"

def test_ledger_updates_updated_at_on_later_events():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Timestamp Task"})
        created_record = ledger.get_task(task_id)
        assert created_record is not None
        created_at = created_record.created_at

        ledger.append_event(task_id, "review_completed", {"accepted": True})
        reviewed_record = ledger.get_task(task_id)

        assert reviewed_record is not None
        assert reviewed_record.created_at == created_at
        assert reviewed_record.updated_at >= created_at
        assert reviewed_record.status == "reviewed"
