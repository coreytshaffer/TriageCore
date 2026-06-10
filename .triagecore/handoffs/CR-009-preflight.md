# Handoff for CR-009

> [!WARNING]
> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.

## Task Scope
Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation. Verify source files before editing and produce a plan before code changes.

## Forbidden Scope
Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.

## Context
Task: Prepare preflight handoff for CR-009
Data: # CR-009: Ledger Query / Audit Inspection CLI

## Status
Implemented

## Scope
Provide a safe, read-only CLI command (`tc audit`) to inspect recent route decision audit events. This command must only display metadata and explicitly exclude raw task payloads, prompts, or data contents to preserve privacy constraints.

## Implementation Authority
Implemented implicitly by request.

## Description
To make the `RouteDecisionAudit` records from CR-008 visible and actionable to operators without exposing raw task content, a new `audit` subcommand is added to the `triage_core.tc_cli` utility.

Usage:
`python -m triage_core.tc_cli audit --kind route_audit --last 10`

It streams the end of `.triagecore/ledger.jsonl`, filters by the given `event_type`, and prints a human-readable metadata summary.

## Acceptance Criteria
- [x] `audit` subcommand added to `tc_cli`.
- [x] Parses the `.triagecore/ledger.jsonl` file gracefully.
- [x] Provides filters like `--last` and `--kind`.
- [x] Does not print `prompt`, `data`, or `content` fields even for generic events.


Files:
--- docs/change/requests\CR-009-audit-inspection-cli.md ---
# CR-009: Ledger Query / Audit Inspection CLI

## Status
Implemented

## Scope
Provide a safe, read-only CLI command (`tc audit`) to inspect recent route decision audit events. This command must only display metadata and explicitly exclude raw task payloads, prompts, or data contents to preserve privacy constraints.

## Implementation Authority
Implemented implicitly by request.

## Description
To make the `RouteDecisionAudit` records from CR-008 visible and actionable to operators without exposing raw task content, a new `audit` subcommand is added to the `triage_core.tc_cli` utility.

Usage:
`python -m triage_core.tc_cli audit --kind route_audit --last 10`

It streams the end of `.triagecore/ledger.jsonl`, filters by the given `event_type`, and prints a human-readable metadata summary.

## Acceptance Criteria
- [x] `audit` subcommand added to `tc_cli`.
- [x] Parses the `.triagecore/ledger.jsonl` file gracefully.
- [x] Provides filters like `--last` and `--kind`.
- [x] Does not print `prompt`, `data`, or `content` fields even for generic events.


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
- `docs/change/requests\CR-009-audit-inspection-cli.md` (Size: 1063, Hash: d3495d9c)
- `docs/change/change_management.md` (Size: 1966, Hash: a6ea8335)

<!-- Tokens: Raw=1030, Compressed=1102, Ratio=-0.07 -->
