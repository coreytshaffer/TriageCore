# Identity Rotation and Recovery Policy

## Purpose

This document defines the trust policy for future TriageCore identity rotation
and recovery work. It exists to prevent runtime implementation from silently
encoding the wrong historical-verification or operator-recovery model.

This is a policy and design document only. It does not change current signing,
verification, revocation, or ledger behavior.

## Status Definitions

### Revoked

Revoked means the identity is no longer trusted for current use.

Current policy:

- revoked identities must not sign new events
- revoked identities fail verification under current semantics
- revocation is a current trust failure, not a historical preservation mode

This matches the currently implemented conservative behavior.

### Rotated

Rotated means a successor key has replaced the old key for future signing, but
the old key may still be retained as historical verification material.

Policy requirements:

- rotated keys must not sign new events
- rotated keys may verify historical events recorded before rotation
- rotation must preserve explicit linkage between old and new identities or key
  records
- rotation must not silently rewrite old ledger records

Rotation is not the same as revocation. It is a lifecycle transition, not an
automatic trust failure.

### Compromised

Compromised means the operator believes a key may have been exposed or used by
an unauthorized party.

Policy requirements:

- compromised keys must not sign new events
- compromised keys are not trusted for historical verification by default
- historical events from a compromised key require explicit operator acceptance
  if they are to be treated as usable evidence

This is stricter than ordinary rotation because the trust model has been
damaged, not merely superseded.

### Lost Key

Lost key means the private signing key is unavailable.

Policy requirements:

- signing ability is not recoverable from registry metadata alone
- loss of a key does not prove compromise
- the operator must create a new identity or perform a future supported
  rotation flow if the old registry metadata is still trustworthy

There is no assumption that TriageCore can reconstruct signing authority from
public metadata.

## Historical Verification Policy

The future trust model should distinguish three cases:

- revoked: fail verification under current conservative policy
- rotated: allow historical verification for old events, but reject new signing
- compromised: treat historical verification as invalid unless operator policy
  explicitly overrides that default

This means revocation and rotation are intentionally different states. The
current implementation only supports revocation semantics, so future runtime
rotation work must add the additional metadata and verification policy needed
for historical trust.

## Old-Key Handling

Future runtime rotation must define what happens to old keys without deleting
evidence blindly.

Minimum policy:

- old private keys should no longer be used for signing after rotation
- old public verification material may remain available for historical checks
- rotated key material should be clearly labeled and separated from active key
  material
- compromised key material should be treated more strictly than rotated key
  material

Runtime implementation should avoid destructive deletion as the first action.
Operators need a clear audit trail and clear state labels before any archival
or removal workflow is considered.

## Future CLI Expectations

This document defines the intended boundary for a future `tc identity rotate`
command.

Future `tc identity rotate` should:

- create or register successor signing material explicitly
- mark the old key as rotated rather than revoked by default
- record enough metadata to support historical verification of old events
- prevent the old key from signing new events
- produce clear operator-facing output about active vs historical trust state

Future `tc identity rotate` should not:

- silently delete old keys
- silently rewrite ledger history
- silently convert rotation into compromise semantics
- silently restore trust to revoked identities
- imply that backup or recovery exists when it does not

## Recovery and Backup Warnings

Operator-facing recovery language should remain conservative.

Recommended warning model:

- local private keys are high-value trust material
- loss of a private key means loss of signing ability for that key
- public registry metadata alone does not restore signing authority
- backups, if used, must be treated as sensitive local secrets
- recovery procedures should be explicit, documented, and operator-approved

TriageCore should not imply safe self-healing or automatic recovery for key
loss. Any future recovery feature needs its own CR and explicit trust review.

## Non-Goals

This policy does not:

- implement `tc identity rotate`
- implement key recovery tooling
- change current revoked verification semantics
- add deletion, archival, or backup automation
- expand signing beyond current event types

## Implementation Guidance

Before runtime rotation is implemented, future work should answer at least:

1. What metadata links an old key to its successor?
2. How does verification decide whether an old signature is historically valid?
3. How is compromise represented differently from ordinary rotation?
4. What operator workflow acknowledges manual exceptions for compromised keys?
5. What backup language is safe to expose in CLI help and docs?

Until those questions are implemented deliberately, the current conservative
model should remain in force.
