# Verification Guide

This guide separates quick developer checks from human review checks and scientific evidence checks.

## 1. Quick Code Verification

Use this after a focused code change.

```powershell
python -m py_compile triage_core\ui\app.py
python -m pytest tests\test_ui_smoke.py
```

Pass condition:

- The edited Python file compiles.
- The focused smoke tests pass.

## 2. Full Regression Verification

Use this before committing a broader change.

```powershell
python -m pytest
```

Pass condition:

- All tests pass.
- No unrelated files were changed.

## 3. UI Review Verification

Use this when TriageDesk layout or review behavior changes.

```powershell
triagecore desk
```

Check the main screen:

- The window opens maximized with the title bar visible.
- The dispatch buttons read left to right as the workflow.
- The output box is followed by the live backend/activity log.
- The recent task ledger panel is visible without opening the full Ledger tab.

Check the Ledger tab:

- Each reviewable card shows an `Assessment snapshot`.
- The snapshot explains the decision need, path, reason or benchmark result, and cost.
- The dense evidence stays behind `Details`.
- The optional `Review load` selector can be left at `Not set` or set to `Low`, `Medium`, or `High`.
- `Approve & Load` reloads the task into the dispatch prompt.
- `Deny` records a review decision without hiding the evidence trail.

Check accessibility basics:

- Tab through the visible controls and confirm the focus order follows the task flow.
- Confirm buttons and segmented controls are large enough to click without precision.
- Confirm long card text wraps cleanly without overlapping actions.
- Confirm the workload selector helps review instead of making cards feel noisy.

## 4. Study Evidence Verification

Use this before trusting a benchmark run as scientific evidence.

```powershell
triagecore benchmark --list-only --study-id study_001
triagecore benchmark --study-id study_001 --run-id trial_003
triagecore benchmark-report --study-id study_001 --run-id trial_003 --output reports\study_001_trial_003_benchmark_report.md
```

Pass condition:

- The run has a unique `run_id`.
- The report excludes exploratory or older trial records.
- Validator failures and handoff-required cases are explained instead of silently averaged away.
- Any proposed learning remains pending until a human records a review decision.
- Human review records include review time and may include subjective workload.

## 5. Human Review Rule

Do not accept a learning proposal only because a benchmark failed. First decide whether the issue came from:

- prompt wording
- validator strictness
- model behavior
- backend configuration
- benchmark ambiguity

Record that decision explicitly with:

```powershell
triagecore review-lesson <proposal_id> --decision accepted --notes "Reason for accepting."
triagecore review-lesson <proposal_id> --decision rejected --notes "Reason for rejecting."
```
