import os
import uuid
import tempfile
import pytest

from triage_core.agent_identity import (
    AgentIdentityRegistry,
    REVOKED_STATUS,
    RevokedAgentError,
    UnauthorizedCapabilityError,
)
from triage_core.task_ledger import (
    TaskLedger,
    verify_route_audit_event_signature,
    verify_route_decision_event_signature,
    verify_validation_result_event_signature,
)

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

def test_ledger_tracks_supervisor_review():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Supervisor Task"})
        ledger.append_event(task_id, "supervisor_reviewed", {
            "supervisor_tool": "codex",
            "supervisor_model": "gpt-5",
            "supervisor_profile": "high",
            "supervisor_decision": "needs_revision",
            "supervisor_notes": "Local draft needs tests.",
            "supervisor_artifact_path": "triage_tasks/codex_task_abc.md",
            "supervisor_input_tokens_est": 1200,
            "supervisor_output_tokens_est": 300,
            "supervisor_token_source": "imported_exact",
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.supervisor_tool == "codex"
        assert record.supervisor_model == "gpt-5"
        assert record.supervisor_profile == "high"
        assert record.supervisor_decision == "needs_revision"
        assert record.supervisor_notes == "Local draft needs tests."
        assert record.supervisor_artifact_path == "triage_tasks/codex_task_abc.md"
        assert record.supervisor_input_tokens_est == 1200
        assert record.supervisor_output_tokens_est == 300
        assert record.supervisor_token_source == "imported_exact"
        assert "triage_tasks/codex_task_abc.md" in record.artifact_paths

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

def test_ledger_context_methods():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Context Task", "description": "Desc"})
        ledger.append_event(task_id, "local_draft_generated", {"status": "success", "duration_seconds": 5.0})
        
        events = ledger.get_events(task_id)
        assert len(events) == 2
        assert events[0]["event_type"] == "task_created"
        
        ctx = ledger.get_task_context(task_id)
        assert ctx is not None
        assert ctx.record.title == "Context Task"
        assert len(ctx.events) == 2
        
        recent = ledger.get_recent_tasks(10)
        assert len(recent) == 1
        
        search_res = ledger.search_tasks("Context")
        assert len(search_res) == 1
        search_res2 = ledger.search_tasks("Not Found")
        assert len(search_res2) == 0


def test_context_budget_event_reduces_to_task_record():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Context Budget"})
        ledger.append_event(
            task_id,
            "context_budgeted",
            {
                "context_pack_path": ".triagecore/context_packs/context_pack_123.json",
                "context_strategy": "context_budget_planner_v1",
                "context_estimated_tokens": 120,
                "context_budget_tokens": 4000,
                "context_budget_status": "within_budget",
                "context_required_items": 1,
                "context_helpful_items": 2,
                "context_optional_items": 0,
                "context_excluded_items": 1,
            },
        )

        record = ledger.get_task(task_id)
        ctx = ledger.get_task_context(task_id)

        assert record is not None
        assert record.context_pack_path.endswith("context_pack_123.json")
        assert record.context_estimated_tokens == 120
        assert record.context_budget_tokens == 4000
        assert record.context_budget_status == "within_budget"
        assert record.context_excluded_items == 1
        assert record.context_pack_path in record.artifact_paths
        assert ctx is not None
        assert ctx.telemetry_summary["context_estimated_tokens"] == 120


def test_ledger_tracks_wasted_tokens():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Wasted Tokens Task"})
        ledger.append_event(task_id, "local_draft_generated", {
            "status": "handoff_required",
            "wasted_tokens": 1500
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.status == "local_draft_generated"
        assert record.wasted_tokens == 1500


def test_route_decision_and_worker_result_reduce_to_task_record():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Route Telemetry"})
        ledger.append_event(
            task_id,
            "route_decision",
            {
                "selected_route": "local_fast",
                "selected_backend": "ollama",
                "selected_model": "qwen2.5-coder:7b",
                "reason": "local_fast_available_for_small_or_repetitive_task",
                "fallback_depth": 3,
                "route_source": "resilience_router_v1",
                "human_review_required": False,
            },
        )
        ledger.append_event(
            task_id,
            "worker_result",
            {
                "selected_route": "local_fast",
                "selected_backend": "ollama",
                "selected_model": "qwen2.5-coder:7b",
                "worker_result_status": "completed",
                "validation_status": "passed",
                "failure_type": None,
                "failure_stage": None,
                "backend_failure": False,
                "elapsed_seconds": 1.25,
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
                "tokens_per_second": 11.2,
            },
        )

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.selected_route == "local_fast"
        assert record.selected_backend == "ollama"
        assert record.route_reason == "local_fast_available_for_small_or_repetitive_task"
        assert record.route_source == "resilience_router_v1"
        assert record.fallback_depth == 3
        assert record.worker_result_status == "completed"
        assert record.validation_status == "passed"
        assert record.backend_failure is False
        assert record.total_tokens == 14


def test_ledger_tracks_story_118_control_signals():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Telemetry Controls"})
        ledger.append_event(
            task_id,
            "council_completed",
            {
                "reason": "Early stopping: Exceeded energy budget (0.0300 > 0.02).",
                "early_stopped": True,
                "early_stop_reason": "Exceeded energy budget (0.0300 > 0.02).",
                "firewall_triggered": True,
                "firewall_reason": "Ethical Firewall: Triggered rule 'public_health_and_safety'.",
                "credit_allowance_total": 1000,
                "credit_allowance_used": 1200,
                "credit_allowance_remaining": 0,
                "credit_allowance_exhausted": True,
            },
        )

        record = ledger.get_task(task_id)
        ctx = ledger.get_task_context(task_id)

        assert record is not None
        assert record.early_stopped is True
        assert "Exceeded energy budget" in record.early_stop_reason
        assert record.firewall_triggered is True
        assert "Ethical Firewall" in record.firewall_reason
        assert record.credit_allowance_total == 1000
        assert record.credit_allowance_used == 1200
        assert record.credit_allowance_remaining == 0
        assert record.credit_allowance_exhausted is True
        assert ctx is not None
        assert ctx.telemetry_summary["early_stopped"] is True
        assert ctx.telemetry_summary["credit_allowance_exhausted"] is True


def test_append_event_adds_schema_version():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Test Version"})
        events = ledger.get_events(task_id)

        assert len(events) == 1
        assert "schema_version" in events[0]
        assert events[0]["schema_version"] == "0.2.0"

        record = ledger.get_task(task_id)
        assert record is not None
        assert record.schema_version == "0.2.0"

def test_append_event_adds_role_taxonomy_version():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {"title": "Test Role Taxonomy"})
        events = ledger.get_events(task_id)

        assert len(events) == 1
        assert "role_taxonomy_version" in events[0]
        assert events[0]["role_taxonomy_version"] == "2026-06-worker-council-v2"

        record = ledger.get_task(task_id)
        assert record is not None
        assert record.role_taxonomy_version == "2026-06-worker-council-v2"

def test_legacy_events_without_versions_still_reduce():
    import json
    from datetime import datetime, timezone
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        # Manually write an old-style event without version fields
        event = {
            "event_id": str(uuid.uuid4()),
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "task_created",
            "payload": {"title": "Legacy Task"}
        }
        with open(ledger.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        record = ledger.get_task(task_id)
        assert record is not None
        assert record.title == "Legacy Task"
        assert record.schema_version is None
        assert record.role_taxonomy_version is None

def test_mixed_schema_versions_do_not_crash():
    import json
    from datetime import datetime, timezone
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        # 1. Manually write an old-style event
        event_old = {
            "event_id": str(uuid.uuid4()),
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "task_created",
            "payload": {"title": "Mixed Version Task"}
        }
        with open(ledger.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_old) + "\n")

        # 2. Append new event (which will have versions)
        ledger.append_event(task_id, "review_completed", {"accepted": True})

        # 3. Read it back
        record = ledger.get_task(task_id)
        assert record is not None
        assert record.title == "Mixed Version Task"
        assert record.status == "reviewed"
        # Since the second event had versions, the record should have the latest version.
        assert record.schema_version == "0.2.0"
        assert record.role_taxonomy_version == "2026-06-worker-council-v2"

def test_handoff_generated_sets_artifact_not_resolution():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "handoff_generated", {})
        record = ledger.get_task(task_id)
        assert record.artifact_status == "generated"
        assert record.task_outcome == "unresolved"

def test_local_draft_generated_sets_artifact_not_resolution():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "local_draft_generated", {})
        record = ledger.get_task(task_id)
        assert record.artifact_status == "generated"
        assert record.task_outcome == "unresolved"

def test_review_completed_can_set_resolved_task_outcome():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "review_completed", {
            "review_decision": "accepted",
            "task_outcome": "resolved"
        })
        record = ledger.get_task(task_id)
        assert record.artifact_status == "reviewed"
        assert record.task_outcome == "resolved"
        assert record.review_decision == "accepted"

