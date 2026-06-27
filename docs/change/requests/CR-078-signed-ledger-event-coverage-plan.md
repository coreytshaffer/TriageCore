# CR-078: Signed Ledger Event Coverage Plan

## Status
Implemented

## Scope

- Document signed ledger event coverage beyond `route_audit`.
- Keep `route_audit` signed support unchanged.
- Add the first additional signed ledger event path for `validation_result`.
- Require the explicit `validation_result:sign` capability for that path.
- Add focused tests for valid signing, tampering, revoked agents, and unauthorized capability.
- Update backlog and change log wording so the active recommendation matches the current backlog.

## Non-Goals

- No runtime key rotation behavior.
- No approval, safety, or correctness inference from a valid signature.
- No private key persistence outside the existing local `.triagecore/identity/keys/` path.
- No signing requirement for every ledger event.
- No CLI expansion for non-`route_audit` signature verification in this slice.
- No changes to human review, admission, or safety gates.

## Signed Event Coverage

| Event type | Current signing status | Capability | Reason |
|---|---|---|---|
| `route_audit` | Signed path exists | `route_audit:sign` | Route-audit records are control-plane evidence and already have operator-facing verification. |
| `validation_result` | Signed path added in this slice | `validation_result:sign` | Validation records are useful reviewer evidence when tied to a known local validator identity. |
| `taskpacket_created` | Intentionally unsigned for now | Not assigned | Creation records may later need signing, but the payload contract should be reviewed first to avoid signing ambiguous or sensitive metadata. |
| `route_decision` | Intentionally unsigned for now | Not assigned | Route decisions are important, but signing them should be paired with a route-decision verification plan rather than silently widening current audit semantics. |
| `project_steward_decision` | Intentionally unsigned for now | Not assigned | Steward decisions are close to approval semantics, so they need a separate design pass to avoid implying that signature equals approval. |

## Acceptance Criteria

- [x] Signed and intentionally unsigned event types are documented.
- [x] `validation_result` events can be appended with signature metadata through an explicit helper.
- [x] The `validation_result` signed path requires `validation_result:sign`.
- [x] Tampering with signed `validation_result` event payloads fails verification.
- [x] Revoked identities cannot verify signed `validation_result` events.
- [x] Unauthorized identities cannot sign `validation_result` events.
- [x] A valid signature is documented as provenance only, not approval, safety, or correctness.

## Validation

- `python -m py_compile triage_core/task_ledger.py tests/test_task_ledger.py`
- `python -m pytest tests/test_task_ledger.py tests/test_agent_identity.py`
- `git diff --check -- triage_core/task_ledger.py tests/test_task_ledger.py docs/current_backlog.md docs/change/change_log.md docs/change/requests/CR-078-signed-ledger-event-coverage-plan.md`
