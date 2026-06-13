# CR-024: Persistent Artifact Audit Command

## Status
Implemented

## Scope
Add `tc audit --privacy-invariants` to scan existing persistent ledger records
for forbidden raw-content keys using the CR-021 invariant.

## Implementation Authority
Authorized for implementation.

## Description
This change adds an operator-facing audit command on top of the existing
persistent artifact privacy invariant. It scans `.triagecore/ledger.jsonl`,
reports malformed lines and forbidden persistent keys with line/task/event/path
metadata, and avoids echoing sensitive values.

## Acceptance Criteria
- [x] `tc audit --privacy-invariants` scans `.triagecore/ledger.jsonl`.
- [x] Safe ledger records pass with a clear success summary.
- [x] Forbidden persistent keys fail the command.
- [x] Failure output includes line number, task ID, event type, violation path, and key.
- [x] Failure output does not echo sensitive values.
- [x] Malformed JSONL lines fail the audit.
- [x] Missing ledger path fails consistently with existing audit behavior.
- [x] Existing `tc audit`, `tc audit --self-test`, `--kind`, and `--last` behavior remains unchanged.
- [x] Targeted audit tests and full test suite pass.

## Validation

```powershell
python -m py_compile triage_core\tc_cli.py
python -m pytest tests\test_audit_cli.py -q
python -m pytest tests\test_privacy_invariants.py -q
python -m pytest -q
tc audit --privacy-invariants
python -m triage_core.tc_cli audit --privacy-invariants
```
