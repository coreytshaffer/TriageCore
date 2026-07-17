# Current Backlog

## Status

This document summarizes the active TriageCore backlog after CR-126.

## Active GitHub Backlog

- CR-126: Preflight Privacy Before Ledger Persistence
  - Status: complete via CR-126
  - Purpose: Preflight the complete `tc run` packet before any ledger write, replace persisted prompt/data text with fixed metadata and lengths, and extend the persistent-artifact audit to reject forbidden keys plus high-confidence PII, credential, and precise-location value patterns. Historical records are not rewritten, and arbitrary free-text safety classification remains out of scope.

- CR-125: Honor Terminal Resilience Routes
  - Status: complete via CR-125
  - Purpose: Make `human_handoff` and the currently unimplemented `deterministic` resilience routes terminal at `TriageClient.run_task`: record the route decision and a `worker_result` with `not_attempted`, return `handoff_required`, and ensure `tc run` exits 3 without invoking any backend. This slice does not add an approval-and-resume workflow or make every `human_review_required` flag pre-execution blocking.

- CR-124: Eval Handoff Hygiene, Bug, and Drift Slice
  - Status: complete via CR-124
  - Purpose: Fix the generator/single-pass iterable bug in actual outcome export writing and clean up stale eval sequencing docs so they point from CR-123 toward bundle/manifest work while preserving the rule that scoring remains external to TriageCore.

- CR-123: Evaluation Handoff Contract
  - Status: complete via CR-123 (contract-only)
  - Purpose: Define the file-contract boundary between TriageCore and the external evaluator suite, including required fixture and actual-outcome inputs, contract/version identifiers, deterministic future bundle path vocabulary, and TriageCore-side exit-code expectations, while keeping scoring, evaluator execution, model/backend calls, routing/admission integration, ledger writes, result import/display, and score interpretation out of scope.

- CR-122: Eval Fixture Validation CLI
  - Status: complete via CR-122 (validator CLI only)
  - Purpose: Expose the CR-121 safety-boundary eval fixture validator through `tc eval validate-fixtures --input <path>`, with bounded pass output and fail-closed line-aware diagnostics, while keeping scoring, observed-behavior comparison, model/backend calls, routing/admission integration, ledger writes, runtime behavior, and adversarial/tampering expansion out of scope.

- CR-121: Eval Fixture Validator
  - Status: complete via CR-121 (validator-only)
  - Purpose: Add a pure deterministic JSONL validator for the CR-077 safety-boundary eval fixture contract, with line-aware diagnostics and fail-closed checks for malformed JSON, missing required fields, empty/duplicate `case_id`, and closed-vocabulary violations, while keeping `tc eval`, scoring, model calls, routing/admission integration, ledger writes, and adversarial tampering tests out of scope.

- CR-120: Telemetry Lane Release Hygiene
  - Status: complete via CR-120 (docs-only)
  - Purpose: Freeze the completed CR-117 through CR-119 reviewer/telemetry lane after PR #91, #92, and #93 merged; add a concise operations note with the commit/validation anchors; correct stale CR-114 probe wording in the telemetry brief; and mark the reviewer checkpoint/release-hygiene candidate complete without adding probe execution, routing integration, schemas, ledger writes, CLI behavior, tags, or model/backend calls.

- CR-115: Final Control-Plane Extraction Package
  - Status: complete via CR-115 (docs-only); no tag — CR-114 carried the checkpoint tags, CR-115 is doctrine/handoff material committed normally
  - Purpose: Bank the exit-window doctrine as four operations docs — control-plane invariant checklist (invariant → enforcement locus → reviewer verification command), outer-loop control review recipe (repeatable external review process with risk classes and stop conditions), Fable final capability note (model role was drafting/review/evidence collection under plan-gated human control; no runtime dependency on any model), and future agent/maintainer handoff (cold-start entry point, ordered next slices, binding conventions). Signatures, manifests, evaluator verdicts, and model recommendations remain evidence, not approval. Telemetry lane renumbered to CR-118+ after CR-117 claimed the task-show signature-verification slice.

