import json

import pytest
from unittest.mock import patch

from triage_core.tc_cli import (
    tc_identity_check,
    tc_identity_init,
    tc_identity_list,
    tc_identity_revoke,
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
