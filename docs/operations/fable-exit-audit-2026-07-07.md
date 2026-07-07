# Fable Exit Audit — 2026-07-07

## Purpose

This is a point-in-time control-plane review of TriageCore, written as a
handoff artifact for whichever reviewer or model continues this work after
the current session lineage ends. It identifies the strongest existing
evidence, the weakest reviewer-facing gap, and the highest-value
control-preserving next slices.

It is an evidence record of one repository state on one date. It is not a
release certification, and it does not prove production readiness, safety,
legal compliance, or correctness of model outputs.

## Audit Baseline

- **Branch:** `main`
- **HEAD Commit:** `f8bf33c` (Add CR-113 checkpoint note)
- **Working Tree:** clean (`git status --short` empty)
- **Full Regression:** `python -m pytest -q` → **803 passed, 2 skipped in 102.62s**, run locally on 2026-07-07
- **Last Remote CI Evidence:** GitHub Actions run `28733743705` passed on Python 3.10/3.11/3.12 at `88c9cfb` (per CR-113 checkpoint note)

## 1. Current Strongest Evidence

Ranked, strongest first:

1. **The offline regression suite.** 803 passing tests at HEAD on a clean
   tree, runnable by anyone with `python -m pytest -q`, no network, no
   model. This is the single most durable control: it does not depend on
   any model's memory of the project.
2. **Fail-closed identity registry handling with adversarial regression
   tests** (CR-097, `tests/test_cr_097_identity_registry_load.py`). The
   tests cover malformed, truncated, wrong-shape, and unreadable
   registries, secret-leak regression, no-ledger-mutation-after-failure,
   and no-partial-verification-output. This is reviewer evidence of
   fail-closed behavior, not just a claim of it.
3. **The persisted privacy invariant** (CR-021,
   `tc audit --privacy-invariants`): a runnable check that the append-only
   ledger contains no forbidden raw-content keys, independent of any doc
   claim.
4. **The deterministic runtime strategy evidence lane** (CR-104 → CR-112):
   pure arithmetic over declared records, byte-identical exports, no
   default write locations, fail-closed reason-coded IO, recorded records
   never mixed into fixture reports — followed by **CR-113**, which wrote
   the design brief for the lane's first non-deterministic slice *before*
   any probe code exists. The pattern "define the boundary in a docs-only
   CR, then implement against it" is itself strong control evidence.
5. **The reviewer documentation discipline**: per-CR notes with explicit
   Scope / Non-Goals / Validation sections, a reviewer entrypoints index, a
   smoke runbook with a `python -m triage_core.tc_cli` fallback for the
   blocked `tc.exe` shim, and dated frozen checkpoints
   (`reviewer-release-checkpoint-2026-07-02.md`). Conservative claim
   language ("signatures prove provenance only, never approval") is applied
   consistently across docs, CLI output, and tests.

## 2. Current Weakest Reviewer-Facing Gap

**The newest fifteen commits (CR-100 → CR-113: the route-worker ledger lane
and the entire runtime strategy lane) have no consolidated dated checkpoint,
and the last checkpoint's anchor is broken.**

Specifically:

- The most recent frozen checkpoint is
  `reviewer-release-checkpoint-2026-07-02.md`, taken at `355c521` with a
  suite count of 715/2. HEAD is now `f8bf33c` with 803/2.
- That checkpoint recommends the tag
  `v0.1.0-reviewer-checkpoint-2026-07-02`. **The tag was never created.**
  `git tag` shows nothing newer than the 2026-06-25 baselines and
  `v0.1.0`/`v0.1.0-alpha`. A reviewer arriving cold and following the
  checkpoint doc cannot find its promised anchor.
- Per-CR notes for CR-100 → CR-113 exist individually, but nothing binds
  the current HEAD, suite counts, and CI run IDs into one dated record the
  way the 2026-07-02 checkpoint did for PR #82.

