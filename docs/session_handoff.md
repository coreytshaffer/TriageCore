# Session Handoff

Last updated: 2026-06-04

## Current State

- Active branch: `main`
- Current slice: Codex/Antigravity bridge for supervised local workflows
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

Latest verification:

```bash
python -m py_compile triage_core\sustainability.py triage_core\task_ledger.py triage_core\cli.py
python -m pytest
```

Result:

```text
86 passed
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

The Codex/Antigravity bridge now has a ledger event and CLI command for supervised work:

```bash
triagecore record-supervisor-review <task_id> --tool codex --decision needs_revision --notes "Local draft missed tests." --model gpt-5 --profile high
triagecore record-supervisor-review <task_id> --tool antigravity --decision accepted --notes "IDE supervisor accepted the local draft." --model gemini-3.1-pro-high --profile supervisor
```

The bridge protocol is documented in `docs/codex_antigravity_bridge.md`, and the methodology now distinguishes local-only outcomes from Codex- or Antigravity-supervised outcomes.

Supervisor reviews now appear in expanded ledger detail text, compact assessment snapshots, and compact ledger feed lines. Benchmark reports now include a `By Supervision` section so local-only runs can be separated from Codex-supervised and Antigravity-supervised outcomes.

Benchmark reports now also include a `Supervisor Reviews` table under the active `study_id` and `run_id` filters. It summarizes review counts, decision counts, and estimated supervisor token totals by tool for paper-facing evidence.

TriageCore now includes a generic `scan-supervisor-usage` command for read-only discovery and an `import-supervisor-usage` command for JSON or JSONL supervisor usage artifacts. Imported values can be labelled as `imported_estimate` or `imported_exact`; manual `record-supervisor-review` entries default to `manual_estimate`.

The importer now supports `--dry-run` so candidate supervisor usage artifacts can be previewed before ledger mutation. A local search of Antigravity brain files found narrative token estimates and context-limit notes, but not a verified exact machine-readable supervisor usage log format yet. The read-only scanner found no importable JSON/JSONL supervisor usage artifacts under `C:\Users\corey\.gemini\antigravity-ide\brain`.

CLI commands that create or scan visible work now append `[cli]` activity lines to `triagecore.log`, which TriageDesk already tails in the live backend/activity log. Manual verification is still pending: run TriageDesk, execute a CLI command, and confirm the live log plus recent task ledger panel update as expected.

CLI `run-pipeline` now creates or appends a ledger task, records runner `pipeline`, stores success evidence as `local_draft_generated`, and records handoff outcomes as blocked tasks. This gives TriageDesk ledger views a concrete task record to display for CLI-started pipeline work.

Next step: identify where Codex, Antigravity, Gemini, or IDE supervisor token usage is exposed in a stable exact format, then add tool-specific adapters that feed the generic importer while preserving manual estimates as the fallback.

Future idea captured in backlog: a private mobile app or mobile web control surface that connects to the locally hosted TriageCore/model pipeline at home through a private tunnel such as VPN, Tailscale, or WireGuard. The initial mobile scope should stay bounded to review, approve/deny, logs, and small task submission before any write-capable workflow.
