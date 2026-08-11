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
- `Status` records a CR's lifecycle or acceptance state. An `Approved` status may record acceptance of the proposal, design, or architecture for the purpose stated in the CR, but status alone does not authorize code changes.
- Code changes require explicit human implementation authority recorded for the CR and scoped to the named change plus bounded files, systems, or actions.
- Design or architecture acceptance, implementation authority, implementation acceptance, merge authority, release authority, and closeout are separate decisions unless an explicit human grant deliberately names and bundles particular stages.
- A grant explicitly defined as single-slice, single-use, or stage-bound is exhausted when its authorized action or stage is completed. No grant creates standing authority beyond its recorded scope, conditions, and duration.

## Architectural Decision Records (ADR)
Significant architectural shifts, especially those concerning privacy, routing, or task structure, must be captured in an ADR.
- ADRs reside in `docs/change/adr/`.
- They provide the context and rationale for *why* a decision was made.

## Governance Rule
Aspirational features or future architecture ideas may be tracked in the **Futures Register** (`docs/futures/futures_register.md`). However, an item in the Futures Register **does not authorize code changes**. Any implementation must first be promoted to a formal Change Request and receive human approval.
