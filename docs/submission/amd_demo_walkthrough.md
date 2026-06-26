# AMD Track: Judge-Facing Demo Walkthrough

This walkthrough demonstrates TriageCore's test-backed governance behavior for AMD Cloud escalation. It shows how TriageCore processes a `TaskPacket` and applies routing policy to determine if a task can safely execute on AMD cloud infrastructure.

## 1. The TaskPacket

Every AI task begins as a `TaskPacket`. Instead of a raw, unverified string sent directly to a cloud API, TriageCore requires a structured envelope containing the task payload, privacy metadata, and execution requirements.

```json
{
  "task_id": "task_12345",
  "intent": "analyze_log_data",
  "privacy_level": "internal_only",
  "requires_high_compute": true,
  "payload": "..."
}
```

## 2. Policy Classification

Before any execution occurs, TriageCore evaluates the `TaskPacket` against the current route manifest. The route manifest defines the acceptable boundaries for local execution, deterministic tooling, and cloud escalation.

When a task targets the `amd_cloud` route, TriageCore's routing policy engine (`triage_core.routing.policy.classify_route`) kicks in to assess the risk.

## 3. The AMD Route Outcomes

Depending on the `TaskPacket`'s metadata and the active policy, TriageCore enforceably routes the task into one of three AMD cloud states:

### Scenario A: AMD Blocked (Privacy Violation)
If the `TaskPacket` contains highly sensitive data (e.g., `privacy_level: "strict_confidential"`) and the AMD route is not cleared for that data tier, the policy engine explicitly blocks egress. The task fails closed locally.
**Result:** `blocked`

### Scenario B: AMD Approval Required (Governed Escalation)
If the task requires heavy compute but operates in a gray area (e.g., normal business data where the operator must acknowledge cloud egress), the engine pauses execution. A human operator must explicitly review the preflight artifact and approve the escalation before it leaves the local environment.
**Result:** `approval_required`

### Scenario C: AMD Allowed (Safe Path)
If the task deals with public data and specifically requests high-performance inference, the policy engine verifies the constraints and immediately allows escalation to the AMD backend.
**Result:** `allowed`

*(Note: These outcomes are backed by our executable routing policy tests in `tests/test_routing_policy.py`, proving this is live governance behavior, not just documentation.)*

## 4. The Audit Ledger

Regardless of the outcome (Blocked, Approval Required, or Allowed), the route decision is permanently recorded in TriageCore's append-only audit ledger. 

This ensures that the decision to use AMD cloud acceleration is always reviewable and auditable, capturing the *metadata* of the decision without leaking the raw prompt context.

**Example Audit Ledger Entry:**
```json
{
  "timestamp": "2026-06-25T14:32:01Z",
  "event_type": "route_audit",
  "task_id": "task_12345",
  "target_route": "amd_cloud",
  "decision": "approval_required",
  "policy_version": "v1.2.0",
  "operator_id": "ops_user_01"
}
```

## Summary
TriageCore ensures that AMD cloud compute is a governed, conscious decision. By wrapping high-performance AI execution in privacy checks, approval gates, and auditable ledgers, we make AMD cloud acceleration safer and enterprise-ready.