- CR-114: Reviewer Checkpoint 2026-07-07 and Tag Reconciliation
  - Status: complete via CR-114 (docs-only); recommended checkpoint tags remain operator-run future steps and do not exist until created and pushed deliberately
  - Purpose: Consolidate the CR-100 through CR-113 route-worker telemetry and runtime strategy lanes into a dated reviewer checkpoint at HEAD `f8bf33c` with fresh validation evidence (803 passed / 2 skipped, privacy invariants, signature verification, identity list, backend-free benchmark listing), and reconcile the never-created `v0.1.0-reviewer-checkpoint-2026-07-02` tag by preserving the `355c521` anchor in-document and recommending exact tag commands without running them. Note: CR-114 was claimed by this checkpoint slice at commit time, shifting the telemetry probe implementation candidate previously referenced as "CR-114+"; after CR-115 was claimed by the extraction package and CR-117 by the task-show signature-verification slice, the telemetry lane is now CR-118+.

- CR-113: Local Backend Telemetry Design Brief
  - Status: complete via CR-113 (docs-only); CR-118 pinned the serialized record contract, and CR-119 gates emitted probe results through that contract before treating them as observations
  - Purpose: Define the boundaries for a future read-only local backend telemetry slice — metadata-only availability and model/runtime identity observations for Ollama, LM Studio, and llama.cpp local endpoints — including candidate fields with privacy considerations, a closed failure vocabulary, evidence-tier provenance, an opt-in probe posture, and a reviewer path that requires no model execution, before any probe code is written.

- CR-112: Recorded Runtime Strategy Report Export
  - Status: complete via CR-112
  - Purpose: Write recorded runtime strategy delta reports as deterministic, metadata-only JSON artifacts through the same shared export path as fixture reports, with fail-closed reason-coded handling for existing files, missing directories, and write failures, and no default output location.

- CR-110: Recorded Runtime Strategy Evidence Report
  - Status: complete via CR-110
  - Purpose: Compare operator-supplied recorded strategy evidence records from an explicit JSON file against a selectable baseline through the existing validation and delta paths, rendered as a separate recorded report with fail-closed reason-coded input handling and no live model calls, routing changes, or ledger writes.

- CR-109: Runtime Strategy Report Export
  - Status: complete via CR-109
  - Purpose: Write the deterministic runtime strategy delta report as a metadata-only JSON artifact to an explicit operator-named path, fail-closed on existing files and missing directories, with byte-identical repeated exports and no default write location.

- CR-108: Quality-Gate-Aware Delta Interpretation
  - Status: complete via CR-108
  - Purpose: Qualify token-based delta interpretations with an independent quality-gate effect axis (failure dominates, closed vocabulary) without letting quality gates rewrite cost interpretations, rank strategies, or recommend a "best" strategy.

- CR-107: Runtime Strategy Delta Report Command
  - Status: complete via CR-107
  - Purpose: Expose the fixture-derived strategy deltas through a read-only, deterministic `tc runtime-strategy report` command with text and JSON output, without live model calls, telemetry adapters, or strategy selection.

- CR-106: Strategy Delta Calculation
  - Status: complete via CR-106
  - Purpose: Compare a candidate runtime strategy fixture against the heavy-only baseline and report token delta, percent delta, model-call delta, handoff delta, and a closed interpretation label, including the over-orchestrated negative control losing to the baseline.

- CR-105: Runtime Strategy Comparison Fixture
  - Status: complete via CR-105
  - Purpose: Compare heavy-only, small-first compact, small-only, and over-orchestrated strategy fixtures with derived token, model-call, handoff, backend-token, and quality-gate metrics before live runtime integration.

- CR-104: Runtime Strategy Evidence Record
  - Status: complete via CR-104
  - Purpose: Record one metadata-only orchestration strategy shape with typed model/runtime steps, estimated token totals, model-call counts, handoff counts, and quality-gate status before changing routing behavior.

