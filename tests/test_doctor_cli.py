import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from triage_core.tc_cli import (
    tc_identity_check,
    tc_identity_init,
    tc_identity_doctor,
    tc_identity_revoke,
    tc_identity_rotate,
    main,
)
from triage_core.agent_identity import AgentIdentityRegistry, IdentityDoctorIssue

def run_cli_command_with_exit_code(monkeypatch, capsys, tmp_path, args):
    """Run a CLI command, returning ``(stdout, exit_code)``.

    The printed status line and the process exit code are separate contracts, and
    CR-133 turns specifically on the second one: the post-change-state trap was a
    revoked identity exiting 0 while printing no capability finding. Tests that
    assert only on stdout cannot detect that.

    ``main()`` returning without raising is a success exit, reported as 0.
    """
    monkeypatch.chdir(tmp_path)
    import sys
    exit_code = 0
    with monkeypatch.context() as m:
        m.setattr(sys, 'argv', ["tc"] + args)
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        try:
            main()
        except SystemExit as exc:
            exit_code = exc.code or 0
    return capsys.readouterr().out, exit_code


def run_cli_command(monkeypatch, capsys, tmp_path, args):
    out, _ = run_cli_command_with_exit_code(monkeypatch, capsys, tmp_path, args)
    return out

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

    out, exit_code = run_cli_command_with_exit_code(monkeypatch, capsys, tmp_path, ["identity", "doctor", "router-tools", "--for-capability", "route_decision:sign"])
    # Positive control for the revoked exit-code pins below.
    assert exit_code == 0
    assert "Identity doctor passed" in out
    assert "OK capability_ready agent_id=router-tools capability=route_decision:sign" in out


def test_doctor_capability_check_fails_when_capability_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("router-tools", "Role", ["route_audit:sign"])

    out, exit_code = run_cli_command_with_exit_code(monkeypatch, capsys, tmp_path, ["identity", "doctor", "router-tools", "--for-capability", "route_decision:sign"])
    # Negative control: a genuinely absent capability on an *active* identity still
    # exits 1 via missing_requested_capability, distinct from the revoked path.
    assert exit_code == 1
    assert "Identity doctor failed" in out
    assert "ERROR missing_requested_capability agent_id=router-tools" in out
    assert "route_decision:sign" in out


def test_doctor_fails_for_unknown_scoped_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "missing-agent", "--for-capability", "route_decision:sign"])
    assert "Identity doctor failed" in out
    assert "ERROR unknown_agent agent_id=missing-agent" in out


# --- CR-133: revoked-identity health semantics -------------------------------
#
# Accepted semantics (option (a)): LifecycleHealthy != OperationallyUsable !=
# CapabilityReady. Terminal revocation is a valid lifecycle end-state, so it is
# healthy *as revoked* while remaining unusable for capability readiness.
#
# Recorded pre-change behavior at main@770d9f2 for a revoked identity, which the
# first three cases below invert:
#     ERROR   no_active_key
#     WARNING missing_rotated_at
#     WARNING missing_archived_key
#     exit 1


def _registry_path(tmp_path):
    return tmp_path / ".triagecore" / "identity" / "agents.json"


def _mutate_registry(tmp_path, mutate):
    """Rewrite registry records directly.

    Required for compromised and multiply-revoked states: no production code path
    sets COMPROMISED_STATUS, and `identity init` refuses to re-register a revoked
    agent_id, so neither state is reachable through supported commands.
    """
    path = _registry_path(tmp_path)
    data = json.loads(path.read_text())
    mutate(data["agents"])
    path.write_text(json.dumps(data, indent=2))


def _fingerprints_by_status(tmp_path, agent_id):
    registry = AgentIdentityRegistry(ledger_dir=tmp_path / ".triagecore")
    return {
        identity.status: identity.public_key_fingerprint
        for identity in registry.load()[agent_id]
    }


def _lines_starting(out, prefix):
    return [line for line in out.splitlines() if line.startswith(prefix)]


def _setup_revoked(tmp_path, monkeypatch, capabilities=("cap:read",)):
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", list(capabilities))
        tc_identity_revoke("agent-001")


def test_doctor_passes_for_terminal_revoked_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _setup_revoked(tmp_path, monkeypatch)

    out, exit_code = run_cli_command_with_exit_code(
        monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"]
    )

    assert exit_code == 0
    assert "Identity doctor passed" in out
    assert "errors=0 warnings=0" in out
    # The three findings that previously arose from revocation are gone...
    assert "no_active_key" not in out
    assert "missing_rotated_at" not in out
    assert "missing_archived_key" not in out
    # ...but the lifecycle state is stated positively rather than merely silent,
    # so "passed" cannot be misread as "this signer is ready".
    assert "lifecycle_state=revoked" in out
    assert "operationally_usable=false" in out
    assert "capability_ready=false" in out


def test_doctor_for_capability_fails_explicitly_for_revoked_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _setup_revoked(tmp_path, monkeypatch, capabilities=["route_decision:sign"])

    out, exit_code = run_cli_command_with_exit_code(
        monkeypatch, capsys, tmp_path,
        ["identity", "doctor", "agent-001", "--for-capability", "route_decision:sign"],
    )

    # The post-change-state trap: without this pin, a revoked identity exiting 0
    # while printing no capability finding would pass the stdout assertions.
    assert exit_code == 1
    assert "Identity doctor failed" in out
    assert "ERROR revoked_identity_not_capability_ready agent_id=agent-001" in out
    # The capability *is* present in the revoked record's metadata, so reusing
    # missing_requested_capability here would assert something false.
    assert "missing_requested_capability" not in out
    assert "OK capability_ready" not in out


