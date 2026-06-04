# Session Handoff

Last updated: 2026-06-04

## Current State

- Active branch: `feature/specialized-council-handoffs`
- Tracked worktree: clean after housekeeping
- Runtime evidence files under `.triagecore/` and generated reports under `reports/` are intentionally ignored

Recent commits:

- `324759c feat: improve dispatch observability and controls`
- `1cdc7f1 feat: expand ledger cards with review details`
- `bc74636 fix: clarify structured extraction and timestamp tasks`
- `c170c7f feat: scope benchmark reports by run`
- `71fc8bf docs: add session handoff checkpoint`

## What Changed Tonight

- Added `study_id` support for formal benchmark evidence scoping.
- Ran Study 001 against the configured Ollama model.
- Added deterministic validators for log-summary and monitoring JSON fixtures.
- Fixed validator-triggered handoffs so model, token, and validator context are preserved.
- Documented Study 001 results and the stricter-validation rerun.

## Verification

Latest full test run:

```bash
python -m pytest
```

Result:

```text
74 passed
```

Benchmark fixture smoke check:

```bash
python -m triage_core.cli benchmark --list-only --study-id study_001
```

Result: all five Study 001 fixtures load.

## Next Decision Point

Run/trial scoping has been added. `study_001` / `trial_001` isolated one formal run and produced a 5-run report with one `structured_extraction` mismatch and one validator failure.

The structured-extraction issue was diagnosed as benchmark ambiguity: the model interpreted `site_name` as `"Clear Lake"` while the validator expected station code `CLW-07`. The fixture and validator now use `site_id`; `study_001` / `trial_002` produced a clean 5-run report with no mismatches or validator failures.

Aggregated task records now expose both `created_at` and `updated_at`. Raw ledger events already had timestamps; this makes the reduced task view and CSV export more useful for review and reporting.

Ledger task cards now have a Details/Hide toggle. Expanded cards show timestamps, prompt, routing, model/backend, benchmark status, handoff reason, artifacts, and review metrics while preserving expanded state across refreshes.

The dispatch screen now opens maximized with the Windows title bar visible, uses larger self-describing dispatch controls, includes a compact live backend/activity log under the output box, and shows richer subagent states for queued/running/complete/issue worker activity.

The dispatch screen now also includes a compact recent task ledger feed. Ledger review cards include a short assessment snapshot before dense details, with clearer `Approve & Load` and `Deny` actions for human review.

Verification instructions are now documented in `docs/verification_guide.md`, including code checks, UI review checks, study evidence checks, and human-reviewed learning rules.

Reviewable ledger cards now include an optional `Review load` selector (`not_recorded`, `low`, `medium`, `high`). The selection is stored in review records as `review_workload` and documented in the evidence schema and methodology artifacts as a subjective review-burden measure.

The superseded `study_001` / `trial_001` structured-extraction proposals were explicitly rejected in `.triagecore/learning_reviews.jsonl`: `961b769f4d1c`, `2cc74fd2cabf`, and `6b2e9cdfdd20`. They were rejected because the failure was traced to `site_name` benchmark ambiguity and resolved by the `site_id` fixture/validator clarification in `trial_002`.

Study 002 model/backend comparison has begun. Benchmark reports now include a `By Backend` grouping, and `docs/study_002_model_backend_comparison.md` defines the comparison protocol and command pattern.

Next step: run the first `study_002` comparison pair and generate `reports/study_002_model_backend_comparison.md`.
