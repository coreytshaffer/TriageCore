# Agentic Repository Hygiene as an Evidence-Window Task Family — Research Candidate

Status: **nominated / not authorized**
Recorded: 2026-08-12

## What this document is, and is not

**This is a research/practice nomination. It is not evidence, not an approved evidence-window
task category, not a backlog item, and not an implementation authorization.**

It records a hypothesis about a task family — read-only refactor discovery/specification —
and the conditions under which running one as a `tc run` invocation could later be authorized.
It exists so the idea has a durable home rather than being decided ad hoc the next time a
refactor candidate happens to surface.

Specifically, this document:

- grants no CLI change, evidence-schema change, scoring-criterion change, backlog-population
  rule, or standing cadence (e.g. "refactor every Friday");
- authorizes no `tc run` invocation of any kind;
- is not part of the open daily-use evidence window and does not amend its Window Protocol;
- proposes no new CR lineage or number — if this is later promoted, numbering follows the
  repo's own pre-draft CR-allocation check, not this document;
- makes no claim that a refactor-discovery run is safer, more valuable, or more evidence-rich
  than any other task category already eligible under the window's "materially useful task"
  rule — that is the hypothesis under test, not a conclusion.

## Motivation

An external design discussion (summarized, not reproduced verbatim) argued that agentic SDLC
gives routine, narrowly-scoped refactoring a stronger systems-level payoff than it has in a
purely human-written codebase: coding agents reproduce repository patterns — including bad
ones — so competing implementations of the same concept read as "any of these is acceptable"
rather than "the first two are legacy." The argument cites OpenAI's own agent-first
engineering writeup, which treats recurring, mechanically-checked refactoring as a form of
garbage collection against a short, hierarchical instruction layer, and separately cites a
2026 study finding that repository context files can *reduce* task success when they contain
unnecessary requirements — i.e., prefer removing complexity from the repo over explaining it
to the agent.

Both sources describe environments materially different from TriageCore (no daily-use
evidence window, no CR/authority model, no signed capability claims), so their conclusions are
treated here as **hypotheses worth testing against this repository**, not as findings that
already transfer.

## Core distinction carried into TriageCore's own model

The discussion proposed keeping three change classes separate rather than letting
"refactoring" become a semantic loophole:

```
Behavior-changing development        — normal CR / change authority
Behavior-preserving normalization    — refactor lane + equivalence tests
Knowledge-base / agent-legibility    — docs/topology maintenance, no runtime change
maintenance
```

This maps onto TriageCore's existing authority split cleanly: only the first class ever
touches the CR-DD-012B "capability evidence constrains execution, never decision formation"
line or an implementation allowlist. The second and third classes are candidates for
**read-only or docs-only `tc run` tasks**, which is the part actually relevant to the daily-use
evidence window.

## The proposed task family: refactor discovery and specification

Two tiers, both read-only, both scoped as `tc run` candidates. A third tier (implementation)
is named for completeness and explicitly **not** proposed for authorization here.

**Tier 1 — Refactor discovery (read-only).** Inspect a named area for duplicated
implementations, competing patterns, or obsolete paths; produce a bounded report. No
repository mutation. Predeclared success criterion is structural: does the report name real
files/symbols, cite actual evidence of duplication or divergence (or actual evidence that none
exists), and identify affected tests — not whether its recommendation is later accepted.

**Tier 2 — Refactor specification (read-only).** Turn an already-accepted Tier-1 candidate
into an implementation-ready spec: scope, invariants to preserve, affected symbols, required
tests, explicit non-goals. Still no code change. For TriageCore specifically this tier would
need to state the same kind of invariant list a real CR states (e.g. "preserve `Configured` !=
`ObservedAvailable`" is the shape of thing an actual spec would need to name) — this document
does not attempt to write one, since no Tier-1 candidate has been run yet.

**Tier 3 — Refactor implementation (not proposed here).** Once a run mutates code, it is
testing mediated software change, not analysis quality, and would need its own implementation
allowlist, deterministic validators, and human review before merge — the same bar every other
implementation-authority CR in this repo already clears. Not in scope for this document.

## Fit against the existing evidence-window eligibility rule

The daily-use evidence window already requires that a run contribute to a real deliverable,
bounded decision, review, evidence analysis, or planned next action — synthetic tasks invented
merely to exercise `tc run` do not count. The discussion's proposed discipline for this task
family is stricter, not looser:

```
Observed repository friction  →  candidate Tier-1 run
```

not

```
Need another evidence-window observation  →  invent something to refactor
```

Concretely: a real repeated friction event (e.g. this session repeatedly reading the same file
before finding the right section, or a prior session's note that four call sites do the same
thing three different ways) is legitimate provenance for a Tier-1 candidate. "Find something
in the repo we can clean up so today's trial counts" is not, and would need to be rejected on
exactly the same "synthetic task" grounds the window already applies to everything else.

## Existing-vocabulary test

Before any new metric or field is added on the strength of this document, it must first be
checked against vocabulary the repo already has:

- `docs/current_backlog.md`'s Backlog Scope Taxonomy may already cover "candidate future work"
  well enough that a refactor candidate is just another backlog entry, not a new category.
- The evidence-bound review harness (`review_submission_v0` / `review_result_v0`) already has
  a structural-grounding-only, non-approval result contract — a Tier-1 report may fit that
  shape rather than needing a new one.
- The window's own "operator disposition" vocabulary (accepted/revised/rejected) may already
  be adequate for disposing of a Tier-1 report without inventing a parallel taxonomy.

None of this is resolved here. It is listed so a future author drafting an actual Tier-1 task
does not skip the check.

## Candidate future metric — explicitly unauthorized, listed for the record only

The discussion proposed an "agentic friction" measure (implementations-per-concept,
entry-points-per-operation, files inspected before the correct edit location, unrelated files
touched per task, retry rate, instruction burden, mechanically-enforced-vs-merely-documented
invariant ratio) as a possible refactoring trigger. This is recorded here as a **future
research idea only** — no collection mechanism, ledger field, or scoring use is proposed. It
would need its own evidence-fidelity discipline (per the correction-lane sequencing rule
already in force in this project) before it could inform any actual decision.

## Non-goals

- No standing refactor cadence (explicitly rejects "refactor every Friday" as the operating
  model — friction-triggered, not calendar-triggered).
- No new `tc` CLI verb, evidence-record field, or scoring criterion.
- No automatic backlog population from a Tier-1 report.
- No authorization for Tier 3 (implementation) work of any kind.
- No claim that refactor-discovery tasks are better evidence-window material than the tasks
  already run in Days 1-3 — this is a hypothesis about a task family, to be tested by actually
  running one, not asserted here.

## Open questions (for disposition, not resolved by this document)

1. Should a Tier-1 pilot draw its target from *already-observed* friction in this project's
   own session notes (e.g. a documented "searched N places before finding X" moment), rather
   than a fresh cold search — to keep the very first pilot honest about the
   observed-friction-first rule this document itself states?
2. If a Tier-1 pilot is run, does its report get evaluated against the evidence-bound review
   harness's existing result contract, or does it need its own — and who decides that before
   the pilot, not after?
3. ~~Does this belong in `docs/research/candidates/` or a numbered CR lineage?~~ **Resolved
   2026-08-12 (operator decision):** filed as an unnumbered research candidate, matching
   GBrain's precedent. If a future Tier-1 pilot's results warrant promotion, numbering follows
   the repo's normal CR-allocation process at that time — no lineage is reserved by this
   document.

## Disposition

Nominated. No work authorized. No `tc run` invocation proposed or scheduled by this document.