def test_doctor_for_capability_revoked_identity_when_capability_never_granted(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _setup_revoked(tmp_path, monkeypatch, capabilities=["route_audit:sign"])

    out, exit_code = run_cli_command_with_exit_code(
        monkeypatch, capsys, tmp_path,
        ["identity", "doctor", "agent-001", "--for-capability", "route_decision:sign"],
    )

    # Revocation is the operative reason whether or not the capability was ever
    # granted, so the diagnostic is the same and claims nothing about the grant.
    assert exit_code == 1
    assert "Identity doctor failed" in out
    assert "ERROR revoked_identity_not_capability_ready agent_id=agent-001" in out
    assert "missing_requested_capability" not in out
    assert "OK capability_ready" not in out


def test_doctor_preserves_rotated_history_checks_when_current_identity_revoked(tmp_path, monkeypatch, capsys):
    """CR-133 acceptance constraint 2: historical integrity is not globally disabled."""
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])
        tc_identity_rotate("agent-001", False)
        tc_identity_revoke("agent-001")

    fingerprints = _fingerprints_by_status(tmp_path, "agent-001")
    archived_keys = list((tmp_path / ".triagecore" / "identity" / "keys").glob("*.rotated"))
    assert len(archived_keys) == 1
    archived_keys[0].unlink()

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    # Genuine rotated history still receives archival checks...
    warnings = _lines_starting(out, "WARNING")
    assert any("missing_archived_key" in line for line in warnings)
    assert any(fingerprints["rotated"] in line for line in warnings)
    # ...while the revoked record contributes no findings of its own.
    assert not any(fingerprints["revoked"] in line for line in warnings)
    assert "no_active_key" not in out


def test_doctor_compromised_state_behavior_unchanged(tmp_path, monkeypatch, capsys):
    """CR-133 acceptance constraint 1: compromised health semantics are untouched.

    Behavioral non-change proof. These are exactly the findings a single non-active
    record produced at main@770d9f2, recorded here because no pre-existing test pins
    compromised doctor behavior.
    """
    monkeypatch.chdir(tmp_path)
    _setup_revoked(tmp_path, monkeypatch)

    def to_compromised(agents):
        for agent in agents:
            if agent["status"] == "revoked":
                agent["status"] = "compromised"

    _mutate_registry(tmp_path, to_compromised)

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    assert "Identity doctor failed" in out
    assert "ERROR no_active_key agent_id=agent-001" in out
    assert "missing_rotated_at" in out
    assert "missing_archived_key" in out
    assert "lifecycle_state=revoked" not in out


@pytest.mark.parametrize("shape", ["rotated_only", "multiply_revoked"])
def test_doctor_no_active_key_preserved_for_other_zero_active_causes(tmp_path, monkeypatch, capsys, shape):
    """CR-133 acceptance constraint 3: only accepted terminal revocation is exempt.

    Guards the predicate against being widened to "no active identity".
    """
    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_init("agent-001", "Role", ["cap:read"])
        tc_identity_rotate("agent-001", False)
        if shape == "multiply_revoked":
            tc_identity_revoke("agent-001")

    if shape == "rotated_only":
        def mutate(agents):
            for agent in agents:
                if agent["status"] == "active":
                    agent["status"] = "rotated"
                    agent["rotated_at"] = "2026-08-14T00:00:00+00:00"
    else:
        def mutate(agents):
            for agent in agents:
                agent["status"] = "revoked"

    _mutate_registry(tmp_path, mutate)

    out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    assert "Identity doctor failed" in out
    assert "ERROR no_active_key agent_id=agent-001" in out
    assert "lifecycle_state=revoked" not in out


def test_doctor_read_only_guarantee_for_revoked_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _setup_revoked(tmp_path, monkeypatch)

    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "agent-001.key"
    registry_before = _registry_path(tmp_path).read_bytes()
    key_before = key_path.read_bytes()

    run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])
    run_cli_command(
        monkeypatch, capsys, tmp_path,
        ["identity", "doctor", "agent-001", "--for-capability", "cap:read"],
    )

    # No private-key disposition is introduced or inferred by this slice.
    assert _registry_path(tmp_path).read_bytes() == registry_before
    assert key_path.read_bytes() == key_before


def test_check_and_doctor_do_not_contradict_for_revoked_state(tmp_path, monkeypatch, capsys):
    """Narrow non-contradiction for the revoked state only.

    CR-133 establishes no general rule that `check` and `doctor` must agree; it
    requires that a *contradiction* follow from a stated lifecycle rule rather than
    from incidental filter mechanics. `check` already passed for a revoked identity
    (tests/test_identity_cli.py), while `doctor` failed.
    """
    monkeypatch.chdir(tmp_path)
    _setup_revoked(tmp_path, monkeypatch)

    doctor_out = run_cli_command(monkeypatch, capsys, tmp_path, ["identity", "doctor", "agent-001"])

    with monkeypatch.context() as m:
        m.setattr("triage_core.tc_cli._repo_root_or_cwd", lambda: tmp_path)
        tc_identity_check()
    check_out = capsys.readouterr().out

    assert "Identity doctor passed" in doctor_out
    assert "Identity check passed" in check_out
