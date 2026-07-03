import json
import sys

import pytest

from triage_core.route_worker_ledger import (
    append_route_worker_ledger_event,
    build_route_decision_recorded_event,
    build_worker_result_recorded_event,
)
from triage_core.tc_cli import main, tc_route_worker_ledger_inspect

TIMESTAMP = "2026-07-03T12:00:00+00:00"


def _route_event():
    return build_route_decision_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        selected_route="local_fast",
        backend="ollama",
        worker_class="local_worker",
        decision_basis="policy:local_ok_low_sensitivity",
        timestamp=TIMESTAMP,
    )


def _worker_event(status="succeeded"):
    return build_worker_result_recorded_event(
        task_id="task-123",
        request_id="request-abc",
        worker_id="router-tools",
        backend="ollama",
        status=status,
        timestamp=TIMESTAMP,
    )


def test_route_worker_ledger_inspect_prints_valid_mixed_summary(tmp_path, capsys):
    ledger_path = tmp_path / "route_worker_ledger.jsonl"
    append_route_worker_ledger_event(ledger_path, _route_event())
    append_route_worker_ledger_event(ledger_path, _worker_event("succeeded"))
    append_route_worker_ledger_event(ledger_path, _worker_event("blocked"))

    tc_route_worker_ledger_inspect(str(ledger_path))

    out = capsys.readouterr().out
    assert "Route/Worker Ledger Inspection" in out
    assert f"Ledger: {ledger_path}" in out
    assert "Validation: passed" in out
    assert "Total records: 3" in out
    assert "- route_decision_recorded: 1" in out
    assert "- worker_result_recorded: 2" in out
    assert "- blocked: 1" in out
    assert "- succeeded: 1" in out
    assert "Mutation: none" in out


def test_route_worker_ledger_inspect_missing_file_fails_closed(tmp_path, capsys):
    missing_path = tmp_path / "missing.jsonl"

    with pytest.raises(SystemExit) as exc:
        tc_route_worker_ledger_inspect(str(missing_path))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=ledger_not_found" in out
    assert "Traceback" not in out


def test_route_worker_ledger_inspect_malformed_json_fails_closed(tmp_path, capsys):
    ledger_path = tmp_path / "route_worker_ledger.jsonl"
    ledger_path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        tc_route_worker_ledger_inspect(str(ledger_path))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=route_worker_ledger_invalid" in out
    assert "line 1: malformed JSON" in out
    assert "Traceback" not in out


def test_route_worker_ledger_inspect_invalid_event_fails_closed(tmp_path, capsys):
    ledger_path = tmp_path / "route_worker_ledger.jsonl"
    event = _worker_event("failed")
    del event["payload"]["worker_id"]
    ledger_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        tc_route_worker_ledger_inspect(str(ledger_path))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=route_worker_ledger_invalid" in out
    assert "line 1" in out
    assert "worker_id" in out


def test_route_worker_ledger_inspect_unknown_field_fails_closed(tmp_path, capsys):
    ledger_path = tmp_path / "route_worker_ledger.jsonl"
    event = _route_event()
    event["payload"]["raw_payload"] = "should fail"
    ledger_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        tc_route_worker_ledger_inspect(str(ledger_path))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=route_worker_ledger_invalid" in out
    assert "raw_payload" in out


def test_route_worker_ledger_inspect_is_read_only(tmp_path, capsys):
    ledger_path = tmp_path / "route_worker_ledger.jsonl"
    append_route_worker_ledger_event(ledger_path, _route_event())
    before = ledger_path.read_bytes()
    before_files = sorted(path.name for path in tmp_path.iterdir())

    tc_route_worker_ledger_inspect(str(ledger_path))

    after = ledger_path.read_bytes()
    after_files = sorted(path.name for path in tmp_path.iterdir())
    assert after == before
    assert after_files == before_files
    assert "Validation: passed" in capsys.readouterr().out


def test_route_worker_ledger_inspect_cli_requires_explicit_ledger(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["tc", "route-worker-ledger", "inspect"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--ledger" in err
