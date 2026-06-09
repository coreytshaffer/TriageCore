# TriageCore Performance Backlog

## Purpose

This backlog tracks TriageCore performance work learned from SafeTask AI development.

SafeTask AI is the source project for examples and telemetry. TriageCore is the separate local-LLM assignment learner and should own the final router, lesson store, and implementation code.

## Status Key

- `[ ]` Not started
- `[~]` Started or documented, but not implemented in the real TriageCore system
- `[x]` Complete enough as a learning artifact

## Performance Goal

Improve TriageCore's ability to:

- get higher useful output per local model call
- lower wasted retries and overpowered model use
- expand the variety of tasks that can be confidently assigned to local LLM combinations
- keep cloud, local, deterministic, and human-handoff paths explicit

## Gate TC-0: Boundary And Seed Evidence

- [x] Story TC-0.1: Clarify the SafeTask/TriageCore boundary.
  - Acceptance: Learning docs state that SafeTask AI is source-project evidence and TriageCore owns the assignment learner.
  - Artifact: `triagecore-performance-lessons-from-safetask.md`
- [x] Story TC-0.2: Seed SafeTask-derived assignment outcome examples.
  - Acceptance: JSONL examples parse and include required fields.
  - Artifact: `examples/triagecore-assignment-outcomes.safetask.jsonl`
- [x] Story TC-0.3: Add an improvement ranking gate.
  - Acceptance: New proposals receive a confidence score and bucket.
  - Artifact: `triagecore-improvement-ranking-system.md`
- [x] Story TC-0.4: Add a low-priority container.
  - Acceptance: Candidates below `0.65` confidence have a holding area.
  - Artifact: `triagecore-low-priority-improvements.md`

## Gate TC-1: Assignment Outcome Telemetry

- [x] Story TC-1.1: Define assignment outcome schema.
  - Acceptance: Schema captures task class, model combo, tool path, result status, correction burden, waste signal, and confidence after review.
  - Artifact: `triagecore-assignment-outcome-schema.md`
- [x] Story TC-1.2: Add SafeTask outcome seed records.
  - Acceptance: At least three examples exist and validate.
  - Current count: 3 outcome records.
- [x] Story TC-1.3: Move outcome schema into the real TriageCore lesson store.
  - Acceptance: TriageCore can read the schema and records outside the SafeTask AI repo.
- [x] Story TC-1.4: Add outcome ingestion command.
  - Acceptance: A local command can validate and import JSONL outcome records.

## Gate TC-2: Task-Class To Local-Combo Routing

- [x] Story TC-2.1: Define starter local-combo routing map.
  - Acceptance: Task classes map to default local combos, required checks, confidence, and human-review posture.
  - Artifact: `triagecore-local-combo-routing-map.md`
- [ ] Story TC-2.2: Implement task-class routing map in TriageCore.
  - Acceptance: TriageCore can return the default combo and required checks for a task class.
- [ ] Story TC-2.3: Update task-class confidence from outcome records.
  - Acceptance: Repeated accepted outcomes can raise confidence; repeated corrections or waste signals can lower it.

## Gate TC-3: Waste Controls

- [x] Story TC-3.1: Define waste signals and escalation rules.
  - Acceptance: Rules cover overpowered, underpowered, repeated retry, missing context, tool-should-handle, ambiguous scope, and human-review-required cases.
  - Artifact: `triagecore-waste-controls.md`
- [ ] Story TC-3.2: Add waste-signal evaluation in TriageCore.
  - Acceptance: TriageCore can classify an outcome record's waste signal and suggest next action.
- [ ] Story TC-3.3: Add downgrade/escalation recommendations.
  - Acceptance: Repeated low-burden successes suggest smaller combos; repeated high-burden outcomes suggest stronger combos or more deterministic checks.

## Gate TC-4: Assignment Preflight

