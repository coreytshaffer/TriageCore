# Daily-Driver Local-First / Frontier-Cloud Orchestrator — Planning Spec

## Status

Proposed — planning artifact, not implementation. Governed by CR-DD-000.

This document is a review-gated planning artifact. It records a target direction and a
readiness assessment. It adds **no** runtime behavior, no command surface, and no schema.
Every capability described as "future" remains future until its own implementation CR lands.

## Scope Basis (repo-grounded)

Assessment performed against `main` at commit `72c070f` (merge of PR #87,
`cr-rh-003-eval-review-cli`). Verified with `git merge-base --is-ancestor`: CR-RH-003
(`50f666c`, "Add tc eval review CLI wrapper") is an ancestor of `HEAD`, and `origin/main`
also points at `72c070f`. So PR #87 is **merged** and CR-RH-003 is present on `main` at the
time of assessment. (Earlier planning notes that described PR #87 as "open" predate this
merge; this document supersedes that wording.)

If this spec is revisited later, re-pin the commit and re-verify with `merge-base` before
treating any readiness claim as current.

## Thesis

TriageCore stops being *only* a governance harness and becomes the **governed execution
surface** for local-first AI work: one command runs a task, prefers local compute, enforces
a token budget, and escalates to cloud only when justified — all through the existing
privacy, routing, and evidence layers.

## Readiness Assessment

| Dimension | Readiness | Basis |
|---|---|---|
| Local-first daily driver | ~60% | Governed loop is available through `tc run`; live capability signals and enforced budgets remain absent. |
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

- **G1 — No unified operator run surface.** `tc run` exposes the governed loop, but
  `triagecore run-pipeline` remains local-only and bypasses the router.
- **G2 — Cloud is Qwen, not frontier.** No live Claude/GPT/Gemini backends, no provider
  abstraction beyond OpenAI-compatible, no per-provider cost/credit model.
- **G3 — Route decisions outrun execution bindings.** `local_heavy`/`local_fast` and
  `cloud_primary`/`cloud_secondary` collapse to one local backend and Qwen respectively.
- **G4 — Health/capability signals are inputs, not observations.** Nothing populates
  `lm_studio_ok`, `memory_headroom_mb`, `cloud_credit_state`, `recent_*_failures` live.
- **G5 — Budgets warn but do not act.** `compression.py` is not bound into the send path.
- **G6 — No circuit breakers / degraded modes** (backlog Story 13.6 open).
- **G7 — TriageDesk cannot act** (read-only by invariant).
- **G8 — Single-shot, not interactive.**

## Sequencing (do not skip ahead)

The order is load-bearing. Observed local routing and live health signals must exist
**before** cloud escalation can be trusted. Going straight to frontier integrations would be
backwards.

1. **M0 — Unified run surface (next implementation candidate).** One governed `tc run`
   command wrapping `run_task`, using `choose_resilience_route`, producing route/worker/token
   evidence. Converts hidden library capability into daily-use evidence. Tracked as CR-DD-009.
2. **M1 — Live capability probe + real route bindings + circuit breakers** (G3, G4, G6).
3. **M2 — Frontier provider backends** (G2). *Future work; see boundary below.*
4. **M3 — Budget enforcement + prefer-local economics** (G5).
5. **M4 — Actionable cockpit + interactive session** (G7, G8).

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
Each claim maps to a concrete, inspectable check. Most require M0 to exist first, because
today the governed loop is not exercised by an operator command.

| Claim to verify | Required evidence | Where |
|---|---|---|
| Local-first actually happened | `route_decision` events with `selected_route` in `local_*` dominating over a real usage window | `.triagecore/ledger.jsonl` (`tc audit --kind route_decision`) |
| Cloud escalation happened only when justified | `worker_result` / `route_decision` showing cloud reached only after local failure/unavailability, with `fallback_depth > 0` and reason codes | ledger route/worker events |
| Token-budget evidence recorded per run | a `token_efficiency_record` / context-pack artifact linked to each task attempt | context packs + ledger |
| Privacy fail-closed remained intact | `route_audit` with `privacy_scan_passed`, and **no** external route for `local_only` packets (CR-021 invariant scan clean) | `tc audit --privacy-invariants` |
| Operator actually used it daily | frequency/recency of `tc run` task events across days | ledger task feed |
| Readiness % is real, not estimated | the four checks above computed over the usage window via TriageLab stats | `triagecore stats` / `tc lab report` |

Until `tc run` (CR-DD-009) exists and writes these events, the readiness percentages remain
planning estimates and should be cited as such.

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
