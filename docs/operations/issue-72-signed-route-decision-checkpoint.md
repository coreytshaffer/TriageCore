# Issue #72 Signed Route Decision Checkpoint

## Purpose
This checkpoint demonstrates the current opt-in signed `route_decision` verification path on `main`.

It does not make route-decision signing automatic, does not alter default task execution behavior, and does not expand the trusted execution surface. It adds a bounded operator flow for checking signer readiness, creating one signed route-decision smoke artifact, and verifying signed route-decision events through the audit CLI.

## What This Checkpoint Proves

- `route_decision` events have an explicit signed ledger path.
- `TriageClient.run_task(...)` can opt into route-decision signing.
- Audit can verify signed `route_decision` metadata after the fact.
- Operators can check signer readiness before running the smoke path.
- Missing identity or missing `route_decision:sign` permission fails closed.
- Default runtime behavior remains unchanged unless signing is explicitly requested.

## What This Checkpoint Does Not Prove

- that route-decision signing is automatic
- that a valid signature implies approval
- that a valid signature implies safety or correctness
- that the signed route-decision path changes admission or review policy
- that additional ledger event types are now signed

## Operator / Reviewer Path
Run the following commands in order:

```powershell
tc identity doctor <agent-id> --for-capability route_decision:sign
tc audit --signed-route-decision-smoke-test --agent-id <agent-id>
tc audit --verify-signatures --kind route_decision
```

## Expected Readouts

### 1. Identity Readiness
The readiness check should report a successful capability-specific doctor result for a healthy signer:

```text
Identity doctor passed: checked_agents=1 errors=0 warnings=0
OK capability_ready agent_id=router-tools capability=route_decision:sign fingerprint=<fingerprint>
```

### 2. Smoke Artifact Creation
The smoke command should append one metadata-only signed `route_decision` event:

```text
Success: Wrote metadata-only signed route_decision smoke test event to <ledger-path> using agent_id=router-tools.
```

### 3. Audit Verification
The verification command should report metadata-only pass/fail output without echoing raw prompt or task content:

```text
Route decision signature verification passed: event_type=route_decision valid_signed=1 invalid_signed=0 unsigned=0 malformed=0 skipped_non_target=0 strict=off
PASS event_type=route_decision task_id=audit-signed-route-decision-smoke-test agent_id=router-tools
```

## Failure Boundaries
The path fails closed when:

- the scoped agent identity does not exist
- the active identity lacks `route_decision:sign`
- the active key material is missing or malformed
- public metadata and active key fingerprint do not match
- the signed event payload has been tampered with

Warnings may still appear for separate rotation-history issues without changing the core meaning of a passing capability readiness check.

## Related Docs

- [signed-route-decision-verification.md](signed-route-decision-verification.md)
- [signed-validation-result-verification.md](signed-validation-result-verification.md)
- [../security/agent_identity_provenance.md](../security/agent_identity_provenance.md)
