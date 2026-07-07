# Fable Final Capability Note — 2026-07-07

## Purpose

A factual record of what the Claude Fable 5 assisted sessions contributed
to TriageCore and, more importantly, what the repository does and does not
depend on now that those sessions end. Written so a future maintainer can
calibrate exactly how much weight to give model-authored artifacts.

## What the Model's Role Actually Was

- **Drafting and review assistance under human control.** Slices were
  proposed as plans, approved by the operator before edits, staged from
  exact file lists, and committed only on explicit instruction. The CR-114
  commit, tags, and push on 2026-07-07 were executed from operator-supplied
  commands.
- **Evidence collection.** The model ran read-only verification commands
  and recorded their real output (e.g. the 803 passed / 2 skipped suite
  run and the signature/privacy/identity outputs in
  [reviewer-checkpoint-2026-07-07.md](reviewer-checkpoint-2026-07-07.md)).
- **External review.** The model produced
  [fable-exit-audit-2026-07-07.md](fable-exit-audit-2026-07-07.md), whose
  key finding (the never-created 2026-07-02 checkpoint tag) was verified
  against `git tag` output before being acted on.

## What the Model's Role Was Not

- It did not certify safety, correctness, or compliance. Model-authored
  review text is reviewer evidence, not approval — the same rule the repo
  applies to signatures, manifests, and evaluator verdicts.
- It did not hold execution authority. `tc doctor` postures at the final
  checkpoint: external execution **blocked**, human approval
  **human-review-required**, network/tool execution **unavailable**
  (verified 2026-07-07).
- It did not expand autonomy, weaken fail-closed behavior, or change
  approval, signature, identity, routing, privacy, or audit semantics in
  the exit-window slices (CR-114 and the CR-115 extraction package are
  docs-only).

## What Changes When This Model Is Gone

**At runtime: nothing.** TriageCore has no dependency on any specific
assistant model. Every control is enforced by code, verified by the
offline test suite, or documented in-repo. Verification requires only
Python, pytest, and the repository.

**What is actually lost is session context** — unwritten reasoning about
why slices were shaped the way they were. Mitigations, all in-repo as of
`74260b3`:

- per-CR notes with explicit Scope / Non-Goals / Validation
  (`docs/change/requests/`)
- dated checkpoints (2026-07-02 and 2026-07-07) with real command output
- the exit audit and this extraction package
- [control-plane-invariant-checklist.md](control-plane-invariant-checklist.md)
  and
  [outer-loop-control-review-recipe.md](outer-loop-control-review-recipe.md),
  which make the review style reproducible by any successor, human or
  model

## Standing Caution for Successor Models

Model-authored documents in this repo, including this one, are
point-in-time claims. Verify against commands before acting on them. Do
not treat prior model output as precedent for expanding scope: the
conventions that bound this model — plan-gated approvals, exact staging
lists, conservative claim language, docs-only boundary briefs before
boundary crossings — bind successors equally.

## Verified Facts at Time of Writing

- HEAD: `74260b3` ("Add July 2026 reviewer checkpoint"), pushed to
  `origin/main`.
- Tags `v0.1.0-reviewer-checkpoint-2026-07-02` (at `355c521`) and
  `v0.1.0-reviewer-checkpoint-2026-07-07` (at `74260b3`) created and
  pushed 2026-07-07.
- Full suite at pre-slice HEAD `f8bf33c`: 803 passed, 2 skipped.
- Privacy invariant audit: 698 ledger records, passed.

## Related Docs

- [future-agent-maintainer-handoff-2026-07-07.md](future-agent-maintainer-handoff-2026-07-07.md)
- [reviewer-checkpoint-2026-07-07.md](reviewer-checkpoint-2026-07-07.md)
- [fable-exit-audit-2026-07-07.md](fable-exit-audit-2026-07-07.md)
