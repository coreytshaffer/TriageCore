# CR-029: Identity Revocation CLI

## Status

Implemented

## Scope

Add a narrow operator-facing revocation command for local persistent agent
identities:

```powershell
tc identity revoke --agent-id <id>
```

Revocation updates the public registry status to `revoked` without deleting
private keys, rotating keys, altering ledger records, or expanding signing
beyond `route_audit`.

## Description

CR-020 already covered identity initialization, signing helpers, signed
`route_audit`, verification, and smoke-path evidence. The next minimum
lifecycle control is revocation.

This change:

- loads `.triagecore/identity/agents.json`
- marks the matching identity `revoked`
- preserves public key, fingerprint, role, capabilities, and `created_at`
- leaves the existing private key file in place
- keeps current conservative trust semantics where revoked identities fail
  future signing and verification

This change does not add key deletion, rotation, recovery, cloud identity, or
broader event signing.

## Acceptance Criteria

- [x] `tc identity revoke --agent-id <id>` marks the identity as `revoked`.
- [x] Unknown identity revocation fails cleanly.
- [x] Revoking an already revoked identity is idempotent with a clear message.
- [x] Revoked identity cannot sign new `route_audit` smoke events.
- [x] Signed events from a revoked identity fail verification under current
  policy.
- [x] `tc identity list` shows revoked status.
- [x] `tc identity check` still reports registry/key consistency without
  deleting the key.
- [x] No key deletion, rotation, recovery, cloud identity, or broader signing
  is added.

## Validation

```powershell
python -m py_compile triage_core\agent_identity.py triage_core\tc_cli.py
python -m pytest tests\test_agent_identity.py -q
python -m pytest tests\test_identity_cli.py -q
python -m pytest tests\test_audit_cli.py -q
python -m pytest -q
tc identity check
tc audit --privacy-invariants
tc audit --verify-signatures
```
