# Current Backlog

## Status

CR-DD-012A is complete and merged through PR #107 as `bccaaad`. CR-YK-001 is
complete and merged through PR #110 as `52dccd3`; its physically tested,
request-bound WebAuthn authorization evidence and offline verification are now
the baseline, and no CR-YK-001 lineage, validation, or cleanup work remains.

CR-YK-002 is complete and merged through PR #117 as `5155bbb`. Claim ownership
and lifecycle state now live in a local SQLite registry at schema version
`triagecore.capability_claims.v2`; the ledger remains durable evidence and is
no longer the concurrency lock. CLI surfaces, `tc run` integration,
`--confirmed-plan`, backend calls, routing/worker changes, and FIDO2 changes
remain unauthorized. CR-DD-012B's atomic-claiming prerequisite is
satisfied, and CR-DD-012B has since been implemented on an unmerged branch under
its own direct implementation instruction; the merge of this foundation was not
that instruction, and CR-DD-012B's implementation acceptance remains ungranted.

CR-OC-001C is complete and merged through PR #128 as `f65a864`; the
Windows/NTFS constrained replacement executor exists as a non-integrated
library surface, with hosted Windows evidence and 31/31 mutant kills.
CR-OC-001D, CR-OC-001E, and runtime integration remain separately
unauthorized.
Detailed lineage — the three contract amendments, the five implementation
discoveries, the seven harness corrections, and the hosted evidence — lives in
the CR document and the change log rather than here.

CR-DD-013 is complete and merged through PR #116 as `98df9c1`. `tc run` now
binds validated recorded local-runtime evidence and explicit route-class
declarations into route input while preserving observed/configured/unknown
provenance. Automatic probing, class-to-model binding, circuit breakers, and
runtime revalidation remain outside the slice. Implementation and merge
authority are spent; CR-DD-012B is unaffected and receives no authority from
this closeout. Detailed design history lives in the CR document. CR-DD-012B's
implemented branch does change what consumes CR-DD-013's output — capability now
constrains execution binding only and no longer reaches route policy — but that
correction is made under CR-DD-012B's own authority, touches no CR-DD-013 module,
and reaches `main` only if that slice is accepted and merged.

## Backlog Scope Taxonomy

This taxonomy classifies backlog work by relationship to TriageCore's identity.
It does not assign priority, status, approval, implementation or execution
permission, or standing authority.

- **Governance kernel**: decision integrity; identity and authority; capability
  and effect bounds; evidence and reconstruction; review and human control;
  evaluator independence; privacy and provenance.
- **Supporting subsystems**: resource-aware routing; tokens and context; energy;
  telemetry; workspace and presentation surfaces; provider adapters.
- **Adjacent applications**: software agents; environmental and edge workflows;
  external agent frameworks and automation tools.

Mixed items must be decomposed into separately reviewable slices. Each slice
must be classified by the governance invariant it strengthens; if no invariant
can be named, it remains a supporting subsystem or adjacent application rather
than inheriting governance-kernel status.

Category is recorded separately from maturity and integration status. Current,
optional/separate-lane, implemented-but-disconnected, future, and conceptual
components may occur in any category. Dependencies do not promote supporting or
adjacent work into the governance kernel.

Scope test: `Does this strengthen the evidence-bound governance kernel, or is it merely an interesting adjacent capability?`

## Active GitHub Backlog

