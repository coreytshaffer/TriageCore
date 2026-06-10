# Handoff for CR-011

> [!WARNING]
> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.

## Task Scope
Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation. Verify source files before editing and produce a plan before code changes.

## Forbidden Scope
Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.

## Context
Task: Prepare preflight handoff for CR-011
Data: # CR-011: Change Request Scaffold CLI

## Status
Proposed

## Scope
Introduce a `tc propose` (or `tc scaffold`) subcommand to the `tc_cli` utility. This command will automatically generate a new boilerplate Change Request markdown file in `docs/change/requests/` and correctly assign the next sequential CR number.

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Description
Currently, when proposing a new Change Request, the operator or agent must manually identify the next available CR number by scanning `docs/change/requests/`, create the file, and copy-paste boilerplate markdown (Status, Scope, Implementation Authority, Description, Acceptance Criteria).

Adding `python -m triage_core.tc_cli propose [NAME]` will:
1. Scan the `requests/` directory for the highest existing CR number.
2. Increment the number to establish the new CR ID.
3. Generate the markdown file using a standard template.
4. Optionally prompt the user for a description or automatically append a trailing identifier (e.g., `CR-012-my-new-feature.md`).

This drastically reduces friction and ensures standardization across all Change Requests.

## Acceptance Criteria
- [ ] `tc_cli.py` supports a new `propose` (or `scaffold`) command.
- [ ] Command accurately determines the next available CR number.
- [ ] Command generates a valid Markdown file with standard headers (Status, Scope, Implementation Authority, Description, Acceptance Criteria).
- [ ] The generated file defaults to `Proposed` status.
- [ ] The command accepts an optional slug parameter (e.g., `tc propose my-new-feature` -> `CR-012-my-new-feature.md`).
- [ ] Tests verify sequence generation and correct scaffolding.


Files:
--- docs/change/requests\CR-011-change-request-scaffold-cli.md ---
# CR-011: Change Request Scaffold CLI

## Status
Proposed

## Scope
Introduce a `tc propose` (or `tc scaffold`) subcommand to the `tc_cli` utility. This command will automatically generate a new boilerplate Change Request markdown file in `docs/change/requests/` and correctly assign the next sequential CR number.

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Description
Currently, when proposing a new Change Request, the operator or agent must manually identify the next available CR number by scanning `docs/change/requests/`, create the file, and copy-paste boilerplate markdown (Status, Scope, Implementation Authority, Description, Acceptance Criteria).

Adding `python -m triage_core.tc_cli propose [NAME]` will:
1. Scan the `requests/` directory for the highest existing CR number.
2. Increment the number to establish the new CR ID.
3. Generate the markdown file using a standard template.
4. Optionally prompt the user for a description or automatically append a trailing identifier (e.g., `CR-012-my-new-feature.md`).

This drastically reduces friction and ensures standardization across all Change Requests.

## Acceptance Criteria
- [ ] `tc_cli.py` supports a new `propose` (or `scaffold`) command.
- [ ] Command accurately determines the next available CR number.
- [ ] Command generates a valid Markdown file with standard headers (Status, Scope, Implementation Authority, Description, Acceptance Criteria).
- [ ] The generated file defaults to `Proposed` status.
- [ ] The command accepts an optional slug parameter (e.g., `tc propose my-new-feature` -> `CR-012-my-new-feature.md`).
- [ ] Tests verify sequence generation and correct scaffolding.


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
- `docs/change/requests\CR-011-change-request-scaffold-cli.md` (Size: 1739, Hash: 6f2b1dfd)
- `docs/change/change_management.md` (Size: 1966, Hash: a6ea8335)

<!-- Tokens: Raw=1368, Compressed=1442, Ratio=-0.05 -->
