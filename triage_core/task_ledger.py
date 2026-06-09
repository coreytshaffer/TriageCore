import csv
import dataclasses
import json
import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

LEDGER_SCHEMA_VERSION = "0.2.0"
ROLE_TAXONOMY_VERSION = "2026-06-worker-council-v2"


@dataclass
class TaskRecord:
    task_id: str
    schema_version: Optional[str] = None
    role_taxonomy_version: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    title: str = ""
    description: str = ""
    target_files: List[str] = field(default_factory=list)
    runner: Optional[str] = None
    status: str = "pending"
    study_id: Optional[str] = None
    run_id: Optional[str] = None
    permission_profile: Optional[str] = None
    risk_level: Optional[str] = None
    energy_kwh_estimate: float = 0.0
    emissions_gco2e_estimate: float = 0.0
    grid_intensity_gco2e_per_kwh: float = 0.0
    grid_intensity_source: str = "static_config"
    wasted_tokens: int = 0
    early_stopped: bool = False
    early_stop_reason: str = ""
    firewall_triggered: bool = False
    firewall_reason: str = ""
    credit_allowance_total: int = 0
    credit_allowance_used: int = 0
    credit_allowance_remaining: int = 0
    credit_allowance_exhausted: bool = False

    # Benchmark / model evaluation fields (Codex)
    backend_name: Optional[str] = None
    model: Optional[str] = None
    backend: Optional[str] = None          # alias used by worker_registry
    benchmark_task_id: Optional[str] = None
    benchmark_category: Optional[str] = None
    expected_status: Optional[str] = None
    observed_status: Optional[str] = None
    timeout_seconds: Optional[float] = None
    elapsed_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    validator_passed: Optional[bool] = None
    handoff_reason: Optional[str] = None
    human_review_required: bool = False
    accepted: bool = False
    artifact_paths: List[str] = field(default_factory=list)
    artifact_status: Optional[str] = None
    task_outcome: Optional[str] = None
    review_decision: Optional[str] = None
    selected_route: Optional[str] = None
    route_reason: Optional[str] = None
    route_source: Optional[str] = None
    fallback_depth: Optional[int] = None
    selected_backend: Optional[str] = None
    worker_result_status: Optional[str] = None
    failure_type: Optional[str] = None
    failure_stage: Optional[str] = None
    backend_failure: Optional[bool] = None
    validation_status: Optional[str] = None
    validator_name: Optional[str] = None
    validator_version: Optional[str] = None
    validator_scope: Optional[str] = None
    checked_artifacts: List[str] = field(default_factory=list)
    checked_files: List[str] = field(default_factory=list)
    reviewer_notes: Optional[str] = None
    correction_summary: Optional[str] = None
    affected_files: List[str] = field(default_factory=list)
    remaining_risk: Optional[str] = None

    # Token balance experiment / extended sustainability fields (Antigravity)
    experiment_id: Optional[str] = None
    prompt_strategy: Optional[str] = None
    context_strategy: Optional[str] = None
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    water_liters_estimate: float = 0.0
    embodied_gco2e_allocated: float = 0.0
    storage_written_mb: float = 0.0
    human_review_minutes: float = 0.0
    review_workload: str = ""
    supervisor_tool: str = ""
    supervisor_model: str = ""
    supervisor_profile: str = ""
    supervisor_decision: str = ""
    supervisor_notes: str = ""
    supervisor_artifact_path: str = ""
    supervisor_input_tokens_est: int = 0
    supervisor_output_tokens_est: int = 0
    supervisor_token_source: str = ""
    completed_at: str = ""
    retry_count: int = 0
    hardware_profile: Optional[str] = None
    duration_seconds: float = 0.0
    context_pack_path: str = ""
    context_strategy: str = ""
    context_estimated_tokens: int = 0
    context_budget_tokens: int = 0
    context_budget_status: str = ""
    context_required_items: int = 0
    context_helpful_items: int = 0
    context_optional_items: int = 0
    context_excluded_items: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task state for lightweight UI/API responses."""
        return dataclasses.asdict(self)


@dataclass
class TaskContext:
    record: TaskRecord
    events: List[Dict[str, Any]] = field(default_factory=list)
    artifact_paths: List[str] = field(default_factory=list)
    latest_artifact_text: Optional[str] = None
    telemetry_summary: Dict[str, Any] = field(default_factory=dict)
    review_summary: Dict[str, Any] = field(default_factory=dict)


class TaskLedger:
    def __init__(self, ledger_dir: str = ".triagecore"):
        self.ledger_dir = ledger_dir
        self.ledger_path = os.path.join(self.ledger_dir, "ledger.jsonl")
        try:
            os.makedirs(self.ledger_dir, exist_ok=True)
        except PermissionError as e:
            raise RuntimeError(
                f"Permission denied creating ledger directory at '{os.path.abspath(self.ledger_dir)}'. "
                "Ensure you are running TriageCore from within your project workspace, "
                "not a system directory."
            ) from e

    def append_event(self, task_id: str, event_type: str, payload: Dict[str, Any]):
        event = {
            "event_id": str(uuid.uuid4()),
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "schema_version": LEDGER_SCHEMA_VERSION,
            "role_taxonomy_version": ROLE_TAXONOMY_VERSION,
            "event_type": event_type,
            "payload": payload
        }
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        if not os.path.exists(self.ledger_path):
            return None

        record = TaskRecord(task_id=task_id)
        found = False

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("task_id") != task_id:
                    continue

                found = True
                self._apply_event(record, event)

        return record if found else None

    def get_all_tasks(self) -> List[TaskRecord]:
        if not os.path.exists(self.ledger_path) or os.path.getsize(self.ledger_path) == 0:
            return []

        tasks_map: Dict[str, TaskRecord] = {}
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                task_id = event.get("task_id")
                if not task_id:
                    continue
                if task_id not in tasks_map:
                    tasks_map[task_id] = TaskRecord(task_id=task_id)

                self._apply_event(tasks_map[task_id], event)

        return sorted(list(tasks_map.values()), key=lambda x: x.created_at, reverse=True)

    def get_events(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieve all raw events for a specific task."""
        if not os.path.exists(self.ledger_path):
            return []

        events = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    if event.get("task_id") == task_id:
                        events.append(event)
                except json.JSONDecodeError:
                    continue
        return events

    def get_task_context(self, task_id: str) -> Optional[TaskContext]:
        """Hydrate a full TaskContext object for the UI."""
        record = self.get_task(task_id)
        if not record:
            return None

        events = self.get_events(task_id)
        
        artifact_paths = list(record.artifact_paths)
        latest_text = None
        if artifact_paths:
            latest_path = artifact_paths[-1]
            if os.path.exists(latest_path):
                with open(latest_path, "r", encoding="utf-8") as f:
                    latest_text = f.read()

        total_tok = record.total_tokens or ((record.estimated_input_tokens or 0) + (record.estimated_output_tokens or 0))
        telemetry_summary = {
            "duration_seconds": record.duration_seconds,
            "energy_kwh": record.energy_kwh_estimate,
            "emissions_gco2e": record.emissions_gco2e_estimate,
            "water_liters": record.water_liters_estimate,
            "embodied_gco2e": record.embodied_gco2e_allocated,
            "total_tokens": total_tok,
            "early_stopped": record.early_stopped,
            "early_stop_reason": record.early_stop_reason,
            "firewall_triggered": record.firewall_triggered,
            "firewall_reason": record.firewall_reason,
            "credit_allowance_total": record.credit_allowance_total,
            "credit_allowance_used": record.credit_allowance_used,
            "credit_allowance_remaining": record.credit_allowance_remaining,
            "credit_allowance_exhausted": record.credit_allowance_exhausted,
            "context_estimated_tokens": record.context_estimated_tokens,
            "context_budget_tokens": record.context_budget_tokens,
            "context_budget_status": record.context_budget_status,
        }

        review_summary = {
            "status": record.status,
            "accepted": record.accepted,
            "human_review_required": record.human_review_required,
            "supervisor_tool": record.supervisor_tool,
            "supervisor_decision": record.supervisor_decision
        }

        return TaskContext(
            record=record,
            events=events,
            artifact_paths=artifact_paths,
            latest_artifact_text=latest_text,
            telemetry_summary=telemetry_summary,
            review_summary=review_summary
        )

    def get_recent_tasks(self, limit: int = 25) -> List[TaskRecord]:
        """Efficiently get the most recent tasks for list rendering."""
        return self.get_all_tasks()[:limit]

    def search_tasks(self, query: str) -> List[TaskRecord]:
        """Simple substring search across title, description, and task_id."""
        query = query.lower()
        results = []
        for task in self.get_all_tasks():
            if (query in task.task_id.lower() or 
                (task.title and query in task.title.lower()) or 
                (task.description and query in task.description.lower())):
                results.append(task)
        return results

    def _apply_event(self, record: TaskRecord, event: Dict[str, Any]) -> None:
        """Single reducer used by both get_task and get_all_tasks."""
        etype = event.get("event_type")
        payload = event.get("payload", {})
        event_timestamp = event.get("timestamp", "")
        if event_timestamp:
            record.updated_at = event_timestamp

        if "schema_version" in event:
            record.schema_version = event["schema_version"]
        if "role_taxonomy_version" in event:
            record.role_taxonomy_version = event["role_taxonomy_version"]

        if etype == "task_created":
            record.created_at = event_timestamp
            record.title = payload.get("title", "")
            record.description = payload.get("description", "")
            record.target_files = payload.get("target_files", [])
            if "study_id" in payload:
                record.study_id = payload["study_id"]
            if "run_id" in payload:
                record.run_id = payload["run_id"]
        elif etype == "task_classified":
            record.permission_profile = payload.get("recommended_profile")
            record.risk_level = payload.get("risk_level")
            if record.risk_level in ["medium", "high"]:
                record.human_review_required = True
        elif etype == "runner_selected":
            record.runner = payload.get("runner")
        elif etype in ["handoff_generated", "local_draft_generated", "council_completed"]:
            record.status = etype
            record.completed_at = event_timestamp
            record.artifact_status = "generated"
            if record.task_outcome != "resolved":
                record.task_outcome = "unresolved"
            if "artifact_path" in payload:
                record.artifact_paths.append(payload["artifact_path"])
            self._apply_model_evaluation(record, payload)
            self._apply_story_118_signals(record, payload)
            if "reason" in payload:
                record.handoff_reason = payload["reason"]
                record.human_review_required = True
            if "wasted_tokens" in payload:
                record.wasted_tokens = payload["wasted_tokens"]
        elif etype == "model_evaluated":
            self._apply_model_evaluation(record, payload)
            self._apply_story_118_signals(record, payload)
        elif etype == "validator_completed":
            record.validator_passed = payload.get("passed")
            if "validation_status" in payload:
                record.validation_status = payload["validation_status"]
            elif payload.get("passed") is True:
                record.validation_status = "passed"
            elif payload.get("passed") is False:
                record.validation_status = "failed"
            else:
                record.validation_status = "inconclusive"

            if "validator_name" in payload:
                record.validator_name = payload["validator_name"]
            if "validator_version" in payload:
                record.validator_version = payload["validator_version"]
            if "validator_scope" in payload:
                record.validator_scope = payload["validator_scope"]
            if "checked_artifacts" in payload:
                record.checked_artifacts = payload["checked_artifacts"]
            if "checked_files" in payload:
                record.checked_files = payload["checked_files"]

            if payload.get("passed"):
                record.artifact_status = "validated"
        elif etype == "energy_estimated":
            record.energy_kwh_estimate += payload.get("energy_kwh", 0.0)
            record.emissions_gco2e_estimate += payload.get("emissions_gco2e", 0.0)
            record.grid_intensity_gco2e_per_kwh = payload.get("grid_intensity_gco2e_per_kwh", 0.0)
            record.grid_intensity_source = payload.get("grid_intensity_source", record.grid_intensity_source)
            record.water_liters_estimate += payload.get("water_liters_estimate", 0.0)
            record.embodied_gco2e_allocated += payload.get("embodied_gco2e_allocated", 0.0)
            record.duration_seconds += payload.get("duration_seconds", 0.0)
        elif etype == "review_completed":
            record.status = "reviewed"
            record.accepted = payload.get("accepted", False)
            record.human_review_minutes = payload.get("human_review_minutes", 0.0)
            record.review_workload = payload.get("review_workload", "")
            record.reviewer_notes = payload.get("reviewer_notes", record.reviewer_notes)
            record.correction_summary = payload.get("correction_summary", record.correction_summary)
            if "affected_files" in payload:
                record.affected_files = payload["affected_files"]
            record.remaining_risk = payload.get("remaining_risk", record.remaining_risk)

            if "review_decision" in payload:
                record.review_decision = payload["review_decision"]
            elif "accepted" in payload:
                record.review_decision = "accepted" if payload["accepted"] else "rejected"

            if "task_outcome" in payload:
                record.task_outcome = payload["task_outcome"]
            elif "accepted" in payload:
                # Do not infer resolved from old boolean accepted
                if not record.task_outcome:
                    record.task_outcome = "unresolved"

            if record.review_decision in ["accepted", "accepted_with_minor_edits"]:
                record.artifact_status = "reviewed"
            elif record.review_decision == "rejected":
                record.artifact_status = "rejected"
        elif etype == "outcome_revised":
            if "revised_outcome" in payload:
                record.task_outcome = payload["revised_outcome"]
            record.reviewer_notes = payload.get("reason", record.reviewer_notes)
            if "affected_files" in payload:
                record.affected_files = payload["affected_files"]
        elif etype == "supervisor_reviewed":
            record.supervisor_tool = payload.get("supervisor_tool", "")
            record.supervisor_model = payload.get("supervisor_model", "")
            record.supervisor_profile = payload.get("supervisor_profile", "")
            record.supervisor_decision = payload.get("supervisor_decision", "")
            record.supervisor_notes = payload.get("supervisor_notes", "")
            record.supervisor_artifact_path = payload.get("supervisor_artifact_path", "")
            record.supervisor_input_tokens_est = payload.get("supervisor_input_tokens_est", 0)
            record.supervisor_output_tokens_est = payload.get("supervisor_output_tokens_est", 0)
            record.supervisor_token_source = payload.get("supervisor_token_source", "")
            if record.supervisor_artifact_path:
                record.artifact_paths.append(record.supervisor_artifact_path)
        elif etype == "context_budgeted":
            record.context_pack_path = payload.get("context_pack_path", "")
            record.context_strategy = payload.get("context_strategy", "")
            record.context_estimated_tokens = payload.get("context_estimated_tokens", 0)
            record.context_budget_tokens = payload.get("context_budget_tokens", 0)
            record.context_budget_status = payload.get("context_budget_status", "")
            record.context_required_items = payload.get("context_required_items", 0)
            record.context_helpful_items = payload.get("context_helpful_items", 0)
            record.context_optional_items = payload.get("context_optional_items", 0)
            record.context_excluded_items = payload.get("context_excluded_items", 0)
            if record.context_pack_path:
                record.artifact_paths.append(record.context_pack_path)
        elif etype == "route_decision":
            record.selected_route = payload.get("selected_route", record.selected_route)
            record.route_reason = payload.get("reason", record.route_reason)
            record.route_source = payload.get("route_source", record.route_source)
            if "fallback_depth" in payload:
                record.fallback_depth = payload["fallback_depth"]
            if "selected_backend" in payload:
                record.selected_backend = payload["selected_backend"]
            if "selected_model" in payload and not record.model:
                record.model = payload["selected_model"]
            if payload.get("human_review_required"):
                record.human_review_required = True
        elif etype == "worker_result":
            if "worker_result_status" in payload:
                record.worker_result_status = payload["worker_result_status"]
            if "failure_type" in payload:
                record.failure_type = payload["failure_type"]
            if "failure_stage" in payload:
                record.failure_stage = payload["failure_stage"]
            if "backend_failure" in payload:
                record.backend_failure = bool(payload["backend_failure"])
            if "validation_status" in payload:
                record.validation_status = payload["validation_status"]
            if "elapsed_seconds" in payload:
                record.elapsed_seconds = payload["elapsed_seconds"]
            if "input_tokens" in payload:
                record.input_tokens = payload["input_tokens"]
            if "output_tokens" in payload:
                record.output_tokens = payload["output_tokens"]
            if "total_tokens" in payload:
                record.total_tokens = payload["total_tokens"]
            if "tokens_per_second" in payload:
                record.tokens_per_second = payload["tokens_per_second"]
            if "selected_route" in payload:
                record.selected_route = payload["selected_route"]
            if "selected_backend" in payload:
                record.selected_backend = payload["selected_backend"]
            if "selected_model" in payload and payload["selected_model"]:
                record.model = payload["selected_model"]
        elif etype == "task_blocked":
            record.status = "blocked"
            record.handoff_reason = payload.get("reason", record.handoff_reason)
            record.human_review_required = True
            self._apply_story_118_signals(record, payload)
            if "input_tokens" in payload:
                record.input_tokens = payload["input_tokens"]
            if "output_tokens" in payload:
                record.output_tokens = payload["output_tokens"]
            if "total_tokens" in payload:
                record.total_tokens = payload["total_tokens"]
            if "wasted_tokens" in payload:
                record.wasted_tokens = payload["wasted_tokens"]

    @staticmethod
    def _apply_model_evaluation(record: TaskRecord, payload: Dict[str, Any]) -> None:
        """Apply benchmark/model evaluation fields from a payload dict."""
        if "backend_name" in payload:
            record.backend_name = payload["backend_name"]
        if "study_id" in payload:
            record.study_id = payload["study_id"]
        if "run_id" in payload:
            record.run_id = payload["run_id"]
        if "model" in payload:
            record.model = payload["model"]
        if "benchmark_task_id" in payload:
            record.benchmark_task_id = payload["benchmark_task_id"]
        if "benchmark_category" in payload:
            record.benchmark_category = payload["benchmark_category"]
        if "expected_status" in payload:
            record.expected_status = payload["expected_status"]
        if "observed_status" in payload:
            record.observed_status = payload["observed_status"]
        if "timeout_seconds" in payload:
            record.timeout_seconds = payload["timeout_seconds"]
        if "elapsed_seconds" in payload:
            record.elapsed_seconds = payload["elapsed_seconds"]
        if "input_tokens" in payload:
            record.input_tokens = payload["input_tokens"]
        if "output_tokens" in payload:
            record.output_tokens = payload["output_tokens"]
        if "total_tokens" in payload:
            record.total_tokens = payload["total_tokens"]
        if "tokens_per_second" in payload:
            record.tokens_per_second = payload["tokens_per_second"]
        if "validator_passed" in payload:
            record.validator_passed = payload["validator_passed"]
        if "handoff_reason" in payload:
            record.handoff_reason = payload["handoff_reason"]
            record.human_review_required = True
        if "wasted_tokens" in payload:
            record.wasted_tokens = payload["wasted_tokens"]
        if "worker_result_status" in payload:
            record.worker_result_status = payload["worker_result_status"]
        if "failure_type" in payload:
            record.failure_type = payload["failure_type"]
        if "failure_stage" in payload:
            record.failure_stage = payload["failure_stage"]
        if "backend_failure" in payload:
            record.backend_failure = bool(payload["backend_failure"])
        if "validation_status" in payload:
            record.validation_status = payload["validation_status"]
        if "validator_name" in payload:
            record.validator_name = payload["validator_name"]
        if "validator_version" in payload:
            record.validator_version = payload["validator_version"]
        if "validator_scope" in payload:
            record.validator_scope = payload["validator_scope"]

    @staticmethod
    def _apply_story_118_signals(record: TaskRecord, payload: Dict[str, Any]) -> None:
        """Hydrate integrated telemetry controls from explicit payload keys or stable reasons."""
        reason = (
            payload.get("early_stop_reason")
            or payload.get("firewall_reason")
            or payload.get("handoff_reason")
            or payload.get("reason")
            or ""
        )
        reason_lower = reason.lower()

        if payload.get("early_stopped") or reason_lower.startswith("early stopping:"):
            record.early_stopped = True
            record.early_stop_reason = payload.get("early_stop_reason") or reason

        if payload.get("firewall_triggered") or "ethical firewall:" in reason_lower:
            record.firewall_triggered = True
            record.firewall_reason = payload.get("firewall_reason") or reason

        if "credit_allowance_total" in payload:
            record.credit_allowance_total = payload["credit_allowance_total"] or 0
        if "credit_allowance_used" in payload:
            record.credit_allowance_used = payload["credit_allowance_used"] or 0
        if "credit_allowance_remaining" in payload:
            record.credit_allowance_remaining = payload["credit_allowance_remaining"] or 0
        if "credit_allowance_exhausted" in payload:
            record.credit_allowance_exhausted = bool(payload["credit_allowance_exhausted"])
        elif "token credit allowance exhausted" in reason_lower:
            record.credit_allowance_exhausted = True

    def export_csv(self, export_path: str):
        """Export all task records to a research-ready CSV."""
        tasks = self.get_all_tasks()
        if not tasks:
            return

        field_names = [f.name for f in dataclasses.fields(TaskRecord)]
        with open(export_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()
            for task in tasks:
                row = dataclasses.asdict(task)
                row["target_files"] = ";".join(row["target_files"]) if row["target_files"] else ""
                row["artifact_paths"] = ";".join(row["artifact_paths"]) if row["artifact_paths"] else ""
                writer.writerow(row)
