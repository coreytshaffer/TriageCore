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
