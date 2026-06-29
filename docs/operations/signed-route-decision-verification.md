# Signed Route Decision Verification

## Purpose
This document shows the reviewer-facing path for inspecting optional signed `route_decision` ledger evidence after CR-082 and CR-083.

## Related Checkpoint
For the full Issue #72 reviewer/operator flow, see [issue-72-signed-route-decision-checkpoint.md](issue-72-signed-route-decision-checkpoint.md).

## Default Unsigned Behavior
By default, `TriageClient.run_task(...)` still writes ordinary unsigned `route_decision` events. Signing remains opt-in.

## Opt-In Signed Smoke Path
Use the existing audit surface with the dedicated route-decision smoke flag:

```powershell
tc audit --signed-route-decision-smoke-test --agent-id router-tools
```

This appends one metadata-only signed `route_decision` event using an existing identity with `route_decision:sign`.

## Verification Command

```powershell
tc audit --verify-signatures --kind route_decision
```

## Success Example
A successful verification run stays metadata-only and reports the event type, task id, and signing identity:

```text
Route decision signature verification passed: event_type=route_decision valid_signed=1 invalid_signed=0 unsigned=0 malformed=0 skipped_non_target=0 strict=off
PASS event_type=route_decision task_id=audit-signed-route-decision-smoke-test agent_id=router-tools
```

## Failure Example
Verification failures also stay metadata-only and report a safe failure reason without echoing raw prompt or payload content:

```text
Route decision signature verification failed: event_type=route_decision valid_signed=0 invalid_signed=1 unsigned=0 malformed=0 skipped_non_target=0 strict=off
FAIL event_type=route_decision task_id=route-task agent_id=router-tools reason=signature_mismatch
```

## Boundary
A valid signature proves provenance and tamper evidence only.

It does not prove:
- approval
- safety
- correctness
- authority escalation

This keeps cryptographic identity separate from human review, admission decisions, and other safety controls.