- CR-103: Add Route/Worker Ledger Inspection Runbook Check
  - Status: complete via CR-103
  - Purpose: Harden the reviewer runbook and focused regression test so the CR-100 through CR-102 route-worker telemetry path remains one-command verifiable without new CLI or runtime behavior.

- CR-102: Add Route/Worker Ledger Fixture Demo
  - Status: complete via CR-102
  - Purpose: Provide a deterministic metadata-only demo ledger and operations note for reviewers to inspect the CR-100/CR-101 route-worker telemetry path without runtime integration.

- CR-101: Add Route/Worker Ledger Inspection CLI
  - Status: complete via CR-101
  - Purpose: Add an explicit-path, read-only CLI inspection command for CR-100 route/worker telemetry JSONL files, with fail-closed validation and reviewer summary counts.

- CR-100: Record Route-Decision and Worker-Result Ledger Events
  - Status: complete via CR-100
  - Purpose: Add a standalone telemetry-only route/worker ledger event contract with fail-closed metadata validation, without changing routing, execution, admission, approval, or identity behavior.

- CR-099: Reviewer Release Checkpoint and Changelog Cut
  - Status: complete via CR-099
  - Purpose: Bind repository state, changelog claims, and validation results into a clean dated checkpoint record.

- CR-098: Add Task Evidence Show Command
  - Status: complete via CR-098
  - Purpose: Read-only task evidence display. Shows the task's complete ledger-derived evidence timeline and status, fail closed on missing tasks, and prints note that signatures are not checked.

- CR-097: Fail-Closed Identity Registry Load Handling
  - Status: complete via CR-097
  - Purpose: Catch unhandled identity registry IO/parse exceptions in reviewer-facing CLI paths and return a bounded `registry_load_failed` output without leaking stack traces or secret strings.

- CR-096: Fix TriageDesk review evidence payload integrity
  - Status: complete via CR-096
  - Purpose: fix payload keys so "needs revision" survives end-to-end and remove fabricated effort metadata from the GUI review submission, ensuring the ledger only claims what is actually known.


- Issue #72: Expand signed ledger event coverage beyond `route_audit`
  - Status: `validation_result` creation, verification, and reviewer-facing example complete via CR-078, CR-079, and CR-081; signed `route_decision` creation and operator-facing verification complete via CR-082; signed `route_decision` smoke example and reviewer-facing verification doc complete via CR-083; capability-targeted identity doctor checks for route-decision signers complete via CR-084; consolidated reviewer checkpoint doc complete via CR-085; stabilization reviewer checkpoint and packaging/readiness docs complete via CR-086; broader event coverage remains future work
  - Purpose: selectively enforce identity checks and signatures for core ledger events beyond `route_audit` without treating signatures as approval. Additional signed-event paths now cover `validation_result` creation, operator-facing verification, reviewer-facing examples, explicit signed `route_decision` creation plus verification, and an end-to-end signed `route_decision` smoke example; future work is deciding whether to sign additional event types such as `taskpacket_created` or `project_steward_decision`.

- Issue #73: Implement runtime key rotation behavior
  - Status: open
  - Purpose: implement safe key rotation logic separate from the identity MVP, ensuring superseded keys are rejected while old signatures remain verifiable.

- Stabilization and packaging readiness
  - Status: reviewer checkpoint and packaging/readiness docs complete via CR-086; reviewer smoke runbook complete via CR-087; submission video runbook complete via CR-088; reviewer entrypoints index complete via CR-089; release mechanics remain future work
  - Purpose: make the current system easier to trust, run, review, and package without adding new cryptographic surface area, execution pathways, or agent authority.

