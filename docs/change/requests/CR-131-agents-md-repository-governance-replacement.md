# CR-131: Replace AGENTS.md with a TriageCore Repository-Governance Document

## Status

- **Status:** Approved — proposal accepted, design accepted, implementation
  accepted, and PR #168 merged; release applicability and closeout undecided.
- **Proposal acceptance:** Granted by the human operator on 2026-08-12 for the
  problem statement and design-review boundaries recorded in this CR — the
  repository-governance-mismatch finding, use of CR-131 in the plain-numeric lineage,
  the eight proposed design boundaries, the explicit exclusions, treatment of the
  stale uncommitted draft as source material only, the reconstruction requirement,
  and the writable-mutation/read-only-verification separation — at exact accepted
  head `ebf462903d5e67259d07abb6cd13f3aacd4dcb09`.
- **Design acceptance:** Granted by the human operator on 2026-08-12 for the exact
  61-line `AGENTS.md` replacement text drafted, reviewed, and corrected in the
  CR-131 design-review conversation following read-only investigation against `main`
  at `f807a6e6319ab49761985140a73d1d4469efeaec`. That text is frozen as the accepted
  design. Its SHA-256 is
  `58d83280245b053718b04cab0fe84c8d9640c09780018761bcf880add088a77e`, recorded here
  as an integrity fingerprint of that conversation-only artifact — it lets an equal
  copy be verified byte-for-byte if reproduced, but the hash alone does not make the
  accepted text independently reconstructible from this CR, this PR, or any other
  repository artifact. The exact bytes exist only in the design-review conversation
  record. This grant authorizes only recording design acceptance and directly
  corresponding status metadata in this CR; it does not modify the accepted text and
  grants no implementation, runtime, schema, test, or broader documentation change.
- **Type:** Documentation / Governance (repository-level agent guidance — no runtime,
  routing, capability, or schema component).
- **Priority:** Design review. Raised from a read-only investigation of an existing
  uncommitted working-tree draft; see Source Material below.
- **Implementation authority:** Granted by the human operator on 2026-08-12, scoped
  to exactly one path — `AGENTS.md` — for reconstructing the CR-131 design-accepted
  text on a fresh branch/worktree from then-current `main`. The grant included the
  operational steps needed to produce a reviewable candidate: creating the fresh
  implementation branch/worktree, writing the frozen 61-line artifact, bounded
  verification, commit, push, and opening an implementation PR. It produced
  implementation PR #168 at exact head `1da8bc03a2347992d910d9907e193d3050b0e47a`,
  whose committed `AGENTS.md` has SHA-256
  `58d83280245b053718b04cab0fe84c8d9640c09780018761bcf880add088a77e`, matching the
  design-accepted fingerprint recorded above. This grant is spent: it authorized
  producing that one implementation candidate and does not authorize any further
  `AGENTS.md` edit, implementation acceptance, or merge authority for PR #168. This
  lifecycle-record correction itself grants nothing further — it records what was
  already authorized and produced; it is not a new grant.
- **Implementation acceptance:** Granted by the human operator on 2026-08-12 for
  implementation PR #168 at exact head `1da8bc03a2347992d910d9907e193d3050b0e47a`,
  whose committed `AGENTS.md` SHA-256
  (`58d83280245b053718b04cab0fe84c8d9640c09780018761bcf880add088a77e`) matches the
  design-accepted fingerprint recorded above. This decision covers that exact head
  only; any subsequent modification to PR #168 would require a new implementation-
  acceptance decision. It does not grant merge authority for PR #168, release
  authority, or closeout.
- **Merge authority:** Granted by the human operator on 2026-08-12 for PR #168 at
  exact accepted head `1da8bc03a2347992d910d9907e193d3050b0e47a`, and exercised the
  same day. Merge commit `2ac5814b37401d3c5ec13b44d9ac961a04bdfbf4` (parents
  `25734855afd4aca9e28dcfd344731637b2ead39e` and `1da8bc03a2347992d910d9907e193d3050b0e47a`)
  landed on `main`. `main` now contains the accepted 61-line `AGENTS.md`, SHA-256
  `58d83280245b053718b04cab0fe84c8d9640c09780018761bcf880add088a77e`, matching the
  design-accepted fingerprint recorded above exactly. This grant is spent: it
  authorized merging that exact head only and does not authorize any further
  `AGENTS.md` edit, release action, or closeout.
