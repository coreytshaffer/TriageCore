import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from triage_core.agent_identity import AgentIdentityRegistry
from triage_core.task_ledger import TaskLedger
from triage_core.tc_cli import (
    tc_audit,
    tc_audit_privacy_invariants,
    tc_audit_signed_smoke_test,
    tc_audit_self_test,
    tc_audit_verify_signatures,
    tc_identity_revoke,
)

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
    with patch("triage_core.tc_cli._ledger_path", return_value=Path("nonexistent_ledger.jsonl")):
        with pytest.raises(SystemExit) as exc:
            tc_audit("route_audit", 10)
        assert exc.value.code == 1
    
    out, err = capsys.readouterr()
    assert "Error: nonexistent_ledger.jsonl not found." in out

def test_audit_filters_by_kind_and_ignores_malformed(mock_ledger, capsys):
    with patch("triage_core.tc_cli._ledger_path", return_value=Path(mock_ledger)):
        tc_audit("route_audit", 10)
        
    out, err = capsys.readouterr()
    assert "Task: 1 | Type: route_audit" in out
    assert "Task: 2 | Type: route_audit" in out
    assert "Task: 4 | Type: route_audit" in out
    # Should not print Task 3 because it's 'other_event'
    assert "Task: 3" not in out

def test_audit_last_limits_output(mock_ledger, capsys):
    with patch("triage_core.tc_cli._ledger_path", return_value=Path(mock_ledger)):
        tc_audit("route_audit", 2)
        
    out, err = capsys.readouterr()
    # It should only print the last 2 'route_audit' events (Task 2 and 4)
    assert "Task: 1" not in out
    assert "Task: 2" in out
    assert "Task: 4" in out

def test_audit_no_raw_fields_displayed(mock_ledger, capsys):
    with patch("triage_core.tc_cli._ledger_path", return_value=Path(mock_ledger)):
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

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
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
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit_self_test()
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit("route_audit", 10)

    out, err = capsys.readouterr()
    assert "Task: audit-self-test | Type: route_audit" in out
    assert "Decision: allowed | Reason: audit_self_test" in out
    assert "Backend: self_test" in out


def test_audit_self_test_event_contains_no_raw_payload_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
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

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit_self_test()

    assert ledger_path.exists()


def test_audit_self_test_creates_parent_directory_if_needed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    ledger_dir = tmp_path / ".triagecore"
    assert not ledger_dir.exists()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit_self_test()

    assert ledger_dir.is_dir()


def test_signed_smoke_test_writes_signed_route_audit_event(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ledger_dir = tmp_path / ".triagecore"
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "project-steward",
        "ProjectSteward",
        ["route_audit:sign"],
    )

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit_signed_smoke_test("project-steward")

    out = capsys.readouterr().out
    ledger_path = ledger_dir / "ledger.jsonl"
    assert "Success: Wrote metadata-only signed route_audit smoke test event" in out
    assert "agent_id=project-steward" in out
    assert ledger_path.exists()

    records = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    record = records[0]
    payload = record["payload"]

    assert record["event_type"] == "route_audit"
    assert record["task_id"] == "audit-signed-smoke-test"
    assert record["signature_metadata"]["agent_id"] == "project-steward"
    assert record["signature_metadata"]["capability"] == "route_audit:sign"
    assert payload == {
        "decision": "allowed",
        "reason_code": "signed_smoke_test",
        "privacy_level": "public",
        "privacy_scan_passed": True,
        "is_local_only": True,
        "recommended_route": "local",
        "selected_backend": "local",
        "smoke_test": True,
    }
    for forbidden_field in ["prompt", "data", "content", "raw_prompt", "raw_data"]:
        assert forbidden_field not in payload


def test_signed_smoke_test_fails_if_identity_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_audit_signed_smoke_test("missing-agent")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error: Unknown agent identity: missing-agent" in out


