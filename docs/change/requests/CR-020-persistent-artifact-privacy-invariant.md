# CR-020: Persistent Artifact Privacy Invariant

## Status

Implemented

## Purpose

Prevent raw task content or sensitive payload fields from being written to
persistent TriageCore artifacts, especially `.triagecore/ledger.jsonl` and
future audit or handoff persistence paths.

TriageCore should preserve useful auditability without retaining raw user
prompt or data content.

## Problem

Existing hardening work protects several specific surfaces, including the mobile
API boundary. The next privacy risk is accumulated memory: ledgers, handoffs,
audit trails, and saved operational artifacts. Persistent artifact safety
should be enforced centrally rather than relying on each caller to remember
which fields are unsafe.

## Non-goals

- Do not add encryption in this CR.
- Do not redesign the TaskPacket state model.
- Do not change cloud routing behavior.
- Do not scan arbitrary user files.
- Do not scan the entire repository.
- Do not weaken existing audit utility.

## Implemented Change

- Added `triage_core/privacy_invariants.py`.
- Added a recursive persistent-event validator for prohibited raw-content keys.
- Wired validation into the standard ledger append path.
- Ensured validation failures prevent ledger modification.
- Ensured failure messages identify the prohibited key path without echoing
  sensitive values.
- Added focused tests for top-level, nested, and list-contained prohibited
  keys.
- Confirmed the existing audit self-test still passes.

## Prohibited Persistent Keys

```python
PROHIBITED_PERSISTENT_KEYS = {
    "prompt",
    "data",
    "content",
    "raw_prompt",
    "raw_data",
    "message_body",
    "body",
}
```

## Acceptance Criteria

- [x] Safe metadata-only ledger events pass.
- [x] Top-level prohibited keys fail.
- [x] Nested prohibited keys fail.
- [x] Prohibited keys inside list items fail.
- [x] Existing `tc audit --self-test` behavior remains privacy-safe and passing.
- [x] Ledger file is not modified when validation fails.
- [x] Full test suite passes.

## Validation

- `python -m py_compile triage_core/privacy_invariants.py`
- `python -m pytest tests/test_privacy_invariants.py -q`
- `python -m pytest tests/test_audit_cli.py -q`
- `python -m pytest -q`

## Risk

Low-to-medium. This change may reveal existing code paths that were implicitly
writing unsafe fields. Those paths should be fixed to emit metadata-only events
rather than weakening the invariant.

## Rollback

Remove the validator call from the ledger writer and delete the new invariant
tests. Rollback should not be needed unless the invariant blocks required
metadata unexpectedly.
