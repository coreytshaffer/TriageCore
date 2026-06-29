# CR-082: Signed Route Decision Verification Path

## Status
Implemented

## Scope

- Add an explicit signed ledger helper for `route_decision` events.
- Allow `TriageClient.run_task()` to write a signed `route_decision` event only when a caller explicitly supplies a signing registry and agent id.
- Extend `tc audit --verify-signatures` to support `--kind route_decision`.
- Print metadata-only verification readouts showing pass or fail state, `event_type`, `task_id`, `agent_id`, and safe failure reasons.
- Update backlog and change log wording to reflect the new signed-event surface.

## Non-Goals

- No runtime key rotation behavior.
- No automatic signing of all `route_decision` events.
- No signing expansion to `taskpacket_created` or `project_steward_decision`.
- No reviewer-facing route-decision example document in this slice.
- No approval, safety, or correctness inference from a valid signature.
- No raw prompt or sensitive payload output in verification readouts.

## Acceptance Criteria

- [x] `route_decision` events can be appended with signature metadata through an explicit helper.
- [x] The signed `route_decision` path requires `route_decision:sign`.
- [x] `TriageClient.run_task()` can write a signed `route_decision` event when explicit signing inputs are provided.
- [x] `tc audit --verify-signatures --kind route_decision` verifies signed `route_decision` events.
- [x] Verification output remains metadata-only and includes pass or fail state, `event_type`, `task_id`, `agent_id`, and safe failure reasons.
- [x] Tampered signed `route_decision` events fail with a clear operator-facing reason.
- [x] Unsupported verification kinds still fail closed with an explicit error.

## Validation

- `python -m py_compile triage_core/task_ledger.py triage_core/client.py triage_core/tc_cli.py tests/test_task_ledger.py tests/test_client.py tests/test_audit_cli.py`
- `python -m pytest tests/test_task_ledger.py tests/test_client.py tests/test_audit_cli.py -q`
- `git diff --check`