def test_legacy_accepted_boolean_does_not_imply_resolved():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "review_completed", {
            "accepted": True
        })
        record = ledger.get_task(task_id)
        assert record.artifact_status == "reviewed"
        assert record.task_outcome == "unresolved"
        assert record.review_decision == "accepted"

def test_ledger_tracks_provenance_fields():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())

        ledger.append_event(task_id, "task_created", {
            "title": "Evaluate local model provenance",
        })
        ledger.append_event(task_id, "model_evaluated", {
            "backend_name": "ollama",
            "backend_uri": "http://localhost:11434",
            "execution_node": "localhost",
            "model": "qwen2.5-coder:7b"
        })

        record = ledger.get_task(task_id)

        assert record is not None
        assert record.backend_uri == "http://localhost:11434"
        assert record.execution_node == "localhost"


def test_append_signed_route_audit_event_writes_signature_metadata():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "project-steward",
            "project_steward",
            ["route_audit:sign"],
        )

        payload = {
            "decision": "allowed",
            "reason_code": "public_safe_demo",
            "privacy_level": "public",
            "privacy_scan_passed": True,
            "is_local_only": False,
            "recommended_route": "qwen_cloud",
            "selected_backend": "qwen_cloud",
        }
        written_event = ledger.append_signed_route_audit_event(
            "task-123",
            payload,
            signing_registry=registry,
            signing_agent_id="project-steward",
        )

        assert written_event["event_type"] == "route_audit"
        assert written_event["payload"] == payload
        assert written_event["signature_metadata"]["agent_id"] == "project-steward"
        assert written_event["signature_metadata"]["capability"] == "route_audit:sign"
        assert verify_route_audit_event_signature(written_event, registry) is True

        stored_events = ledger.get_events("task-123")
        assert len(stored_events) == 1
        assert "signature_metadata" in stored_events[0]
        assert verify_route_audit_event_signature(stored_events[0], registry) is True


