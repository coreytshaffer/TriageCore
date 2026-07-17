import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from triage_core.build_review_integrity import canonical_json_bytes

PROJECT_ROOT = Path(__file__).parent.parent
EXPECTED_PACKET_FILES = {
    "diff-summary.json",
    "review.html",
    "review.json",
    "review.md",
    "validation-results.json",
}


def _run(command, *, cwd=None):
    return subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git(repo: Path, *args: str) -> None:
    result = _run(["git", "-C", repo, *args])
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="session")
def installed_tc(tmp_path_factory):
    venv = tmp_path_factory.mktemp("build-review-tc") / "venv"
    created = _run(
        [sys.executable, "-m", "venv", "--system-site-packages", venv]
    )
    assert created.returncode == 0, created.stderr
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    installed = _run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "-e",
            PROJECT_ROOT,
        ]
    )
    assert installed.returncode == 0, installed.stderr
    executable = scripts / ("tc.exe" if os.name == "nt" else "tc")
    assert executable.is_file()
    return executable


@pytest.fixture
def cli_case(tmp_path):
    repo = tmp_path / "subject"
    (repo / "triage_core").mkdir(parents=True)
    (repo / "triage_core" / "app.py").write_text(
        "def answer():\n    return 41\n",
        encoding="utf-8",
    )
    _git(repo, "init")
    _git(repo, "config", "user.name", "CLI Test")
    _git(repo, "config", "user.email", "cli@example.test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    (repo / "triage_core" / "app.py").write_text(
        "def answer():\n    return 42\n",
        encoding="utf-8",
    )
    request = tmp_path / "CR-TEST.md"
    request.write_text(
        "# CR-TEST — Change answer\n\n"
        "## Declared scope\n\n"
        "- `triage_core/`\n",
        encoding="utf-8",
    )
    return {
        "repo": repo,
        "request": request,
        "output": tmp_path / "packets",
    }


def _source_snapshot(repo: Path):
    return {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }


def _create(installed_tc: Path, case):
    result = _run(
        [
            installed_tc,
            "build-review",
            "create",
            "--repo",
            case["repo"],
            "--request-file",
            case["request"],
            "--base",
            "HEAD",
            "--head",
            "WORKTREE",
            "--expect",
            "triage_core/",
            "--output-dir",
            case["output"],
        ]
    )
    packet_dirs = (
        [path for path in case["output"].iterdir() if path.is_dir()]
        if case["output"].exists()
        else []
    )
    assert len(packet_dirs) == 1, result.stderr
    return result, packet_dirs[0]


def _decide(installed_tc: Path, packet: Path, status: str):
    return _run(
        [
            installed_tc,
            "build-review",
            "decide",
            packet,
            status,
            "--reviewer",
            "Build Week reviewer",
            "--note",
            f"Recorded {status} during the installed-command test.",
        ]
    )


def test_cli_creates_complete_review_packet(installed_tc, cli_case):
    before = _source_snapshot(cli_case["repo"])
    result, packet = _create(installed_tc, cli_case)

    assert result.returncode == 0
    assert result.stderr == ""
    assert {path.name for path in packet.iterdir()} == EXPECTED_PACKET_FILES
    review = json.loads((packet / "review.json").read_text(encoding="utf-8"))
    diff = json.loads(
        (packet / "diff-summary.json").read_text(encoding="utf-8")
    )
    validations = json.loads(
        (packet / "validation-results.json").read_text(encoding="utf-8")
    )
    assert review["packet_id"]
    assert packet.name == review["packet_id"]
    assert diff["review_id"] == review["packet_id"]
    assert validations["review_id"] == review["packet_id"]
    assert _source_snapshot(cli_case["repo"]) == before


