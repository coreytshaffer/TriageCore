import json

import pytest
from unittest.mock import patch

from triage_core.tc_cli import tc_identity_init, tc_identity_list


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