def test_signed_route_audit_event_verification_fails_after_payload_tamper():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "validator-tools",
            "validator_tools",
            ["route_audit:sign"],
        )

        event = ledger.append_signed_route_audit_event(
            "task-456",
            {
                "decision": "allowed",
                "reason_code": "public_safe_demo",
                "privacy_level": "public",
                "privacy_scan_passed": True,
                "is_local_only": False,
                "recommended_route": "qwen_cloud",
                "selected_backend": "qwen_cloud",
            },
            signing_registry=registry,
            signing_agent_id="validator-tools",
        )

        tampered_event = dict(event)
        tampered_event["payload"] = dict(event["payload"])
        tampered_event["payload"]["decision"] = "blocked"

        assert verify_route_audit_event_signature(tampered_event, registry) is False


def test_unsigned_route_audit_events_still_work():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)

        ledger.append_event(
            "task-789",
            "route_audit",
            {
                "decision": "allowed",
                "reason_code": "legacy_unsigned_route_audit",
            },
        )

        stored_events = ledger.get_events("task-789")
        assert len(stored_events) == 1
        assert stored_events[0]["event_type"] == "route_audit"
        assert "signature_metadata" not in stored_events[0]
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        assert verify_route_audit_event_signature(stored_events[0], registry) is False


def test_signed_route_audit_event_fails_for_revoked_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "revoked-route-auditor",
            "validator_tools",
            ["route_audit:sign"],
            status=REVOKED_STATUS,
        )

        event = {
            "event_id": "evt-1",
            "task_id": "task-999",
            "timestamp": "2026-06-12T00:00:00+00:00",
            "schema_version": "0.2.0",
            "role_taxonomy_version": "2026-06-worker-council-v2",
            "event_type": "route_audit",
            "payload": {
                "decision": "allowed",
                "reason_code": "public_safe_demo",
            },
            "signature_metadata": {
                "agent_id": "revoked-route-auditor",
                "capability": "route_audit:sign",
                "payload_hash": "abc",
                "signature_algorithm": "ed25519",
                "signed_at": "2026-06-12T00:00:00+00:00",
                "signature": "ZmFrZQ==",
            },
        }

        assert verify_route_audit_event_signature(event, registry) is False


