from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from triage_core.privacy_invariants import (
    FORBIDDEN_PERSISTENT_KEYS,
    PersistentPrivacyInvariantError,
    PrivacyInvariantViolation,
    assert_persistent_privacy_safe,
)

ROUTE_WORKER_LEDGER_SCHEMA_VERSION = "route-worker-ledger.v1"
ROUTE_DECISION_RECORDED = "route_decision_recorded"
WORKER_RESULT_RECORDED = "worker_result_recorded"
WORKER_RESULT_STATUSES = frozenset({"succeeded", "failed", "blocked", "skipped"})

ROUTE_WORKER_TOP_LEVEL_FIELDS = frozenset(
    {"schema_version", "event_type", "task_id", "request_id", "timestamp", "payload"}
)
ROUTE_DECISION_PAYLOAD_FIELDS = frozenset(
    {"selected_route", "backend", "worker_class", "decision_basis", "evidence_refs"}
)
WORKER_RESULT_PAYLOAD_FIELDS = frozenset(
    {
        "worker_id",
        "backend",
        "status",
        "duration_seconds",
        "error_category",
        "evidence_refs",
    }
)

PROHIBITED_ROUTE_WORKER_KEYS = FORBIDDEN_PERSISTENT_KEYS | frozenset(
    {
        "exception",
        "exception_trace",
        "model_output",
        "output",
        "raw_exception",
        "raw_exception_trace",
        "raw_model_output",
        "raw_output",
        "raw_payload",
        "stack_trace",
        "traceback",
    }
)


@dataclass(frozen=True)
class RouteWorkerLedgerValidationError(ValueError):
    """Raised when a route/worker telemetry event is unsafe or incomplete."""

    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass
class RouteWorkerLedgerInspectionSummary:
    ledger_path: str
    total_records: int = 0
    event_type_counts: dict[str, int] = field(default_factory=dict)
    worker_status_counts: dict[str, int] = field(default_factory=dict)