def test_cli_records_approved_decision(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    result = _decide(installed_tc, packet, "approved")
    assert result.returncode == 0
    assert json.loads(
        (packet / "decision.json").read_text(encoding="utf-8")
    )["status"] == "approved"


def test_cli_records_rejected_decision(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    result = _decide(installed_tc, packet, "rejected")
    assert result.returncode == 0
    assert json.loads(
        (packet / "decision.json").read_text(encoding="utf-8")
    )["status"] == "rejected"


def test_cli_records_needs_revision_decision(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    result = _decide(installed_tc, packet, "needs_revision")
    assert result.returncode == 0
    assert json.loads(
        (packet / "decision.json").read_text(encoding="utf-8")
    )["status"] == "needs_revision"


def test_cli_refuses_decision_overwrite(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    assert _decide(installed_tc, packet, "approved").returncode == 0
    original = (packet / "decision.json").read_bytes()
    second = _decide(installed_tc, packet, "rejected")

    assert second.returncode == 1
    assert "not overwritten" in second.stderr
    assert (packet / "decision.json").read_bytes() == original


def test_cli_verifies_intact_packet(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    assert _decide(installed_tc, packet, "approved").returncode == 0
    before = {
        path.name: path.read_bytes() for path in packet.iterdir() if path.is_file()
    }

    result = _run([installed_tc, "build-review", "verify", packet])

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.startswith("VERIFIED ")
    assert "decision=approved" in result.stdout
    after = {
        path.name: path.read_bytes() for path in packet.iterdir() if path.is_file()
    }
    assert after == before


def test_cli_detects_modified_evidence(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    review_path = packet / "review.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["request"]["text"] = "Altered after review."
    review_path.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")

    result = _run([installed_tc, "build-review", "verify", packet])

    assert result.returncode == 1
    assert "evidence hash mismatch" in result.stderr


def test_cli_detects_modified_decision_reference(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    assert _decide(installed_tc, packet, "approved").returncode == 0
    decision_path = packet / "decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["evidence_sha256"] = "0" * 64
    decision_path.write_text(
        json.dumps(decision, indent=2) + "\n",
        encoding="utf-8",
    )

    result = _run([installed_tc, "build-review", "verify", packet])

    assert result.returncode == 1
    assert "does not reference the verified evidence hash" in result.stderr


def test_cli_detects_missing_artifact(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    (packet / "validation-results.json").unlink()

    result = _run([installed_tc, "build-review", "verify", packet])

    assert result.returncode == 1
    assert "missing required artifact" in result.stderr
    assert "validation-results.json" in result.stderr


def test_cli_detects_modified_derived_summary(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    summary_path = packet / "diff-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["summary"]["files_changed"] = 99
    summary_path.write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    result = _run([installed_tc, "build-review", "verify", packet])

    assert result.returncode == 1
    assert "does not match authoritative review evidence" in result.stderr


def test_cli_malformed_invocation_exits_two(installed_tc):
    result = _run([installed_tc, "build-review", "verify"])
    assert result.returncode == 2
    assert "required" in result.stderr


def test_cli_detects_malformed_and_duplicate_json(installed_tc, cli_case):
    _, packet = _create(installed_tc, cli_case)
    (packet / "review.json").write_text(
        '{"packet_id":"one","packet_id":"two"}',
        encoding="utf-8",
    )

    result = _run([installed_tc, "build-review", "verify", packet])

    assert result.returncode == 1
    assert "malformed JSON" in result.stderr
    assert "duplicate JSON key" in result.stderr


def test_cli_rejects_sensitive_packet_before_write(installed_tc, cli_case):
    result = _run(
        [
            installed_tc,
            "build-review",
            "create",
            "--repo",
            cli_case["repo"],
            "--request",
            "Send results to reviewer@example.test.",
            "--base",
            "HEAD",
            "--head",
            "WORKTREE",
            "--expect",
            "triage_core/",
            "--output-dir",
            cli_case["output"],
        ]
    )

    assert result.returncode == 1
    assert "persistent privacy invariant" in result.stderr
    assert "reviewer@example.test" not in result.stderr
    assert not cli_case["output"].exists()


def test_canonical_json_is_deterministic_and_unicode_preserving():
    first = {"z": ["é", 2], "a": {"later": True, "first": None}}
    reordered = {"a": {"first": None, "later": True}, "z": ["é", 2]}

    assert canonical_json_bytes(first) == canonical_json_bytes(reordered)
    assert canonical_json_bytes(first) == (
        '{"a":{"first":null,"later":true},"z":["é",2]}'.encode("utf-8")
    )
