import pytest
from unittest.mock import patch
import io
import sys
import os
from triage_core.tc_cli import tc_doctor

def test_doctor_command_runs_and_prints_header():
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        tc_doctor()
    output = mock_stdout.getvalue()
    assert "TriageCore Doctor" in output
    assert "Python Executable:" in output
    assert "triage_core path:" in output
    assert "Git Status:" in output

@patch("subprocess.check_output")
def test_missing_git_repo_handled_gracefully(mock_subprocess):
    # Simulate git error
    mock_subprocess.side_effect = Exception("Git not found")
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        tc_doctor()
    output = mock_stdout.getvalue()
    assert "Git Repo Root: unavailable" in output
    assert "Git Branch: unavailable" in output
    assert "Git Status: unavailable" in output

def test_scratch_exclusion_detection(tmp_path):
    # Create a dummy pyproject.toml
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[tool.pytest.ini_options]\nnorecursedirs = ["scratch"]\n', encoding="utf-8")
    
    with patch("os.getcwd", return_value=str(tmp_path)):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            tc_doctor()
        output = mock_stdout.getvalue()
        assert "Scratch Excluded: yes" in output
        assert "pytest config:" in output
