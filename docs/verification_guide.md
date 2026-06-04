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
- CLI-initiated activity appears in the live backend/activity log after running a CLI command that writes to `triagecore.log`.
- CLI-created tasks appear in the recent task ledger panel after the next refresh.

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

Check CLI-to-desktop observability:

```powershell
triagecore desk
triagecore codex-task --prompt "Smoke test desktop CLI logging" --files README.md
triagecore run-pipeline --prompt "Smoke test CLI pipeline observability" --files README.md --output reports\pipeline-smoke.md
triagecore scan-supervisor-usage supervisor_logs\
```

Pass condition:

- The live backend/activity log shows `[cli]` activity for the command.
- The recent task ledger panel shows the CLI-created task when the command appends ledger evidence.
- CLI pipeline runs show a `pipeline` runner and either `local_draft_generated` or `blocked` status in the ledger.
- The raw ledger view shows the same task/event if the Logs tab is switched to ledger mode.

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

For model/backend comparison, use one shared study label and unique run IDs:

```powershell
triagecore benchmark --study-id study_002 --run-id ollama_qwen25_coder_7b_trial_001 --backend-type ollama --model qwen2.5-coder:7b-triagecore
triagecore benchmark --study-id study_002 --run-id lmstudio_loaded_model_trial_001 --backend-type custom --base-url http://localhost:1234/v1 --model <loaded-model-name>
triagecore benchmark-report --study-id study_002 --output reports\study_002_model_backend_comparison.md
```

Pass condition:

- Each backend/model pair has a unique `run_id`.
- The combined report includes `By Supervision`, `By Backend`, `By Model`, and `By Category`.
- The report includes a `Supervisor Reviews` table when supervised benchmark records exist in the selected study/run scope.
- Any comparison claim cites the same fixture set and timeout settings.

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

## 6. Supervisor Review Verification

Use this when a Codex, Antigravity, Gemini, or human supervisor reviews a task
that began as a local draft, worker-council result, benchmark run, or pipeline
attempt.

```powershell
triagecore record-supervisor-review <task_id> --tool codex --decision needs_revision --notes "Local draft missed tests." --model gpt-5 --profile high
triagecore record-supervisor-review <task_id> --tool antigravity --decision accepted --notes "IDE supervisor accepted the local draft." --model gemini-3.1-pro-high --profile supervisor
triagecore scan-supervisor-usage supervisor_logs\
triagecore import-supervisor-usage supervisor_usage.jsonl --tool codex --token-source imported_exact --dry-run
triagecore import-supervisor-usage supervisor_usage.jsonl --tool codex --token-source imported_exact
```

Pass condition:

- The task already exists in `.triagecore/ledger.jsonl`.
- The reduced task record shows `supervisor_tool`, `supervisor_decision`, and any model/profile details that were supplied.
- Estimated supervisor token fields are used only when exact usage is unavailable.
- Imported usage records use `imported_exact` only when the source artifact exposes verified token usage.
- Candidate directories are scanned before importing so parseable JSON/JSONL files can be reviewed.
- Dry-run output is reviewed before importing candidate supervisor usage artifacts.
- Scientific notes distinguish local-only outcomes from supervised outcomes.
- Benchmark reports keep supervisor-review summaries inside the active `study_id` and `run_id` filters.

## 7. Local-First Dashboard Verification

Use this when checking that the operator bench emphasizes the benefits of local
compute without overstating scientific claims.

```powershell
triagecore desk
```

Pass condition:

- The dashboard title reads `Savings & Telemetry Dashboard`.
- The first telemetry card is `Local-First Benefits`.
- The benefit card shows accepted yield, kept-local share, local accepted work,
  and review-light tasks before raw energy, emissions, water, or token totals.
- The methodology still describes these as benefit or avoidance signals unless a
  baseline comparison study is defined.
