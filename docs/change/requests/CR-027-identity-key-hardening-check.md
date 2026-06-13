# CR-027: Identity Key Hardening and Consistency Check

## Status

Implemented

## Scope

Harden local identity creation and add an operator consistency check before
expanding signed ledger coverage beyond `route_audit`.

## Implementation Authority

Authorized for implementation.

## Description

This change applies restrictive private-key permissions where the operating
system supports them, makes identity creation transactional with cleanup after
failed writes, and adds `tc identity check` for registry and key consistency.

## Implemented Behavior

- POSIX private keys receive mode `0600`.
- Windows private keys have inherited ACLs removed and grant access to the
  current user, SYSTEM, and Administrators.
- Identity creation writes temporary key and registry files before atomically
  replacing final paths.
- Failed registry commits remove the newly committed key and temporary files.
- Existing registry identities are preserved when adding another identity.
- Unsafe agent IDs that could escape the key directory are rejected.
- `tc identity check` detects:
  - missing private keys
  - orphaned private keys
  - malformed registry data
  - private-key permission warnings

## Acceptance Criteria

- [x] Private-key permissions are restricted where supported.
- [x] Permission hardening failure aborts identity creation.
- [x] Identity creation cleans partial files after a failed commit.
- [x] Adding a second identity preserves existing registry entries.
- [x] Unsafe agent IDs cannot escape the private-key directory.
- [x] `tc identity check` passes for a consistent registry.
- [x] Missing keys fail the check.
- [x] Orphaned keys fail the check.
- [x] Malformed registry data fails the check.
- [x] Permission concerns are reported as warnings.
- [x] Check output never prints private key contents.
- [x] No revocation, rotation, deletion, recovery, cloud identity, or broader
  signing behavior is added.

## Non-Goals

- Revocation CLI
- Key rotation
- Key deletion
- Backup or recovery
- Cloud identities
- Signing additional event types

## Validation

```powershell
python -m py_compile triage_core\agent_identity.py triage_core\tc_cli.py
python -m pytest tests\test_agent_identity.py -q
python -m pytest tests\test_identity_cli.py -q
python -m pytest -q
tc identity check
tc audit --privacy-invariants
tc audit --verify-signatures
```
