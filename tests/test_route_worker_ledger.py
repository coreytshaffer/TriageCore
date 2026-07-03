import json

import pytest

from triage_core.privacy_invariants import PersistentPrivacyInvariantError
from triage_core.route_worker_ledger import (
    ROUTE_DECISION_RECORDED,
    WORKER_RESULT_RECORDED,
    RouteWorkerLedgerValidationError,
    append_route_worker_ledger_event,
    build_route_decision_recorded_event,
    build_worker_result_recorded_event,
    validate_route_worker_ledger_event,
)

TIMESTAMP = "2026-07-03T12:00:00+00:00"


def test_build_route_decision_recorded_event_is_metadata_only():
    event = build_route_decision_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        selected_route="local_fast",
        backend="ollama",
        worker_class="local_worker",
        decision_basis="policy:local_ok_low_sensitivity",
        timestamp=TIMESTAMP,
        evidence_refs=["ledger:route_audit:evt-1"],
    )

    assert event["event_type"] == ROUTE_DECISION_RECORDED
    assert event["task_id"] == "task-123"
    assert event["request_id"] == "request-abc"
    assert event["payload"] == {
        "selected_route": "local_fast",
        "backend": "ollama",
        "worker_class": "local_worker",
        "decision_basis": "policy:local_ok_low_sensitivity",
        "evidence_refs": ["ledger:route_audit:evt-1"],
    }
    json.dumps(event)


def test_build_worker_result_recorded_event_accepts_bounded_status_and_timing():
    event = build_worker_result_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        worker_id="router-tools",
        backend="ollama",
        status="succeeded",
        timestamp=TIMESTAMP,
        duration_seconds=1.25,
    )

    assert event["event_type"] == WORKER_RESULT_RECORDED
    assert event["payload"]["status"] == "succeeded"
    assert event["payload"]["duration_seconds"] == 1.25
    json.dumps(event)


@pytest.mark.parametrize("missing_field", ["task_id", "request_id", "timestamp"])
def test_route_worker_event_rejects_missing_top_level_required_fields(missing_field):
    event = build_route_decision_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        selected_route="local_fast",
        backend="ollama",
        worker_class="local_worker",
        decision_basis="policy:local_ok_low_sensitivity",
        timestamp=TIMESTAMP,
    )
    event[missing_field] = ""

    with pytest.raises(RouteWorkerLedgerValidationError, match=missing_field):
        validate_route_worker_ledger_event(event)


def test_route_decision_event_rejects_missing_policy_basis():
    event = build_route_decision_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        selected_route="local_fast",
        backend="ollama",
        worker_class="local_worker",
        decision_basis="policy:local_ok_low_sensitivity",
        timestamp=TIMESTAMP,
    )
    del event["payload"]["decision_basis"]

    with pytest.raises(RouteWorkerLedgerValidationError, match="decision_basis"):
        validate_route_worker_ledger_event(event)


def test_worker_result_event_rejects_unknown_status():
    with pytest.raises(RouteWorkerLedgerValidationError, match="worker result status"):
        build_worker_result_recorded_event(
            task_id="task-123",
            request_id="request-abc",
            worker_id="router-tools",
            backend="ollama",
            status="timed_out",
            timestamp=TIMESTAMP,
        )


@pytest.mark.parametrize("unsafe_key", ["prompt", "raw_payload", "raw_exception_trace", "api_key"])
def test_route_worker_event_rejects_secret_like_and_raw_payload_keys(unsafe_key):
    event = build_worker_result_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        worker_id="router-tools",
        backend="ollama",
        status="failed",
        timestamp=TIMESTAMP,
        error_category="backend_timeout",
    )
    event["payload"][unsafe_key] = "do not persist this"

    with pytest.raises(PersistentPrivacyInvariantError):
        validate_route_worker_ledger_event(event)


def test_append_route_worker_ledger_event_is_deterministic_and_bounded(tmp_path):
    ledger_path = tmp_path / "route_worker_ledger.jsonl"
    event = build_worker_result_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        worker_id="router-tools",
        backend="ollama",
        status="blocked",
        timestamp=TIMESTAMP,
        error_category="policy_handoff",
    )

    append_route_worker_ledger_event(ledger_path, event)
    append_route_worker_ledger_event(ledger_path, event)

    files = list(tmp_path.iterdir())
    assert files == [ledger_path]
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == lines[1]
    assert json.loads(lines[0]) == event


def test_append_route_worker_ledger_event_does_not_create_parent_directory(tmp_path):
    event = build_worker_result_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        worker_id="router-tools",
        backend="ollama",
        status="skipped",
        timestamp=TIMESTAMP,
    )

    with pytest.raises(RouteWorkerLedgerValidationError, match="parent directory"):
        append_route_worker_ledger_event(tmp_path / "missing" / "ledger.jsonl", event)
