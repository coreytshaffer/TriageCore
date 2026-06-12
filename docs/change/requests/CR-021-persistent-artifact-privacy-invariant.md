# CR-021: Persistent Artifact Privacy Invariant

## Status
Implemented

## Scope

Add a central, recursive privacy invariant for persistent ledger payloads.
Reject prohibited raw-content fields before any ledger write occurs.

## Implementation Authority
Authorized for implementation.

## Description

Persistent artifacts are accumulated memory. This change prevents raw task,
prompt, message, data, and content fields from entering the standard ledger
write path while preserving metadata-only auditability.

## Acceptance Criteria
- [x] Safe metadata-only ledger events pass.
- [x] Top-level prohibited keys fail.
- [x] Nested prohibited keys fail.
- [x] Prohibited keys inside list items fail.
- [x] Error messages report key paths without echoing sensitive values.
- [x] Rejected writes do not create or modify the ledger file.
- [x] Existing audit self-test behavior remains privacy-safe.

## Non-Goals

- Encryption.
- Cryptographic agent identity implementation.
- Cloud routing changes.
- Scanning arbitrary user files or the repository.

## Validation

```powershell
python -m py_compile triage_core/privacy_invariants.py triage_core/task_ledger.py
python -m pytest tests/test_privacy_invariants.py -q
python -m pytest tests/test_audit_cli.py -q
python -m pytest -q
```
