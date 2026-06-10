# CR-001: TaskPacket Privacy Metadata

## Status
Implemented

## Scope
Introduce privacy metadata fields to the TaskPacket structure to support deterministic privacy scanning and routing.

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Human Approval Requirement
Explicit human review and approval of the metadata schema and its integration points in the routing logic.

## Acceptance Criteria
- [x] Privacy metadata schema is defined and documented.
- [x] TaskPacket structure is updated to include the metadata fields.
- [x] Existing tests are updated to handle the new TaskPacket format.
- [x] No changes are made to core logic without ensuring backward compatibility with existing preflight records.