def test_signed_smoke_test_fails_if_identity_lacks_route_audit_sign(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ledger_dir = tmp_path / ".triagecore"
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "project-steward",
        "ProjectSteward",
        ["validation_result:sign"],
    )

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_audit_signed_smoke_test("project-steward")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "route_audit:sign" in out


def test_signed_smoke_test_event_verifies_with_signature_audit(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ledger_dir = tmp_path / ".triagecore"
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "project-steward",
        "ProjectSteward",
        ["route_audit:sign"],
    )

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit_signed_smoke_test("project-steward")
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit_verify_signatures()

    out = capsys.readouterr().out
    assert "Route audit signature verification passed" in out
    assert "valid_signed=1" in out
    assert "invalid_signed=0" in out
    assert "unsigned=0" in out


def test_signed_smoke_test_fails_for_revoked_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        registry = AgentIdentityRegistry(ledger_dir=tmp_path / ".triagecore")
        registry.generate_identity(
            "revoked-smoke-agent",
            "ProjectSteward",
            ["route_audit:sign"],
        )
        tc_identity_revoke("revoked-smoke-agent")
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_audit_signed_smoke_test("revoked-smoke-agent")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "is not active" in out
    assert "status=revoked" in out


def test_audit_verify_signatures_fails_for_revoked_signing_identity(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "revoked-smoke-agent",
        "ProjectSteward",
        ["route_audit:sign"],
    )
    ledger.append_signed_route_audit_event(
        "signed-task",
        {
            "decision": "allowed",
            "reason_code": "revoked_identity_target",
            "privacy_level": "public",
            "privacy_scan_passed": True,
            "is_local_only": True,
            "recommended_route": "local",
            "selected_backend": "local",
        },
        signing_registry=registry,
        signing_agent_id="revoked-smoke-agent",
    )
    registry.revoke_identity("revoked-smoke-agent")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Route audit signature verification failed" in out
    assert "valid_signed=0" in out
    assert "invalid_signed=1" in out
    assert "revoked_identity_target" not in out


