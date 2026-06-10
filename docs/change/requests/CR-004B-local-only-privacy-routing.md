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
- [x] The router mechanics (`SpecialistRouter`, `ProjectSteward`) are not broadly refactored.