- CR-OC-001B: Atomic Client-Request Reservation
  - Status: complete and merged; requirements through PR #122 as `f22fee1`, implementation through PR #123 as `47fb3d5`; runtime integration, CLI, IPC, OpenClaw work, and CR-OC-001C-E remain unauthorized, and direct callers of `triage_core.authz.claim_capability` are unchanged
  - Purpose: Provide the one durable binding CR-OC-001A cannot — `client_request_id` -> `request_digest` -> `broker_connection_id` -> `capability_id` — so two callers cannot obtain authority for the same logical operation. `classify_request_replay` compares bindings it is handed and cannot discover that a prior one exists; this slice makes the discovery atomic and durable. Reservation precedes capability issuance so a crash leaves an inert reservation rather than unattributable authority; the reserve/issue/bind window spans SQLite and the JSONL ledger with no shared transaction, so a durable verifier for an ephemeral ownership token, given once to the insert winner, decides who may advance the row — returned raw once and persisted only as its SHA-256 digest, so reading the database grants no authority — and a retry may inspect the row but never receives the token, leaving a lost owner's reservation inert by construction rather than by a policy guess, with no caller having to assert that a crash occurred when it cannot know. A one-shot `reserved -> issuing` transition consumes the right to issue before the capability call, since two holders of the same valid token could otherwise both issue and only then race to bind, leaving a second capability in the ledger that the unchanged direct claim path would still honour. The lifecycle stops at `reserved -> issuing -> authorized`, with `reserved -> denied` as the only other transition and denial illegal once issuance has begun: mirroring the claim states would create a second lifecycle authority across two stores with no shared transaction, so claim and execution lifecycle stay exclusively in CR-YK-002. One-to-one binding is enforced by schema uniqueness in both directions, not by the caller. Capability expiry must not release a reservation, or expiry becomes a reuse channel. Store failure is distinguished from a successful lookup finding nothing, carrying the CR-YK-002 terminal-reason lesson forward before the defect can be written. Binding verifies that effect, request, and linkage describe one transition, because CR-OC-001A demonstrated that individually valid digests are not evidence that components belong together. Gating is scoped to the CR-OC mediated entry point only: `issue_capability` mints its own ID and `claim_capability` delegates straight to the claim store with no reservation lookup, so a wrapper can refuse to delegate but cannot constrain direct callers, and the acceptance claim says so rather than implying global enforcement. Sequenced before the executor deliberately: an executor that can be driven twice for one request is worse than no executor. No files, IPC, named pipes, OpenClaw work, CLI, or runtime consumption; `authz.py`, `capability_claims.py`, and `task_ledger.py` stay unmodified.

- CR-OC-001A: Mediated Single-File Effect Contract
  - Status: complete and merged; contract through PR #119 as `bfa1d6e`, pure-module implementation through PR #120 as `1e1f441`; runtime integration, persistence, IPC, capability issuance, and CR-OC-001C-E remain unauthorized. Cross-object binding is enforced so a linkage or capability bundle cannot mix an effect with an unrelated request, and the closed vocabulary widens from 11 to 16 codes so each names the condition that actually failed
  - Purpose: Define how one exact single-file content transition is represented, validated, and bound, as the first slice of the mediated OpenClaw experiment. A pure module would describe a replacement by syntactically validated `target_file_id` rather than caller-supplied path, pin it to exact pre- and post-content digests over exact bytes, keep client-declared invocation context structurally separate from a distinct broker-connection identifier field, define five versioned closed-field canonical objects, provide a pure replay-classification function keyed to the client request on a specific connection, and expose a metadata-only persistent projection that never carries proposed bytes. It maps onto the merged CR-YK-002 capability without changing `AuthorizationRequest` or the capability schema. The claim it may support is bounded: an exact authorized pre-content digest became an exact authorized post-content digest — not exact filesystem state, not an authenticated context, not broker provenance for the connection identifier, not allowlist membership for the file identifier, not replay prevention, not path safety, and not that any file changed. No file access, IPC, persistence, capability issuance, named pipes, OpenClaw configuration, or mutation. CR-OC-001B is now complete and merged through PR #123 as `47fb3d5`; CR-OC-001C through CR-OC-001E each require separate approval.

