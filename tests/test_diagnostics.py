import pytest
import os
from unittest.mock import patch, mock_open
from triage_core.diagnostics import (
    get_git_repo_root,
    get_git_status,
    get_git_branch,
    get_ledger_status,
    get_ledger_last_event_timestamp
)

@patch("subprocess.check_output")
def test_get_git_repo_root_success(mock_check_output):
    mock_check_output.return_value = b"/mock/repo/root\n"
    assert get_git_repo_root() == "/mock/repo/root"

@patch("subprocess.check_output")
def test_get_git_repo_root_failure(mock_check_output):
    mock_check_output.side_effect = Exception("Not a git repo")
    assert get_git_repo_root() is None

@patch("subprocess.check_output")
def test_get_git_status_clean(mock_check_output):
    mock_check_output.return_value = b""
    assert get_git_status() == "clean"

@patch("subprocess.check_output")
def test_get_git_status_dirty(mock_check_output):
    mock_check_output.return_value = b" M some_file.py\n"
    assert get_git_status() == "dirty"

@patch("subprocess.check_output")
def test_get_git_branch_success(mock_check_output):
    mock_check_output.return_value = b"main\n"
    assert get_git_branch() == "main"

def test_get_ledger_status_missing():
    with patch("os.path.exists", return_value=False):
        assert get_ledger_status("/fake/ledger.jsonl") == (False, False, False)

def test_get_ledger_status_exists():
    with patch("os.path.exists", return_value=True):
        with patch("os.access", side_effect=lambda path, mode: mode == os.R_OK):
            # simulate readable but not writable
            assert get_ledger_status("/fake/ledger.jsonl") == (True, True, False)

def test_get_ledger_last_event_timestamp_missing():
    with patch("os.path.exists", return_value=False):
        assert get_ledger_last_event_timestamp("/fake/ledger.jsonl") == "unavailable"

def test_get_ledger_last_event_timestamp_valid():
    content = '{"event": "start", "timestamp": "2026-06-25T17:56:00Z"}\n{"event": "stop", "timestamp": "2026-06-25T18:00:00Z"}\n'
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=content)):
            assert get_ledger_last_event_timestamp("/fake/ledger.jsonl") == "2026-06-25 18:00"