def test_append_signed_route_audit_event_fails_for_unauthorized_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "context-planner",
            "context_planner",
            ["validation_result:sign"],
        )

        with pytest.raises(UnauthorizedCapabilityError):
            ledger.append_signed_route_audit_event(
                "task-unauthorized",
                {
                    "decision": "allowed",
                    "reason_code": "public_safe_demo",
                },
                signing_registry=registry,
                signing_agent_id="context-planner",
            )


def test_append_signed_route_decision_event_writes_signature_metadata():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "router-tools",
            "router_tools",
            ["route_decision:sign"],
        )

        payload = {
            "selected_route": "local_fast",
            "reason": "bounded_local_route",
            "route_source": "resilience_router",
            "selected_backend": "ollama",
            "selected_model": "qwen2.5-coder:7b",
            "fallback_depth": 0,
        }
        written_event = ledger.append_signed_route_decision_event(
            "task-route-123",
            payload,
            signing_registry=registry,
            signing_agent_id="router-tools",
        )

        assert written_event["event_type"] == "route_decision"
        assert written_event["payload"] == payload
        assert written_event["signature_metadata"]["agent_id"] == "router-tools"
        assert written_event["signature_metadata"]["capability"] == "route_decision:sign"
        assert verify_route_decision_event_signature(written_event, registry) is True

        stored_events = ledger.get_events("task-route-123")
        assert len(stored_events) == 1
        assert "signature_metadata" in stored_events[0]
        assert verify_route_decision_event_signature(stored_events[0], registry) is True


def test_signed_route_decision_event_verification_fails_after_payload_tamper():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "router-tools",
            "router_tools",
            ["route_decision:sign"],
        )

        event = ledger.append_signed_route_decision_event(
            "task-route-456",
            {
                "selected_route": "local_fast",
                "reason": "tamper_target",
                "route_source": "resilience_router",
            },
            signing_registry=registry,
            signing_agent_id="router-tools",
        )

        tampered_event = dict(event)
        tampered_event["payload"] = dict(event["payload"])
        tampered_event["payload"]["selected_route"] = "cloud_primary"

        assert verify_route_decision_event_signature(tampered_event, registry) is False


def test_append_signed_route_decision_event_fails_for_unauthorized_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "context-planner",
            "context_planner",
            ["validation_result:sign"],
        )

        with pytest.raises(UnauthorizedCapabilityError):
            ledger.append_signed_route_decision_event(
                "task-route-unauthorized",
                {
                    "selected_route": "local_fast",
                    "reason": "public_safe_demo",
                },
                signing_registry=registry,
                signing_agent_id="context-planner",
            )


def test_append_signed_validation_result_event_writes_signature_metadata():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "validator-tools",
            "validator_tools",
            ["validation_result:sign"],
        )

        payload = {
            "validator_name": "deterministic_demo_validator",
            "validator_version": "1.0",
            "validation_status": "passed",
            "checked_files": ["triage_core/task_ledger.py"],
        }
        written_event = ledger.append_signed_validation_result_event(
            "task-validation-123",
            payload,
            signing_registry=registry,
            signing_agent_id="validator-tools",
        )

        assert written_event["event_type"] == "validation_result"
        assert written_event["payload"] == payload
        assert written_event["signature_metadata"]["agent_id"] == "validator-tools"
        assert written_event["signature_metadata"]["capability"] == "validation_result:sign"
        assert verify_validation_result_event_signature(written_event, registry) is True

        stored_events = ledger.get_events("task-validation-123")
        assert len(stored_events) == 1
        assert "signature_metadata" in stored_events[0]
        assert verify_validation_result_event_signature(stored_events[0], registry) is True