This is exactly the gap the backlog itself already names ("Reviewer
checkpoint or release-hygiene slice"). It is a docs-plus-tag gap, not a code
gap — which is why it is both the weakest point and the cheapest to fix.

Secondary gaps, in order:

- `tc task show` prints an explicit "signatures not checked" warning, but
  the safe opt-in `--verify-signatures` flag remains a backlog candidate;
  the evidence timeline and provenance verification are still two separate
  commands a reviewer must know to combine.
- Local-state findings live only in session memory and external notes, not
  in the repo: the ~100 pending `tc review list` items are deliberate
  early-June experiment residue, and the local Windows Application Control
  block on `tc.exe` is documented only as the runbook fallback note. A cold
  reviewer could misread the pending queue as abandoned approvals.

## 3. Top 5 Next Slices

| # | Slice | Risk class | Summary |
|---|---|---|---|
| 1 | **Reviewer release checkpoint 2026-07-07 + tag reconciliation** | docs-only (tag creation itself is runtime-safe repo metadata) | Freeze CR-100 → CR-113: HEAD `f8bf33c`, 803/2 suite count, CI run ID, changelog cut. Resolve the missing `v0.1.0-reviewer-checkpoint-2026-07-02` tag explicitly — either create it retroactively on `355c521` with an annotation, or amend the doc to state no tag was cut. Then cut the new checkpoint tag. |
| 2 | **Review-queue residue disposition note** | docs-only | One runbook paragraph stating that the ~100 pending review items in local `.triagecore` state are deliberately unreviewed early-June experiment residue, so `tc review list` output is not misread as abandoned human-approval work. |
| 3 | **`tc task show --verify-signatures` opt-in** | runtime-safe (read-only code, plus test-only coverage) | The backlog's named candidate: decouple signature checking from CLI-abort mechanics so verification can run on a task timeline, reusing the CR-097 `registry_load_failed` categories and failing closed on a corrupt registry. No new authority; joins two existing read-only surfaces. |
| 4 | **Telemetry schema-and-fixture sub-slice (CR-114a)** | test-only | Land only the record schema, strict-mapping validation, `synthetic_fixture`-tier examples, and privacy-rejection tests from the CR-113 brief — no probe code, no HTTP, no CLI probe command. This banks the deterministic half of the telemetry design while the non-deterministic half stays gated. |
| 5 | **Telemetry probe implementation (CR-114b)** | runtime-risky (relative to this repo's baseline: first non-deterministic contact point) | The opt-in, explicit-endpoint, metadata-only probe bounded by the CR-113 brief. Reachable failure categories tested without a live backend; default posture `probe_disabled`. |

## 4. Which Slice First

**Slice 1 — the 2026-07-07 reviewer checkpoint and tag reconciliation.**

Rationale: it converts the current verified-green state into durable,
anchored evidence before anything else changes; it repairs the one broken
promise a cold reviewer would actually hit (the missing tag); it is
docs-only plus a tag; and the repo's own backlog already recommends it over
adding more telemetry features. In an exit window, banking evidence beats
adding capability.

## 5. Which Slices Should Not Be Done Yet

- **Slice 5 (telemetry probe)** — not until Slices 1 and 4 land. It is the
  lane's first non-deterministic boundary; cross it from a freshly
  checkpointed state, with the deterministic schema half already merged and
  reviewed.
- **Issue #73 runtime key rotation** — cryptographic lifecycle behavior;
  runtime-risky; keep as its own carefully planned CR, not an exit-window
  slice.
- **Signed-event expansion** to `taskpacket_created` /
  `project_steward_decision` — expands cryptographic surface area for no
  reviewer-facing gain right now.
- **Authority-manifest binding** to the identity registry, admission, or
  route enforcement — this is the step where a passing manifest starts to
  mean something at runtime; it must not happen as a side effect of other
  work, only as its own gated CR sequence.
- **Live benchmark capture, dashboard/TUI expansion, or any new execution
  surface** — all expand autonomy or runtime scope; none are blocking a
  reviewer today.

## 6. Controls That Must Remain Invariant

Any future slice, regardless of author or model, must preserve:

1. **Fail-closed registry handling** — corrupt/unreadable identity state
   yields bounded `registry_load_failed` categories, exit 1, no traceback,
   no secret material, no ledger mutation, no partial verification output.
2. **The persisted privacy invariant** — no prompts, completions,
   embeddings, credentials, or private paths in any persisted evidence
   record; `tc audit --privacy-invariants` must keep passing.
3. **Read-only by default; explicit mutation only** — no default write
   locations, fail-closed on existing files, backups for in-place writes.
4. **Signatures prove provenance and tamper evidence only** — never
   approval, safety, correctness, or execution authority. The evaluator
   never becomes approval authority. Human review gates stay outside every
   automated loop.
5. **Local-only routing fails closed** before the bounded external-safe
   Qwen path is considered; TriageDesk stays a read-only console with zero
   direct LLM calls, file writes, or ledger mutations.
6. **Determinism boundaries** — fixture reports stay byte-identical and
   never ingest recorded or probe data; recorded/probe tiers are always
   labeled (`evidence_tier`) and validated through strict mapping with
   unknown fields rejected.
7. **Closed vocabularies for failure and interpretation** — reason codes,
   never raw error text; quality gates qualify cost interpretations, never
   rewrite or rank them.
8. **A passing authority manifest grants nothing** — validation is
   metadata-only until a dedicated CR deliberately binds it, and denied
   actions always take precedence.

## 7. Suggested Validation Commands

From the repository root (substitute `python -m triage_core.tc_cli` for
`tc` where the console-script shim is blocked by local application-control
policy):

```powershell
git status --short                # expect empty before trusting results
git diff --check                  # minimum check for docs-only slices
python -m pytest -q               # expect 803 passed, 2 skipped at f8bf33c
tc doctor                         # expect Overall: OK
tc identity list                  # public signer metadata only
tc audit --privacy-invariants     # persisted-ledger privacy invariant
tc audit --verify-signatures --kind route_decision
triagecore benchmark --list-only  # fixture discovery, no backend contact
```

Focused fail-closed regression:

```powershell
python -m pytest tests/test_cr_097_identity_registry_load.py tests/test_privacy_invariants.py -q
```

Anchor check for this audit's baseline:

```powershell
git log -1 --format="%H %ci"      # expect f8bf33c... 2026-07-05
git tag                           # note: no tag newer than v0.1.0 era yet
```

## 8. Final Handoff Note for a Future Reviewer

You are inheriting a repository whose value is its evidence discipline, not
its feature surface. The safety spine (privacy scanning, fail-closed
routing, append-only ledger, fail-closed identity loading, signed
provenance without approval semantics) is implemented, tested, and
documented in conservative language. The habit that produced it — small
CRs with explicit Non-Goals, docs-only boundary briefs written *before*
implementation, dated frozen checkpoints, and a backlog that names what
should *not* be done yet — is the thing to preserve.

Trust the test suite and the runnable checks before any document, including
this one. Documents here are point-in-time records and say so; where a doc
and the repo disagree (as with the never-created 2026-07-02 checkpoint
tag), the repo is the truth and the disagreement is itself a finding worth
recording.

The immediate move is boring on purpose: cut the CR-100 → CR-113 reviewer
checkpoint, reconcile the tags, and only then let the telemetry lane cross
its first non-deterministic boundary — schema and fixtures first, probe
second, exactly as the CR-113 brief prescribes. Do not let any slice, ever,
turn a signature, a manifest, or an evaluator verdict into permission.
