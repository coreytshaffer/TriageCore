# Handoff for CR-006

> [!WARNING]
> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.

## Task Scope
Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation. Verify source files before editing and produce a plan before code changes.

## Forbidden Scope
Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.

## Context
Task: Prepare preflight handoff for CR-006
Data: # CR-006: Seamless Operator Workflow Integration

## Status
Implemented

## Scope
Define a command-oriented workflow integration for TriageCore and Antigravity. Focus on operator ergonomics, handoff artifacts, clipboard support, and repo-local handoff files.
- Do not implement UI dashboards yet unless separately approved.
- Do not implement autonomous editing.

## Implementation Authority
Not authorized until human approval.

## Human Approval Requirement
Explicit human approval required before any source code implementation.

## Description
TriageCore should support a low-friction workflow where the operator can run a small number of commands from inside Antigravity’s terminal to generate local preflight bundles, write handoff artifacts, copy prompts to clipboard, inspect latest ledger state, and run local smoke checks. This minimizes alt-tabbing and coordinates local inference workflows with Antigravity/cloud execution through explicit, human-readable handoff artifacts.

Potential commands to propose:
* `tc status`
* `tc preflight <CR_ID>`
* `tc handoff latest`
* `tc ledger latest`
* `tc smoke local`

Expected artifact path:
* `.triagecore/handoffs/latest.md`
* `.triagecore/handoffs/<CR_ID>-preflight.md`

## Acceptance Criteria
- [x] A proposed command workflow is documented.
- [x] Handoff files are repo-local and human-readable.
- [x] Latest handoff can be opened from the repo tree.
- [x] Latest handoff can be copied to clipboard by command.
- [x] Handoff includes task scope, forbidden scope, relevant files, source verification reminder, and CR-004A-compatible provenance when local LLM compression is used.
- [x] Workflow can be run from Antigravity’s integrated terminal.
- [x] Preflight and handoff commands do not edit source code.
- [x] `status`, `handoff`, `ledger`, and `preflight` commands are non-destructive and do not modify source files.
- [x] Antigravity must still verify source files before editing.
- [x] Human approval remains required before implementation.
- [x] Dashboard or GUI work is explicitly deferred to a future CR or Futures Register item.
- [x] If local LLM compression is unavailable, the workflow can still generate a deterministic-only handoff bundle with a clear warning.
- [x] If clipboard copy fails, the command prints the handoff path and exits with a clear warning rather than failing silently.

## Relationship to CR-005
CR-005 creates provenance-tracked local preflight context bundles. CR-006 defines the operator workflow that makes those bundles easy to generate, open, copy, and hand off.

## Relationship to Futures Register
A full Triage Desk dashboard, hotkey system, or single-pane GUI should be recorded as future work unless separately promoted to a CR.


Files:
--- docs/change/requests/CR-006-seamless-operator-workflow-integration.md ---
# CR-006: Seamless Operator Workflow Integration

## Status
Implemented

## Scope
Define a command-oriented workflow integration for TriageCore and Antigravity. Focus on operator ergonomics, handoff artifacts, clipboard support, and repo-local handoff files.
- Do not implement UI dashboards yet unless separately approved.
- Do not implement autonomous editing.

## Implementation Authority
Not authorized until human approval.

## Human Approval Requirement
Explicit human approval required before any source code implementation.

## Description
TriageCore should support a low-friction workflow where the operator can run a small number of commands from inside Antigravity’s terminal to generate local preflight bundles, write handoff artifacts, copy prompts to clipboard, inspect latest ledger state, and run local smoke checks. This minimizes alt-tabbing and coordinates local inference workflows with Antigravity/cloud execution through explicit, human-readable handoff artifacts.

Potential commands to propose:
* `tc status`
* `tc preflight <CR_ID>`
* `tc handoff latest`
* `tc ledger latest`
* `tc smoke local`

Expected artifact path:
* `.triagecore/handoffs/latest.md`
* `.triagecore/handoffs/<CR_ID>-preflight.md`

