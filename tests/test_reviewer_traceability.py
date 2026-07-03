"""Regression coverage for the reviewer traceability chain.

Replays the documented lifecycle fixture
(docs/examples/ledger_task_lifecycle.example.jsonl) and asserts that a
reviewer can trace input -> route decision -> evidence record -> review
state through the existing surfaces. Also drift-checks the fixture against
the TaskLedger reducer and the persistent privacy invariant.
"""

import json
from pathlib import Path
from unittest.mock import patch

from triage_core import tc_cli
from triage_core.privacy_invariants import assert_persistent_privacy_safe
from triage_core.review_queue import get_pending_reviews
from triage_core.task_ledger import TaskLedger

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "examples"
    / "ledger_task_lifecycle.example.jsonl"
)
TASK_ID = "example-task-0001"

EXPECTED_EVENT_ORDER = [
    "task_created",
    "task_classified",
    "route_decision",
    "worker_result",
    "validator_completed",
    "review_completed",
]

ENVELOPE_KEYS = {
    "event_id",
    "task_id",
    "timestamp",
    "schema_version",
    "role_taxonomy_version",
    "event_type",
    "payload",
}


def _load_fixture_events():
    events = []
    with FIXTURE_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _write_ledger(ledger_dir: Path, events) -> Path:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / "ledger.jsonl"
    with ledger_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    return ledger_path


def test_fixture_shape_and_privacy_invariant():
    events = _load_fixture_events()

    assert [event["event_type"] for event in events] == EXPECTED_EVENT_ORDER
    for event in events:
        assert ENVELOPE_KEYS.issubset(event.keys())
        assert event["task_id"] == TASK_ID
        # The fixture must stay metadata-only under the CR-021 invariant.
        assert_persistent_privacy_safe(
            event["payload"],
            artifact_name=f"lifecycle fixture event {event['event_type']}",
        )


def test_lifecycle_reduces_to_traceable_record(tmp_path):
    events = _load_fixture_events()
    _write_ledger(tmp_path, events)

    record = TaskLedger(str(tmp_path)).get_task(TASK_ID)
    assert record is not None

    # Input stage
    assert record.title == "Example lifecycle task"
    assert record.target_files == ["examples/logs_parsing.py"]

    # Classification opens the human review gate
    assert record.risk_level == "high"
    assert record.human_review_required is True

    # Route decision evidence
    assert record.selected_route == "local_heavy"
    assert record.route_reason == "sensitive task kept on local heavy route"
    assert record.route_source == "resilience_router_v1"
    assert record.fallback_depth == 0
    assert record.selected_backend == "ollama"
    assert record.model == "example-local-model"

    # Execution and validation evidence
    assert record.worker_result_status == "completed"
    assert record.validator_passed is True
    assert record.validation_status == "passed"
    assert record.validator_name == "python_syntax_validator"
    assert record.checked_files == ["examples/logs_parsing.py"]

    # Approval state
    assert record.status == "reviewed"
    assert record.review_decision == "accepted"
    assert record.task_outcome == "resolved"
    assert record.accepted is True
    assert record.artifact_status == "reviewed"


def test_review_queue_gate_opens_and_clears(tmp_path):
    events = _load_fixture_events()

    _write_ledger(tmp_path, events[:-1])
    ledger = TaskLedger(str(tmp_path))
    pending = get_pending_reviews(ledger)
    assert [task.task_id for task in pending] == [TASK_ID]

    _write_ledger(tmp_path, events)
    assert get_pending_reviews(TaskLedger(str(tmp_path))) == []


def test_tc_review_list_reflects_review_state(tmp_path, capsys):
    events = _load_fixture_events()

    ledger_path = _write_ledger(tmp_path, events[:-1])
    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        tc_cli.tc_review_list()
    out = capsys.readouterr().out
    assert "Status: available" in out
    assert f"ID: {TASK_ID}" in out

    ledger_path = _write_ledger(tmp_path, events)
    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        tc_cli.tc_review_list()
    out = capsys.readouterr().out
    assert "Status: empty" in out