- CR-YK-002: Atomic Execution-Capability Claiming
  - Status: complete and merged through PR #117 as `5155bbb`; CLI, runtime integration, and execution remain unauthorized
  - Purpose: Provide a local SQLite registry for atomic, irrevocable capability claiming while retaining the task ledger as durable evidence. The conservative invariant holds: a crash or a post-commit evidence-write failure burns the authorization rather than risking duplicate execution. The former strict concurrency `xfail` is replaced by passing multi-threaded atomicity tests over independent SQLite connections. The schema is at `triagecore.capability_claims.v2`, which enforces row shape per state, permits only legal transitions, and freezes claim ownership and terminal metadata at the proper lifecycle points; v1 databases fail closed rather than being migrated. Terminal store failures report `capability_store_busy` or `capability_store_unavailable` rather than falsely reporting an absent capability. `triage_core/authz.py` is the sole authorized module permitted to import the claim store; no CLI, run path, router, worker, or backend consumes it. Implementation grants no execution or CR-DD-012B authority.

- CR-YK-001: FIDO2 Security-Key-Backed Human Authorization Receipts
  - Status: complete and merged through PR #110 as `52dccd3`; feature refs cleaned up; recovery branches retained
  - Purpose: Provide physically tested, request-bound WebAuthn authorization evidence with offline verification and explicit assurance limits. Atomic capability claiming is delivered by the CR-YK-002 foundation, merged through PR #117 as `5155bbb`.

- CR-DD-012A: Governed Decision Foundation
  - Status: complete and merged through PR #107 as `bccaaad`; no public integration
  - Purpose: Provide the immutable snapshot and canonical decision foundation without public integration. The contract distinguishes optional provenance `SourceBytes`, existing-behavior `NormalizedComponentBytes`, and authoritative worker-facing `AssembledExecutionBytes`. The latter is the UTF-8 strict encoding of the current worker user-message content, not raw filesystem or backend transport bytes. Implementation is limited to two internal foundation modules, bounded deterministic construction, pure decision building, canonical identity verification, and three focused test files; `tc run`, preview, existing file reading/assembly, workers, ledgers, artifacts, runtime observations, cloud authority, and route execution remain unchanged.

- CR-DD-012B: Shared Preview/Execution Consumption
  - Status: implemented on `claude/cr-dd-012b-shared-preview-execution-consumption`; implementation authority spent; implementation acceptance, merge, and closeout NOT granted. The CR-YK-002 sequencing prerequisite was satisfied through PR #117 as `5155bbb`, and the operator's direct implementation instruction — which named no replacement allowlist, so the CR's own provisional list bound the work — opened the implementation phase. Two regression-test paths beyond that provisional list were taken and are named in the CR's Implementation Record; every deliberately excluded module is untouched. All five approval gates pass and the full suite is green at 1787 passed / 6 skipped. `main` behavior is unchanged until the slice is accepted and merged
  - Purpose: Make `tc run --plan` and ordinary `tc run` consume one immutable `GovernedRunInputSnapshot` and one completed `GovernedDecision` built at a single seam before the preview branch, so context sources are read exactly once and neither path reclassifies, recalculates privacy or context budget, selects specialist policy, or logically reroutes. Volatile facts stay in a validated internal `RuntimeObservation` that subsumes CR-DD-013's capability resolution without re-deriving it; actual backend binding is a filter over the decision's closed ordered fallback envelope, never an injection surface; and bounded `decision_id` linkage rides the existing open route/worker payload extension point with no new ledger schema. Direct `run_task` callers that omit the decision keep current behavior. All three previously open questions are settled by recorded decision: capability evidence constrains execution binding only and never governed-decision formation, so a volatile observation may execute, bind an already-authorized fallback, or fail closed but never invent a route — a deliberate correction to current `tc run` route selection, recorded as such rather than absorbed as an implementation detail; the deterministic classifier is authoritative while any model-assisted classifier stays advisory; and `build_run_plan`'s signature is preserved only if it remains one coherent projection, since a narrow break beats an attractive second integration path. Five approval gates are recorded across two stages: two proposal-stage preconditions — the capability decision and the pre-`planning` seam statement — are satisfied, while three test obligations must be bound by any bounded implementation approval and pass before implementation acceptance, merge, or closeout; those three are replacing rather than deleting the CR-DD-012A integration-absence guard and negative tests for capability volatility and unavailability. Saved-plan execution, `--confirmed-plan`, plan v2, durable observation schemas, new cloud authority, acceptance, resume, and quality scoring stay excluded.

