# TriageCore & TriageDesk Backlog

This backlog tracks the planned features and scientific enhancements for the local-compute-first orchestration harness and control plane.

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

* [ ] **Story 5.3: Human Review Superseded Learning Proposals**
  * Review the `structured_extraction` proposals generated from `trial_001`.
  * Record whether they are rejected or superseded because the failure came from benchmark ambiguity.
  * Keep the review decision explicit before using accepted/rejected proposals to guide future behavior.

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
* [ ] **Story 6.6: Accessibility And Workload Review**
  * Audit keyboard focus order, visible focus states, and minimum click/tap target size.
  * Add user-adjustable density or reduced-motion preferences if visual load increases.
  * Consider a lightweight workload self-check after complex agent sessions.
* [x] **Story 6.7: Review Card Decision Clarity**
  * Add a compact assessment snapshot to each ledger review card.
  * Keep forensic evidence behind Details so approval/denial does not require scanning every field.
  * Rename review actions to `Approve & Load` and `Deny`.
* [x] **Story 6.8: Verification Guidance**
  * Add a practical verification guide for code checks, UI review checks, study evidence checks, and human learning reviews.
