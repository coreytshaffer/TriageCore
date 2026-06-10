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
- [x] Human approval remains required before implementation.
- [x] Dashboard or GUI work is explicitly deferred to a future CR or Futures Register item.
- [x] If local LLM compression is unavailable, the workflow can still generate a deterministic-only handoff bundle with a clear warning.
- [x] If clipboard copy fails, the command prints the handoff path and exits with a clear warning rather than failing silently.

## Relationship to CR-005
CR-005 creates provenance-tracked local preflight context bundles. CR-006 defines the operator workflow that makes those bundles easy to generate, open, copy, and hand off.

## Relationship to Futures Register
A full Triage Desk dashboard, hotkey system, or single-pane GUI should be recorded as future work unless separately promoted to a CR.
