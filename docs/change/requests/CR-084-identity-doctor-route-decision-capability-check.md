# CR-084: Identity Doctor Route-Decision Capability Check

## Status
Implemented

## Scope

- Add an optional capability-targeted check to `tc identity doctor`.
- Support `tc identity doctor <agent-id> --for-capability route_decision:sign` as a read-only pre-smoke-test readiness check.
- Fail closed when the scoped agent is unknown or the active identity lacks the requested capability.
- Reuse the existing doctor checks for missing keys, fingerprint mismatches, malformed registry state, and rotation-related warnings.
- Update backlog and change log wording to reflect the diagnosability slice.

## Non-Goals

- No signing-policy changes.
- No automatic route-decision signing.
- No new ledger event types.
- No dashboard or TUI changes.
- No private-key exposure.

## Acceptance Criteria

- [x] `tc identity doctor <agent-id> --for-capability route_decision:sign` passes for a healthy active signer.
- [x] The command fails closed when the agent is unknown.
- [x] The command fails closed when the active identity lacks `route_decision:sign`.
- [x] Successful capability checks remain read-only and do not alter identity files.
- [x] Existing doctor warnings and errors remain intact.

## Validation

- `python -m py_compile triage_core/tc_cli.py tests/test_doctor_cli.py`
- `python -m pytest tests/test_doctor_cli.py -q`
- `git diff --check`
