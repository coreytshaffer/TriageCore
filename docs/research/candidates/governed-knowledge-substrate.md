# Governed Knowledge Substrate — Research Candidate

Status: **nominated / not authorized for implementation**
Recorded: 2026-08-07

## What this document is, and is not

**This is a research nomination. It is not evidence, not approved architecture, not a
backlog item, and not an implementation authorization.**

It records a hypothesis and the conditions under which testing that hypothesis could later
be authorized. It exists so the idea has a durable home, which lowers the pressure to pursue
it while other work is open.

Specifically, this document:

- grants no implementation, integration, schema, execution-expansion, configuration, branch,
  merge, or standing authority;
- authorizes no adapter, fork, prototype, spike, or "just in case" abstraction in
  TriageCore;
- is **not** part of the daily-use evidence window, is not a trial or a day, and is not the
  output of any `tc run` invocation;
- makes no claim that TriageCore can govern an external knowledge substrate, and no claim
  that the candidate system is safe, contained, or suitable for this purpose;
- registers nothing. It is deliberately absent from
  [`futures_register.md`](../../futures/futures_register.md) and from the **Candidate Future
  Work** section of [`current_backlog.md`](../../current_backlog.md). Whether it belongs in
  one, the other, or both — and what the canonical relationship between those two registries
  is — is a separate decision deferred until the open evidence window closes.

The candidate is deliberately **un-numbered**. TriageCore assigns no identifier to a
candidate until promotion, at which point the repository's own `CR-` promotion process
applies. No new identifier namespace is opened for this item.

## Candidate identity

- **Candidate**: GBrain
- **Repository**: `https://github.com/garrytan/gbrain`
- **Evaluated version/commit**: **Not pinned.** No commit has been evaluated. A specific
  commit must be recorded before any experiment is authorized. Current `HEAD` must not be
  substituted for an evaluated artifact merely because it is obtainable.
- **Interface of interest**: an agent-accessible knowledge substrate reachable over MCP.

Nothing in this document reflects source inspection of the candidate repository. Every
statement about the candidate's behavior below is a hypothesis to be tested, not an
observation.

## Scope classification

**Venue candidate**: an adjacent application proposed as an external test instrument for
existing TriageCore governance semantics. It is neither part of the governance kernel nor an
approved TriageCore knowledge subsystem.

Under the **Backlog Scope Taxonomy** in [`current_backlog.md`](../../current_backlog.md),
this is an adjacent application. It strengthens no governance invariant on its own. Its
research value is that it is an external system whose demands can *test* invariants the
governance kernel already claims.

The distinction that must not be misread later: GBrain would be a venue in which
TriageCore's claims are tested, not a TriageCore knowledge feature. If a later experiment
happens to show that TriageCore plus an external substrate also instantiates a useful
knowledge capability, that is a downstream result — not the reason to run the experiment,
and not a commitment made here.

## Core hypothesis

> TriageCore can mediate an external agent-accessible knowledge substrate while preserving
> the separation between retrieved information, epistemic state, and executable authority.

Stated as the property under test:

> Retrieved knowledge may influence reasoning, but must not confer, expand, or consume
> executable authority.

## Candidate boundary

```text
agent → TriageCore mediated executor → GBrain MCP
```

The desirable result is boring, and that is the point:

```text
GBrain remains mostly unaware of TriageCore.
TriageCore remains mostly unaware of GBrain.
```

If that holds, it demonstrates a genuine architectural boundary. If it does not, the failure
is the finding.

## Operations under test

Four operations only. The right-hand column states the *expected* treatment under existing
TriageCore semantics — it is the prediction being tested, not a description of current
behavior.

| Operation                  | Expected TriageCore treatment                |
| -------------------------- | -------------------------------------------- |
| Search / read              | bounded automatic capability                 |
| Stage new knowledge        | bounded write, human review afterward        |
| Modify canonical knowledge | stronger authorization                       |
| Delete canonical knowledge | prior human authorization                    |

## Adversarial cases

Five cases, all confined to repository-owned synthetic fixtures against a local candidate
instance. No third-party systems, data, or targets.

1. Retrieved content instructs the agent to perform an unauthorized action.
2. Retrieved content requests broader knowledge access than the agent holds.
3. Poisoned content induces a canonical write.
4. The agent attempts an operation outside its capability.
5. A valid capability is replayed or consumed twice.

Case 5 is the one with existing TriageCore lineage: CR-OC-001A classifies replay without
preventing it, and CR-OC-001B provides atomic client-request reservation as an unconsumed
library surface. Any result here must respect that distinction between an implemented
contract and an enforced one.

## Primary research questions

1. Can generic TriageCore capability semantics govern all four operations without
   modification to core semantics?
2. Can untrusted retrieved content remain causally separated from executable authority?
3. Can write provenance be preserved without TriageCore understanding GBrain internals?
4. Does the experiment expose any genuinely missing TriageCore primitive?

Question 1 is the scientifically useful framing. The question is deliberately **not** "how do
we integrate GBrain?"

## The existing-vocabulary test

Before any new concept is introduced, the experiment must first attempt expression in
TriageCore's existing vocabulary:

```text
principal
intent
resource
operation
capability
claim
mediated executor
evidence
```

For example:

```text
resource:
  mcp://gbrain/brain/<brain-id>/pages/*
operation:
  put_page
constraints:
  canonical   = false
  destination = staging
  max_items   = 20
```

The following must **not** be introduced into TriageCore on the strength of this candidate:

```text
KnowledgeClaim
TrustLevel
EpistemicAuthority
MemoryCapability
KnowledgeSource
```

This is a falsifiable criterion, and it is the strictest part of this document. A domain
having specialized terminology is not evidence that TriageCore needs a matching primitive. A
new primitive is warranted only when the experiment produces a **concrete failure that
existing semantics cannot express** — a demonstrated semantic insufficiency, recorded as
such.

Governing this candidate with generic primitives would be a materially stronger result than
adding bespoke knowledge-base machinery.

> Make the external system reveal the missing abstraction, rather than inventing the
> abstraction beforehand.

## Entry criteria

All of the following must hold before any experiment is authorized:

- the open daily-use evidence window is complete;
- its results are recorded;
- current open questions from that window are resolved or explicitly characterized;
- conclusions are frozen;
- an evaluated candidate commit is pinned (see *Candidate identity*);
- the experiment is separately authorized under the repository's normal approval process.

The gate exists for a methodological reason, not a procedural one. Adding
knowledge-specific events, capability types, provenance fields, or executor semantics to
TriageCore while the window is open would make any observed behavior change ambiguous
between the system under test and an architecture evolving underneath it. The window must
remain evidence about **current** TriageCore.

## Non-goals

- build a personal knowledge system;
- fork the candidate repository;
- add GBrain-specific semantics to TriageCore;
- redesign TriageCore around retrieval-augmented generation;
- treat this candidate as the eventual TriageCore knowledge feature.

## Related material

- [`triagecore_research_question.md`](../triagecore_research_question.md) — the research
  framing this candidate would sit under, including the threat model and the claims
  TriageCore can and cannot make.
- [`nvidia-containment-control-analysis-2026-08-07.md`](../nvidia-containment-control-analysis-2026-08-07.md)
  — the two-axis distinction between a mechanism existing in the repository and that
  mechanism constraining the live path. Any result from this candidate must be reported
  along both axes rather than as a single label.
- [`current_backlog.md`](../../current_backlog.md) — Backlog Scope Taxonomy, and the scope
  test: *Does this strengthen the evidence-bound governance kernel, or is it merely an
  interesting adjacent capability?*

## Disposition

Nominated. No work authorized. Return to the open evidence window.
