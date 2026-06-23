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