- CR-DD-012: Shared Governed Run Decision
  - Status: architecture approved; monolithic implementation withheld; CR-DD-012A complete and merged through PR #107 as `bccaaad`; CR-DD-012B implemented on an unmerged branch with acceptance ungranted
  - Purpose: Define the shared-decision architecture around one immutable `GovernedRunInputSnapshot` and one canonical `GovernedDecision` with a domain-separated decision ID. CR-DD-012A is the merged no-CLI/no-ledger foundation and centers the binding on normalized worker-facing execution bytes rather than raw filesystem bytes. CR-DD-012B is implemented on an unmerged branch and gated on implementation acceptance. `governed_run_plan.v2`, durable `RuntimeObservation`/`ExecutionRecord` schemas, saved-plan execution, `--confirmed-plan`, route injection, new cloud authority, resume, acceptance, and quality scoring remain deferred.

- CR-DD-011: Governed Plan Artifact And Exact Confirmation Linkage
  - Status: complete via CR-DD-011 (PR #104)
  - Purpose: Provide the smallest safe foundation after CR-DD-010: an operator-named privacy-safe canonical plan artifact, independent semantic and exact-byte SHA-256 digests, explicit exact-digest review confirmation, metadata-only task-ID linkage, and task-show inspection including isolated/custom ledgers. Confirmed execution remains explicitly blocked because preview and execution do not yet share one enforceable decision path; confirmation is not approval or execution authority.

- CR-DD-010: Governed Run Plan Preview
  - Status: complete via CR-DD-010 (PR #104)
  - Purpose: Add a deterministic, stdout-only `tc run --plan` preview that combines current packet preflight, privacy, deterministic classification, logical routing, configured backend binding, and context-budget logic to show context sources, token posture, privacy/egress posture, escalation conditions, and expected verification without model calls, backend probes, ledger mutation, file writes, confirmation, execution, resume, reporting, or TriageDesk changes.

- CR-129: External Evaluator Adapter Contract
  - Status: complete via CR-129 (PR #102)
  - Purpose: Define the closed-profile, pre-launch validation, process safety, exit, output, network, and trust boundaries required before a future external evaluator wrapper can be implemented. CR-129 adds no CLI or subprocess.

- CR-128: Evaluation Handoff Integrity Validator
  - Status: complete via CR-128 (PR #101)
  - Purpose: Read-only validation of an existing CR-127 bundle's closed manifest, exact inventory, safe paths, byte hashes, fixture/actual contracts, membership, and privacy invariants. Hash agreement detects drift relative to the manifest; it is not authenticity, provenance, approval, safety, or correctness.

- CR-127: Evaluation Handoff Bundle Builder
  - Status: complete via CR-127
  - Purpose: Package an explicit validated fixture and explicit actual-outcome directory into a deterministic, privacy-checked, unscored handoff bundle with byte-preserving copies and a SHA-256 manifest. External scoring remains authoritative; existing-bundle integrity validation is the next separately scoped slice.

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

- TriageCore identity consolidation and agentic boundary governance
  - Status: Track 1 documentation is complete through PRs #137-#143 plus this
    backlog taxonomy slice. Track 2 remains candidate research-only. This entry
    grants no implementation, runtime integration, branch, merge, or standing
    authority for any code-bearing or integration slice.
  - Identity thesis: TriageCore is a local-first, evidence-bound research
    workbench for governing AI-assisted decisions and consequential actions
    through explicit authority, reviewable artifacts, bounded execution
    mechanisms, and independently governed evaluation boundaries.
    Resource-aware routing remains one governed subsystem rather than the whole
    identity.
  - Category distinctions: **workbench** names the maturity and research posture;
    **control plane** names an architectural function; **harness** names the
    experimental and evaluation role; **runtime** applies only to
    execution-bearing paths. Do not describe TriageCore as a platform, general
    agent runtime, complete containment system, or safety-certification
    authority.
  - Continuity: preserve local control and operator sovereignty, evidence before
    claims, explicit authority, fail-closed uncertainty, reviewable artifacts,
    and the separation of observation, recommendation, authorization,
    execution, and evaluation.
  - Scope taxonomy: use the stable **Backlog Scope Taxonomy** above. Mixed work
    must be decomposed and classified by the governance invariant strengthened.
  - Sequenced track 1 — **Identity consolidation**: complete through the
    canonical identity (PR #137), package description (PR #138), README (PR
    #139), `AGENTS.md` supervisor-verdict terminology (PR #140), public claim
    boundaries (PR #141), architecture identity/index linkage (PR #142),
    submission and portfolio entry point (PR #143), and this backlog taxonomy.
    These were separately reviewed documentation slices and grant no runtime or
    implementation authority.
  - `AGENTS.md` history: PR #140's supervisor-verdict terminology checkpoint
    (`ARTIFACT_REVIEW_PASSED` as an evidence-only quality verdict) applied to the
    `AGENTS.md` content of that era. CR-131 subsequently replaced `AGENTS.md` in
    full with a TriageCore-specific repository-governance document, merged through
    PR #168 (`main` `AGENTS.md` SHA-256
    `58d83280245b053718b04cab0fe84c8d9640c09780018761bcf880add088a77e`); the
    current `AGENTS.md` no longer contains PR #140's supervisor-verdict
    terminology or `ARTIFACT_REVIEW_PASSED`. This entry records that the
    replacement is complete; it does not claim any related documentation
    cross-references elsewhere in the repository were updated to match.
  - Sequenced track 2 — **Agentic boundary governance**: candidate research-only
    work covering evaluation-environment assurance, evaluator-harness threat
    modeling, incident-derived adversarial fixtures, delegation-chain
    capability attenuation building on CR-095, reality-and-scope uncertainty
    handling, trajectory-level policy evaluation, and incident reconstruction
    and recovery.
  - Sequence boundary: Track 2 grants research classification only. Every
    code-bearing or integration slice must remain separate and requires its own
    approved CR plus authoritative evidence or a versioned profile, as
    applicable.
  - Uncertainty and limitations: preserve the distinctions among current,
    implemented-but-disconnected, and future components. Do not claim that
    TriageCore solves alignment, certifies safety, or currently composes
    authorization through execution end to end.
  - Scope test: `Does this strengthen the evidence-bound governance kernel, or is
    it merely an interesting adjacent capability?`

- Adversarial multimodal canary authority-boundary research
  - Source: Track 2 agentic boundary governance research candidate
  - Status: candidate research-only; inert synthetic fixture and study design
    only. No slice is approved or active, and this entry grants no
    implementation, ingestion, runtime-enforcement, integration, branch, merge,
    or standing authority.
  - Scope: governance-kernel research into identity and authority, capability and
    effect bounds, and review and human control.
  - Purpose: define bounded studies using inert canary instructions deliberately
    hidden in synthetic, repository-owned JPEG, PDF, and other common-container
    fixtures to test whether a future ingestion boundary treats embedded
    instructions strictly as untrusted data and preserves existing capability,
    route, target-file, approval, and effect-authority bounds.
  - Exclusions and limitations: no OCR or parser implementation; macros or other
    active content; malformed-file or parser exploits; offensive payloads;
    third-party systems, data, or targets; runtime enforcement; authority
    expansion; or safety or certification claims. A passing study would support
    only the named fixture, container, and ingestion assumptions.

- Docker microVM execution-venue evaluation
  - Source: operator request during the 2026-08-01 daily-use evidence window
  - Status: candidate research-only; architecture and trust-boundary
    specification only. No slice is approved or active, and this entry grants no
    implementation, runtime-integration, container-provisioning, network-policy,
    credential, branch, merge, or standing authority.
  - Scope: supporting containment subsystem (execution-venue isolation). Venue
    isolation is orthogonal to governance-kernel authority decisions and does
    not substitute for them.
  - Purpose: define a bounded evaluation of hypervisor-isolated microVM
    sandboxes (for example Docker Sandboxes) as a worker execution venue:
    trust-boundary definition; clone-mode workspaces; default-deny egress with
    explicitly enumerated host-endpoint apertures; a TriageCore-owned broker
    that mediates model access as an allowlisted, budgeted, ledger-evidenced
    capability rather than a raw network aperture; artifact-only supervision
    that keeps evaluator models outside the contained worker's reach; in-venue
    council serving against digest-pinned model weights; venue evidence capture
    (sandbox identity, workspace mode, network policy, reachability
    observations, lifecycle disposition); and comparative host-versus-microVM
    trials.
  - Exclusions and limitations: no execution-venue adapter implementation; no
    changes to routing, authority, privacy, or ledger code; no serving-stack
    migration; no cloud execution; no third-party targets. Contained-execution
    success remains a worker result requiring validation and human disposition.
    MicroVM isolation bounds host exposure only; it establishes no workload
    safety, authority-enforcement, model-behavior, or certification claim.

- Agent authority and delegation boundary
  - Source: CR-095 task-scoped agent authority manifest
  - Status: authority manifest contract, reviewer-style example, invalid example, and metadata-only CLI validation complete; identity-registry binding, manifest signing, admission enforcement, and route enforcement remain future slices
  - Purpose: keep cryptographic provenance separate from task-scoped action authority by making owner, purpose, allowed actions, denied actions, resource scope, approval gates, expiration, and revocation state inspectable before any future workflow treats an agent action as inside bounds.

- Empirical AI safety evaluation track
  - Source: CR-076 and CR-077 research framing/eval taxonomy docs
  - Status: research question, threat model, eval taxonomy, fixture schema, toy boundary fixtures, **TC-EVAL-001 (Export Actual Outcome Contract Files)**, **TC-EVAL-002 (Actual Outcome Export CLI Smoke)**, **[x] TC-EVAL-003 (Map One Real Internal Decision Path Into the Export Contract)**, **[x] TC-EVAL-004 (Export One Real Privacy Scanner Actual)**, **[x] TC-EVAL-005 / 006 / 007 (Privacy Reason Normalization)** documented; fixture validator complete via CR-121; fixture validation CLI complete via CR-122; external-evaluator handoff contract complete via CR-123; deterministic bundle/manifest builder complete via CR-127; read-only bundle integrity validation complete via CR-128; external evaluator adapter contract complete via CR-129; adapter implementation, adversarial tests, toy audit tampering eval, behavioral route diffing, **[x] TC-EVAL-008 (Structured Privacy Scanner Finding Codes)**, **[x] TC-EVAL-009 (Shared Internal Reason-Code Constants for Privacy Findings)**, **[x] TC-EVAL-010 (Export One Forbidden Tool-Call Actual)** and technical report remain future slices
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

For the empirical AI safety evaluation track, CR-121 completes fixture validation, CR-122 exposes it through a narrow CLI, CR-123 defines the external-evaluator handoff contract, CR-127 builds the deterministic unscored bundle, CR-128 validates bundle integrity read-only, and CR-129 defines the contract-only adapter boundary. A code-bearing adapter requires a separately approved CR plus an authoritative versioned external evaluator profile. Scoring and score interpretation remain external to TriageCore; adversarial expansion also requires separate approval.

For external runtime interoperability, the next approved slice should be policy tests or execution-path validation for the bounded adapter path.

For the mediated OpenClaw experiment, CR-OC-001A and CR-OC-001B are both complete and merged — CR-OC-001A's contract through PR #119 as `bfa1d6e` and its module through PR #120 as `1e1f441`, CR-OC-001B's contract through PR #122 as `f22fee1` and its store through PR #123 as `47fb3d5` — as the first two of five slices: CR-OC-001A the effect contract, CR-OC-001B atomic client-request reservation, CR-OC-001C the constrained replacement executor, CR-OC-001D the privilege-separated broker and hardened named pipe, CR-OC-001E the exclusive OpenClaw tool and effective-schema evaluation. CR-OC-001C through CR-OC-001E remain unauthorized and each requires its own approval. Neither completed slice authorizes target-file mutation, runtime integration, IPC, or OpenClaw work. CR-OC-001B's local reservation persistence and mediated issuance exist only as unconsumed library surfaces; no runtime module imports either `triage_core.mediated_effect` or `triage_core.request_reservation`. The named-pipe hardening requirements — `PIPE_REJECT_REMOTE_CLIENTS`, an explicit security descriptor denying `NT AUTHORITY\NETWORK`, a random per-run pipe name with `FILE_FLAG_FIRST_PIPE_INSTANCE`, and shim-side verification of the pipe server before any content is transmitted — are recorded as CR-OC-001D requirements and are not satisfied by any earlier slice. Do not treat an implemented contract as an enforced one: CR-OC-001A classifies replay without preventing it, and names a broker connection identifier without authenticating it. Its bounded claim is that an exact authorized pre-content digest became an exact authorized post-content digest — not filesystem state, broker provenance, allowlist membership, path safety, or that any file changed.

For the daily-driver lane, CR-DD-009 established the governed `tc run` execution surface, and CR-DD-010/011 landed the deterministic preview plus exact-plan artifact and review-confirmation foundation through PR #104. CR-DD-012's architecture is approved, but monolithic implementation is withheld. CR-DD-012A is complete and merged through PR #107 as `bccaaad`; it distinguishes source bytes, normalized component bytes, and authoritative assembled worker-execution bytes while preserving existing reading and assembly behavior. CR-YK-002's atomic-claiming foundation is complete and merged through PR #117 as `5155bbb`, which satisfies CR-DD-012B's prerequisite; the CR-DD-012B proposal settled the consumption questions the parent deferred and the slice is now implemented on an unmerged branch under a direct implementation instruction bounded by that proposal's own provisional allowlist; implementation acceptance, merge, and closeout are separate gates and remain ungranted, so its CLI, runtime-integration, and execution surfaces reach `main` only if that slice is accepted. Confirmed-plan execution, `governed_run_plan.v2`, and durable observation/execution schemas require later CRs. Do not combine either slice with general approval, persistence/resume, efficiency claims, live probes, circuit breakers, provider expansion, or TriageDesk authority. Separately, CR-DD-013 — the first M1 slice, binding an existing recorded local backend probe observation into `ResilienceRouteInput` — is complete and merged through PR #116 as `98df9c1`; its implementation and merge authority are spent, and further correction, expansion, or downstream integration needs new authority. It does not belong to the CR-DD-012 lane, carries no CR-YK-002 gate, and grants CR-DD-012B nothing.

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
- **[done] Evaluation handoff bundle builder (CR-127)**: Builds the deterministic fixed-layout handoff and SHA-256 manifest from explicit inputs without scoring.
- **[done] Evaluation handoff integrity validator (CR-128)**: Validates the closed manifest, exact inventory, hashes, contracts, membership, and privacy without mutating or scoring the bundle.
- **[done] External evaluator adapter contract (CR-129)**: Defines the closed-profile and process-safety prerequisites without adding a CLI or subprocess.
- **[done] Governed run plan preview (CR-DD-010)**: Integrates existing context-budget and governed-routing components into a non-executing `tc run --plan` preview. Confirmation/execution coupling, persistence/resume, combined evidence reporting, live capability signals, and TriageDesk actions remain separately gated.
- **[done] Exact-plan artifact and confirmation linkage (CR-DD-011)**: Adds an operator-named metadata-only canonical plan artifact, independent semantic and exact-byte digests, exact artifact-byte-digest review confirmation, and task-show linkage including isolated/custom-ledger inspection. It grants no execution authority. Confirmed execution remains blocked pending an implemented and reviewed CR-YK-002 atomic-claiming foundation, CR-DD-012B's acceptance and merge, and a later CR independently authorizing saved-artifact execution.
- **[architecture approved; bounded A implementation merged] Shared governed run decision (CR-DD-012)**: Establishes the immutable input-snapshot and decision architecture, bounded runtime-observation separation, parity invariant, and A/B implementation sequence. CR-DD-012A is complete and merged through PR #107 as `bccaaad`; the architecture grants no runtime authority.
- **[complete; merged through PR #107 as `bccaaad`] Governed decision foundation (CR-DD-012A)**: Implements immutable snapshot and decision contracts around the established worker-facing execution representation, with raw source bytes optional and non-authoritative. Work remains limited to the approved internal value types, deterministic bounded construction, pure building, canonical identity verification, and focused tests without CLI, ledger, runtime-observation persistence, plan-artifact, worker, or route-execution changes.
- **[implemented on an unmerged branch; acceptance not granted] Shared preview/execution consumption (CR-DD-012B)**: The CR-YK-002 atomic-claiming prerequisite is satisfied through PR #117 as `5155bbb`, and the slice is now built to the settled proposal: one snapshot/decision construction seam before the preview branch, projection rather than recomputation in the plan path, a `RuntimeObservation` that subsumes CR-DD-013 capability evidence without re-deriving it, envelope-filtered backend binding, bounded `decision_id` linkage through the existing open payload extension point, an optional-parameter compatibility boundary for direct callers, and a fail-closed matrix in which termination is never repair. All five approval gates pass and the full suite is green; implementation acceptance, merge, and closeout remain ungranted, and the CR's Implementation Record names the two regression-test paths taken beyond the provisional allowlist, the behavioral changes an accepting reviewer is approving, and the places the built code is narrower than the recommendation. All three previously open questions are settled by recorded decision — capability constrains binding only, the deterministic classifier is authoritative with any model-assisted classifier advisory, and `build_run_plan`'s signature yields to coherence — and five approval gates are recorded. No saved-artifact execution or `--confirmed-plan`.
- **[complete; merged through PR #116 as `98df9c1`] Observed local capability binding (CR-DD-013)**: `tc run` consumes a validated recorded CR-114/CR-118/CR-119 probe record and explicit `[capability]` route-class declarations to populate `ResilienceRouteInput`, replacing hardcoded optimistic local availability with evidence that keeps observed-available, observed-unavailable, configured, and unknown distinct. Unknown is never promoted to availability, a fresh observed-unavailable result overrides declarations, and a fresh reachable runtime proves reachability only — so operators with neither an observation nor an explicit declaration see local capability treated as unknown rather than healthy. Direct `run_task` callers that omit the capability object are unaffected. Automatic probing, class-to-model binding (G3), circuit breakers, and post-resolution runtime revalidation (G6) remain outside the slice and require new authority. This was the first M1 slice; it is independent of CR-DD-012B and the CR-YK lane and grants neither anything. CR-DD-012B's implemented branch changes what consumes this resolution — capability constrains execution binding only and no longer reaches route policy — under its own authority and without touching `capability_evidence.py`.
- **The next evaluator-adapter slice requires a new approved CR**: A code-bearing adapter requires an authoritative versioned external evaluator profile and separate approval; adversarial expansion also remains separate. Do not add arbitrary executable/argv forwarding, scoring or score interpretation inside TriageCore, approval-and-resume behavior, routing integration beyond the governed path, ledger integration, circuit breakers, automatic discovery, background polling, or additional telemetry behavior without a new approved CR.
