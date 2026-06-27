# CR-079: Verify Signed Validation Result Events

## Status
Implemented

## Scope

- Extend the operator-facing signature verification path to support signed `validation_result` ledger events.
- Keep the existing `tc audit --verify-signatures` command as the entrypoint.
- Allow `--kind validation_result` in addition to the existing `route_audit` default.
- Print metadata-only verification readouts showing pass or fail status, `event_type`, `task_id`, `agent_id`, and safe failure reasons.
- Add focused CLI coverage for valid verification, tampering, revoked identities, unknown agents, and unsupported verification kinds.
- Update backlog and change log wording to reflect the new verification surface.

## Non-Goals

- No runtime key rotation.
- No signing expansion to additional event types.
- No approval, safety, or correctness inference from a valid signature.
- No raw prompt or sensitive payload output in verification readouts.
- No dashboard or TUI work.

## Acceptance Criteria

- [x] `tc audit --verify-signatures` still verifies `route_audit` events by default.
- [x] `tc audit --verify-signatures --kind validation_result` verifies signed `validation_result` events.
- [x] Verification output remains metadata-only and includes pass or fail state, `event_type`, `task_id`, `agent_id`, and safe failure reasons.
- [x] Tampered signed `validation_result` events fail with a clear operator-facing reason.
- [x] Revoked and unknown signing identities fail with clear operator-facing reasons.
- [x] Unsupported verification kinds fail closed with an explicit error.

## Validation

- `python -m py_compile triage_core/task_ledger.py triage_core/tc_cli.py tests/test_audit_cli.py`
- `python -m pytest tests/test_audit_cli.py tests/test_task_ledger.py tests/test_agent_identity.py -q`
- `python -m pytest tests -q`
- `git diff --check`
