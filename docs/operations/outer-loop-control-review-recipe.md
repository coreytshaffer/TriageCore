# Outer-Loop Control Review Recipe

## Purpose

A repeatable recipe for running an external control-plane review of this
repository — the kind of review recorded in
[fable-exit-audit-2026-07-07.md](fable-exit-audit-2026-07-07.md). Any
reviewer, human or model, should be able to follow it cold and produce a
comparable artifact. The recipe itself is docs-only and grants nothing.

## Ground Rules for the Reviewer

- Do not propose broad refactors.
- Do not weaken fail-closed behavior, expand autonomy, remove human
  approval gates, or reduce audit evidence.
- Prefer docs, fixtures, tests, and reviewer evidence over runtime change.
- Trust runnable checks over documents; where a doc and the repo disagree,
  the repo is truth and the disagreement is itself a finding.
- Classify every recommendation as one of: **docs-only**, **test-only**,
  **runtime-safe**, **runtime-risky**.

## Step 1 — Establish the Baseline

```powershell
git rev-parse HEAD
git status --short          # expect empty before trusting results
git log --oneline -15
git tag                     # compare against tags that docs promise exist
```

Record HEAD, tree state, and any doc-promised anchors (tags, checkpoint
commits) that do not resolve. Missing anchors are first-class findings.

## Step 2 — Run the Evidence Commands

Substitute `python -m triage_core.tc_cli` for `tc` if the console-script
shim is unavailable (see the reviewer smoke runbook).

```powershell
python -m pytest -q                                   # full offline regression
tc doctor                                             # runtime-safety postures
tc audit --privacy-invariants                         # persisted privacy invariant
tc audit --verify-signatures --kind route_decision    # provenance, metadata-only
tc identity list                                      # public signer metadata
triagecore benchmark --list-only                      # fixtures, no backend contact
git diff --check
```

Record exact counts (tests passed/skipped, records checked, signature
tallies) — future reviews diff against them.

## Step 3 — Cross-Check Docs Against Repo State

- Read, in order: `reviewer-entrypoints.md`, `reviewer-readiness.md`,
  the newest dated checkpoint, `../current_backlog.md`,
  `../change/change_log.md`.
- For every claim of the form "X exists" or "tag/commit Y anchors Z",
  verify it with a command. Note drift (stale counts are expected in
  point-in-time docs and are not findings; broken anchors are).
- Check that the newest completed work has a consolidated dated
  checkpoint. Uncheckpointed arcs are the most common gap.

## Step 4 — Check the Invariants

Walk [control-plane-invariant-checklist.md](control-plane-invariant-checklist.md)
row by row. Every row should still have a passing verification path. Any
row without one is a finding ranked above feature gaps.

## Step 5 — Write the Report

Use this structure (the format of the 2026-07-07 exit audit):

1. Current strongest evidence (ranked)
2. Current weakest reviewer-facing gap (one primary, secondaries listed)
3. Top 5 next slices (each risk-classified)
4. Which slice should be done first, and why
5. Which slices should not be done yet, and why
6. Controls that must remain invariant
7. Suggested validation commands (with expected values)
8. Final handoff note for a future reviewer

## Ordering Heuristic

**Bank evidence before adding capability.** When in doubt, the first slice
is a docs-only checkpoint that freezes the current verified state; the
last slices are anything that crosses a determinism, autonomy, or
enforcement boundary. A boundary crossing should always be preceded by a
docs-only brief that defines it (the CR-113 → CR-118+ pattern).

## Stop Conditions

Abort and report instead of proceeding if:

- HEAD or the working tree differs from what the requester specified;
- a doc-promised anchor does not resolve and the requester has not been
  told;
- any proposed change would touch runtime code, tests, or the semantics of
  approval, signatures, identity, routing, privacy, or audit under a
  docs-only mandate.

## Related Docs

- [fable-exit-audit-2026-07-07.md](fable-exit-audit-2026-07-07.md)
- [reviewer-checkpoint-2026-07-07.md](reviewer-checkpoint-2026-07-07.md)
- [control-plane-invariant-checklist.md](control-plane-invariant-checklist.md)
- [reviewer-smoke-runbook.md](reviewer-smoke-runbook.md)
