import csv
import dataclasses
import json
import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class TaskRecord:
    task_id: str
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

    def _apply_event(self, record: TaskRecord, event: Dict[str, Any]) -> None:
        """Single reducer used by both get_task and get_all_tasks."""
        etype = event.get("event_type")
        payload = event.get("payload", {})
        event_timestamp = event.get("timestamp", "")
        if event_timestamp:
            record.updated_at = event_timestamp

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
            if "artifact_path" in payload:
                record.artifact_paths.append(payload["artifact_path"])
            self._apply_model_evaluation(record, payload)
            if "reason" in payload:
                record.handoff_reason = payload["reason"]
                record.human_review_required = True
        elif etype == "model_evaluated":
            self._apply_model_evaluation(record, payload)
        elif etype == "validator_completed":
            record.validator_passed = payload.get("passed")
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
        elif etype == "task_blocked":
            record.status = "blocked"
            record.handoff_reason = payload.get("reason", record.handoff_reason)
            record.human_review_required = True

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
