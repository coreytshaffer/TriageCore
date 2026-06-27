import json

import pytest
from unittest.mock import patch

from triage_core.tc_cli import (
    tc_identity_check,
    tc_identity_init,
    tc_identity_list,
    tc_identity_revoke,
    tc_identity_rotate,
)


def test_identity_init_creates_key_and_public_metadata(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "project-steward",
            "ProjectSteward",
            ["route_audit:sign"],
        )

    out = capsys.readouterr().out
    registry_path = tmp_path / ".triagecore" / "identity" / "agents.json"
    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "project-steward.key"

    assert "Success: Initialized local identity" in out
    assert "agent_id=project-steward" in out
    assert "role=ProjectSteward" in out
    assert "capabilities=route_audit:sign" in out
    assert registry_path.exists()
    assert key_path.exists()

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert len(payload["agents"]) == 1
    metadata = payload["agents"][0]
    assert metadata["agent_id"] == "project-steward"
    assert metadata["role"] == "ProjectSteward"
    assert metadata["capabilities"] == ["route_audit:sign"]
    assert "public_key" in metadata


def test_identity_init_fails_if_identity_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "project-steward",
            "ProjectSteward",
            ["route_audit:sign"],
        )
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_identity_init(
                "project-steward",
                "ProjectSteward",
                ["route_audit:sign"],
            )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "already exists in the local registry" in out


def test_identity_list_shows_public_metadata_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "project-steward",
            "ProjectSteward",
            ["route_audit:sign"],
        )
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_list()

    out = capsys.readouterr().out
    assert "Identities: 1" in out
    assert "agent_id=project-steward" in out
    assert "role=ProjectSteward" in out
    assert "key_algorithm=ed25519" in out
    assert "capabilities=route_audit:sign" in out
    assert "PRIVATE KEY" not in out
    assert "BEGIN PRIVATE KEY" not in out
    assert ".key" not in out


def test_identity_list_when_empty_reports_no_identities(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_list()

    out = capsys.readouterr().out
    assert "No identities found in" in out


def test_identity_check_passes_for_consistent_registry(tmp_path, capsys):
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "project-steward",
            "ProjectSteward",
            ["route_audit:sign"],
        )
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_check()

    out = capsys.readouterr().out
    assert "Identity check passed" in out
    assert "identities=1" in out
    assert "keys=1" in out
    assert "missing_keys=0" in out
    assert "orphaned_keys=0" in out
    assert "permission_warnings=0" in out
    assert "PRIVATE KEY" not in out


def test_identity_check_fails_for_missing_private_key(tmp_path, capsys):
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "project-steward",
            "ProjectSteward",
            ["route_audit:sign"],
        )
    capsys.readouterr()
    key_path = (
        tmp_path
        / ".triagecore"
        / "identity"
        / "keys"
        / "project-steward.key"
    )
    key_path.unlink()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_identity_check()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Identity check failed" in out
    assert "ERROR missing_private_key agent_id=project-steward" in out


def test_identity_check_fails_for_orphaned_private_key(tmp_path, capsys):
    keys_dir = tmp_path / ".triagecore" / "identity" / "keys"
    keys_dir.mkdir(parents=True)
    (keys_dir / "orphaned-agent.key").write_text(
        "test key placeholder",
        encoding="utf-8",
    )

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_identity_check()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "orphaned_keys=1" in out
    assert "ERROR orphaned_private_key agent_id=orphaned-agent" in out
    assert "test key placeholder" not in out


def test_identity_check_fails_for_malformed_registry(tmp_path, capsys):
    identity_dir = tmp_path / ".triagecore" / "identity"
    identity_dir.mkdir(parents=True)
    (identity_dir / "agents.json").write_text("{not json\n", encoding="utf-8")

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_identity_check()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "malformed_registry=1" in out
    assert "ERROR malformed_registry" in out
    assert "{not json" not in out


def test_identity_check_reports_permission_warning_without_key_contents(
    tmp_path, capsys
):
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "project-steward",
            "ProjectSteward",
            ["route_audit:sign"],
        )
    capsys.readouterr()

    with (
        patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path),
        patch(
            "triage_core.agent_identity.check_private_key_permissions",
            return_value="permissions are inherited",
        ),
    ):
        tc_identity_check()

    out = capsys.readouterr().out
    assert "Identity check warnings" in out
    assert "permission_warnings=1" in out
    assert "WARNING private_key_permissions project-steward.key" in out
    assert "PRIVATE KEY" not in out


def test_identity_revoke_marks_identity_revoked_and_preserves_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "revocation-test-agent",
            "ProjectSteward",
            ["route_audit:sign"],
        )
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_revoke("revocation-test-agent")

    out = capsys.readouterr().out
    registry_path = tmp_path / ".triagecore" / "identity" / "agents.json"
    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "revocation-test-agent.key"
    assert "Success: Revoked local identity" in out
    assert "agent_id=revocation-test-agent" in out
    assert "status=revoked" in out
    assert key_path.exists()

    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    metadata = payload["agents"][0]
    assert metadata["agent_id"] == "revocation-test-agent"
    assert metadata["status"] == "revoked"
    assert "public_key" in metadata


def test_identity_list_shows_revoked_status(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "revocation-test-agent",
            "ProjectSteward",
            ["route_audit:sign"],
        )
        tc_identity_revoke("revocation-test-agent")
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_list()

    out = capsys.readouterr().out
    assert "agent_id=revocation-test-agent" in out
    assert "status=revoked" in out
    assert "PRIVATE KEY" not in out


def test_identity_revoke_unknown_identity_fails_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_identity_revoke("missing-agent")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error: Unknown agent identity: missing-agent" in out


