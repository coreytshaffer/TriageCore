# CR-030: Identity Rotation and Recovery Policy

## Status

Implemented

## Scope

Documentation only.

This change defines:

- identity rotation semantics
- recovery assumptions
- historical verification policy
- what happens to old keys
- what future runtime commands should and should not do

This change does not modify signing, verification, revocation, ledger behavior,
or any runtime CLI behavior.

## Description

CR-020 now includes identity initialization, signing helpers, signed
`route_audit`, verification, smoke-path evidence, and revocation. The next
trust-model decision is rotation and recovery policy.

This CR establishes the conservative operator policy that future runtime
rotation/recovery commands must follow before any implementation work begins.

## Policy Summary

- Revoked = current trust failure.
- Rotated = old key may verify historical events, but must not sign new events.
- Compromised = old key invalidates trust for events unless manually accepted
  by operator policy.
- Lost key = no recovery of signing ability; create a new identity or rotate if
  old registry metadata remains trustworthy.

## Acceptance Criteria

- [x] Defines difference between revoked, rotated, compromised, and lost keys.
- [x] Defines historical verification behavior.
- [x] Defines future CLI expectations for `tc identity rotate`.
- [x] Defines backup/recovery warning language.
- [x] Keeps CR-030 documentation-only.
- [x] Does not alter signing, verification, revocation, or ledger behavior.

## Validation

```powershell
python -m pytest -q
tc identity check
tc audit --privacy-invariants
tc audit --verify-signatures
```
