# CR-028: Signed Smoke-Path Evidence

## Status

Implemented

## Scope

Add one operator-facing smoke command that appends a metadata-only signed
`route_audit` event using an existing authorized identity, then relies on the
existing signature-verification path to prove it.

## Description

CR-020 phase 3 proved that TriageCore can sign `route_audit` events, and phase
4 proved that operators can verify signed `route_audit` records from the CLI.
CR-028 adds the smallest end-to-end evidence path between those two pieces:

```powershell
tc audit --signed-smoke-test --agent-id project-steward
tc audit --verify-signatures
```

The smoke command does not create identities, does not widen signing coverage,
and does not sign raw prompt or data content. It writes one boring,
metadata-only signed `route_audit` record that is safe to keep in the ledger.

## Acceptance Criteria

- [x] `tc audit --signed-smoke-test --agent-id <id>` appends one signed
  `route_audit` event.
- [x] The command fails if the identity is missing.
- [x] The command fails if the identity lacks `route_audit:sign`.
- [x] The smoke event verifies with `tc audit --verify-signatures`.
- [x] The smoke payload is metadata-only.
- [x] The command does not create identities automatically.
- [x] The command does not expand signing beyond `route_audit`.
- [x] Existing unsigned legacy `route_audit` events remain allowed by default.
- [x] `tc audit --privacy-invariants` passes.
- [x] Full suite passes.

## Smoke Payload

The signed smoke event writes only metadata:

```python
{
    "decision": "allowed",
    "reason_code": "signed_smoke_test",
    "privacy_level": "public",
    "privacy_scan_passed": True,
    "is_local_only": True,
    "recommended_route": "local",
    "selected_backend": "local",
    "smoke_test": True,
}
```

It does not include prompt, data, content, raw prompt, raw data, user text, or
model response fields.

## Validation

```powershell
python -m py_compile triage_core\tc_cli.py triage_core\task_ledger.py triage_core\agent_identity.py
python -m pytest tests\test_audit_cli.py -q
python -m pytest tests\test_identity_cli.py -q
python -m pytest tests\test_agent_identity.py -q
python -m pytest -q
tc identity check
tc audit --privacy-invariants
tc audit --verify-signatures
tc audit --signed-smoke-test --agent-id project-steward
tc audit --verify-signatures
```