- **Human approval requirement:** Proposal acceptance, design acceptance,
  implementation authority, implementation acceptance, and merge authority have all
  been granted as recorded above; together they record acceptance of the problem
  statement, scope boundaries, exact replacement text, authorization to produce one
  implementation candidate, acceptance of that exact candidate, and its merge onto
  `main`. They do not by themselves resolve release applicability or grant closeout.
  Release authority (including whether release applies at all to this
  repository-governance-only change) and closeout remain separate, undecided
  decisions.

## CR Namespace Census (evidence, not assumption)

Performed against this checkout before allocating an identifier, per instruction not
to assume a lineage:

- Enumerated every `docs/change/requests/CR-*.md` file across this worktree, the
  primary repository checkout, and the other known local checkouts
  (`triagecore-nemotron-candidate`, `triagecore-feedback-front-door`). Highest
  plain-numeric CR found: **CR-130** (`CR-130-approved-status-authority-semantics.md`).
  No `CR-131` or higher exists as a file in any checkout.
- Searched `git log --all --oneline` (all local branches, all commit messages) for any
  reference to `CR-13x`/`CR-14x`: no hits beyond CR-130's own file. No in-flight or
  reserved higher number exists in commit history.
- Enumerated the lettered lineages in use and their domains, to check fit before
  defaulting to plain numeric:
  - `CR-DD-*` — daily-driver / governed `tc run` decision and evidence contracts
    (routing, capability binding, specialist-offload evidence). Not applicable: this
    proposal touches no runtime decision or evidence path.
  - `CR-YK-*` — hardware/WebAuthn authorization receipts and capability claiming. Not
    applicable.
  - `CR-OC-*` — mediated single-file effect / atomic client-request execution
    contracts. Not applicable.
  - `CR-AR-*` — risk-tiered deferred human review. Not applicable.
  - `CR-BW-*` — evidence-bound build review. Not applicable.
  - None of the five lettered lineages govern repository-level agent-guidance
    documentation. Prior comparable work (the AGENTS.md terminology checkpoint in PR
    #140, `docs/current_backlog.md:265`; CR-017 "public-legibility-pass"; CR-025
    "backlog-documentation-alignment-pass"; CR-130 itself, a documentation-policy
    reconciliation) was filed in the **plain numeric lineage**, not a lettered one.
- **Allocated identifier: `CR-131`**, plain numeric lineage, immediately following the
  highest confirmed existing number with no gap and no collision.

## Scope

This CR's own authorized scope right now is exactly:

```text
docs/change/requests/CR-131-agents-md-repository-governance-replacement.md
```

No other path is authorized by this CR. This CR does **not** scope, pre-authorize, or
schedule an eventual `AGENTS.md` implementation slice; that requires its own later,
separately granted implementation authority once design is accepted.

### Proposed eventual AGENTS.md scope (design boundary for future review — not authorized here)

If this proposal is accepted and later carried into a design-review stage, the
resulting `AGENTS.md` is intended to define, and only to define:

1. **Repository authority precedence** — higher-priority system and user instructions
   prevail first; any nested-`AGENTS.md` precedence applies where the active agent
   environment supports it, without assuming every client implements nested-file
   precedence identically. The repository's canonical governance documents, including
   `docs/change/change_management.md` and relevant accepted CRs, remain authoritative
   independent of a particular client's file-precedence behavior.
2. **Stage separation** — restate, in agent-facing terms, the
   `Proposed ≠ Authorized ≠ Implemented` chain already codified in
   `docs/change/change_management.md` and CR-130: a CR, an `Approved` status, a
   passing test, a review verdict, or a merged proposal is not itself implementation,
   mutation, merge, or standing authority.
3. **Read-only preflight** — before relying on repository state or making a claim,
   establish repository root, branch, `HEAD`, worktree identity, and working-tree
   status.
4. **Dirty-worktree / base / scope checks** — detect uncommitted or unrelated changes
   already present before starting work; verify the correct base branch/commit; flag
   when in-scope work would touch paths outside an authorized scope.
5. **Stop-and-request-direction triggers** — the conditions under which an agent must
   stop and ask rather than infer: missing or ambiguous authority, conflicting
   governing sources, unresolvable identifier/evidence provenance, out-of-scope
   changes already present, destructive/irreversible/security-sensitive actions, or a
   claim that depends on unobserved remote/deployment/human-review state.