- Runtime efficiency evidence
  - Status: runtime efficiency ledger schema, backend profiles, deterministic record builder, and focused tests complete via CR-090; controlled experiment plans, agent group profiles, synthetic result records, schemas, and focused tests complete via CR-091; experiment observability trace contract, schema, and focused tests complete via CR-092; token-efficiency evidence records complete via CR-094; runtime strategy evidence records complete via CR-104; runtime strategy comparison fixtures complete via CR-105; live benchmark capture and durable evidence storage remain future work
  - Purpose: record comparable token, latency, backend-profile, quality-gate, agent-group, baseline-lineage, claim-validity, and energy-evidence-tier data for local runtime choices such as Ollama and llama.cpp before any runtime migration.

## Candidate Future Work

- Agent authority and delegation boundary
  - Source: CR-095 task-scoped agent authority manifest
  - Status: authority manifest contract, reviewer-style example, invalid example, and metadata-only CLI validation complete; identity-registry binding, manifest signing, admission enforcement, and route enforcement remain future slices
  - Purpose: keep cryptographic provenance separate from task-scoped action authority by making owner, purpose, allowed actions, denied actions, resource scope, approval gates, expiration, and revocation state inspectable before any future workflow treats an agent action as inside bounds.

- Empirical AI safety evaluation track
  - Source: CR-076 and CR-077 research framing/eval taxonomy docs
  - Status: research question, threat model, eval taxonomy, fixture schema, toy boundary fixtures, **TC-EVAL-001 (Export Actual Outcome Contract Files)**, **TC-EVAL-002 (Actual Outcome Export CLI Smoke)**, **[x] TC-EVAL-003 (Map One Real Internal Decision Path Into the Export Contract)**, **[x] TC-EVAL-004 (Export One Real Privacy Scanner Actual)**, **[x] TC-EVAL-005 / 006 / 007 (Privacy Reason Normalization)** documented; fixture validator complete via CR-121; fixture validation CLI complete via CR-122; external-evaluator handoff contract complete via CR-123; bundle/manifest building, bundle integrity validation, evaluator invocation, adversarial tests, toy audit tampering eval, behavioral route diffing, **[x] TC-EVAL-008 (Structured Privacy Scanner Finding Codes)**, **[x] TC-EVAL-009 (Shared Internal Reason-Code Constants for Privacy Findings)**, **[x] TC-EVAL-010 (Export One Forbidden Tool-Call Actual)** and technical report remain future slices
  - Purpose: make TriageCore legible as a reproducible local-first AI control and evaluation harness for testing privacy, routing, identity, provenance, audit, and human-approval boundaries under controlled adversarial pressure.

- Operator UX implementation path
  - Source: CR-051, CR-052, CR-053, CR-054, CR-055, CR-056, CR-057, CR-058, CR-059, CR-060, CR-061, CR-062, CR-063, CR-064, CR-065, CR-066, CR-067, CR-068, CR-069, CR-070, CR-071, CR-072, CR-073, CR-074, CR-075, CR-DD-001, CR-DD-002, CR-DD-003, CR-DD-004, CR-DD-005, CR-DD-006, CR-DD-007, and CR-DD-008
  - Status: design, template, markdown renderer, CLI preview/draft/wizard commands, CLI documentation, admission CLI smoke coverage, no-mutation invariant coverage, contract documentation, contract linkage, fixture drift coverage, review bundle dry-run support, manifest contract coverage, status command, doctor polish, diagnostic helper extraction, token budget model, context plan dry-run, packet renderer, review queue list, and quickstart documentation complete; TUI and dashboard work transitioned to TriageDesk track.
  - Purpose: keep operator UX calm, legible, and evidence-first without jumping straight to a web dashboard or hidden automation surface.

- TriageDesk GUI implementation path
  - Source: TD-001, TD-002, TD-003, TD-004, TD-005, TD-006, TD-007
  - Status: **[x] TD-001 (TriageDesk GUI inventory and read-only shell plan)**, **[x] TD-002 (TriageDesk read-only adapter layer)**, **[x] TD-003 (TriageDesk status panel wiring)**, **[x] TD-004 (TriageDesk review queue panel)**, **[x] TD-005 (Read-only Context Planner panel)**, **[x] TD-006 (Packet Preview UI integration)**, **[x] TD-007 (TriageDesk GUI consolidation pass)** complete.
  - Purpose: Provide a calm, read-only operator console wrapping the daily-driver baseline capabilities without expanding execution authority.