def build_route_decision_recorded_event(
    *,
    task_id: str,
    request_id: str,
    selected_route: str,
    backend: str,
    worker_class: str,
    decision_basis: str,
    timestamp: str,
    evidence_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a metadata-only route-decision telemetry event."""
    event = {
        "schema_version": ROUTE_WORKER_LEDGER_SCHEMA_VERSION,
        "event_type": ROUTE_DECISION_RECORDED,
        "task_id": task_id,
        "request_id": request_id,
        "timestamp": timestamp,
        "payload": {
            "selected_route": selected_route,
            "backend": backend,
            "worker_class": worker_class,
            "decision_basis": decision_basis,
            "evidence_refs": list(evidence_refs or []),
        },
    }
    validate_route_worker_ledger_event(event)
    return event


def build_worker_result_recorded_event(
    *,
    task_id: str,
    request_id: str,
    worker_id: str,
    backend: str,
    status: str,
    timestamp: str,
    duration_seconds: float | None = None,
    error_category: str | None = None,
    evidence_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a metadata-only worker-result telemetry event."""
    payload: dict[str, Any] = {
        "worker_id": worker_id,
        "backend": backend,
        "status": status,
        "evidence_refs": list(evidence_refs or []),
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = duration_seconds
    if error_category is not None:
        payload["error_category"] = error_category

    event = {
        "schema_version": ROUTE_WORKER_LEDGER_SCHEMA_VERSION,
        "event_type": WORKER_RESULT_RECORDED,
        "task_id": task_id,
        "request_id": request_id,
        "timestamp": timestamp,
        "payload": payload,
    }
    validate_route_worker_ledger_event(event)
    return event


def validate_route_worker_ledger_event(event: Mapping[str, Any]) -> None:
    """Fail closed for incomplete telemetry or unsafe persistent fields."""
    _reject_prohibited_keys(event)
    _reject_unknown_keys(event, ROUTE_WORKER_TOP_LEVEL_FIELDS, path="$")
    assert_persistent_privacy_safe(
        event,
        artifact_name="route worker ledger event",
    )

    _require_text(event, "schema_version")
    if event.get("schema_version") != ROUTE_WORKER_LEDGER_SCHEMA_VERSION:
        raise RouteWorkerLedgerValidationError("unsupported schema_version")

    event_type = _require_text(event, "event_type")
    _require_text(event, "task_id")
    _require_text(event, "request_id")
    _validate_timestamp(_require_text(event, "timestamp"))

    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        raise RouteWorkerLedgerValidationError("payload must be an object")

    if event_type == ROUTE_DECISION_RECORDED:
        _reject_unknown_keys(payload, ROUTE_DECISION_PAYLOAD_FIELDS, path="$.payload")
        _validate_route_decision_payload(payload)
    elif event_type == WORKER_RESULT_RECORDED:
        _reject_unknown_keys(payload, WORKER_RESULT_PAYLOAD_FIELDS, path="$.payload")
        _validate_worker_result_payload(payload)
    else:
        raise RouteWorkerLedgerValidationError(f"unsupported event_type: {event_type}")


def append_route_worker_ledger_event(
    ledger_path: str | Path,
    event: Mapping[str, Any],
) -> None:
    """Append one validated JSONL event without creating other artifacts."""
    validate_route_worker_ledger_event(event)
    path = Path(ledger_path)
    if not path.parent.exists():
        raise RouteWorkerLedgerValidationError("ledger parent directory does not exist")

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(event), sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def inspect_route_worker_ledger(ledger_path: str | Path) -> RouteWorkerLedgerInspectionSummary:
    """Read and summarize one explicit route/worker telemetry JSONL file."""
    path = Path(ledger_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not path.is_file():
        raise RouteWorkerLedgerValidationError("ledger path must be a file")

    summary = RouteWorkerLedgerInspectionSummary(ledger_path=str(path))
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RouteWorkerLedgerValidationError(
                    f"line {line_number}: malformed JSON ({exc.msg})"
                ) from exc
            if not isinstance(event, Mapping):
                raise RouteWorkerLedgerValidationError(
                    f"line {line_number}: event must be an object"
                )
            try:
                validate_route_worker_ledger_event(event)
            except (PersistentPrivacyInvariantError, RouteWorkerLedgerValidationError) as exc:
                raise RouteWorkerLedgerValidationError(f"line {line_number}: {exc}") from exc

            event_type = str(event["event_type"])
            summary.total_records += 1
            summary.event_type_counts[event_type] = summary.event_type_counts.get(event_type, 0) + 1
            if event_type == WORKER_RESULT_RECORDED:
                payload = event["payload"]
                status = str(payload["status"])
                summary.worker_status_counts[status] = summary.worker_status_counts.get(status, 0) + 1

    return summary


def format_route_worker_ledger_inspection(
    summary: RouteWorkerLedgerInspectionSummary,
) -> str:
    """Render a reviewer-oriented route/worker telemetry summary."""
    lines = [
        "Route/Worker Ledger Inspection",
        f"Ledger: {summary.ledger_path}",
        "Validation: passed",
        f"Total records: {summary.total_records}",
        "Event type counts:",
    ]

    if summary.event_type_counts:
        for event_type in sorted(summary.event_type_counts):
            lines.append(f"- {event_type}: {summary.event_type_counts[event_type]}")
    else:
        lines.append("- none: 0")

    lines.append("Worker result counts by status:")
    if summary.worker_status_counts:
        for status in sorted(summary.worker_status_counts):
            lines.append(f"- {status}: {summary.worker_status_counts[status]}")
    else:
        lines.append("- none: 0")

    lines.append("Mutation: none")
    return "\n".join(lines)


def _validate_route_decision_payload(payload: Mapping[str, Any]) -> None:
    _require_text(payload, "selected_route")
    _require_text(payload, "backend")
    _require_text(payload, "worker_class")
    _require_text(payload, "decision_basis")
    _validate_evidence_refs(payload.get("evidence_refs", []))


def _validate_worker_result_payload(payload: Mapping[str, Any]) -> None:
    _require_text(payload, "worker_id")
    _require_text(payload, "backend")
    status = _require_text(payload, "status")
    if status not in WORKER_RESULT_STATUSES:
        raise RouteWorkerLedgerValidationError(
            "worker result status must be one of: blocked, failed, skipped, succeeded"
        )

    if "duration_seconds" in payload:
        duration = payload["duration_seconds"]
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise RouteWorkerLedgerValidationError("duration_seconds must be numeric")
        if duration < 0:
            raise RouteWorkerLedgerValidationError("duration_seconds must be non-negative")

    if "error_category" in payload and payload["error_category"] is not None:
        _require_text(payload, "error_category")
    _validate_evidence_refs(payload.get("evidence_refs", []))


def _reject_unknown_keys(
    value: Mapping[str, Any],
    allowed_keys: frozenset[str],
    *,
    path: str,
) -> None:
    for key in value:
        key_text = str(key)
        if key_text not in allowed_keys:
            child_path = (
                f"{path}.{key_text}"
                if key_text.isidentifier()
                else f"{path}[{key_text!r}]"
            )
            raise RouteWorkerLedgerValidationError(
                f"unknown field: {child_path}"
            )


def _require_text(container: Mapping[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RouteWorkerLedgerValidationError(f"missing required field: {key}")
    return value


def _validate_evidence_refs(value: Any) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise RouteWorkerLedgerValidationError("evidence_refs must be a list of strings")
    for ref in value:
        if not isinstance(ref, str) or not ref.strip():
            raise RouteWorkerLedgerValidationError("evidence_refs must contain only non-empty strings")


def _validate_timestamp(value: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RouteWorkerLedgerValidationError("timestamp must be ISO-8601") from exc


def _reject_prohibited_keys(value: Any, *, path: str = "$") -> None:
    violations: list[PrivacyInvariantViolation] = []
    _collect_prohibited_key_violations(value, path=path, violations=violations)
    if violations:
        raise PersistentPrivacyInvariantError("route worker ledger event", violations)


def _collect_prohibited_key_violations(
    value: Any,
    *,
    path: str,
    violations: list[PrivacyInvariantViolation],
) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = (
                f"{path}.{key_text}"
                if key_text.isidentifier()
                else f"{path}[{key_text!r}]"
            )
            if key_text.lower() in PROHIBITED_ROUTE_WORKER_KEYS:
                violations.append(PrivacyInvariantViolation(path=child_path, key=key_text))
            _collect_prohibited_key_violations(
                child,
                path=child_path,
                violations=violations,
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _collect_prohibited_key_violations(
                child,
                path=f"{path}[{index}]",
                violations=violations,
            )
