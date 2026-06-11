import os
import json
import pytest
from unittest.mock import patch
from triage_core.tc_cli import tc_audit, tc_audit_self_test

@pytest.fixture
def mock_ledger(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    
    events = [
        {"timestamp": "2026-06-10T10:00", "task_id": "1", "event_type": "route_audit", "payload": {"decision": "allowed", "reason_code": "ok", "privacy_level": "local_only", "privacy_scan_passed": True, "is_local_only": True, "recommended_route": "local_fast", "selected_backend": "test"}},
        {"timestamp": "2026-06-10T10:01", "task_id": "2", "event_type": "route_audit", "payload": {"decision": "blocked", "reason_code": "ambiguous", "privacy_level": "local_only", "privacy_scan_passed": True, "is_local_only": True, "recommended_route": "cloud", "selected_backend": "none"}},
        {"timestamp": "2026-06-10T10:02", "task_id": "3", "event_type": "other_event", "payload": {"safe_field": "hello", "prompt": "secret prompt", "data": "secret data", "raw_prompt": "x", "content": "x", "raw_data": "x"}},
        {"timestamp": "2026-06-10T10:03", "task_id": "4", "event_type": "route_audit", "payload": {"decision": "allowed", "reason_code": "ok2"}},
    ]
    with open(ledger_path, "w", encoding="utf-8") as f:
        # Add a malformed JSONL line to test gracefully continuing
        f.write("{malformed json\n")
        for e in events:
            f.write(json.dumps(e) + "\n")
        # Add another malformed line
        f.write("not json at all\n")
            
    return str(ledger_path)

def test_missing_ledger_fails_gracefully(capsys):
    with patch("os.path.join", return_value="nonexistent_ledger.jsonl"):
        with pytest.raises(SystemExit) as exc:
            tc_audit("route_audit", 10)
        assert exc.value.code == 1
    
    out, err = capsys.readouterr()
    assert "Error: nonexistent_ledger.jsonl not found." in out

def test_audit_filters_by_kind_and_ignores_malformed(mock_ledger, capsys):
    with patch("os.path.join", return_value=mock_ledger):
        tc_audit("route_audit", 10)
        
    out, err = capsys.readouterr()
    assert "Task: 1 | Type: route_audit" in out
    assert "Task: 2 | Type: route_audit" in out
    assert "Task: 4 | Type: route_audit" in out
    # Should not print Task 3 because it's 'other_event'
    assert "Task: 3" not in out

def test_audit_last_limits_output(mock_ledger, capsys):
    with patch("os.path.join", return_value=mock_ledger):
        tc_audit("route_audit", 2)
        
    out, err = capsys.readouterr()
    # It should only print the last 2 'route_audit' events (Task 2 and 4)
    assert "Task: 1" not in out
    assert "Task: 2" in out
    assert "Task: 4" in out

def test_audit_no_raw_fields_displayed(mock_ledger, capsys):
    with patch("os.path.join", return_value=mock_ledger):
        # Query for 'other_event'
        tc_audit("other_event", 10)
        
    out, err = capsys.readouterr()
    assert "Task: 3 | Type: other_event" in out
    assert "safe_field: hello" in out
    # Must not contain raw fields
    assert "secret prompt" not in out
    assert "prompt:" not in out
    assert "data:" not in out
    assert "secret data" not in out
    assert "raw_prompt:" not in out
    assert "content:" not in out
    assert "raw_data:" not in out


def test_audit_self_test_writes_route_audit_event(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    tc_audit_self_test()

    out, err = capsys.readouterr()
    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    assert "Success: Wrote privacy-safe route_audit self-test event" in out
    assert ledger_path.exists()

    records = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    record = records[0]
    payload = record["payload"]

    assert record["event_type"] == "route_audit"
    assert record["task_id"] == "audit-self-test"
    assert payload["decision"] == "allowed"
    assert payload["reason"] == "audit_self_test"
    assert payload["privacy_level"] == "public"
    assert payload["privacy_passed"] is True
    assert payload["local_only"] is False
    assert payload["requested_backend"] == "self_test"
    assert payload["selected_backend"] == "self_test"


def test_audit_self_test_event_is_displayed_by_kind_route_audit(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tc_audit_self_test()
    capsys.readouterr()

    tc_audit("route_audit", 10)

    out, err = capsys.readouterr()
    assert "Task: audit-self-test | Type: route_audit" in out
    assert "Decision: allowed | Reason: audit_self_test" in out
    assert "Backend: self_test" in out


def test_audit_self_test_event_contains_no_raw_payload_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    tc_audit_self_test()

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    record = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    payload = record["payload"]

    for forbidden_field in ["prompt", "data", "content", "raw_prompt", "raw_data"]:
        assert forbidden_field not in payload


def test_audit_self_test_works_when_ledger_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    assert not ledger_path.exists()

    tc_audit_self_test()

    assert ledger_path.exists()


def test_audit_self_test_creates_parent_directory_if_needed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    ledger_dir = tmp_path / ".triagecore"
    assert not ledger_dir.exists()

    tc_audit_self_test()

    assert ledger_dir.is_dir()