- External runtime execution admission evidence
  - Source: CR-050 admission evidence record
  - Status: evidence structure complete; ledger integration remains future work
  - Purpose: audit the admission of proposals separately from their execution.

- Textual read-only operator dashboard
  - Source: CR-051 follow-on sequence
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: provide a calm terminal control panel for status, approvals, scope, and evidence after CLI/report fields stabilize.

- External runtime execution boundary stub
  - Source: CR-049 execution-path boundary stub
  - Status: stub caller complete; routing policy and admission tokens remain future work
  - Purpose: enforce structural and policy boundaries by ensuring proposals must pass `admit_external_runtime` before proceeding.

- External runtime manifest examples
  - Source: CR-045 docs-only example slice
  - Status: documentation-only slice complete; adapter and execution work remain
    gated
  - Purpose: show what safe read-only, draft-only, and intentionally invalid
    external runtime manifests look like under the CR-044 contract.

- External runtime manifest schema
  - Source: CR-044 docs-only contract slice
  - Status: documentation-only slice complete; example and adapter work remain
    gated
  - Purpose: define the vendor-neutral manifest contract external runtimes must
    provide before TriageCore can classify authority, approval, provenance, and
    revocation expectations.

- External runtime integration doctrine
  - Source: CR-043 docs-only baseline
  - Status: documentation-only slice complete; runtime integration work remains gated
  - Purpose: define vendor-neutral integration rules for external runtimes without granting new authority or adding dependencies.

- Runtime integrity and model provenance enforcement
  - Source: CR-031 policy baseline
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: add operator-facing model or route integrity checks so convenience
    wrappers, aliases, and mutable tags do not become implicit trust
    boundaries.

- Circuit breakers and degraded mode states
  - Source: older Drive performance backlog
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: allow unstable routes to cool down instead of retrying immediately.

## Completed Safety Spine

- CR-021: Persistent Artifact Privacy Invariant
- CR-022: Context Facet Pruning Plan
- CR-023: Offline Demo Dry-Run Evidence
- CR-024: Persistent Artifact Audit Command
- CR-026: Post-Identity Privacy and Security Audit
- CR-027: Identity Key Hardening and Consistency Check
- CR-028: Signed Smoke-Path Evidence
- CR-029: Identity Revocation CLI
- CR-030: Identity Rotation and Recovery Policy
- CR-031: Runtime Integrity and Model Provenance Policy
- CR-032: Model Route Manifest Schema
- CR-033: Model Manifest Check CLI
- CR-034: Repository Consistency and Secrets Hygiene
- CR-095: Task-Scoped Agent Authority Manifest

## Current Recommendation

Keep three work lanes distinct:

- Identity lifecycle work #4 is closed. CR-078, CR-079, CR-081, CR-082, CR-083, CR-084, and CR-085 complete the signed `validation_result` and `route_decision` paths under Issue #72 through creation, verification, smoke evidence, capability readiness checks, and reviewer-facing or operator-facing examples; CR-086 adds a stabilization/readiness checkpoint around that completed lane, CR-087 adds a clean reviewer smoke runbook, CR-088 adds video-first submission packaging, and CR-089 adds a reviewer entrypoints index. Remaining signed-event expansion and Issue #73 runtime rotation behavior should stay separate implementation slices.
- Agent authority work should build on CR-095. Keep authority-manifest validation static and metadata-only until a separate CR binds it to the identity registry, signed route decisions, admission checks, or runtime enforcement. Do not treat a passing authority manifest as approval or execution permission.
- Model and runtime integrity work should build on CR-031 through CR-033. Keep
  policy baseline, route-manifest artifact shape, manifest validation, and live
  enforcement as separate reviewable slices.
- Repository consistency and secrets hygiene from CR-034 is complete. Future
  hygiene work should be limited to stale documented claims or a separately
  proposed repo-consistency checker.

