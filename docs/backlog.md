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

## Current Decision Point

Study 001 has a clean operational baseline, scoped study reporting, and stronger deterministic validators. The validator hardening rerun surfaced one useful mismatch: `json_extraction_small_v1` triggers `handoff_required` under the stricter `monitoring_json` validator.

Recommended next slice:

* [ ] **Story 5.1: Add Run/Trial IDs for Study Evidence**
  * Add a `run_id` or `trial_id` field to benchmark ledger records.
  * Let `benchmark`, `benchmark-report`, and `propose-lessons` filter by both `study_id` and `run_id`.
  * Use this before tuning prompts or validators so repeated Study 001 runs do not aggregate into one summary.

After run/trial scoping is in place, review whether `json_extraction_small_v1` needs prompt tuning, validator adjustment, or a model/backend comparison.
