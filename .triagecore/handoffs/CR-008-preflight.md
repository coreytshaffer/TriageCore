# Handoff for CR-008

> [!WARNING]
> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.

## Task Scope
Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation. Verify source files before editing and produce a plan before code changes.

## Forbidden Scope
Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.

## Context
Task: Prepare preflight handoff for CR-008
Data: # CR-008: Route Decision Audit Trail

## Status
Implemented

## Scope
Introduce a deterministic, append-only audit trail for all routing decisions made by TriageCore. This trail must record the provenance of every task packet, its privacy classification, the selected routing pathway (local vs cloud), and the justification for the selection (e.g., resilience fallback, local-only enforcement, specialist recommendation).

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Human Approval Requirement
Explicit human review of the audit schema and the mechanism for logging these decisions before they are integrated into the core `TriageClient` or `TaskLedger`.

## Description
To ensure complete transparency and accountability in the routing mechanics—especially regarding privacy boundaries (CR-004B) and safe task structures (CR-003)—we need to formally log every routing decision. Currently, the `TaskLedger` captures operational events and token usage, but the specific cryptographic or structural "proof" of why a route was chosen (and whether privacy constraints forced a fallback) requires a dedicated or enhanced audit event.

1. **Audit Schema**: Define a standard JSON schema for the route decision event.
2. **Ledger Integration**: Hook the route decision payload generated in `TriageClient.run_task` into the `TaskLedger` as an immutable entry.
3. **Traceability**: Ensure every route decision points back to the original `TaskPacket` ID and its `PrivacyReport`.

## Acceptance Criteria
- [x] A formal schema for route decision audit events is defined.
- [x] `TriageClient` logs every routing decision to the `TaskLedger` or a dedicated audit log before executing the task.
- [x] Audit logs include privacy constraints (`is_local_only`), the selected route, and the fallback depth.
- [x] Tests verify that routing events are correctly appended to the ledger for both local-only and external-safe packets.


Files:
--- docs/change/requests\CR-008-route-decision-audit-trail.md ---
# CR-008: Route Decision Audit Trail

## Status
Implemented

## Scope
Introduce a deterministic, append-only audit trail for all routing decisions made by TriageCore. This trail must record the provenance of every task packet, its privacy classification, the selected routing pathway (local vs cloud), and the justification for the selection (e.g., resilience fallback, local-only enforcement, specialist recommendation).

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Human Approval Requirement
Explicit human review of the audit schema and the mechanism for logging these decisions before they are integrated into the core `TriageClient` or `TaskLedger`.

## Description
To ensure complete transparency and accountability in the routing mechanics—especially regarding privacy boundaries (CR-004B) and safe task structures (CR-003)—we need to formally log every routing decision. Currently, the `TaskLedger` captures operational events and token usage, but the specific cryptographic or structural "proof" of why a route was chosen (and whether privacy constraints forced a fallback) requires a dedicated or enhanced audit event.

1. **Audit Schema**: Define a standard JSON schema for the route decision event.
2. **Ledger Integration**: Hook the route decision payload generated in `TriageClient.run_task` into the `TaskLedger` as an immutable entry.
3. **Traceability**: Ensure every route decision points back to the original `TaskPacket` ID and its `PrivacyReport`.

## Acceptance Criteria
- [x] A formal schema for route decision audit events is defined.
- [x] `TriageClient` logs every routing decision to the `TaskLedger` or a dedicated audit log before executing the task.
- [x] Audit logs include privacy constraints (`is_local_only`), the selected route, and the fallback depth.
- [x] Tests verify that routing events are correctly appended to the ledger for both local-only and external-safe packets.


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
- `docs/change/requests\CR-008-route-decision-audit-trail.md` (Size: 1991, Hash: c7ff3b16)
- `docs/change/change_management.md` (Size: 1966, Hash: a6ea8335)

<!-- Tokens: Raw=1493, Compressed=1565, Ratio=-0.05 -->
