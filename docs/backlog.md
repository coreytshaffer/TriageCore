# TriageCore & TriageDesk Backlog

This backlog tracks the planned features and scientific enhancements for the local-compute-first orchestration harness and control plane.

## Foundation Backlog Closure

Status: closed as the completed foundation backlog.

Phases 1 through 10 established the working TriageCore foundation: human review, ledger validation, skill routing, sustainability telemetry, visible infrastructure, study evidence, UI ergonomics, Codex/Antigravity supervision, private mobile review access, and persistent environmental feedback.

The next active backlog begins at Phase 11 and shifts the project from "can we observe and coordinate the workflow?" to "can we measurably reduce unnecessary tokens while preserving accepted outcomes, human review, and scientific caution?"

## 🟢 Phase 1: Interactive Human review & Ledger Validation

* [x] **Story 1.1: TriageDesk Task Review Buttons**
  * Render Accept/Reject controls inside completed task cards in the ledger UI.
  * Persist human decisions (`accepted: true/false`) to `.triagecore/ledger.jsonl`.
  * Update card styling to turn Green (Accepted) or Red (Rejected) immediately.
  * Recalculate and update the live telemetry dashboard metrics instantly.

## 🟡 Phase 2: Context Engineering & Skills-Based Routing

* [x] **Story 2.1: Dynamic Skill Files**
  * Move hardcoded agent prompt instructions out of `worker_registry.py` and into external `.md` files under `triage_core/skills/`.
  * Enable dynamic prompt loading from file assets to allow rapid tuning of worker behaviors.
* [x] **Story 2.2: LLM-Based Router**
  * Replace the static python keyword checks in `TaskClassifier` with a lightweight LLM routing call.
  * Instruct the local model to classify incoming requests against registered skills or tag them as `"heavy_lifting"` for cloud handoff.

## 🔵 Phase 3: High-Fidelity Sustainability Telemetry

* [x] **Story 3.1: Automated Human Review Timer**
  * Add a stopwatch UI widget that automatically records `human_review_minutes` from draft completion to human accept/reject click.
* [x] **Story 3.2: Dynamic Power Telemetry (NVML/RAPL)**
  * Integrate hardware measurements using NVML (Nvidia GPUs) and RAPL (Intel/AMD CPUs) to capture real-time power draw during tasks.
* [x] **Story 3.3: Dynamic Grid Carbon Intensity API**
  * Integrate location-based grid APIs (like ElectricityMaps or WattTime) to fetch live carbon intensity instead of static global defaults.

## 🟣 Phase 4: Visible Infrastructure & Audit Tools

* [x] **Story 4.1: TriageDesk System Logs Tab**
  * Configure a file logger (`triagecore.log`) to record internal orchestration milestones, handoff warnings, and errors.
  * Render a scrollable console in TriageDesk showing live run logs and raw JSONL ledger contents.

## Completed Study Evidence Slice

Study 001 has a clean operational baseline, scoped study reporting, and stronger deterministic validators. The validator hardening rerun surfaced one useful mismatch: `json_extraction_small_v1` triggers `handoff_required` under the stricter `monitoring_json` validator.

Recommended next slice:

* [x] **Story 5.1: Add Run/Trial IDs for Study Evidence**
  * Add a `run_id` or `trial_id` field to benchmark ledger records.
  * Let `benchmark`, `benchmark-report`, and `propose-lessons` filter by both `study_id` and `run_id`.
  * Use this before tuning prompts or validators so repeated Study 001 runs do not aggregate into one summary.

After run/trial scoping is in place, review whether `json_extraction_small_v1` needs prompt tuning, validator adjustment, or a model/backend comparison.

## Current Decision Point

* [x] **Story 5.2: Review Structured Extraction Failure**
  * Inspect the `structured_extraction` learning proposals from `study_001` / `trial_001`.
  * Decide whether the failure is prompt wording, validator strictness, model behavior, or backend configuration.
  * Apply only one change at a time, then rerun with a new `run_id`.

Resolution: diagnostic output showed valid JSON with ambiguous `site_name` semantics. The fixture and validator now use `site_id`; `trial_002` restored the expected Study 001 baseline with no mismatches or validator failures.

## Current Decision Point

* [x] **Story 5.3: Human Review Superseded Learning Proposals**
  * Review the `structured_extraction` proposals generated from `trial_001`.
  * Record whether they are rejected or superseded because the failure came from benchmark ambiguity.
  * Keep the review decision explicit before using accepted/rejected proposals to guide future behavior.

Resolution: proposal IDs `961b769f4d1c`, `2cc74fd2cabf`, and `6b2e9cdfdd20` were rejected as superseded by the `site_id` fixture/validator clarification and clean `trial_002` rerun.

## UI Workflow Improvements

* [x] **Story 6.1: Expandable Ledger Review Cards**
  * Add a Details/Hide toggle to ledger task cards.
  * Show timestamps, routing, benchmark context, handoff reasons, artifacts, and review metrics inside expanded cards.
  * Preserve expanded cards across ledger refreshes.
