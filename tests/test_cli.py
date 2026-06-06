from triage_core.cli import _create_packet
from triage_core.cli import _import_learning_seeds
from triage_core.cli import _import_supervisor_usage
from triage_core.cli import _log_cli_activity
from triage_core.cli import _record_supervisor_review
from triage_core.cli import _record_pipeline_handoff
from triage_core.cli import _record_pipeline_success
from triage_core.cli import _scan_supervisor_usage
from triage_core.cli import _start_pipeline_task
from triage_core.task_ledger import TaskLedger

import json
import os
import tempfile
import uuid

def test_create_packet():
    packet = _create_packet("Fix the syntax error", ["main.py"])
    
    assert packet.title == "Task: Bugfix"
    assert "main.py" in packet.target_files
    assert packet.risk_level == "low"
    assert packet.recommended_permission_profile == "workspace-write"


def test_log_cli_activity_writes_desktop_visible_log():
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = _log_cli_activity("benchmark started", ledger_dir=temp_dir)

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert log_path.endswith("triagecore.log")
        assert "[cli] benchmark started" in content


def test_record_supervisor_review_appends_ledger_event():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "task_created", {"title": "Bridge Task"})

        _record_supervisor_review(
            task_id=task_id,
            tool="antigravity",
            decision="accepted",
            notes="IDE supervisor accepted the local draft.",
            model="gemini-3.1-pro-high",
            profile="supervisor",
            artifact_path=".agent_tasks/example/TASK.md",
            input_tokens_est=900,
            output_tokens_est=250,
            token_source="manual_estimate",
            ledger_dir=temp_dir,
        )

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.supervisor_tool == "antigravity"
        assert record.supervisor_model == "gemini-3.1-pro-high"
        assert record.supervisor_profile == "supervisor"
        assert record.supervisor_decision == "accepted"
        assert record.supervisor_input_tokens_est == 900
        assert record.supervisor_output_tokens_est == 250
        assert record.supervisor_token_source == "manual_estimate"


def test_import_supervisor_usage_appends_imported_event():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "task_created", {"title": "Import Task"})
        usage_path = f"{temp_dir}/usage.json"
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": task_id,
                "tool": "codex",
                "decision": "accepted",
                "usage": {
                    "prompt_tokens": 111,
                    "completion_tokens": 22,
                },
            }, f)

        imported = _import_supervisor_usage(
            source_path=usage_path,
            tool="",
            decision="needs_revision",
            notes="",
            model="gpt-5",
            profile="high",
            artifact_path="",
            token_source="imported_exact",
            ledger_dir=temp_dir,
            dry_run=False,
        )

        record = ledger.get_task(task_id)

        assert imported == 1
        assert record is not None
        assert record.supervisor_tool == "codex"
        assert record.supervisor_decision == "accepted"
        assert record.supervisor_model == "gpt-5"
        assert record.supervisor_profile == "high"
        assert record.supervisor_input_tokens_est == 111
        assert record.supervisor_output_tokens_est == 22
        assert record.supervisor_token_source == "imported_exact"


def test_import_supervisor_usage_dry_run_does_not_append_event():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "task_created", {"title": "Dry Run Task"})
        usage_path = f"{temp_dir}/usage.json"
        with open(usage_path, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": task_id,
                "tool": "codex",
                "decision": "accepted",
                "input_tokens": 44,
                "output_tokens": 11,
            }, f)

        imported = _import_supervisor_usage(
            source_path=usage_path,
            tool="",
            decision="accepted",
            notes="",
            model="",
            profile="",
            artifact_path="",
            token_source="imported_exact",
            ledger_dir=temp_dir,
            dry_run=True,
        )

        record = ledger.get_task(task_id)

        assert imported == 1
        assert record is not None
        assert record.supervisor_tool == ""
        assert record.supervisor_input_tokens_est == 0
        assert record.supervisor_output_tokens_est == 0


def test_scan_supervisor_usage_reports_candidates():
    with tempfile.TemporaryDirectory() as temp_dir:
        usage_path = f"{temp_dir}/usage.jsonl"
        with open(usage_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "task_id": "task-1",
                "prompt_tokens": 10,
                "completion_tokens": 5,
            }))

        count = _scan_supervisor_usage(
            paths=[temp_dir],
            tool="codex",
            token_source="imported_exact",
            max_file_bytes=1_000_000,
        )

        assert count == 1


