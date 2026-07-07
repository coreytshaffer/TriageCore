# Reviewer Checkpoint — 2026-07-07

## Purpose

This document preserves a point-in-time reviewer-readiness evidence record
for TriageCore, taken on 2026-07-07. It consolidates the state of the
repository after the CR-100 through CR-113 arc (route/worker telemetry
ledger lane and runtime strategy evidence lane), records fresh validation
results, and reconciles the tag recommendation left open by the previous
checkpoint.

This is an evidence record of one repository state and one local runtime
state on one date. It is not a release certification, and it does not prove
production readiness, safety, legal compliance, or correctness of model
outputs.

## Commit Baseline

- **Branch:** `main`
- **HEAD Commit:** `f8bf33c` (Add CR-113 checkpoint note)
- **Working Tree:** clean of tracked changes; one untracked review
  artifact was present during evidence collection
  (`docs/operations/fable-exit-audit-2026-07-07.md`, an external
  control-plane review that served as input to this checkpoint)
- **Previous Checkpoint:** [reviewer-release-checkpoint-2026-07-02.md](reviewer-release-checkpoint-2026-07-02.md)
  at `355c521` (Merge PR #82)

## What Changed Since the 2026-07-02 Checkpoint (CR Arc Summary)

Fifteen commits landed on `main` between `355c521` and `f8bf33c`, all
docs, fixtures, tests, and read-only evidence surfaces:

1. **Route/worker telemetry ledger lane (CR-100 → CR-103):** a standalone
   telemetry-only route/worker ledger event contract with fail-closed
   metadata validation (CR-100), an explicit-path read-only inspection CLI
   (`tc route-worker-ledger inspect`, CR-101), a deterministic
   metadata-only demo fixture and operations note (CR-102), and runbook
   hardening plus focused regression coverage (CR-103). No routing,
   execution, admission, approval, or identity behavior changed.
2. **Runtime strategy evidence lane (CR-104 → CR-112):** deterministic,
   metadata-only strategy evidence records (CR-104), comparison fixtures
   including an over-orchestrated negative control (CR-105), delta
   calculation with a closed interpretation vocabulary (CR-106), the
   read-only `tc runtime-strategy report` command (CR-107), an independent
   quality-gate effect axis where failure dominates and gates never
   rewrite cost interpretations (CR-108, schema v2), fixture report export
   with fail-closed reason-coded IO and byte-identical repeats (CR-109),
   recorded-evidence reports from operator-supplied JSON kept strictly
   separate from fixture reports (CR-110), and recorded-report export
   through the same shared path (CR-112). No live model calls, no routing
   changes, no ledger writes, no ranking or "best strategy" claims.
3. **Reviewer ergonomics (CR-111):** a docs-only runbook note that every
   `tc ...` command can be run as `python -m triage_core.tc_cli ...` when
   the console-script shim is unavailable or blocked by local
   application-control policy.
4. **Telemetry boundary brief (CR-113):** a docs-only design brief
   ([local-backend-telemetry.md](local-backend-telemetry.md)) bounding the
   lane's first future non-deterministic slice — closed failure
   vocabulary, tiered evidence provenance, opt-in `probe_disabled` default
   posture, and privacy rules — written before any probe code exists.

## Verification Evidence (2026-07-07, local)

All commands were run from the repository root at HEAD `f8bf33c`. The `tc`
console-script shim is blocked by a local application-control policy on
this machine, so `tc ...` commands were run as
`python -m triage_core.tc_cli ...` (CR-111 fallback; identical behavior).

- **Full regression:** `python -m pytest -q` →
  **803 passed, 2 skipped in 102.62s**. (2026-07-02 baseline was 715
  passed, 2 skipped; the growth is the CR-100 → CR-113 test coverage.)
- **Local Python:** 3.14.5.
- **`git diff --check`:** clean.
- **`tc doctor`:** `Overall: WARN` — the only warning source was
  `Git status: dirty`, caused solely by the named untracked review
  artifact above. Runtime safety postures reported: external execution
  **blocked**, human approval **human-review-required**, network/tool
  execution **unavailable**.
- **`tc audit --privacy-invariants`:** passed — **698 ledger records
  checked**, no forbidden raw-content keys.
- **`tc audit --verify-signatures --kind route_decision`:** passed —
  `valid_signed=2 invalid_signed=0 unsigned=0 malformed=0
  skipped_non_target=696 strict=off`, both signed events from
  `agent_id=router-tools`.
- **`tc identity list`:** 1 active identity — `router-tools`, role "Route
  decision signer", ed25519, capability `route_decision:sign`. No private
  key material printed.
- **`triagecore benchmark --list-only`:** 6 fixtures listed, including the
  two `expected=handoff_required` safety-handoff fixtures, with no backend
  contact.
- **Fail-closed identity handling (CR-097):** remains in place and covered
  by `tests/test_cr_097_identity_registry_load.py` (malformed, truncated,
  wrong-shape, and unreadable registries; secret-leak regression;
  no-ledger-mutation-after-failure; no partial verification output) —
  included in the passing full-suite run above.

### Last Remote CI Evidence

GitHub Actions run `28733743705` passed on Python 3.10, 3.11, and 3.12 at
`88c9cfb` (the CR-113 docs commit; `f8bf33c` is its checkpoint note).

## Tag Reconciliation

**Finding:** the 2026-07-02 checkpoint document recommends the tag
`v0.1.0-reviewer-checkpoint-2026-07-02`, but `git tag` (verified
2026-07-07) shows the tag was never created. The newest tags remain the
2026-06-25 baselines and `v0.1.0`. A reviewer following that document
cannot find its promised anchor.

**Resolution recorded by this checkpoint:** the anchor commit for the
2026-07-02 checkpoint is `355c521`; this document is the durable record of
that fact, so the missing tag no longer leaves the anchor undiscoverable.

**Recommended tag commands (NOT run as part of this docs-only slice; no
tag exists until an operator runs and pushes these deliberately):**

```powershell
# Retroactive anchor for the 2026-07-02 checkpoint document
git tag -a v0.1.0-reviewer-checkpoint-2026-07-02 355c521 -m "Retroactive reviewer checkpoint anchor; recommended by reviewer-release-checkpoint-2026-07-02.md but not created at the time. Created <date>."

# Anchor for this checkpoint - run only AFTER the commit that adds this
# document, pointing at that commit so the tag includes its own evidence
git tag -a v0.1.0-reviewer-checkpoint-2026-07-07 <commit-adding-this-doc> -m "Reviewer checkpoint 2026-07-07: CR-100..CR-113 consolidated; suite 803 passed / 2 skipped at f8bf33c."

# Publish (separate deliberate step)
git push origin v0.1.0-reviewer-checkpoint-2026-07-02 v0.1.0-reviewer-checkpoint-2026-07-07
```

Until those commands are run, the accurate claim is: **no reviewer
checkpoint tags exist**; the anchors are the commit hashes recorded here.

## Reviewer Guide

### What is safe to trust?

- The offline regression suite (`python -m pytest -q`) — 803 tests, no
  network, no model.
- The persisted privacy invariant (`tc audit --privacy-invariants`) over
  the append-only ledger.
- Fail-closed identity registry handling: corrupt or unreadable registry
  state yields bounded `registry_load_failed` categories, exit 1, no
  traceback, no secret material, and no ledger mutation.
- Deterministic fixture reports: byte-identical exports that never ingest
  recorded or probe data.

### What is explicitly NOT claimed?

- A valid signature proves provenance and tamper evidence only — never
  approval, safety, or correctness.
- A passing authority manifest grants nothing; validation is
  metadata-only.
- Strategy delta reports rank nothing and recommend no "best" strategy;
  quality gates qualify cost interpretations but never rewrite them.
- The telemetry design brief (CR-113) describes future intent only; no
  probe code, CLI surface, schema, or fixture exists for that lane.
- `tc task show` does not verify signatures; it prints an explicit warning
  and directs users to `tc audit --verify-signatures`.

## What Should Be Reviewed Next?

In order:

1. **Tag creation and push** using the commands above (operator-run,
   deliberate, not part of this slice).
2. **`tc task show --verify-signatures` opt-in** — the standing backlog
   candidate: decouple signature checking from CLI-abort mechanics,
   reusing the CR-097 fail-closed categories.
3. **Telemetry schema-and-fixture sub-slice** — land only the record
   schema, strict-mapping validation, `synthetic_fixture`-tier examples,
   and privacy-rejection tests from the CR-113 brief, with no probe code.
4. **Telemetry probe implementation** — only after the above, exactly
   within the CR-113 boundaries.

## Related Docs

- [reviewer-release-checkpoint-2026-07-02.md](reviewer-release-checkpoint-2026-07-02.md)
- [reviewer-readiness.md](reviewer-readiness.md)
- [reviewer-smoke-runbook.md](reviewer-smoke-runbook.md)
- [reviewer-entrypoints.md](reviewer-entrypoints.md)
- [local-backend-telemetry.md](local-backend-telemetry.md)
- [runtime-strategy-evidence.md](runtime-strategy-evidence.md)
- [route-worker-ledger-inspection.md](route-worker-ledger-inspection.md)
