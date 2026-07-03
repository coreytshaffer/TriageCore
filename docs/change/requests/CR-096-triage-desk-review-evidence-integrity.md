# CR-096: TriageDesk Review Evidence Integrity

## Background
A review found two defects in `_execute_context_review` / TriageDesk GUI review handling:
1. GUI review decisions persisted fabricated effort metadata (`human_review_minutes: 1.0` and `review_workload: "medium"`).
2. "Needs Revision" decisions were silently reduced to rejected because the GUI payload key used `"decision"` while the reducer reads `"review_decision"`.

## Changes
- Updated `triage_core.ui.app._execute_context_review` to emit `"review_decision"` instead of `"decision"`.
- Removed fabricated effort defaults from the `_execute_context_review` payload, deferring to schema defaults.
- Added a targeted regression test (`tests/test_ui_execute_context_review.py`) ensuring the GUI payload uses the correct reducer-consumed keys and correctly propagates "needs revision".

## Impact
- **Ledger Integrity**: The ledger now captures exact "needs revision" outcomes from the GUI.
- **Evidence Honesty**: The current behavior avoids recording unmeasured effort as factual evidence. The GUI-generated payload no longer emits `human_review_minutes: 1.0` and `review_workload: "medium"` by default.
- **Reducer Defaults**: Any reducer defaults such as `0.0` or empty string represent unrecorded/unknown effort, not measured effort.
- **Historical Immutability**: Historical ledger entries are not rewritten. Prior GUI-generated `review_completed` events may contain fabricated effort defaults (1.0 minutes, "medium" workload) and remain as append-only historical records.