def test_signed_validation_result_event_verification_fails_after_payload_tamper():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "validator-tools",
            "validator_tools",
            ["validation_result:sign"],
        )

        event = ledger.append_signed_validation_result_event(
            "task-validation-456",
            {
                "validator_name": "deterministic_demo_validator",
                "validation_status": "passed",
                "checked_files": ["triage_core/task_ledger.py"],
            },
            signing_registry=registry,
            signing_agent_id="validator-tools",
        )

        tampered_event = dict(event)
        tampered_event["payload"] = dict(event["payload"])
        tampered_event["payload"]["validation_status"] = "failed"

        assert verify_validation_result_event_signature(tampered_event, registry) is False


def test_signed_validation_result_event_fails_for_revoked_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "revoked-validator",
            "validator_tools",
            ["validation_result:sign"],
            status=REVOKED_STATUS,
        )

        event = {
            "event_id": "evt-validation-1",
            "task_id": "task-validation-999",
            "timestamp": "2026-06-12T00:00:00+00:00",
            "schema_version": "0.2.0",
            "role_taxonomy_version": "2026-06-worker-council-v2",
            "event_type": "validation_result",
            "payload": {
                "validator_name": "deterministic_demo_validator",
                "validation_status": "passed",
            },
            "signature_metadata": {
                "agent_id": "revoked-validator",
                "capability": "validation_result:sign",
                "payload_hash": "abc",
                "signature_algorithm": "ed25519",
                "signed_at": "2026-06-12T00:00:00+00:00",
                "signature": "ZmFrZQ==",
            },
        }

        assert verify_validation_result_event_signature(event, registry) is False


def test_append_signed_validation_result_event_fails_for_unauthorized_agent():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "context-planner",
            "context_planner",
            ["route_audit:sign"],
        )

        with pytest.raises(UnauthorizedCapabilityError):
            ledger.append_signed_validation_result_event(
                "task-validation-unauthorized",
                {
                    "validator_name": "deterministic_demo_validator",
                    "validation_status": "passed",
                },
                signing_registry=registry,
                signing_agent_id="context-planner",
            )


def test_review_completed_preserves_needs_revision_end_to_end():
    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "task_created", {"title": "test task"})

        # 1. Test approved
        ledger.append_event(task_id, "review_completed", {"accepted": True, "review_decision": "accepted"})
        r = ledger.get_task(task_id)
        assert r.status == "reviewed"
        assert r.accepted is True
        assert r.review_decision == "accepted"

        # 2. Test rejected
        ledger.append_event(task_id, "review_completed", {"accepted": False, "review_decision": "rejected"})
        r = ledger.get_task(task_id)
        assert r.accepted is False
        assert r.review_decision == "rejected"

        # 3. Test needs_revision
        ledger.append_event(task_id, "review_completed", {"accepted": False, "review_decision": "needs_revision"})
        r = ledger.get_task(task_id)
        assert r.accepted is False
        assert r.review_decision == "needs_revision"

        # 4. Old-style payload without review_decision behaves compatibly
        ledger.append_event(task_id, "review_completed", {"accepted": True})
        r = ledger.get_task(task_id)
        assert r.accepted is True
        assert r.review_decision == "accepted"

        ledger.append_event(task_id, "review_completed", {"accepted": False})
        r = ledger.get_task(task_id)
        assert r.accepted is False
        assert r.review_decision == "rejected"

        # 5. Negative regression check: the reducer ignores the legacy/wrong 'decision' key and falls back to boolean-derived rejected behavior
        ledger.append_event(task_id, "review_completed", {"accepted": False, "decision": "needs_revision"})
        r = ledger.get_task(task_id)
        assert r.accepted is False
        assert r.review_decision == "rejected"
