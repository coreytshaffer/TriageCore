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

* [x] **Story 11.3: Cybernetic Ecology Boundary Harness Integration**
  * [x] Integrate framework principles (community/sovereignty boundaries, public health, regulatory interpretation) as active firewall policies in `ProjectSteward`.
  * [x] Let the harness dynamically inspect prompts and outputs, warning or blocking execution based on local-first policy files (JSON/YAML).
  * [x] Verify that the ethical firewall escalates sensitive contexts (e.g., Bloody Island, sacred/archaeological sites) cleanly.

* [x] **Story 11.4: Escalate to Antigravity on Credit Allowance Depletion**
  * [x] Track a local token/credit allowance limit or budget within `ProjectSteward` or a credit coordinator.
  * [x] When the credit allowance runs out, trigger a structured handoff/escalation to Antigravity (cloud coordinator) for allowance optimization or approval, ensuring the steward remains operational.

* [x] **Story 11.5: Early Stopping for Energy Budget Overruns (Study 003)**
  * Implement dynamic "early stopping" during task execution when real-time energy telemetry (measured via `PowerSampler` or estimated) projects that the task will overrun its configured max energy budget.
  * Base this early stopping method on recent research regarding energy-aware resource allocation, terminating model inference early to save local power.

* [x] **Story 11.6: Post-Sprint Codex Stability Pass**
  * Establish a formal Codex-run stability pass script/procedure (`triagecore stability-pass`) to run after each sprint.
  * Automatically verify harness boundary enforcement, logging compliance, and regression safety across all benchmark tasks.

* [x] **Story 11.7: Token Efficiency and Escaped Waste Reporting**
  * [x] Add reporting for wasted tokens (e.g., on cancelled/failed workers or early-stopped tasks).
  * [x] Track credit consumption and report on cost-benefit metrics per runner lane.

* [x] **Story 11.8: Integrated Telemetry Dashboard Controls**
  * [x] Surface early stopping events, firewall triggers, credit status, and stability pass results directly on the TriageDesk GUI.

## 🧪 Phase 12: TriageLab Analytical Engine & Predictive Routing

Goal: Shift from operational tracking to analytical optimization, converting the historical ledger into training datasets and predictive routing policies.

* [x] **Story 12.1: TriageLab Stats and Markdown Reporting CLI**
  * Implement a derived view over `ledger.jsonl` calculating primary scientific metrics (e.g., accepted-task yield, mean review burden, mean tokens/kWh per accepted task).
  * Expose via CLI: `triagecore stats` or `triagecore lab report`.
* [x] **Story 12.2: TriageLab Tabular Dataset Export**
  * Implement `triagecore lab export --format csv` (and/or parquet) to extract an ML-ready flat feature table (e.g., including quantization, model, tokens, duration, and human acceptance).
* [x] **Story 12.3: Predictive Local Success Warning**
  * Train an interpretable predictor (Logistic Regression / Decision Tree) on exported run data.
  * Integrate an advisory warning before dispatching a task if local execution has a high projected failure/escalation probability.

## 🧭 Phase 13: Resilience Routing And Assignment Learning Store

Goal: turn TriageCore's local-first evidence loop into a concrete assignment-learning system that can route work across cloud, local heavy, local fast, deterministic, and human-handoff paths without wasting attempts or hiding uncertainty.

Primary performance outcome: higher accepted work per local model call, lower retry waste, and more task classes confidently assignable to local LLM combinations.

Boundary: SafeTask AI can provide seed examples and telemetry, but TriageCore owns the lesson store, routing policy, and implementation code.

* [x] **Story 13.1: Import SafeTask-Derived Learning Seed Artifacts**
  * [x] Create `docs/learning/` in the TriageCore repo.
  * [x] Import assignment outcome, preflight, context-pack, routing-map, waste-control, ranking-gate, low-priority, resilience-routing, and performance-backlog artifacts.
  * [x] Preserve SafeTask references as source-project evidence only.

* [x] **Story 13.2: Establish Assignment Learning Schemas**
  * [x] Define assignment outcome schema.
  * [x] Define assignment preflight schema.
  * [x] Define context pack templates.
  * [x] Seed three SafeTask-derived preflight records, context packs, and outcome records.
  * [x] Validate that outcome records reference existing preflight and context-pack IDs.

* [x] **Story 13.3: Add Learning Seed Import Command**
  * [x] Add `import-learning-seeds` to validate and import JSONL seed records into `.triagecore/learning_seeds/`.
  * [x] Acceptance: invalid records report missing fields or broken references and do not mutate the lesson store.
  * [x] Acceptance: imported records keep `source_project` labels so SafeTask data remains clearly external evidence.
  * [x] Acceptance: command defaults to dry-run validation; `--write` is required before records are stored.

* [x] **Story 13.4: Implement Static Resilience Router**
  * [x] Add `triage_core/routing/resilience_router.py`.
  * [x] Route across `cloud_primary`, `cloud_secondary`, `local_heavy`, `local_fast`, `deterministic`, and `human_handoff`.
  * [x] Acceptance: route choice considers internet/cloud credit state, LM Studio health, local model availability, memory headroom, task class, sensitivity, deterministic tool availability, and recent failures.
  * [x] Acceptance: high-sensitivity work routes to human handoff instead of silently using local or cloud automation.

* [x] **Story 13.5: Record Route-Decision And Worker-Result Ledger Events**
  * [x] Add structured `route_decision` and `worker_result` events.
  * [x] Acceptance: events capture selected route, selected model/backend, reason, provider health, fallback depth, validation status, duration, tokens, and failure type.
  * [x] Acceptance: safety handoffs are recorded as `not_attempted` router outcomes instead of backend failures.