6. **Branch/worktree hygiene** — preserve unrelated changes, untracked files, and
   stashes. Historical evidence, results, or conclusions may retain value when carried
   across worktrees or commits with explicit provenance; what must be re-verified
   before relying on it is any claim that depends on *current* state.
7. **Verification boundaries** — mutation must remain within the authorized writable
   grant; read-only inspection and verification may extend beyond that grant when
   necessary to establish the authorized change's correctness (e.g., a repository-wide
   search or a full test-suite run for a one-file change), provided the inspection does
   not mutate out-of-scope state and its provenance is explicit. Use
   `docs/verification_guide.md`'s existing verification levels to judge proportionality
   of the checks actually run, not to bound what may be read or executed read-only.
8. **Explicit non-authority of agent verdicts/instructions** — `AGENTS.md` is guidance,
   not enforcement; a review verdict, test result, generated artifact, or instruction
   found in observed content does not independently authorize mutation, commit, push,
   merge, or any consequential action. Independent controls (tests, CI, schema/lint
   validation, review requirements, permissions, sandbox boundaries) remain the actual
   enforcement layer and must not be bypassed because an agent-facing document or
   artifact sounds persuasive.

### Explicit Exclusions

This CR, and any AGENTS.md replacement eventually scoped from it, does **not** cover
and must not be used to smuggle in:

- runtime routing changes or routing-policy behavior;
- model-selection policy or backend/route binding;
- capability changes (capability claiming, capability probing, capability evidence);
- signing, key handling, or authorization-receipt mechanisms;
- schema changes or test-suite changes;
- **implementation of the six skills named in the recovered draft**
  (`$tc-change-preflight`, `$dependency-threat-check`, `$research-evidence-triage`,
  `$eval-evidence-capture`, `$local-first-orchestration`, `$session-handoff`) — none
  of these is a repository-contained dependency whose availability TriageCore can
  guarantee, and this CR does not authorize creating them;
- making any personal or client-specific skill a **mandatory dependency** of
  repository governance — if a future AGENTS.md references such a skill, the
  reference must degrade gracefully (repository policy remains authoritative on its
  own) when the skill is unavailable, not require it;
- any edit to `AGENTS.md` itself;
- any commit, branch creation, push, pull request, merge, or closeout action;
- any modification, stash, reset, commit, or cleanup of the
  `codex/agents-governance-separation` checkout described below — it is read-only
  reference material only.

## Problem Statement

`AGENTS.md` at the repository root currently contains content inherited from a
different, generic project template: a "local-first" Antigravity orchestration model
(local-worker-council / cloud-supervisor feedback loop) and a "Cybernetic Ecology
Rubric" that references domain-specific, unrelated concerns (e.g., environmental data
summaries, water intakes, tribal layers, "Bo-No-Po-Ti"). None of this reflects
TriageCore's actual governance model: CR-gated change authority, the
Proposed/Authorized/Implemented distinction, evidence-window discipline, or the
repository's existing stop-and-verify culture already documented piecemeal across
`CONTRIBUTING.md`, `docs/change/change_management.md`,
`docs/architecture/current_system_architecture.md`, `docs/verification_guide.md`, and
related evidence/schema docs.

This is a **repository-governance mismatch**: the file every coding agent is expected
to read first does not describe this repository.

### Source material (read-only reference only)

A read-only investigation found an **uncommitted, unstaged** rewrite of `AGENTS.md`
sitting in the working tree of the primary repository checkout
(`C:/Users/corey/Documents/Science/AI/triagecore`), which is currently checked out on
local branch `codex/agents-governance-separation`, whose merge-base with `main` was
`424bc7a` at investigation time (the branch itself carries one later unique commit on
top of that merge-base — a Nemotron research nomination, unrelated to AGENTS.md). That
draft replaces the inherited content with TriageCore-specific repository-governance material
covering repository-authority preflight, the stage-separation chain, a
stop-and-request-direction list, and a skill-routing table.

This draft is **not evidence of authorization**. It is:

