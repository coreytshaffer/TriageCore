"""
Diagnostic helper functions for TriageCore operator commands.
Provides pure or mostly-pure checks for environment, repository, and ledger state
without incurring side-effects or expanding runtime authority.
"""
import os
import subprocess
import json
import sys
from typing import Tuple, Optional

def get_git_repo_root() -> Optional[str]:
    """Returns the git repository root directory, or None if unavailable."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], 
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        return root if root else None
    except Exception:
        return None

def get_git_status() -> str:
    """Returns 'clean', 'dirty', or 'unavailable'."""
    try:
        status_out = subprocess.check_output(
            ["git", "status", "--porcelain"], 
            stderr=subprocess.DEVNULL
        ).decode('utf-8')
        return "dirty" if status_out.strip() else "clean"
    except Exception:
        return "unavailable"

def get_git_branch() -> str:
    """Returns the current git branch name or 'unavailable'."""
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        return branch if branch else "unavailable"
    except Exception:
        return "unavailable"

def get_base_dir() -> str:
    """Returns the git repo root if available, otherwise the current working directory."""
    root = get_git_repo_root()
    return root if root else os.getcwd()

def get_tc_executable_path() -> str:
    """Returns the path to the tc executable if found in PATH, otherwise 'unavailable'."""
    try:
        cmd = "where" if sys.platform == "win32" else "which"
        tc_path = subprocess.check_output(
            [cmd, "tc"], 
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip().split('\n')[0]
        return tc_path if tc_path else "unavailable"
    except Exception:
        return "unavailable"

def get_ledger_last_event_timestamp(ledger_path: str) -> str:
    """
    Parses the ledger file for the timestamp of the last recorded event.
    Returns the formatted timestamp, 'none', 'unavailable', or 'error reading ledger'.
    """
    if not os.path.exists(ledger_path):
        return "unavailable"
    try:
        with open(ledger_path, 'r', encoding='utf-8') as f:
            last_line = None
            for line in f:
                if line.strip():
                    last_line = line
            if last_line:
                last_record = json.loads(last_line)
                if "timestamp" in last_record:
                    ts = last_record["timestamp"]
                    return ts[:16].replace('T', ' ')
        return "none"
    except Exception:
        return "error reading ledger"

def get_ledger_status(ledger_path: str) -> Tuple[bool, bool, bool]:
    """Returns a tuple (exists, readable, writable) for the ledger path."""
    exists = os.path.exists(ledger_path)
    if not exists:
        return False, False, False
    readable = os.access(ledger_path, os.R_OK)
    writable = os.access(ledger_path, os.W_OK)
    return exists, readable, writable