For signed ledger coverage, the reviewer-facing `validation_result` path and the signed `route_decision` path are now in place, including a smoke example, a capability-targeted doctor check, and a consolidated reviewer checkpoint for the latter. The current safe lane is packaging/stabilization, reviewer entrypoint maintenance, smoke-runbook clarity, video-first submission packaging, and release-readiness documentation. Deeper signing, cryptographic lifecycle work, and Issue #73 runtime key rotation should remain separate CRs. Do not treat a valid signature as approval, safety, or correctness.

For the empirical AI safety evaluation track, CR-121 completes fixture validation, CR-122 exposes it through a narrow CLI, and CR-123 defines the external-evaluator handoff contract. Keep the next slices sequential: bundle/manifest builder, bundle integrity validator, then a narrow external evaluator adapter. Scoring and score interpretation must remain external to TriageCore, and broader adversarial/tampering studies should wait until the handoff path is stable.

For external runtime interoperability, the next approved slice should be policy tests or execution-path validation for the bounded adapter path.

For operator UX, future slices should focus on reviewability, export polish, and dashboard/TUI surfaces only after artifact contracts remain stable. Avoid re-opening completed wizard or Markdown renderer work unless there is a concrete regression or usability gap.

## Next Candidate Slices

- **[done] Signature verification on task show (CR-117, runtime-safe)**: Opt-in `tc task show --verify-signatures` verifies the shown task's signed ledger events via a task-scoped helper that reuses the CR-097 fail-closed categories; fail-closed (exits 1) on invalid or malformed signatures and registry-load failure, while unsigned signed-type events stay informational (exit 0). Whole-ledger `tc audit --verify-signatures` behavior is unchanged ([task-show-signature-verification.md](operations/task-show-signature-verification.md)).
- **[done] Telemetry schema and synthetic-fixture validation (CR-118)**: Hardened the existing local backend probe's serialized record contract before any further probe work — strict schema, pure validator, synthetic fixtures only, no endpoint calls, no routing integration, no ledger writes, and no CLI behavior changes.
- **[done] Local backend telemetry probe validation gate (CR-119)**: Every emitted local backend probe result now validates against the CR-118 record contract before it is treated as an observation; validation failure raises a fail-closed `ProbeInputError`, with no generation calls, routing integration, or ledger writes.
- **[done] Reviewer checkpoint or release-hygiene slice (CR-120, docs-only)**: Froze the completed CR-117 through CR-119 lane in a concise operations note, corrected stale CR-114 telemetry wording, and kept future telemetry work behind a new explicit scope pass instead of adding more features.
- **[done] Evaluation handoff contract (CR-123, contract-only)**: Defined the file-based boundary between TriageCore-produced fixtures/actuals and external scoring, including deterministic future bundle path vocabulary.
- **[done] Eval handoff hygiene (CR-124)**: Fixed generator-backed actual-outcome writing and removed stale language that implied internal TriageCore scoring.
- **[done] Honor terminal resilience routes (CR-125)**: `human_handoff` and currently unimplemented `deterministic` routes now return a governed handoff before backend execution, recording `worker_result_status=not_attempted`; `tc run` reports the valid handoff with exit code 3. Approval-and-resume behavior, broader `human_review_required` semantics, and other execution seams remain future work.
- **[done] Preflight privacy before ledger persistence (CR-126)**: `tc run` now scans its complete packet before opening the ledger, persists only metadata and input lengths, and extends the persistent artifact audit with high-confidence sensitive-value detection. Historical records remain unchanged; arbitrary free-text safety classification and a full DLP engine remain out of scope.
- **Next slice requires a new approved CR**: The eval lane's next bounded candidate is a deterministic bundle/manifest builder for already-validated fixtures and already-exported actuals. Do not add scoring or score interpretation inside TriageCore, and do not start approval-and-resume behavior, routing integration beyond the governed path, ledger integration, circuit breakers, automatic discovery, background polling, or additional telemetry behavior without a new approved CR.