def test_audit_reads_repo_ledger_from_subdirectory(tmp_path, monkeypatch, capsys):
    repo = tmp_path
    ledger_dir = repo / ".triagecore"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "timestamp": "2026-06-11T00:00:00+00:00",
                "task_id": "audit-self-test",
                "event_type": "route_audit",
                "payload": {
                    "decision": "allowed",
                    "reason_code": "audit_self_test",
                    "privacy_level": "public",
                    "privacy_scan_passed": True,
                    "is_local_only": False,
                    "recommended_route": "self_test",
                    "selected_backend": "self_test",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    subdir = repo / "tests"
    subdir.mkdir()
    monkeypatch.chdir(subdir)

    with patch("subprocess.check_output") as mock_check_output:
        def fake_check_output(args, **kwargs):
            if args[:3] == ["git", "rev-parse", "--show-toplevel"]:
                return str(repo).encode("utf-8")
            raise Exception("unexpected command")

        mock_check_output.side_effect = fake_check_output
        tc_audit("route_audit", 10)

    out = capsys.readouterr().out
    assert "audit-self-test" in out
    assert "audit_self_test" in out


def test_audit_privacy_invariants_passes_safe_ledger(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-06-12T00:00:00+00:00",
                "task_id": "safe-task",
                "event_type": "route_audit",
                "payload": {
                    "decision": "allowed",
                    "reason_code": "safe_metadata_only",
                    "privacy_level": "public",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        tc_audit_privacy_invariants()

    out = capsys.readouterr().out
    assert "Privacy invariant audit passed" in out
    assert "1 record(s) checked" in out


def test_audit_privacy_invariants_fails_without_echoing_sensitive_values(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    sensitive_value = "secret raw prompt value"
    ledger_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-06-12T00:00:00+00:00",
                "task_id": "unsafe-task",
                "event_type": "route_audit",
                "payload": {
                    "decision": "blocked",
                    "nested": {
                        "raw_prompt": sensitive_value,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        with pytest.raises(SystemExit) as exc:
            tc_audit_privacy_invariants()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Privacy invariant audit failed" in out
    assert "$.payload.nested.raw_prompt" in out
    assert "raw_prompt" in out
    assert sensitive_value not in out


def test_audit_privacy_invariants_flags_malformed_json(tmp_path, capsys):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text("{not json\n", encoding="utf-8")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        with pytest.raises(SystemExit) as exc:
            tc_audit_privacy_invariants()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL line 1: malformed JSON" in out
    assert "Privacy invariant audit failed" in out


def test_audit_privacy_invariants_missing_ledger_fails(capsys):
    with patch("triage_core.tc_cli._ledger_path", return_value=Path("missing-ledger.jsonl")):
        with pytest.raises(SystemExit) as exc:
            tc_audit_privacy_invariants()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error: missing-ledger.jsonl not found." in out


def test_audit_verify_signatures_passes_with_signed_and_unsigned_route_audit(
    tmp_path, capsys
):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "project-steward",
        "project_steward",
        ["route_audit:sign"],
    )

    ledger.append_signed_route_audit_event(
        "signed-task",
        {
            "decision": "allowed",
            "reason_code": "safe_signed_route",
            "privacy_level": "public",
            "privacy_scan_passed": True,
            "is_local_only": False,
            "recommended_route": "qwen_cloud",
            "selected_backend": "qwen_cloud",
        },
        signing_registry=registry,
        signing_agent_id="project-steward",
    )
    ledger.append_event(
        "unsigned-task",
        "route_audit",
        {
            "decision": "allowed",
            "reason_code": "legacy_unsigned_route",
        },
    )
    ledger.append_event(
        "other-task",
        "other_event",
        {
            "safe_field": "still_ignored",
        },
    )

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        tc_audit_verify_signatures()

    out = capsys.readouterr().out
    assert "Route audit signature verification passed" in out
    assert "valid_signed=1" in out
    assert "invalid_signed=0" in out
    assert "unsigned=1" in out
    assert "malformed=0" in out
    assert "skipped_non_target=1" in out
    assert "safe_signed_route" not in out
    assert "legacy_unsigned_route" not in out


def test_audit_verify_signatures_fails_for_invalid_signed_route_audit(
    tmp_path, capsys
):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "validator-tools",
        "validator_tools",
        ["route_audit:sign"],
    )

    event = ledger.append_signed_route_audit_event(
        "signed-task",
        {
            "decision": "allowed",
            "reason_code": "tamper_target",
            "privacy_level": "public",
        },
        signing_registry=registry,
        signing_agent_id="validator-tools",
    )
    tampered = dict(event)
    tampered["payload"] = dict(event["payload"])
    tampered["payload"]["decision"] = "blocked"

    (ledger_dir / "ledger.jsonl").write_text(json.dumps(tampered) + "\n", encoding="utf-8")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Route audit signature verification failed" in out
    assert "valid_signed=0" in out
    assert "invalid_signed=1" in out
    assert "tamper_target" not in out


def test_audit_verify_signatures_strict_fails_on_unsigned_route_audit(
    tmp_path, capsys
):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    ledger.append_event(
        "unsigned-task",
        "route_audit",
        {
            "decision": "allowed",
            "reason_code": "legacy_only",
        },
    )

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures(strict=True)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Route audit signature verification failed" in out
    assert "unsigned=1" in out
    assert "strict=on" in out


def test_audit_verify_signatures_fails_on_malformed_json(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger_dir.mkdir(parents=True)
    ledger_path = ledger_dir / "ledger.jsonl"
    ledger_path.write_text("{not json\n", encoding="utf-8")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Route audit signature verification failed" in out
    assert "malformed=1" in out


def test_audit_verify_signatures_missing_ledger_fails(capsys):
    with patch("triage_core.tc_cli._ledger_path", return_value=Path("missing-signatures-ledger.jsonl")):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error: missing-signatures-ledger.jsonl not found." in out


def test_audit_verify_signatures_validation_result_passes_with_signed_and_unsigned_records(
    tmp_path, capsys
):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "validator-tools",
        "validator_tools",
        ["validation_result:sign"],
    )

    ledger.append_signed_validation_result_event(
        "validation-task",
        {
            "validator_name": "deterministic_demo_validator",
            "validation_status": "passed",
            "checked_files": ["triage_core/task_ledger.py"],
        },
        signing_registry=registry,
        signing_agent_id="validator-tools",
    )
    ledger.append_event(
        "validation-unsigned",
        "validation_result",
        {
            "validator_name": "legacy_validator",
            "validation_status": "passed",
        },
    )
    ledger.append_event(
        "other-task",
        "route_audit",
        {
            "decision": "allowed",
            "reason_code": "ignored_route_event",
        },
    )

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        tc_audit_verify_signatures(kind="validation_result")

    out = capsys.readouterr().out
    assert "Validation result signature verification passed" in out
    assert "event_type=validation_result" in out
    assert "valid_signed=1" in out
    assert "unsigned=1" in out
    assert "skipped_non_target=1" in out
    assert "PASS event_type=validation_result task_id=validation-task agent_id=validator-tools" in out
    assert "deterministic_demo_validator" not in out
    assert "ignored_route_event" not in out


def test_audit_verify_signatures_validation_result_fails_for_tampered_event(
    tmp_path, capsys
):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "validator-tools",
        "validator_tools",
        ["validation_result:sign"],
    )

    event = ledger.append_signed_validation_result_event(
        "validation-task",
        {
            "validator_name": "deterministic_demo_validator",
            "validation_status": "passed",
        },
        signing_registry=registry,
        signing_agent_id="validator-tools",
    )
    tampered = dict(event)
    tampered["payload"] = dict(event["payload"])
    tampered["payload"]["validation_status"] = "failed"
    (ledger_dir / "ledger.jsonl").write_text(json.dumps(tampered) + "\n", encoding="utf-8")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures(kind="validation_result")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Validation result signature verification failed" in out
    assert "FAIL event_type=validation_result task_id=validation-task agent_id=validator-tools reason=signature_mismatch" in out
    assert "deterministic_demo_validator" not in out


def test_audit_verify_signatures_validation_result_fails_for_unknown_agent(
    tmp_path, capsys
):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    ledger.append_event(
        "validation-task",
        "validation_result",
        {
            "validator_name": "deterministic_demo_validator",
            "validation_status": "passed",
        },
    )
    ledger_path = ledger_dir / "ledger.jsonl"
    event = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    event["signature_metadata"] = {
        "agent_id": "missing-validator",
        "capability": "validation_result:sign",
        "payload_hash": "abc",
        "signature_algorithm": "ed25519",
        "signed_at": "2026-06-27T00:00:00+00:00",
        "signature": "ZmFrZQ==",
    }
    ledger_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures(kind="validation_result")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Validation result signature verification failed" in out
    assert "reason=unknown_agent" in out


def test_audit_verify_signatures_validation_result_fails_for_revoked_identity(
    tmp_path, capsys
):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity(
        "revoked-validator",
        "validator_tools",
        ["validation_result:sign"],
    )
    ledger.append_signed_validation_result_event(
        "validation-task",
        {
            "validator_name": "deterministic_demo_validator",
            "validation_status": "passed",
        },
        signing_registry=registry,
        signing_agent_id="revoked-validator",
    )
    registry.revoke_identity("revoked-validator")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures(kind="validation_result")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Validation result signature verification failed" in out
    assert "reason=revoked_agent" in out


def test_audit_verify_signatures_rejects_unsupported_kind(capsys):
    with patch("triage_core.tc_cli._ledger_path", return_value=Path("ignored.jsonl")):
        with pytest.raises(SystemExit) as exc:
            tc_audit_verify_signatures(kind="other_event")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "supports only 'route_audit' or 'validation_result'" in out
