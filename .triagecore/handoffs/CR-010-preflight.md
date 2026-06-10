# Handoff for CR-010

> [!WARNING]
> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.

## Task Scope
Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation. Verify source files before editing and produce a plan before code changes.

## Forbidden Scope
Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.

## Context
Task: Prepare preflight handoff for CR-010
Data: # CR-010: Audit CLI Test Hardening

## Status
Implemented

## Scope
Add robust regression tests for the `tc audit` CLI subcommand introduced in CR-009 to ensure it fails gracefully on missing files, ignores malformed JSONL lines, applies filters correctly, and never displays raw task content.

## Implementation Authority
Implemented implicitly by request.

## Description
This CR hardens the `tc audit` command against edge cases and strictly enforces privacy rules in the CLI output.

## Acceptance Criteria
- [x] Test verifies missing ledger file fails gracefully.
- [x] Test verifies malformed JSONL lines do not crash the CLI.
- [x] Test verifies `--kind route_audit` filters correctly.
- [x] Test verifies `--last 10` limits output correctly.
- [x] Test verifies raw fields (`prompt`, `data`, `content`, `raw_prompt`, `raw_data`) are never displayed.


Files:
--- docs/change/requests\CR-010-audit-cli-test-hardening.md ---
# CR-010: Audit CLI Test Hardening

## Status
Implemented

## Scope
Add robust regression tests for the `tc audit` CLI subcommand introduced in CR-009 to ensure it fails gracefully on missing files, ignores malformed JSONL lines, applies filters correctly, and never displays raw task content.

## Implementation Authority
Implemented implicitly by request.

## Description
This CR hardens the `tc audit` command against edge cases and strictly enforces privacy rules in the CLI output.

## Acceptance Criteria
- [x] Test verifies missing ledger file fails gracefully.
- [x] Test verifies malformed JSONL lines do not crash the CLI.
- [x] Test verifies `--kind route_audit` filters correctly.
- [x] Test verifies `--last 10` limits output correctly.
- [x] Test verifies raw fields (`prompt`, `data`, `content`, `raw_prompt`, `raw_data`) are never displayed.


--- docs/change/change_management.md ---
# Change Management Policy

This document defines the formal change-management system for TriageCore. Its purpose is to support small, reversible changes, maintain routing policy discipline, and ensure that all systemic modifications are intentional and human-reviewed.

## The Two Histories
TriageCore maintains two distinct types of history to avoid confusing operational data with architecture evolution:

1. **`.triagecore/ledger.jsonl` (Operational History)**:
   - This ledger tracks operational tasks and run history.
   - It records token consumption, model routing, durations, errors, and validation results for individual task executions.
   - It is an append-only log of *what the system did*.

2. **`docs/change/change_log.md` (Architecture History)**:
   - This log is a human-readable history of codebase and architecture changes.
   - It records when Change Requests (CRs) are implemented, when ADRs are ratified, and when major version shifts occur.
   - It is a log of *how the system evolved*.

## Change Requests (CR)
Any new feature, systemic adjustment, or significant code modification must be proposed as a Change Request.
- CRs reside in `docs/change/requests/`.
- A CR must define: Status, Scope, Implementation authority, Human approval requirement, and Acceptance criteria.
- Only CRs with an `Approved` status authorize code changes.

## Architectural Decision Records (ADR)
Significant architectural shifts, especially those concerning privacy, routing, or task structure, must be captured in an ADR.
- ADRs reside in `docs/change/adr/`.
- They provide the context and rationale for *why* a decision was made.

## Governance Rule
Aspirational features or future architecture ideas may be tracked in the **Futures Register** (`docs/futures/futures_register.md`). However, an item in the Futures Register **does not authorize code changes**. Any implementation must first be promoted to a formal Change Request and receive human approval.



[REMINDER: This is a compressed preflight summary and does not replace source verification. Please verify original files when making critical decisions.]

## Files Reference
- `docs/change/requests\CR-010-audit-cli-test-hardening.md` (Size: 858, Hash: 8a0c30ec)
- `docs/change/change_management.md` (Size: 1966, Hash: a6ea8335)

<!-- Tokens: Raw=928, Compressed=1000, Ratio=-0.08 -->
