import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from triage_core.agent_authority import (
    load_authority_manifest,
    validate_authority_manifest,
)
from triage_core.tc_cli import tc_authority_check


def _example_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "security"
        / "examples"
        / name
    )


def test_authority_manifest_example_passes_validation():
    manifest = load_authority_manifest(
        _example_path("agent_authority_manifest_reviewer.json")
    )

    result = validate_authority_manifest(
        manifest,
        now=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )

    assert result.is_valid


def test_authority_manifest_invalid_example_fails_closed():
    manifest = load_authority_manifest(
        _example_path("agent_authority_manifest_invalid_conflict.json")
    )

    result = validate_authority_manifest(
        manifest,
        now=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )

    reasons = {issue.reason for issue in result.issues}
    assert "contradictory_action_scope" in reasons
    assert "wildcard_authority_scope" in reasons
    assert "missing_human_approval_gate" in reasons
    assert "expired_authority_manifest" in reasons


def test_authority_manifest_requires_task_scope_fields():
    manifest = {
        "schema_version": "1.0.0",
        "agent_id": "agent.local.triagecore.reviewer",
        "owner": "operator",
    }

    result = validate_authority_manifest(
        manifest,
        now=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )

    missing_paths = {
        issue.path
        for issue in result.issues
        if issue.reason == "missing_required_field"
    }
    assert "$.purpose" in missing_paths
    assert "$.allowed_actions" in missing_paths
    assert "$.expires_at" in missing_paths


def test_authority_manifest_fails_for_inactive_status():
    manifest = load_authority_manifest(
        _example_path("agent_authority_manifest_reviewer.json")
    )
    manifest["revocation_status"] = "revoked"

    result = validate_authority_manifest(
        manifest,
        now=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )

    assert any(
        issue.reason == "inactive_authority_manifest"
        for issue in result.issues
    )


def test_authority_check_cli_passes_valid_manifest(capsys):
    tc_authority_check(str(_example_path("agent_authority_manifest_reviewer.json")))

    out = capsys.readouterr().out
    assert "Agent authority manifest check passed" in out
    assert "agent_id=agent.local.triagecore.reviewer" in out
    assert "revocation_status=active" in out


def test_authority_check_cli_fails_invalid_manifest(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_authority_check(
            str(_example_path("agent_authority_manifest_invalid_conflict.json"))
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Agent authority manifest check failed" in out
    assert "reason=contradictory_action_scope" in out
    assert "reason=expired_authority_manifest" in out


def _run_authority_check_subprocess(workspace: Path) -> subprocess.CompletedProcess:
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = _example_path("agent_authority_manifest_reviewer.json")

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "authority",
            "check",
            "--manifest",
            str(fixture_path),
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )


def test_authority_cli_does_not_mutate_runtime_state(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    triagecore_dir = workspace / ".triagecore"
    triagecore_dir.mkdir()
    sentinel = triagecore_dir / "sentinel.txt"
    sentinel.write_text("preserve-me\n", encoding="utf-8")

    result = _run_authority_check_subprocess(workspace)

    assert result.returncode == 0
    assert "Agent authority manifest check passed" in result.stdout
    assert sentinel.read_text(encoding="utf-8") == "preserve-me\n"
    assert sorted(path.name for path in triagecore_dir.iterdir()) == ["sentinel.txt"]


def test_authority_check_success_output_states_boundary(capsys):
    tc_authority_check(str(_example_path("agent_authority_manifest_reviewer.json")))

    out = capsys.readouterr().out
    assert (
        "boundary=structural review evidence only; not approval, "
        "permission, authorization, a capability grant, or a "
        "substitute for human approval of one exact canonicalized "
        "action packet"
    ) in out


def test_valid_manifest_does_not_clear_pending_review_or_touch_ledger(tmp_path):
    from triage_core.review_queue import get_pending_reviews
    from triage_core.task_ledger import TaskLedger

    repo_root = Path(__file__).resolve().parents[1]
    lifecycle_fixture = (
        repo_root / "docs" / "examples" / "ledger_task_lifecycle.example.jsonl"
    )
    lifecycle_lines = [
        line
        for line in lifecycle_fixture.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # First five events end before review_completed: the task is pending review.
    pending_ledger_content = "\n".join(lifecycle_lines[:5]) + "\n"

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    triagecore_dir = workspace / ".triagecore"
    triagecore_dir.mkdir()
    ledger_path = triagecore_dir / "ledger.jsonl"
    ledger_path.write_text(pending_ledger_content, encoding="utf-8")

    pending_before = get_pending_reviews(TaskLedger(str(triagecore_dir)))
    assert [task.task_id for task in pending_before] == ["example-task-0001"]

    result = _run_authority_check_subprocess(workspace)

    assert result.returncode == 0
    assert "Agent authority manifest check passed" in result.stdout
    assert ledger_path.read_text(encoding="utf-8") == pending_ledger_content
    pending_after = get_pending_reviews(TaskLedger(str(triagecore_dir)))
    assert [task.task_id for task in pending_after] == ["example-task-0001"]


def test_valid_manifest_does_not_mutate_existing_identity_registry(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    identity_dir = workspace / ".triagecore" / "identity"
    identity_dir.mkdir(parents=True)
    registry_path = identity_dir / "agents.json"
    registry_content = (
        '{"agents": [{"agent_id": "agent.local.triagecore.reviewer", '
        '"role": "Reviewer", "public_key": "test-key", '
        '"public_key_fingerprint": "test-fingerprint", '
        '"key_algorithm": "ed25519", "capabilities": [], '
        '"created_at": "2026-07-01T00:00:00+00:00", "status": "active", '
        '"rotated_at": null}]}\n'
    )
    registry_path.write_text(registry_content, encoding="utf-8")

    result = _run_authority_check_subprocess(workspace)

    assert result.returncode == 0
    assert "Agent authority manifest check passed" in result.stdout
    assert registry_path.read_text(encoding="utf-8") == registry_content
    assert sorted(path.name for path in identity_dir.iterdir()) == ["agents.json"]