def test_identity_revoke_is_idempotent_for_already_revoked_identity(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "revocation-test-agent",
            "ProjectSteward",
            ["route_audit:sign"],
        )
        tc_identity_revoke("revocation-test-agent")
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_revoke("revocation-test-agent")

    out = capsys.readouterr().out
    assert "Notice: Identity already revoked" in out
    assert "agent_id=revocation-test-agent" in out
    assert "PRIVATE KEY" not in out


def test_identity_check_passes_for_revoked_identity_with_existing_key(tmp_path, capsys):
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init(
            "revocation-test-agent",
            "ProjectSteward",
            ["route_audit:sign"],
        )
        tc_identity_revoke("revocation-test-agent")
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_check()

    out = capsys.readouterr().out
    assert "Identity check passed" in out
    assert "identities=1" in out
    assert "keys=1" in out
    assert "PRIVATE KEY" not in out


def test_identity_rotate_performs_rotation_and_prints_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_rotate("rotation-test", dry_run=False)

    out = capsys.readouterr().out
    assert "Identity rotated successfully" in out
    assert "agent_id: rotation-test" in out
    assert "old_fingerprint:" in out
    assert "new_fingerprint:" in out
    assert "active_key:" in out
    assert "archived_key:" in out


def test_identity_rotate_cli_preserves_dry_run_behavior_after_real_rotation_added(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_rotate("rotation-test", dry_run=True)

    out = capsys.readouterr().out
    assert "Identity rotation dry run" in out
    assert "agent_id: rotation-test" in out
    assert "current_status: active" in out
    assert "would_mark_current_key: rotated" in out
    assert "would_set_rotated_at:" in out
    assert "would_generate_new_key: yes" in out
    assert "would_write_registry: no" in out
    assert "would_write_private_key: no" in out
    assert "No files were modified." in out


def test_identity_rotate_dry_run_preserves_registry(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
    capsys.readouterr()

    registry_path = tmp_path / ".triagecore" / "identity" / "agents.json"
    before_content = registry_path.read_text(encoding="utf-8")

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_rotate("rotation-test", dry_run=True)

    after_content = registry_path.read_text(encoding="utf-8")
    assert before_content == after_content


def test_identity_rotate_dry_run_preserves_existing_key_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
    capsys.readouterr()

    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "rotation-test.key"
    before_content = key_path.read_text(encoding="utf-8")

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_rotate("rotation-test", dry_run=True)

    after_content = key_path.read_text(encoding="utf-8")
    assert before_content == after_content


def test_identity_rotate_dry_run_does_not_create_new_key_material(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
    capsys.readouterr()

    keys_dir = tmp_path / ".triagecore" / "identity" / "keys"
    files_before = set(keys_dir.iterdir())

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_rotate("rotation-test", dry_run=True)

    files_after = set(keys_dir.iterdir())
    assert files_before == files_after


def test_identity_rotate_dry_run_unknown_identity_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_identity_rotate("missing-agent", dry_run=True)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error: Unknown agent identity: missing-agent" in out


def test_identity_rotate_dry_run_non_active_identity_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
        tc_identity_revoke("rotation-test")
    capsys.readouterr()

    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        with pytest.raises(SystemExit) as exc:
            tc_identity_rotate("rotation-test", dry_run=True)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Cannot rotate non-active identity" in out


def test_identity_rotate_emits_audit_event_on_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
        tc_identity_rotate("rotation-test", dry_run=False)

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
    events = [json.loads(line) for line in lines if line]

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "identity_rotation"
    assert event["payload"]["agent_id"] == "rotation-test"
    assert event["payload"]["result_status"] == "success"
    assert "old_fingerprint" in event["payload"]
    assert "new_fingerprint" in event["payload"]
    assert "rotated_at" in event["payload"]
    assert "archived_key_path" in event["payload"]
    assert "active_key_path" in event["payload"]
    assert event["payload"]["source"] == "tc identity rotate"
    assert "identity-rotation-rotation-test" in event["task_id"]


def test_identity_rotate_dry_run_emits_no_audit_event(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
        tc_identity_rotate("rotation-test", dry_run=True)

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    assert not ledger_path.exists()


def test_identity_rotate_failed_rotation_emits_no_success_audit_event(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])

        from triage_core.agent_identity import AgentIdentityError
        with patch("triage_core.agent_identity.AgentIdentityRegistry.rotate_identity", side_effect=AgentIdentityError("Mock failure")):
            with pytest.raises(SystemExit):
                tc_identity_rotate("rotation-test", dry_run=False)

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    assert not ledger_path.exists()


def test_identity_rotate_repeated_rotations_produce_distinct_audit_entries(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
        tc_identity_rotate("rotation-test", dry_run=False)
        tc_identity_rotate("rotation-test", dry_run=False)

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
    events = [json.loads(line) for line in lines if line]

    assert len(events) == 2
    assert events[0]["task_id"] != events[1]["task_id"]


def test_tc_audit_renders_identity_rotation_event(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])
        tc_identity_rotate("rotation-test", dry_run=False)

    capsys.readouterr()  # clear

    from triage_core.tc_cli import tc_audit
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_audit("identity_rotation", 5)

    out = capsys.readouterr().out
    assert "identity_rotation agent=rotation-test old=" in out
    assert "status=success" in out


def test_identity_rotate_audit_failure_does_not_rerotate_or_rollback_success(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("triage_core.tc_cli._repo_root_or_cwd", return_value=tmp_path):
        tc_identity_init("rotation-test", "Role", [])

        with patch("triage_core.task_ledger.TaskLedger.append_event", side_effect=OSError("Disk full")):
            tc_identity_rotate("rotation-test", dry_run=False)

    out = capsys.readouterr().out
    assert "Identity rotated successfully" in out
    assert "Warning: Identity rotation completed, but audit event emission failed" in out
    assert "Disk full" in out
