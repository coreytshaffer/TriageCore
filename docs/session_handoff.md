# Session Handoff

Last updated: 2026-06-05

## Current State

- Active branch: `main`
- Current slice: Phase 11 token efficiency and context discipline
- Runtime evidence files under `.triagecore/` and generated reports under `reports/` are intentionally ignored

Recent commits:

- `f69b02b Add context budget planning artifacts`
- `cf0a119 Reconcile Antigravity local-first updates`
- `427d22c Refactor worker council into hierarchical structure with deterministic ValidatorTools`
- `22563f3 Recovery Pass: Update architecture docs and add energy heuristic telemetry`
- `6fdfcca Expand supervised workflow telemetry`

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

Superseded next step: exact supervisor-token import remains useful when a stable source appears, but the active backlog has moved past Phase 11 and Phase 12 into Phase 13 resilience routing and assignment learning. Story 13.3 Learning Seed Import Command, Story 13.4 Static Resilience Router, and Story 13.5 Route-Decision And Worker-Result Ledger Events are now complete enough for the current backlog; the current next step is Story 13.6 Circuit Breakers And Degraded Mode States.

Future idea captured in backlog: a private mobile app or mobile web control surface that connects to the locally hosted TriageCore/model pipeline at home through a private tunnel such as VPN, Tailscale, or WireGuard. The initial mobile scope should stay bounded to review, approve/deny, logs, and small task submission before any write-capable workflow.

## Backlog Phase Transition

The foundation backlog is now closed through Phase 10. Completed foundation work includes human review, ledger validation, skill routing, sustainability telemetry, visible infrastructure, study evidence, UI ergonomics, Codex/Antigravity supervision, private mobile review access, and persistent environmental feedback.

The active backlog now begins with Phase 13: Resilience Routing And Assignment Learning Store. SafeTask-derived learning artifacts have been imported into `docs/learning/` as seed evidence:

- assignment outcome, preflight, and context-pack schemas
- SafeTask-derived JSONL seed records for preflights, context packs, and outcomes
- local-combo routing map, waste controls, ranking gate, low-priority container, and resilience-routing design
- explicit boundary that SafeTask AI is source-project evidence and TriageCore owns the lesson store and router

Completed slice: Story 13.3 Learning Seed Import Command. `import-learning-seeds` validates SafeTask-derived preflight, context-pack, and outcome JSONL records, checks outcome references, defaults to dry-run, and stores records under `.triagecore/learning_seeds/` only when `--write` is supplied.

Completed slice: Story 13.4 Static Resilience Router. `triage_core/routing/resilience_router.py` provides `choose_resilience_route()` for cloud-primary, cloud-secondary, local-heavy, local-fast, deterministic, and human-handoff route modes using capability, credit, memory, task-class, sensitivity, and recent-failure inputs.

Completed slice: Story 13.5 Route-Decision And Worker-Result Ledger Events. `triage_core/routing/route_events.py` builds route and worker-result payloads from resilience-routing inputs and outcomes, and `TriageClient.run_task()` now emits those events into the ledger when a task ID and ledger are available. Benchmark and stability-pass runs record safety handoffs as router outcomes rather than backend failures.

Next recommended slice: Story 13.6 Circuit Breakers And Degraded Mode States. Add explicit route cooldown and recovery state so unstable cloud/local routes stop retrying immediately and route choice can degrade deterministically before human handoff is required.

## Codex And Antigravity Role Separation

The working protocol now treats Antigravity as the high-throughput
implementation lane and Codex as the credibility/stabilization lane.
Antigravity is best used for rapid IDE-native drafting, local model pipeline
coordination, and larger backlog movement. Codex is best used for repo
reconciliation, methodology and documentation credibility, evidence-bound
claims, verification, and Git closeout.

This is a practical division of labor, not a claim that either tool is
automatically correct. Antigravity output remains reviewable draft work until
the repo state, tests, ledger evidence, and paper-facing claims have been
checked by Codex and/or human review.
