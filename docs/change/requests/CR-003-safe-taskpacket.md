# CR-003: Safe TaskPacket

## Status
Implemented

## Scope
Define and enforce the structure of a "Safe TaskPacket", distinguishing between:
- `VerifiedTaskPacket`: passed deterministic intake and may enter internal routing.
- `ExternalSafeTaskPacket`: minimized/redacted and may leave the local trust boundary.

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Human Approval Requirement
Explicit human review of the criteria that define a Safe TaskPacket and the transition logic from an unverified task to a safe task.

## Acceptance Criteria
- [x] A Safe TaskPacket type or state is explicitly defined.
- [x] Only Safe TaskPackets can be passed to the resilience router.
- [x] Attempts to route an unsafe task raise a clear, deterministic error.
- [x] Tests verify the state transition and enforcement boundaries.