* [x] **Story 6.2: Main Screen Ledger Feed**
  * Add a compact scrolling task ledger feed to the main dispatch/dashboard screen.
  * Keep the feed lightweight so it gives recent activity context without replacing the full ledger view.
* [x] **Story 6.3: Live Backend Activity Panel**
  * Add a compact live-scrolling activity log below the dispatch output box.
  * Tail TriageCore backend events during local, council, Codex, and Antigravity runs.
  * Prepare future hooks for external Ollama and LM Studio process logs when their log paths or APIs are configured.
* [x] **Story 6.4: Rich Subagent Status Indicators**
  * Replace binary red/green worker dots with queued/running/complete/issue states.
  * Show last activity details such as model, duration, and token estimates per worker.
  * Preserve enough signal for quick scanning without requiring the full logs view.
* [x] **Story 6.5: Dispatch Control Ergonomics**
  * Increase primary dispatch button size and labels.
  * Use numbered left-to-right action text for Local Draft, Worker Council, Codex Handoff, and Antigravity Handoff.
  * Continue toward keyboard focus, target-size, and workload-reduction improvements.
* [x] **Story 6.6: Accessibility And Workload Review**
  * Added an optional review workload selector to reviewable ledger cards.
  * Persist subjective workload as `review_workload` beside review time.
  * Document workload capture in the evidence schema, verification guide, accessibility note, and methodology artifacts.
* [x] **Story 6.7: Review Card Decision Clarity**
  * Add a compact assessment snapshot to each ledger review card.
  * Keep forensic evidence behind Details so approval/denial does not require scanning every field.
  * Rename review actions to `Approve & Load` and `Deny`.
* [x] **Story 6.8: Verification Guidance**
  * Add a practical verification guide for code checks, UI review checks, study evidence checks, and human learning reviews.
* [x] **Story 6.9: Visual Accessibility QA**
  * Launch TriageDesk and manually verify keyboard focus order, visible focus states, text fit, and minimum click/tap target size.
  * Confirm the review workload selector does not make cards visually noisy or harder to assess.
  * Record any UI fixes from the manual pass as a separate focused change.
* [x] **Story 6.10: CLI-To-Desktop Observability Verification**
  * [x] Ensure CLI-initiated work writes visible activity lines to `triagecore.log`.
  * [x] Ensure CLI `run-pipeline` appends ledger task evidence for success and handoff outcomes.
  * [x] Confirm TriageDesk live backend/activity log displays `[cli]` activity while the desktop app is open.
  * [x] Confirm CLI-created ledger tasks appear in the recent task ledger panel and raw ledger view.
  * [x] Record any display or refresh fixes as a separate focused change.

## Model And Backend Comparison

* [x] **Story 7.1: Prepare Study 002 Comparison Protocol**
  * Add a model/backend comparison study plan.
  * Extend benchmark reports with a backend-level grouping separate from backend/model grouping.
  * Document command patterns for unique run IDs per backend/model pair.
* [x] **Story 7.2: Run Study 002 First Comparison Pair**
  * Run the existing benchmark fixture set for at least two backend/model pairs under `study_002`.
  * Generate `reports/study_002_model_backend_comparison.md`.
  * Review mismatches, unexpected handoffs, validator failures, and learning proposals.

## Codex And Antigravity Bridge

* [x] **Story 8.1: Record Supervisor Reviews In The Ledger**
  * Add a `supervisor_reviewed` ledger event for Codex, Antigravity, Gemini, or human supervisor decisions.
  * Add a `record-supervisor-review` CLI command so supervised work can be logged without editing JSONL by hand.
  * Document the bridge protocol for separating local-only runs from Codex- or Antigravity-supervised workflows.
* [x] **Story 8.2: Surface Supervisor Reviews In UI And Reports**
  * Show supervisor review fields inside expandable ledger detail cards.
  * Add report grouping for local-only, Codex-supervised, and Antigravity-supervised outcomes.
  * Capture exact supervisor token usage when a tool surface exposes it; otherwise keep estimates clearly labelled.
* [x] **Story 8.3: Link Supervisor Reviews To Formal Study Evidence**
  * Add study/run context to supervisor review interpretation where available.
  * Decide whether supervisor-review token estimates should remain manual or be imported from external tool logs.
  * Add a small generated supervisor-review summary for papers and session handoffs.
* [x] **Story 8.4: Import Supervisor Usage From Tool Logs**
  * [x] Add a generic opt-in JSON/JSONL importer for supervisor usage artifacts.
  * [x] Add a read-only scanner for discovering importable JSON/JSONL supervisor usage artifacts.
  * [x] Add dry-run preview so candidate imports can be verified before ledger mutation.
  * [x] Identify where Codex, Antigravity, Gemini, or IDE supervisor usage is exposed on disk or through APIs.
  * [x] Add tool-specific import adapters once exact log formats are verified.
  * [x] Preserve manual estimates as the fallback when exact usage cannot be verified.

