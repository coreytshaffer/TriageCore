# Current Backlog

## Status

This document summarizes the active TriageCore backlog after CR-109.

## Active GitHub Backlog

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
  - Status: research question, threat model, eval taxonomy, fixture schema, toy boundary fixtures, **TC-EVAL-001 (Export Actual Outcome Contract Files)**, **TC-EVAL-002 (Actual Outcome Export CLI Smoke)**, **[x] TC-EVAL-003 (Map One Real Internal Decision Path Into the Export Contract)**, **[x] TC-EVAL-004 (Export One Real Privacy Scanner Actual)**, **[x] TC-EVAL-005 / 006 / 007 (Privacy Reason Normalization)** documented; fixture validator tests, evaluator CLI, adversarial tests, toy audit tampering eval, behavioral route diffing, **[x] TC-EVAL-008 (Structured Privacy Scanner Finding Codes)**, **[x] TC-EVAL-009 (Shared Internal Reason-Code Constants for Privacy Findings)**, **[x] TC-EVAL-010 (Export One Forbidden Tool-Call Actual)** and technical report remain future slices
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

For the empirical AI safety evaluation track, keep the next slices sequential: fixture validation first, evaluator CLI second, and broader adversarial/tampering studies only after the fixture contract is stable.

For external runtime interoperability, the next approved slice should be policy tests or execution-path validation for the bounded adapter path.

For operator UX, future slices should focus on reviewability, export polish, and dashboard/TUI surfaces only after artifact contracts remain stable. Avoid re-opening completed wizard or Markdown renderer work unless there is a concrete regression or usability gap.

## Next Candidate Slices

- **Reviewer checkpoint or release-hygiene slice**: Freeze the completed route-worker reviewer lane into a concise checkpoint, packaging note, or release-hygiene update instead of adding more telemetry features.
- **Signature verification options on task show**: Decouple signature checking from CLI-abort mechanics so `tc task show --verify-signatures` verifies signatures safely.
