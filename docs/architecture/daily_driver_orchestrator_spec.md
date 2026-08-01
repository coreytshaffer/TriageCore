# Daily-Driver Local-First / Frontier-Cloud Orchestrator — Planning Spec

## Status

Proposed — planning artifact, not implementation. Governed by CR-DD-000.

This document is a review-gated planning artifact. It records a target direction and a
readiness assessment. It adds **no** runtime behavior, no command surface, and no schema.
Every capability described as "future" remains future until its own implementation CR lands.

## Scope Basis (repo-grounded)

Assessment re-pinned against `main` at commit `6d585268` (merge of PR #132, the CR-DD-013
documentation-only closeout). Verified with `git merge-base --is-ancestor`: CR-DD-012A
(`bccaaad`, merged through PR #107) and CR-DD-013 (`98df9c1`, merged through PR #116) are
both ancestors of `main`. The immutable decision foundation and governed capability
binding are therefore present on `main` at the time of this re-pin.

The previous pin was `257e79b` (merge of PR #131). Re-pinned after CR-DD-013's
documentation-only closeout; no production, test, workflow, schema, or architecture file
changed between the two pins. The still earlier `ac851d5` and `72c070f` bases are retained
only as history; all are superseded by the pin above.

If this spec is revisited later, re-pin the commit and re-verify with `merge-base` before
treating any readiness claim as current.

Current implementation note (2026-08-01): CR-DD-009 has landed and `tc run` now
provides the governed execution surface described as M0 below. CR-DD-010 now implements
the deterministic, non-executing run-plan preview. CR-DD-011 implements a durable
privacy-safe plan artifact, independent semantic and exact-byte digests, exact review
confirmation, metadata-only ledger linkage, and read-only inspection. Confirmed execution
remains blocked. CR-DD-012's shared-decision architecture is approved, but monolithic
implementation is withheld. **CR-DD-012A is complete and merged through PR #107 as
`bccaaad`.** It distinguishes optional provenance source bytes, normalized component
bytes under current UTF-8/text semantics, and authoritative assembled worker-execution
bytes, but grants no integration authority; no public command consumes it. CR-DD-012B's
CR-YK-002 atomic-claiming prerequisite is satisfied through PR #117 as `5155bbb`, and a
documentation-only proposal now exists at
`docs/change/requests/CR-DD-012B-shared-preview-execution-consumption.md`; implementation
remains blocked on its own explicit approval and bounded file allowlist, and the proposal
is not that approval. **CR-DD-013 is implemented and merged through PR #116 as
`98df9c1`.** `tc run` now resolves recorded capability evidence and binds that resolution
into route selection; configured route declarations and observed reachability remain
separate inputs. Its documentation-only closeout merged through PR #132 at `6d585268` and
records the change as complete, accepted, and merged; its implementation and merge
authority are spent, and it grants no standing authority for downstream integration. Plan
v2, durable observation/execution schemas, and confirmed-plan execution remain deferred.
The readiness percentages below remain historical planning estimates, not current
measurements; this re-pin does not recompute them.

Earlier pre-PR #107 branch-only wording for CR-DD-012A is superseded by the merged status
recorded above.

## Thesis

TriageCore stops being *only* a governance harness and becomes the **governed execution
surface** for local-first AI work: one command runs a task, prefers local compute, enforces
a token budget, and escalates to cloud only when justified — all through the existing
privacy, routing, and evidence layers.

## Readiness Assessment

| Dimension | Readiness | Basis |
|---|---|---|
| Local-first daily driver | ~60% | Governed loop and recorded capability binding are available through `tc run`; distinct real route/backend bindings, circuit breakers, runtime revalidation, and enforced budgets remain absent. |
| Frontier-cloud orchestrator | ~35% | Only live cloud backend is `QwenCloudBackend`; Claude/GPT/Gemini exist solely as after-the-fact file handoffs (Codex/Antigravity). |
| Token efficiency | Measured, not enforced | `context_budget.py` / context packs record usage; budgets are advisory, no pre-send compaction is bound into the run path. |

These percentages are planning estimates, not measurements. They become measurable only
after M0 (below) produces daily-use evidence. See **Evidence Requirements**.

## What Already Works (verified in-repo)

- `TriageClient.run_task` runs a governed loop: verify packet → privacy scan
  (fail-closed) → external-safe packet gate → classify → specialist route → resilience
  route. `local_heavy` and `local_fast` execute locally; `cloud_primary/secondary` use the
  real cloud branch (`_execute_cloud_task`) only for external-safe packets; `human_handoff`
  and the currently unimplemented `deterministic` route return `handoff_required` without
  model execution.
- `routing/resilience_router.py` encodes local-first ordering: deterministic → local_fast /
  local_heavy → cloud, with high-sensitivity forced to human handoff and cloud blocked for
  local-only privacy.
- Token/energy evidence: per-runner and per-category budgets, context-pack artifacts, NVML/
  RAPL power, carbon intensity, battery gating, energy early-stopping; TriageLab stats/export
  and an interpretable local-success predictor.

## Gaps (planning targets)

- **G1 — No confirmed-plan execution linkage.** `tc run` exposes the governed loop,
  CR-DD-010 previews its deterministic planning inputs, and CR-DD-011 records exact
  artifact review linkage. Execution still does not consume that artifact or the same
  immutable decision. CR-DD-012A's bounded internal, non-integrated foundation and focused
  tests are complete and merged through PR #107 as `bccaaad`; no public command consumes
  them. CR-DD-012B has a documentation-only proposal and still has no implementation
  authority. The future shared path must use one immutable input snapshot
  so execution does not reopen or reconstruct governed inputs. Confirmed-artifact
  execution remains a later, separately gated CR; `triagecore run-pipeline` also remains
  local-only and bypasses the router.
- **G2 — Cloud is Qwen, not frontier.** No live Claude/GPT/Gemini backends, no provider
  abstraction beyond OpenAI-compatible, no per-provider cost/credit model.
- **G3 — Route decisions outrun execution bindings.** `local_heavy`/`local_fast` and
  `cloud_primary`/`cloud_secondary` collapse to one local backend and Qwen respectively.
- **G4 — Closed: observed capability is bound into route selection.** CR-DD-013 is
  implemented and merged through PR #116 as `98df9c1`. `tc run` resolves capability
  evidence through `resolve_from_config` and passes the result into route-input
  construction. Fresh observed unavailability overrides configured declarations; fresh
  reachability is evidence of reachability only, while route classes still require their
  corresponding configured declarations. Stale, missing, malformed, or provenance-invalid
  observations fail closed rather than restoring the former optimistic local literals.
- **G5 — Budgets warn but do not act.** `compression.py` is not bound into the send path.
- **G6 — No circuit breakers / degraded modes** (backlog Story 13.6 open).
- **G7 — TriageDesk cannot act** (read-only by invariant).
- **G8 — Single-shot, not interactive.**

## Sequencing (do not skip ahead)

The order is load-bearing. Observed local routing and live health signals must exist
**before** cloud escalation can be trusted. Going straight to frontier integrations would be
backwards.

1. **M0 — Unified run surface (implemented by CR-DD-009).** One governed `tc run`
   command wrapping `run_task`, using `choose_resilience_route`, and producing route/worker
   evidence. Converts hidden library capability into daily-use evidence. Tracked as CR-DD-009.
2. **M0.1 — Governed run-plan preview (implemented by CR-DD-010).** Show context budget,
   privacy/egress posture, a deterministic route forecast, escalation conditions, and
   expected verification without model calls, execution, or persistence.
3. **M0.2 — Exact-plan artifact and review confirmation (implemented by CR-DD-011).** Bind an
   operator-named privacy-safe plan artifact and explicit exact artifact-byte-digest
   confirmation, with independent plan-body-digest validation, under one task ID.
   Confirmation is not approval or execution authority. Confirmed-plan execution remains
   blocked: CR-DD-012A/B establish the shared decision path only, and saved-artifact
   execution still requires a separately approved later CR.
4. **M0.3 — Shared governed run decision (architecture approved by CR-DD-012;
   monolithic implementation withheld).** Required sequence:
   **M0.3a / CR-DD-012A**, complete and merged through PR #107 as `bccaaad`, establishes
   the immutable input snapshot around `SourceBytes`,
   `NormalizedComponentBytes`, and authoritative `AssembledExecutionBytes`, plus the
   canonical decision, pure normalizer/builder, identity, and focused tests with no CLI,
   ledger, worker, route, or plan-v2 change; then **M0.3b / CR-DD-012B**, whose
   CR-YK-002 prerequisite is now satisfied and whose documentation-only proposal is
   recorded, but which remains blocked until it receives its own separate approval and
   bounded file allowlist. It owns shared preview/execution consumption, envelope
   enforcement, bounded decision-ID linkage, and parity/fail-closed tests. A recorded
   decision settles that CR-DD-013 capability evidence constrains **execution binding
   only** and never governed-decision formation, so stable inputs produce the decision,
   route intent, envelope, and decision ID while volatile observations may only
   execute, bind an already-authorized fallback, or fail closed. That is a deliberate
   correction to current `tc run` route selection, recorded as such. Five approval gates
   bind at two stages: the two proposal-stage preconditions — the recorded capability
   decision and the pre-`planning` seam statement — are satisfied, while the three test
   obligations must be **bound by** any bounded implementation approval and **satisfied
   before** implementation acceptance, merge, or closeout. Those three are replacing
   rather than deleting the CR-DD-012A integration-absence guard, a negative test that
   post-decision capability change cannot alter the decision ID, route policy, or
   envelope, and a negative test that unavailable capability yields only an authorized
   fallback or a closed failure. `governed_run_plan.v2`, durable `RuntimeObservation`/`ExecutionRecord` contracts,
   and confirmed-plan execution remain deferred.
5. **M1 — Capability binding complete; real route bindings and circuit breakers remain
   open** (G3, G4, G6).
   - **G4 / CR-DD-013 is complete**, merged through PR #116 as `98df9c1`: recorded
     capability resolution is bound into `ResilienceRouteInput`.
   - **G3 remains open:** route classes still collapse onto one local backend or Qwen
     rather than distinct real execution bindings.
   - **G6 remains open:** circuit breakers, degraded-mode policy, and execution-time
     capability revalidation are not integrated.
6. **M2 — Frontier provider backends** (G2). *Future work; see boundary below.*
7. **M3 — Budget enforcement + prefer-local economics** (G5).
8. **M4 — Actionable cockpit + interactive session** (G7, G8).

## Frontier-Cloud Support Is Future Work

Frontier-cloud execution (live Claude / GPT / Gemini backends) is **not a current
capability** and is **not** the next step. It is M2, explicitly gated behind M0 and M1. When
it is built, it must remain behind the existing external-safe packet gate, with per-provider
spend ceilings, credit-state degradation, and egress logging. Until an M2 implementation CR
lands, the only live cloud path is the bounded Qwen path that exists today. The
Codex/Antigravity supervised-handoff lane is retained and coexists with any future live
backends.

## Evidence Requirements

No readiness claim in this document is canonical until backed by ledger/artifact evidence.
Each claim maps to a concrete, inspectable check. M0 now provides the operator command, but
the token/context evidence linkage and a sufficient daily-use evidence window remain
incomplete.

| Claim to verify | Required evidence | Where |
|---|---|---|
| Local-first actually happened | `route_decision` events with `selected_route` in `local_*` dominating over a real usage window | `.triagecore/ledger.jsonl` (`tc audit --kind route_decision`) |
| Cloud escalation happened only when justified | `worker_result` / `route_decision` showing cloud reached only after local failure/unavailability, with `fallback_depth > 0` and reason codes | ledger route/worker events |
| Token-budget evidence recorded per run | a `token_efficiency_record` / context-pack artifact linked to each task attempt | context packs + ledger |
| Privacy fail-closed remained intact | `route_audit` with `privacy_scan_passed`, and **no** external route for `local_only` packets (CR-021 invariant scan clean) | `tc audit --privacy-invariants` |
| Operator actually used it daily | frequency/recency of `tc run` task events across days | ledger task feed |
| Readiness % is real, not estimated | the four checks above computed over the usage window via TriageLab stats | `triagecore stats` / `tc lab report` |

Until daily-use `tc run` records are evaluated against these checks, the readiness
percentages remain planning estimates and should be cited as such. CR-DD-010 previews are
not execution evidence and do not satisfy these requirements.

## Invariants Preserved

Local-first ordering, privacy fail-closed, external-safe gate before egress, human review as
first-class, append-only evidence, and energy/battery gating remain load-bearing across every
milestone. No milestone relaxes an invariant to ship.

## Non-Goals

- No implementation is authorized by this document; it is planning only.
- No peer-to-peer local compute fabric / LAN discovery (later Phase 14 stories).
- No autonomous background execution without human review.
- No mobile execution-UI changes (mobile stays review-only).
- No replacement of the Codex/Antigravity supervised-handoff lane.
- No claim of energy, cost, quality, or safety improvement; those require measured evidence.

## Companion Artifact

A formatted long-form version of this assessment is maintained as
`TriageCore_DailyDriver_Spec.docx` at the repo root for review/sharing. This markdown file is
the repo-canonical, commit-pinned planning record.

**Mirror drift (recorded 2026-08-01).** No reproducible generation path for the DOCX exists
in this repository: there is no Makefile target, script, packaging entry point, or CI step
that produces it, and no code references it. It was therefore not regenerated alongside this
revision and was deliberately left unmodified rather than hand-edited. The DOCX currently
lags this markdown by the `6d585268` re-pin, the CR-DD-012A merged-status correction, the
CR-DD-013 completion record, and the split between completed G4 capability binding and the
still-open G3/G6 work. It also lagged before this revision. Closing the drift — either by
establishing a reproducible generation path or by retiring the mirror — is bounded follow-up
work and is not authorized here. Until then, this markdown file remains authoritative
wherever the two disagree.
