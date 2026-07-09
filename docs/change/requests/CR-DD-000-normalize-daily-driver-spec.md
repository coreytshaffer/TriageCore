# CR-DD-000: Normalize Daily-Driver Spec As Planning Artifact

## Status

Proposed

Docs-only planning slice. This CR normalizes an external daily-driver orchestrator evaluation
into a review-gated, commit-pinned planning artifact inside the repo. It adds no runtime code,
no CLI surface, no schema, no fixtures, no ledger writes, and no model calls. It does not
authorize any implementation; it records design intent and the evidence bar that later
implementation CRs must meet.

## Scope

- Add a repo-canonical planning spec at
  `docs/architecture/daily_driver_orchestrator_spec.md` (shortened, commit-pinned version of
  the daily-driver orchestrator assessment).
- Correct the scope-basis wording: the assessment is against `main` at `72c070f` (PR #87
  merged; CR-RH-003 present, verified with `git merge-base --is-ancestor`), not an open PR.
- Add an **Evidence Requirements** section mapping each readiness claim (local-first share,
  justified cloud escalation, token-budget evidence, privacy fail-closed, operator daily use,
  and the readiness percentages themselves) to a concrete ledger/artifact check.
- Record **M0 (unified `tc run` surface)** as the next implementation candidate, tracked
  separately as CR-DD-009.
- State explicitly that **frontier-cloud support (live Claude/GPT/Gemini backends) is future
  work (M2), not a current capability**, and is gated behind M0 and M1.
- Cross-link the companion long-form `TriageCore_DailyDriver_Spec.docx` at the repo root.

## Non-Goals

- No implementation authorization: no `tc run`, no probe, no frontier backends, no budget
  enforcement in this CR.
- No runtime code changes of any kind; current behavior is preserved.
- No new CLI surface, schema module, fixtures, or dependencies.
- No ledger writes, model generation calls, or prompt/completion capture.
- No automatic routing changes.
- No claims of energy, cost, quality, or safety improvement; readiness percentages are
  labeled planning estimates until backed by measured evidence.
- No commitment that later slices will be implemented exactly as drafted; implementation CRs
  own final names, fields, and validation.

## Description

An external evaluation assessed how close TriageCore + TriageDesk are to a daily-driver
local-first / frontier-cloud orchestrator and proposed a milestone path (M0–M4). The core
thesis — TriageCore becoming the governed execution surface for local-first AI work — is
sound and worth recording. Before it can be treated as canonical planning, two corrections
are required: (1) the scope basis must reflect verified repo state (PR #87 is merged, not
open), and (2) each readiness claim must carry an explicit evidence requirement so the
percentages are not mistaken for measurements.

This CR captures that corrected, evidence-bounded version in-repo as a planning artifact and
names M0 as the next implementation candidate, while explicitly deferring frontier-cloud
support to a gated future milestone. Sequencing is load-bearing: observed local routing and
live health signals must exist before cloud escalation can be trusted, so frontier
integrations must not precede M0/M1.

## Acceptance Criteria

- [ ] `docs/architecture/daily_driver_orchestrator_spec.md` exists with Status = Proposed
  (planning artifact) and a commit-pinned scope basis citing `72c070f` and the `merge-base`
  verification of CR-RH-003.
- [ ] The spec contains an Evidence Requirements section mapping every readiness claim to an
  inspectable ledger/artifact check.
- [ ] The spec names M0 (unified `tc run` surface) as the next implementation candidate and
  references CR-DD-009.
- [ ] The spec states plainly that frontier-cloud support is future work (M2), gated behind
  M0 and M1, and behind the external-safe gate, spend ceilings, credit-state degradation, and
  egress logging.
- [ ] The spec preserves the existing invariants list and adds no implementation authorization.
- [ ] No files outside `docs/` are changed.

## Validation

- `git diff --check`
- No tests are run or added: this slice adds no code, fixtures, schemas, or documented
  commands that any existing test asserts against; the repo's docs-only review convention
  requires only `git diff --check` for docs-only slices.
