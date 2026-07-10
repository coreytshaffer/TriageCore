# Future Agent / Maintainer Handoff — 2026-07-07

## Purpose

The single entry point for whoever continues TriageCore work — a human
maintainer or a successor model. Read this first; everything else is
linked from here.

## State at Handoff (verified 2026-07-07)

- **Branch/HEAD:** `main` at `74260b3` ("Add July 2026 reviewer
  checkpoint"), pushed to `origin/main`.
- **Checkpoint anchors:** tags `v0.1.0-reviewer-checkpoint-2026-07-02`
  (→ `355c521`) and `v0.1.0-reviewer-checkpoint-2026-07-07` (→ `74260b3`),
  both pushed. The previously missing 2026-07-02 tag is reconciled.
- **Regression suite:** 803 passed / 2 skipped at `f8bf33c` (the commit
  under `74260b3`); CI green on Python 3.10/3.11/3.12 at `88c9cfb`.
- **CR ledger:** CR-100 → CR-115 complete. **CR-114 = the evidence
  checkpoint. CR-115 = this extraction package. CR-117 = the task-show
  signature-verification slice. CR-118+ = the telemetry lane** (the
  numbering marks the boundary between deterministic evidence
  work and the lane's first non-deterministic slice).

## Reading Order

1. [reviewer-checkpoint-2026-07-07.md](reviewer-checkpoint-2026-07-07.md) — current verified state
2. [control-plane-invariant-checklist.md](control-plane-invariant-checklist.md) — what must never break
3. [fable-exit-audit-2026-07-07.md](fable-exit-audit-2026-07-07.md) — ranked evidence, gaps, and slice plan
4. [../current_backlog.md](../current_backlog.md) — work lanes
5. [local-backend-telemetry.md](local-backend-telemetry.md) — the CR-118+ boundary brief
6. [fable-final-capability-note-2026-07-07.md](fable-final-capability-note-2026-07-07.md) — how to weigh model-authored artifacts

## Next Slices, In Order

| Order | Slice | Risk class |
|---|---|---|
| 1 | ~~`tc task show --verify-signatures` opt-in, reusing CR-097 fail-closed categories~~ — done (CR-117, runtime-safe): [task-show-signature-verification.md](task-show-signature-verification.md) | runtime-safe |
| 2 | Telemetry schema + `synthetic_fixture` validation only — no probe code (CR-118 candidate) | test-only |
| 3 | Telemetry probe, exactly within the CR-113 brief: opt-in, explicit endpoint, `probe_disabled` default, closed failure vocabulary (CR-119+ candidate) | runtime-risky |

Deferred deliberately (do not start without a dedicated approved CR):
Issue #73 key rotation; signed-event expansion to new event types;
authority-manifest binding to identity/admission/routing; live benchmark
capture; any new execution surface.

## Working Conventions (binding)

- **Plan-gated approvals:** propose a scoped plan; edit only after the
  operator approves; commit and push only on explicit instruction.
- **Exact staging lists:** name every file staged; never `git add -A`.
- **Conservative claim language:** per-CR notes carry Scope / Non-Goals /
  Validation; docs state what is *not* claimed; "signatures/manifests/
  evaluator verdicts are evidence, not approval" appears wherever it
  applies.
- **Claim CR numbers at commit time**, not draft time (parallel sessions
  have collided before).
- **Boundary crossings get a docs-only brief first** (the CR-113 →
  CR-118+ pattern), then a schema/fixture slice, then implementation.
- **Docs-only validation:** `git diff --check`. Code-bearing validation:
  `python -m pytest -q`.

## Environment Notes (local machine, not repo state)

- A local Windows Application Control policy blocks the `tc.exe`
  console-script shim; use `python -m triage_core.tc_cli ...` (identical
  behavior; documented in the reviewer smoke runbook, CR-111).
- Local Python is 3.14.5; CI covers 3.10–3.12.
- Local identity state: one active `router-tools` ed25519 signer
  (`route_decision:sign`); a 2026-07-02 repair backup exists at
  `.triagecore/identity/agents.json.backup-20260702`.
- `.triagecore/ledger.jsonl` held 698 privacy-clean records at handoff.

## Stop and Ask a Human When

- A change would weaken any row of the
  [invariant checklist](control-plane-invariant-checklist.md).
- A change would give runtime meaning to a signature, manifest, or
  evaluator verdict.
- A doc-promised anchor (tag, commit, file) does not resolve.
- You are about to cross the deterministic/non-deterministic boundary
  (telemetry probe) or any autonomy/enforcement boundary.
- Anything destructive, history-rewriting, or outward-facing beyond an
  approved push.

## First Commands for a Cold Start

```powershell
git status --short && git log --oneline -5 && git tag -l "*reviewer-checkpoint*"
python -m pytest -q
python -m triage_core.tc_cli doctor
python -m triage_core.tc_cli audit --privacy-invariants
```

Expected: clean tree, both checkpoint tags present, suite ≥ 803 passed,
doctor postures blocked / human-review-required / unavailable, privacy
invariant pass. If any of these surprise you, that is your first finding —
follow [outer-loop-control-review-recipe.md](outer-loop-control-review-recipe.md).