def test_import_learning_seeds_dry_run_does_not_write(capsys):
    with tempfile.TemporaryDirectory() as temp_dir:
        source_dir = f"{temp_dir}/examples"
        ledger_dir = f"{temp_dir}/ledger"
        os.makedirs(source_dir, exist_ok=True)
        with open(f"{source_dir}/triagecore-assignment-preflights.safetask.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "preflight_id": "preflight-1",
                "created_at": "2026-06-05T00:00:00Z",
                "source_project": "safetask-ai",
                "assignment_goal": "Classify a compliance copy task.",
                "task_class": "docs_update",
                "complexity": "low",
                "sensitivity": "medium",
                "required_context": ["policy excerpt"],
                "context_pack_type": "bounded_docs",
                "candidate_combo": "local-small+validator",
                "required_checks": ["schema_check"],
                "stop_conditions": ["missing_policy_source"],
                "human_review_required": True,
                "confidence_before_assignment": 0.72,
                "rationale": "Bounded source material with a required review gate.",
            }) + "\n")
        with open(f"{source_dir}/triagecore-context-packs.safetask.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "context_pack_id": "context-1",
                "pack_type": "bounded_docs",
                "source_project": "safetask-ai",
                "task_goal": "Classify a compliance copy task.",
                "source_artifacts": ["docs/policy.md"],
                "constraints": ["do not approve routing automatically"],
                "required_checks": ["schema_check"],
                "budget_note": "Small enough for local review.",
            }) + "\n")
        with open(f"{source_dir}/triagecore-assignment-outcomes.safetask.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "task_id": "task-1",
                "preflight_id": "preflight-1",
                "context_pack_id": "context-1",
                "observed_at": "2026-06-05T00:05:00Z",
                "source_project": "safetask-ai",
                "source_artifacts": ["docs/policy.md"],
                "task_class": "docs_update",
                "complexity": "low",
                "sensitivity": "medium",
                "assignment_goal": "Classify a compliance copy task.",
                "model_combo": "local-small+validator",
                "tool_path": "local",
                "result_status": "accepted_with_review",
                "verification": {"schema_check": "passed"},
                "correction_burden": "low",
                "waste_signal": "low",
                "confidence_after_review": 0.84,
                "lesson": "Bounded docs can route locally when review gates stay explicit.",
                "human_review_required": True,
            }) + "\n")

        count = _import_learning_seeds(source_dir=source_dir, ledger_dir=ledger_dir, write=False)
        captured = capsys.readouterr()

        assert count == 3
        assert "Would import 1 preflight(s)" in captured.out
        assert not os.path.exists(os.path.join(ledger_dir, "learning_seeds"))


def test_pipeline_helpers_record_desktop_visible_ledger_events():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)

        task_id = _start_pipeline_task(
            ledger=ledger,
            prompt="Create a tiny utility.",
            files=["README.md"],
        )
        _record_pipeline_success(
            ledger=ledger,
            task_id=task_id,
            backend_type="ollama",
            model="qwen2.5-coder:7b",
            output_path="reports/pipeline-output.md",
            elapsed_seconds=1.5,
            input_tokens=12,
            output_tokens=8,
            total_tokens=20,
        )

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.title == "Pipeline: Create a tiny utility."
        assert record.runner == "pipeline"
        assert record.status == "local_draft_generated"
        assert record.backend_name == "ollama"
        assert record.model == "qwen2.5-coder:7b"
        assert record.total_tokens == 20
        assert "reports/pipeline-output.md" in record.artifact_paths


def test_pipeline_handoff_records_blocked_task():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = _start_pipeline_task(
            ledger=ledger,
            prompt="Unsafe task.",
            files=[],
        )

        _record_pipeline_handoff(ledger, task_id, "Pipeline handoff required.")

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.status == "blocked"
        assert record.handoff_reason == "Pipeline handoff required."
        assert record.human_review_required is True
        assert record.wasted_tokens == 0


def test_pipeline_handoff_records_blocked_task_with_wasted_tokens():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = _start_pipeline_task(
            ledger=ledger,
            prompt="Unsafe task.",
            files=[],
        )

        _record_pipeline_handoff(
            ledger=ledger,
            task_id=task_id,
            reason="Blocked by ethical policy.",
            input_tokens=150,
            output_tokens=50,
            total_tokens=200,
        )

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.status == "blocked"
        assert record.handoff_reason == "Blocked by ethical policy."
        assert record.human_review_required is True
        assert record.input_tokens == 150
        assert record.output_tokens == 50
        assert record.total_tokens == 200
        assert record.wasted_tokens == 200