Local search note: Antigravity brain files currently show narrative token estimates and context-limit findings, but not a verified exact machine-readable supervisor usage log format yet. The read-only scanner found no importable JSON/JSONL supervisor usage artifacts under `C:\Users\corey\.gemini\antigravity-ide\brain`.

## Private Mobile Access

* [x] **Story 9.1: Private Mobile Control Surface**
  * [x] Explore a mobile app or lightweight mobile web client that connects to the locally hosted TriageCore/model pipeline at home.
  * [x] Require private connectivity such as VPN, Tailscale, WireGuard, or another explicitly approved tunnel rather than exposing the local model server directly to the public internet.
  * [x] Keep the mobile surface bounded to review, approve/deny, monitor logs, and submit small tasks before allowing any write-capable workflow.
  * [x] Preserve local-first evidence capture: every remote mobile action should still append to the local ledger with actor, timestamp, connection mode, and review decision context.
  * [x] Treat security, family privacy, and remote access failure modes as acceptance criteria before implementation.

## Persistent Environmental Feedback

* [x] **Story 10.1: System Tray/Widget**
  * Add a desktop system tray object that displays throughput and basic stats (tasks processed, active backend, energy saved).
  * Integrate into `desktop.py` to provide a single background/foreground execution model.

## 🧠 Phase 11: Token Efficiency And Context Discipline

Goal: turn token accounting into active token stewardship. This phase should reduce unnecessary context, prompts, council calls, retries, and supervisor tokens while keeping all claims evidence-bound.

Primary scientific outcome: tokens per accepted task, interpreted beside validator pass rate, review workload, handoff rate, and supervision lane.

* [x] **Story 11.1: Context Budget Planner**
  * [x] Estimate token cost before each local, council, Codex, Antigravity, benchmark, or pipeline run.
  * [x] Classify context as required, helpful, optional, or excluded.
  * [x] Warn when a task exceeds the expected budget for its category.
  * [x] Keep the planner advisory until repeated evidence supports automatic enforcement.

* [x] **Story 11.2: Context Pack Artifacts**
  * [x] Write a compact context-pack artifact for each task attempt.
  * [x] Record included files, excluded files, summaries, token estimates, and inclusion rationale.
  * [x] Link context packs to the task ledger so reports can audit what the model actually saw.
  * [x] Preserve reproducibility without forcing every future reviewer to reread the entire chat.

* [ ] **Story 11.3: Council Gating Rules**
  * Add deterministic rules for when Worker Council should run.
  * Route small low-risk tasks through one local draft plus validator before council escalation.
  * Escalate to council for ambiguous, safety-sensitive, multi-file, or repeated-failure work.
  * Report tokens saved by avoiding unnecessary council passes as an operational benefit signal, not a formal savings claim without a baseline.

* [ ] **Story 11.4: Prompt And Output Compression Study**
  * Create benchmark variants for short, structured, and verbose prompts.
  * Measure tokens per accepted task, validator pass rate, handoff rate, and review workload.
  * Compare compact output formats against full prose output where task quality permits.
  * Add methodology notes so compression is not treated as better unless quality remains acceptable.

* [ ] **Story 11.5: Token Budget Alerts**
  * Define soft and hard token budgets by benchmark category and runner lane.
  * Surface budget warnings in TriageDesk before dispatch.
  * Allow the human operator to override budget warnings with a recorded reason.
  * Store budget exceedance events in the ledger for later analysis.

* [ ] **Story 11.6: Reusable Context Cache**
  * Cache stable repo summaries, methodology summaries, project rules, and benchmark fixture summaries.
  * Track cache freshness by file hash or timestamp.
  * Prefer cached summaries when unchanged instead of regenerating context every run.
  * Record cache hits and misses as token-efficiency evidence.

* [ ] **Story 11.7: Token Efficiency Report Section**
  * Add report sections for tokens per accepted task, tokens per rejected task, and supervisor tokens per accepted task.
  * Separate local-only, worker-council, Codex-supervised, Antigravity-supervised, and mobile-reviewed lanes.
  * Include "wasted token" indicators for rejected, failed, blocked, or superseded work.
  * Keep wording cautious: report measured token intensity and benefit signals, not absolute savings without baseline comparisons.

* [ ] **Story 11.8: Token Efficiency Dashboard View**
  * Add a dashboard panel that foregrounds tokens avoided or kept local as operator-facing motivation.
  * Keep raw token consumption visible for scientific interpretation.
  * Show context budget, local-first share, council gating decisions, and cache reuse in a compact view.
  * Make the UI encouraging without turning preliminary benefit signals into unsupported scientific claims.

## Current Phase 11 Decision Point

Story 11.1 and Story 11.2 now have a first advisory implementation. Context pack artifacts are generated for CLI packets, benchmarks, pipeline runs, and TriageDesk dispatches; ledger records reduce the context budget fields and expanded UI details show the pack path/status.

Next recommended slice: Story 11.3. Add council gating rules that use task risk, context budget status, file count, and prior failure evidence to decide when Worker Council is worth the extra token spend.
