import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from triage_core.tc_cli import tc_identity_init, tc_identity_doctor, tc_identity_rotate, main
from triage_core.agent_identity import AgentIdentityRegistry, IdentityDoctorIssue

def run_cli_command(monkeypatch, capsys, tmp_path, args):
    monkeypatch.chdir(tmp_path)
    import sys
    with monkeypatch.context() as m:
        m.setattr(sys, 'argv', ["tc"] + args)
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        try:
            main()
        except SystemExit:
            pass
    return capsys.readouterr().out

def test_doctor_healthy_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])
    assert "Identity doctor passed" in out
    assert "errors=0 warnings=0" in out

def test_doctor_read_only_guarantee(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])

    registry_path = tmp_path / ".triagecore" / "identity" / "agents.json"
    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "agent-001.key"

    reg_before = registry_path.read_bytes()
    key_before = key_path.read_bytes()

    # Run check_health directly
    registry = AgentIdentityRegistry(ledger_dir=tmp_path / ".triagecore")
    report = registry.check_health("agent-001")

    assert not report.has_errors

    reg_after = registry_path.read_bytes()
    key_after = key_path.read_bytes()

    assert reg_before == reg_after
    assert key_before == key_after

    # Corrupt key to trigger error and verify still read-only
    key_path.write_bytes(b"corrupted")
    key_before2 = key_path.read_bytes()

    run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    assert registry_path.read_bytes() == reg_after
    assert key_path.read_bytes() == key_before2

def test_doctor_alias_rotation_status(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])

    out_doctor = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])
    out_alias = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "rotation-status", "agent-001"])

    assert "Identity doctor passed" in out_doctor
    assert "Identity doctor passed" in out_alias

def test_doctor_corrupted_active_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])

    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "agent-001.key"
    key_path.write_bytes(b"invalid-pem-data")

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    assert "ERROR" in out
    assert "malformed_active_key" in out

def test_doctor_missing_active_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])

    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "agent-001.key"
    key_path.unlink()

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    assert "ERROR" in out
    assert "missing_active_key" in out

def test_doctor_multiple_active_keys(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])
        registry = AgentIdentityRegistry(ledger_dir=tmp_path / ".triagecore")
        new_identity = registry.generate_identity("agent-002", "Role", ["cap:read"])
        # Change agent_id back to agent-001 so it's a duplicate active key for agent-001

        registry_path = tmp_path / ".triagecore" / "identity" / "agents.json"
        data = json.loads(registry_path.read_text())

        # We find the agent-002 entry and move it to agent-001
        agent2_data = next(a for a in data["agents"] if a["agent_id"] == "agent-002")
        agent2_data["agent_id"] = "agent-001"
        data["agents"].append(agent2_data)
        # remove the original agent-002
        data["agents"] = [a for a in data["agents"] if a["agent_id"] == "agent-001"]
        registry_path.write_text(json.dumps(data))

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    assert "ERROR" in out
    assert "malformed_registry" in out

def test_doctor_missing_archived_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])

        # tc_identity_rotate requires --dry-run or not to just run it, main defaults to no dry run if missing
        # But wait, tc_identity_rotate doesn't exist like this exactly? Let's check imports
        tc_identity_rotate("agent-001", False)

    archived_keys = list((tmp_path / ".triagecore" / "identity" / "keys").glob("*.rotated"))
    assert len(archived_keys) == 1
    archived_keys[0].unlink()

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    assert "WARNING" in out
    assert "missing_archived_key" in out


def test_doctor_capability_check_passes_for_route_decision_signer(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("router-tools", "Role", ["route_decision:sign"])

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "router-tools", "--for-capability", "route_decision:sign"])
    assert "Identity doctor passed" in out
    assert "OK capability_ready agent_id=router-tools capability=route_decision:sign" in out


def test_doctor_capability_check_fails_when_capability_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("router-tools", "Role", ["route_audit:sign"])

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "router-tools", "--for-capability", "route_decision:sign"])
    assert "Identity doctor failed" in out
    assert "ERROR missing_requested_capability agent_id=router-tools" in out
    assert "route_decision:sign" in out


def test_doctor_fails_for_unknown_scoped_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "missing-agent", "--for-capability", "route_decision:sign"])
    assert "Identity doctor failed" in out
    assert "ERROR unknown_agent agent_id=missing-agent" in out
