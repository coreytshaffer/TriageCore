# Handoff for CR-004B

> [!WARNING]
> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.

## Task Scope
Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation. Verify source files before editing and produce a plan before code changes.

## Forbidden Scope
Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.

## Context
Task: Prepare preflight handoff for CR-004B
Data: # CR-004B: Local-Only Privacy Routing Enforcement

## Status
Implemented

## Scope
Enforce strict routing boundaries for tasks that contain sensitive data or PII, ensuring they never leave the local trust boundary. A `VerifiedTaskPacket` that is not an `ExternalSafeTaskPacket` must be designated as local-only.

## Implementation Authority
Not authorized for implementation. This CR must be explicitly approved.

## Human Approval Requirement
Explicit human review required before enforcing routing exceptions or testing deterministic blockages of cloud routes.

## Description
CR-004B establishes a narrow routing gate before the internal routing mechanics (without rewriting `TriageRouter`). It leverages the verified packet types introduced in CR-003. 

1. **Gate Logic**: An attempt is made to cast the packet via `make_external_safe_packet()`. If it fails (due to PII, non-public data, etc.), `is_local_only` is set to `True`.
2. **Resilience Policy**: When `is_local_only = True`, the `resilience_input.privacy_level` is set to `"local_only"`, natively blocking cloud routes in `choose_resilience_route`.
3. **Fail-Closed Guard**: If a local-only packet fails execution locally or the router recommends offloading, the system must **fail closed**. It will raise a `LocalRouteUnavailableError` instead of returning a `handoff_required` payload, explicitly preventing any calling script from silently routing the payload to the cloud.

## Acceptance Criteria
- [x] A local-only packet sets `privacy_level = "local_only"` internally.
- [x] A local-only packet that experiences a local engine timeout or fallback raises `LocalRouteUnavailableError`.
- [x] An `ExternalSafeTaskPacket` that fails local execution successfully returns `handoff_required`.
- [x] A local-only packet categorized as "high risk" raises `LocalRouteUnavailableError` rather than offloading.
- [x] Zero cloud API/network calls are initiated for local-only packets.
- [x] The router mechanics (`SpecialistRouter`, `ProjectSteward`) are not broadly refactored.


Files:
--- docs/change/requests\CR-004B-local-only-privacy-routing.md ---
# CR-004B: Local-Only Privacy Routing Enforcement

## Status
Implemented

## Scope
Enforce strict routing boundaries for tasks that contain sensitive data or PII, ensuring they never leave the local trust boundary. A `VerifiedTaskPacket` that is not an `ExternalSafeTaskPacket` must be designated as local-only.

## Implementation Authority
Not authorized for implementation. This CR must be explicitly approved.

## Human Approval Requirement
Explicit human review required before enforcing routing exceptions or testing deterministic blockages of cloud routes.

## Description
CR-004B establishes a narrow routing gate before the internal routing mechanics (without rewriting `TriageRouter`). It leverages the verified packet types introduced in CR-003. 

1. **Gate Logic**: An attempt is made to cast the packet via `make_external_safe_packet()`. If it fails (due to PII, non-public data, etc.), `is_local_only` is set to `True`.
2. **Resilience Policy**: When `is_local_only = True`, the `resilience_input.privacy_level` is set to `"local_only"`, natively blocking cloud routes in `choose_resilience_route`.
3. **Fail-Closed Guard**: If a local-only packet fails execution locally or the router recommends offloading, the system must **fail closed**. It will raise a `LocalRouteUnavailableError` instead of returning a `handoff_required` payload, explicitly preventing any calling script from silently routing the payload to the cloud.

## Acceptance Criteria
- [x] A local-only packet sets `privacy_level = "local_only"` internally.
- [x] A local-only packet that experiences a local engine timeout or fallback raises `LocalRouteUnavailableError`.
- [x] An `ExternalSafeTaskPacket` that fails local execution successfully returns `handoff_required`.
- [x] A local-only packet categorized as "high risk" raises `LocalRouteUnavailableError` rather than offloading.
- [x] Zero cloud API/network calls are initiated for local-only packets.
- [x] The router mechanics (`SpecialistRouter`, `ProjectSte

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
- `docs/change/requests\CR-004B-local-only-privacy-routing.md` (Size: 2035, Hash: c5ab8951)
- `docs/change/change_management.md` (Size: 1966, Hash: a6ea8335)

<!-- Tokens: Raw=1516, Compressed=1581, Ratio=-0.04 -->
