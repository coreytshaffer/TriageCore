# CR-026: Post-Identity Privacy and Security Audit

## Status

Implemented

## Scope

Audit the CR-020 identity and signing work after Phase 5 before expanding
signing coverage beyond `route_audit`.

## Implementation Authority

Authorized for audit and documentation.

## Description

This change adds a focused privacy and security audit for the persistent
cryptographic agent identity system. The audit reviews identity
initialization, local key storage, public metadata inspection, opt-in signed
`route_audit` events, signature verification, strict-mode behavior, and
remaining key-lifecycle risks.

## Acceptance Criteria

- [x] Audit document exists under `docs/security/`.
- [x] Audit reviews private key storage boundaries.
- [x] Audit reviews public metadata exposure.
- [x] Audit reviews signed `route_audit` verification behavior.
- [x] Audit reviews privacy invariant interaction.
- [x] Audit lists known limitations.
- [x] Audit recommends whether CR-020 can pause, close, or continue.
- [x] No runtime signing expansion is included.

## Outcome

CR-020 remains open. Signing expansion should pause while revocation, rotation,
recovery, filesystem-permission policy, and a metadata-only signed smoke path
are defined.

## Validation

```powershell
python -m pytest -q
tc audit --privacy-invariants
tc audit --verify-signatures
tc audit --verify-signatures --strict
```

Validation on June 13, 2026:

- Full suite: `294 passed, 2 skipped`.
- Privacy invariant audit: passed across 690 records.
- Default signature verification: passed with six unsigned legacy
  `route_audit` records.
- Strict signature verification: failed as expected because those six legacy
  records are unsigned.