- [x] Story TC-4.1: Define assignment preflight schema.
  - Acceptance: Schema captures task class, required context, candidate combo, required checks, stop conditions, and confidence before assignment.
  - Artifact: `triagecore-assignment-preflight-schema.md`
- [x] Story TC-4.2: Seed SafeTask preflight examples.
  - Acceptance: At least three preflight records exist and validate.
  - Current count: 3 preflight records.
- [ ] Story TC-4.3: Add preflight command in TriageCore.
  - Acceptance: TriageCore can produce a preflight record before assigning non-trivial work.
- [ ] Story TC-4.4: Compare preflight predictions to outcomes.
  - Acceptance: TriageCore can report predicted-vs-actual task class, checks, waste, and confidence movement.

## Gate TC-5: Context Packaging

- [x] Story TC-5.1: Define context pack templates.
  - Acceptance: Templates exist for repo evidence, code slice, review packet, benchmark, and handoff packs.
  - Artifact: `triagecore-context-pack-templates.md`
- [x] Story TC-5.2: Seed SafeTask context pack examples.
  - Acceptance: At least three context pack records exist and validate.
  - Current count: 3 context pack records.
- [x] Story TC-5.3: Link outcomes to preflight and context pack IDs.
  - Acceptance: Outcome records reference existing preflight and context pack records.
- [ ] Story TC-5.4: Add context pack builder in TriageCore.
  - Acceptance: TriageCore can build a compact pack for a task class and source project.
- [ ] Story TC-5.5: Track context-pack quality.
  - Acceptance: Missing-context waste can be tied back to omitted context-pack fields.

## Gate TC-6: Resilience And Capability Routing

- [x] Story TC-6.1: Rank resilience routing as an active candidate.
  - Acceptance: Candidate `TCP-007` has score, bucket, route modes, and verification plan.
  - Artifact: `triagecore-resilience-routing.md`
- [x] Story TC-6.2: Implement static resilience router in TriageCore.
  - Acceptance: Router chooses among `cloud_primary`, `cloud_secondary`, `local_heavy`, `local_fast`, `deterministic`, and `human_handoff`.
- [x] Story TC-6.3: Add route-decision and worker-result ledger events.
  - Acceptance: TriageCore records selected route, reason, provider health, fallback depth, validation status, and failure type.
- [ ] Story TC-6.4: Add circuit breakers.
  - Acceptance: Repeated failures cool down a backend instead of retrying indefinitely.
- [ ] Story TC-6.5: Add degraded/offline mode states.
  - Acceptance: TriageCore can distinguish normal, degraded-cloud, offline-local, local-minimal, deterministic-only, and human-handoff modes.

## Gate TC-7: Replay Benchmarks

- [ ] Story TC-7.1: Define a local combo replay benchmark manifest.
  - Acceptance: Manifest includes prompts, allowed context, expected checks, pass/fail criteria, and scoring notes.
- [ ] Story TC-7.2: Add starter replay set from SafeTask examples.
  - Acceptance: Replay tasks cover documentation synthesis, smoke-check design, configuration review, UI/API planning, and vague-request classification.
- [ ] Story TC-7.3: Record replay outcomes.
  - Acceptance: Benchmark results can update routing confidence by task class and combo.

## Current Validated Seed Counts

- Preflight records: 3
- Context pack records: 3
- Outcome records: 3
- Missing preflight references from outcomes: 0
- Missing context-pack references from outcomes: 0

## Next Best Step

The learning artifacts now live in the actual TriageCore repo under `docs/learning/`, `import-learning-seeds` validates the seed preflight, context-pack, and outcome JSONL records before optional `--write` import into `.triagecore/learning_seeds/`, `triage_core/routing/resilience_router.py` can choose safe cloud, local, deterministic, or human-handoff paths from static capability inputs, and `route_decision` plus `worker_result` events now land in the ledger for benchmark and stability-pass runs. Start Story TC-6.4 / Phase 13 Story 13.6: add circuit breakers and degraded mode states so unstable routes cool down instead of retrying immediately.