## Acceptance Criteria
- [x] A proposed command workflow is documented.
- [x] Handoff files are repo-local and human-readable.
- [x] Latest handoff can be opened from the repo tree.
- [x] Latest handoff can be copied to clipboard by command.
- [x] Handoff includes task scope, forbidden scope, relevant files, source verification reminder, and CR-004A-compatible provenance when local LLM compression is used.
- [x] Workflow can be run from Antigravity’s integrated terminal.
- [x] Preflight and handoff commands do not edit source code.
- [x] `status`, `handoff`, `ledger`, and `preflight` commands are non-destructive and do not modify source files.
- [x] Antigravity must still verify source files before editing.
- [x] Human approval remains required before implementat

--- triage_core/tc_cli.py ---
import argparse
import os
import sys
import glob
import subprocess
from typing import List

from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.compression import compress_context
from triage_core.config import default_config
from triage_core.backends import LocalBackend

def _find_cr_file(cr_id: str) -> str:
    # search in docs/change/requests/
    pattern = f"docs/change/requests/{cr_id}-*.md"
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    # exact match just in case
    if os.path.exists(cr_id):
        return cr_id
    return ""

def _write_handoff(filename: str, content: str):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

def _copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            process = subprocess.Popen(["clip"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(input=text.encode("utf-16"))
        elif sys.platform == "darwin":
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(input=text.encode("utf-8"))
        else:
            process = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(input=text.encode("utf-8"))
        return process.returncode == 0
    except Exception:
        return False

def tc_preflight(cr_id: str, files: List[str]):
    cr_file = _find_cr_file(cr_id)
    if not cr_file:
        print(f"Error: Could not find documentation for {cr_id}")
        sys.exit(1)

    try:
        with open(cr_file, "r", encoding="utf-8") as f:
            cr_content = f.read()
    except Exception as e:
        print(f"Error reading {cr_file}: {e}")
        sys.exit(1)

    if not files:
        files = 

--- tests/test_tc_cli.py ---
import os
import sys
import tempfile
import unittest.mock
from unittest.mock import patch, MagicMock

from triage_core.tc_cli import tc_preflight, tc_handoff

def test_tc_preflight_creates_files(tmp_path):
    cr_file = tmp_path / "CR-TEST-123.md"
    cr_file.write_text("Test CR content")
    
    with patch("triage_core.tc_cli._find_cr_file", return_value=str(cr_file)), \
         patch("triage_core.tc_cli.os.makedirs", return_value=None), \
         patch("triage_core.tc_cli._write_handoff") as mock_write, \
         patch("triage_core.tc_cli.compress_context") as mock_compress:
        
        mock_bundle = MagicMock()
        mock_bundle.summary_text = "compressed context"
        mock_bundle.warnings = []
        mock_bundle.source_files = []
        mock_bundle.provenance = None
        mock_bundle.raw_tokens = 10
        mock_bundle.compressed_tokens = 5
        mock_bundle.reduction_ratio = 0.5
        mock_compress.return_value = mock_bundle
        
        tc_preflight("CR-TEST-123", [])
        
        assert mock_write.call_count == 2
        calls = mock_write.call_args_list
        assert calls[0][0][0].endswith("CR-TEST-123-preflight.md")
        assert calls[1][0][0].endswith("latest.md")
        
        content = calls[0][0][1]
        assert "Handoff for CR-TEST-123" in content
        assert "compressed context" in content

def test_tc_preflight_deterministic_fallback(tmp_path):
    cr_file = tmp_path / "CR-TEST-123.md"
    cr_file.write_text("Test CR content")
    
    with patch("triage_core.tc_cli._find_cr_file", return_value=str(cr_file)), \
         patch("triage_core.tc_cli._write_handoff") as mock_write, \
         patch("triage_core.tc_cli.compress_context") as mock_compress:
         
        mock_bundle = MagicMock()
        mock_bundle.warnings = ["Backend unavailable"]
        mock_bundle.summary_text = "raw fallback"
        mock_bundle.source_files = []
        mock_bundle.provenance = None
        mock_bundle.raw_tokens = 10
   


[REMINDER: This is a compressed preflight summary and does not replace source verification. Please verify original files when making critical decisions.]

## Files Reference
- `docs/change/requests/CR-006-seamless-operator-workflow-integration.md` (Size: 2737, Hash: 91dc1741)
- `triage_core/tc_cli.py` (Size: 6947, Hash: 1f130069)
- `tests/test_tc_cli.py` (Size: 3345, Hash: 2fe9b50a)

<!-- Tokens: Raw=3948, Compressed=2272, Ratio=0.42 -->
