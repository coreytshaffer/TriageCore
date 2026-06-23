import sys
import subprocess

def test_task_envelope_preview_command_returns_success():
    result = subprocess.run(
        [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "preview"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "# EXAMPLE-CR-001 Task Envelope" in result.stdout
    assert "## Scope & Risk" in result.stdout
    assert "## Governance" in result.stdout
    assert "## Admission State" in result.stdout
    assert "**Next Allowed Action:** Close preview" in result.stdout
    assert "- None" in result.stdout  # Checks that empty lists render correctly

def test_task_envelope_preview_command_is_deterministic():
    result1 = subprocess.run(
        [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "preview"],
        capture_output=True,
        text=True,
    )
    result2 = subprocess.run(
        [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "preview"],
        capture_output=True,
        text=True,
    )
    assert result1.stdout == result2.stdout

def test_task_envelope_draft_command_returns_success():
    cmd = [
        sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft",
        "--task-id", "CR-055",
        "--title", "CLI Task Envelope Wizard Draft Mode",
        "--objective", "Draft an envelope from CLI flags.",
        "--repo", "TriageCore",
        "--operator-agent-lane", "cli-operator",
        "--route", "local-cli",
        "--risk-level", "Low",
        "--requested-capability", "read_only",
        "--allowed-file", "triage_core/tc_cli.py",
        "--allowed-file", "tests/test_task_envelope_cli.py",
        "--forbidden-area", ".triagecore/ledger.jsonl",
        "--non-scope", "file writes",
        "--approval-gates", "human review",
        "--validation-plan", "pytest",
        "--evidence", "stdout markdown",
        "--current-status", "proposed",
        "--operator-decision", "Pending",
        "--next-allowed-action", "review markdown"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "# CR-055 Task Envelope" in result.stdout
    assert "CLI Task Envelope Wizard Draft Mode" in result.stdout
    assert "triage_core/tc_cli.py" in result.stdout
    assert "tests/test_task_envelope_cli.py" in result.stdout
    assert ".triagecore/ledger.jsonl" in result.stdout
    assert "## Scope & Risk" in result.stdout
    assert "## Governance" in result.stdout
    assert "## Admission State" in result.stdout

def test_task_envelope_draft_command_missing_required_returns_nonzero():
    cmd = [
        sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft",
        "--task-id", "CR-055"
        # missing other required fields
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0

def test_task_envelope_draft_command_missing_list_field_returns_nonzero():
    cmd = [
        sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft",
        "--task-id", "CR-055",
        "--title", "CLI Task Envelope Wizard Draft Mode",
        "--objective", "Draft an envelope from CLI flags.",
        "--repo", "TriageCore",
        "--operator-agent-lane", "cli-operator",
        "--route", "local-cli",
        "--risk-level", "Low",
        "--requested-capability", "read_only",
        # missing --allowed-file
        "--forbidden-area", ".triagecore/ledger.jsonl",
        "--non-scope", "file writes",
        "--approval-gates", "human review",
        "--validation-plan", "pytest",
        "--evidence", "stdout markdown",
        "--current-status", "proposed",
        "--operator-decision", "Pending",
        "--next-allowed-action", "review markdown"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