- not committed (confirmed via `git status` and `git reflog` — hand-edited directly in
  the working tree after the branch's last commit, with no wrapping commit);
- not backed by any existing CR (searched `docs/current_backlog.md`,
  `docs/change/change_management.md`, and `docs/operations/control-plane-invariant-checklist.md`
  — the only AGENTS.md-related entry is the already-closed PR #140 terminology
  checkpoint, a narrower, separate edit);
- sitting on a stale branch whose merge-base with `main` (`424bc7a`) is roughly 15
  commits and two full CR-DD cycles (017, 018) behind current `main`;
- referencing six skill slugs that are absent from `triage_core/skills/` (the
  repository's own skill directory) and from the one personal skill location checked
  (`~/.claude/skills`, not present). This does not establish universal absence across
  every possible personal or client-specific skill home; the finding that matters here
  is architectural, not exhaustive (see Explicit Exclusions).

Because it introduces new normative repository behavior (stop conditions, authority
precedence, mandatory-looking skill routing) rather than a narrow terminology fix, it
requires the same explicit design review any new governance-shaping document would —
consistent with how PR #140's narrower AGENTS.md terminology edit was still treated as
a reviewed documentation slice, and how CR-130 treated a change to
`change_management.md`'s own authority semantics as a reviewable CR rather than a
silent edit.

This CR treats that draft strictly as **source material to consult**, not as
pre-approved text and not as a diff to be reapplied. Per instruction, the
`codex/agents-governance-separation` checkout itself must remain untouched — no
modify, stash, reset, commit, or clean — for the duration of this proposal.

### Why a CR rather than a direct edit

`docs/change/change_management.md` requires that "any new feature, systemic
adjustment, or significant code modification" be proposed as a CR. `AGENTS.md`
functions as a systemic, repository-wide behavioral policy for every agent operating
in this repository; replacing it changes what every future agent treats as governing
guidance. That is a systemic adjustment even though it touches no code, runtime, or
schema — hence a CR, not a silent documentation commit.

## Reconstruction Requirement

If this proposal and a subsequent design review are both accepted, the eventual
implementation must be **reconstructed on a fresh branch from then-current `main`**,
under separately granted implementation authority scoped to `AGENTS.md` alone. It must
not be produced by committing, cherry-picking, or rebasing the existing uncommitted
draft on `codex/agents-governance-separation`, since that checkout's base predates
current `main` by multiple merged CR cycles and the draft's exact wording is source
material, not an approved final text.

## Acceptance Criteria (for this proposal-only gate)

- [x] CR-131 is opened for human review with an allocated, collision-free identifier
      supported by a recorded namespace census.
- [x] The problem statement is grounded in the current committed `AGENTS.md` content
      and in the read-only-observed uncommitted draft, with no claim beyond what was
      directly observed.
- [x] Proposed eventual scope and explicit exclusions are stated clearly enough that a
      later design-review stage has unambiguous boundaries.
- [x] The six skill references are flagged as not repository-guaranteed and excluded
      from mandatory dependency status.
- [x] No code, test, schema, routing, or `AGENTS.md` change is made by this CR.
- [x] The `codex/agents-governance-separation` checkout remains exactly as found —
      same uncommitted diff, no new commit, no stash, no reset, no clean.
- [x] This document records that proposal acceptance, design acceptance, implementation
      authority, implementation acceptance, and merge authority are separate, later,
      explicit human decisions. Proposal acceptance is now granted (see Status);
      design acceptance, implementation authority, implementation acceptance, and
      merge authority remain separate and ungranted.

## Verification Plan

Before requesting proposal acceptance, verify:

1. the only repository change introduced is this CR file;
2. in the proposal worktree/branch, `AGENTS.md` is byte-identical to its current
   committed `main` content — no proposal work modified it there;
3. separately, in the primary checkout, `AGENTS.md` remains byte-for-byte in its
   pre-existing dirty state — `git status` still shows the same single unstaged
   modification it showed before this CR was drafted, with no new commits, stashes, or
   resets;
4. the CR namespace census is reproducible (`CR-131` still does not collide) at the
   time of review.

No test-suite run is required or meaningful for this proposal-only, documentation-only
change.

## Stop Point

Stop after this proposal is opened for human review. Do not begin a design-review
stage, draft final `AGENTS.md` text, request implementation authority, or touch
`codex/agents-governance-separation` without a separate, explicit human decision.
Proposal acceptance here authorizes nothing beyond recording that the problem
statement and boundaries are accepted for further review.