* [ ] **Story 13.6: Add Circuit Breakers And Degraded Mode States**
  * Add cooldown rules for failing cloud, local heavy, and local fast providers.
  * Add mode states: `normal`, `degraded_cloud`, `offline_local`, `local_minimal`, `deterministic_only`, and `human_handoff`.
  * Acceptance: repeated provider failure opens a circuit breaker; recovery requires stable checks before normal routing resumes.

* [ ] **Story 13.7: Connect Preflight To Assignment Outcomes**
  * Add preflight generation for non-trivial tasks.
  * Compare predicted task class, selected combo, required checks, and stop conditions against the final outcome.
  * Acceptance: TriageCore can report whether the preflight prevented waste or needs tuning.

* [ ] **Story 13.8: Build Replay Benchmark Manifest**
  * Define a local combo replay benchmark from the SafeTask-derived examples.
  * Acceptance: replay tasks include prompt, allowed context, expected checks, pass/fail criteria, and scoring notes.
  * Acceptance: replay results can update task-class confidence without automatic routing changes.

## Current Phase 13 Next Step

Start with Story 13.6. The seed files now have a TriageCore-owned validation/import path, the static resilience router exists, and route-decision plus worker-result telemetry now lands in the ledger for benchmark and stability-pass runs. The next performance slice is to add circuit breakers and degraded mode states so failing routes cool down instead of retrying indefinitely.

## Future Phase 14: Local Compute Fabric v0.1

Status: deferred architecture backlog. Do not begin this phase until Phase 13 route telemetry, circuit breakers, preflight/outcome comparison, and replay benchmarks are complete enough to provide a stable routing foundation.

Goal: model trusted local devices as capability-bearing nodes, route explicit tasks to compatible nodes, execute only allowlisted deterministic actions, and preserve human approval and auditability. The first version may run entirely on one machine; it should establish the system shape before adding real networking.

* [ ] **Story 14.1: Add Node Capability Manifests**
  * Define node ID, display name, node type, trust level, capabilities, concurrency limit, and task timeout.
  * Acceptance: valid JSON manifests load; missing fields and malformed capabilities fail with actionable errors.

* [ ] **Story 14.2: Add Explicit Task Request Schema**
  * Define task ID, project, intent, required capabilities, inputs, risk level, and approval requirement.
  * Support risk levels: `read_only`, `safe_tool`, `draft_write`, `repo_write`, `external_write`, and `destructive`.
  * Acceptance: unknown risk levels and malformed task requests fail closed.

* [ ] **Story 14.3: Add Local Fabric Audit Store**
  * Persist nodes, tasks, task events, and task results using a modest local store such as SQLite.
  * Acceptance: lifecycle events are timestamped, ordered, JSON-serializable, and queryable.
  * Reuse or bridge the existing TriageCore ledger where practical instead of creating competing runtime truth.

* [ ] **Story 14.4: Add Deterministic Capability Router**
  * Filter active nodes by required capabilities, trust level, risk level, concurrency, and availability.
  * Return an explainable routed or unroutable decision.
  * Acceptance: no compatible node produces a safe, auditable fallback instead of an implicit execution attempt.

* [ ] **Story 14.5: Add Allowlisted Command Executor**
  * Start with structured command recipes for `git status`, `python -m pytest`, and `python -m compileall`.
  * Never accept arbitrary shell strings.
  * Acceptance: unknown command IDs are rejected; output, timeout, exit status, and result metadata are recorded.

* [ ] **Story 14.6: Add Single-Node Worker Loop**
  * Register one local node, claim one compatible task, execute an allowlisted action, and record completion or failure.
  * Acceptance: worker exits cleanly, respects concurrency/time limits, and cannot bypass approval state.

* [ ] **Story 14.7: Add Fabric CLI Commands**
  * Add bounded commands for initialization, node registration, task submission, routing, one-task execution, status, and recent events.
  * Acceptance: CLI output clearly distinguishes pending, awaiting approval, routed, running, completed, failed, rejected, and unroutable tasks.

* [ ] **Story 14.8: Add LM Studio Provider Capability Stub**
  * Represent `llm.local.chat`, `llm.local.summarize`, and `llm.local.review` as optional node capabilities.
  * Read the LM Studio base URL from configuration and provide a health check.
  * Acceptance: LM Studio being offline disables the capability without crashing deterministic fabric operations.

* [ ] **Story 14.9: Add Dry-Run Fabric Routing**
  * Show the selected node and explain why other nodes were rejected without mutating task state.
  * Acceptance: dry-run output is suitable for capability-manifest debugging and human review.

* [ ] **Story 14.10: Add Human Approval Gate**
  * Hold `repo_write`, `external_write`, and `destructive` tasks in `awaiting_approval`.
  * Add explicit approve/reject actions and audit both decisions.
  * Acceptance: high-risk tasks cannot route to execution without recorded human approval; destructive tasks remain blocked by default.

### Phase 14 Definition Of Done

The local-only fabric milestone is complete when one registered node can receive a capability-matched task, execute an allowlisted deterministic command, record ordered audit events and results, and fail safely when capabilities or approvals are missing.

### Phase 14 Non-Goals

- mobile UI changes
- LAN auto-discovery
- peer-to-peer mesh or consensus
- container orchestration
- arbitrary remote shell execution
- autonomous GitHub pushes
- autonomous deletion or destructive actions
- community compute contribution accounting
