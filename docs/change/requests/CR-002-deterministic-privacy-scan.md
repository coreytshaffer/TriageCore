# CR-002: Deterministic Privacy Scan

## Status
Implemented

## Scope
Implement a deterministic (non-LLM) privacy scanning tool that evaluates both declared TaskPacket privacy metadata and the actual task content before allowing a task to proceed to cloud or local routing.

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Human Approval Requirement
Explicit human review and approval of the scanning logic, ensuring it fails closed and does not rely on probabilistic models.

## Acceptance Criteria
- [x] A deterministic privacy scanner is implemented.
- [x] The scanner correctly blocks tasks that violate privacy metadata constraints.
- [x] The scanner allows tasks that comply with privacy metadata constraints.
- [x] Scanner fails closed when declared metadata and detected content disagree.
- [x] The scanner is integrated into the pre-routing intake flow.
- [x] Tests prove that sensitive tasks cannot bypass the scanner.
