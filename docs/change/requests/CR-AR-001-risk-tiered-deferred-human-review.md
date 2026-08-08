# CR-AR-001: Risk-Tiered Deferred Human Review

## Status

- **Status:** Proposed.
- **Type:** Architecture / Authorization / Runtime Governance.
- **Priority:** Research backlog. Implementation should follow the current empirical
  evidence window rather than run alongside it, so that a behavior change is not
  ambiguous between the system under test and an architecture evolving underneath it.
- **Implementation authority:** Not authorized. No source code, schema, CLI, ledger, or
  runtime change is authorized by this document.
- **Human approval requirement:** Explicit human review and approval of this Change
  Request is required before any implementation begins, and the narrower Initial
  Implementation Slice below requires its own separate approval even after this CR is
  otherwise accepted.
- **Revision:** Revised 2026-08-07 in response to a read-only adversarial design review
  that identified specification gaps at the boundary with the existing CR-YK-002
  capability-claim lifecycle. This revision adds the State Model's explicit claim-lifecycle
  mapping, the `Revised`-disposition rule, the Terminal-Review Assurance section, and the
  Compensation Contract section, and extends the Terminal Evidence Bundle and Required
  Tests accordingly. `Status` and `Implementation Authority` are unchanged by this
  revision.

This document records a requirements contract only. It grants no execution, integration,
or standing authority.

## Scope

TriageCore's agentic execution control plane.

## Problem Statement

TriageCore currently treats human approval primarily as a control applied before
consequential execution. This provides strong governance but can create unnecessary
interruption when an agent performs a sequence of individually low-risk, bounded actions.

Requiring human approval before each low-risk tool call introduces approval fatigue,
increases workflow latency, and reduces the practical usefulness of governed agents. At
the same time, removing human approval without compensating controls would permit agents
to accumulate effects, exceed intended scope, or transform individually minor actions into
a consequential workflow.

TriageCore therefore requires a risk-tiered authorization mechanism that permits low-risk
agent actions to execute autonomously inside a pre-authorized capability envelope while
deferring human review until the end of the workflow.

Human review is deferred; runtime enforcement is not.

## Objective

Introduce a first-class deferred terminal review authorization mode in which an agent may
perform bounded, observable, and sufficiently reversible actions without contemporaneous
human approval.

- The mediated executor MUST continue to enforce capability scope, resource boundaries,
  budgets, risk ceilings, and denial conditions on every action.
- A workflow MUST stop, stage, or escalate before executing an effect that exceeds its
  authorized risk envelope.

## Design Principle

Human intervention SHOULD occur at the point where consequences require human judgment,
rather than at every tool invocation.

TriageCore MUST distinguish between:

- runtime policy enforcement;
- human authorization;
- terminal human review.

Removing a human approval step MUST NOT remove runtime authorization checks.

## Risk Tiers

### R0 — Observe

Actions that do not mutate state: read files, inspect repository state, retrieve
permitted records, search, calculate, classify, analyze.

Default review mode: audit only.

### R1 — Ephemeral

Actions whose effects are temporary, isolated, or disposable: temporary files, test
execution, simulations, sandbox commands, parsing and transformations that do not modify
authoritative state.

Default review mode: autonomous execution with audit evidence.

### R2 — Reversible

Bounded mutations whose effects are reliably identifiable and reversible: modify files in
an isolated worktree, create unpublished commits or branches, create local artifacts,
modify bounded local metadata, and other mutations with a policy-recognized compensation
contract for the specific effect type (see Compensation Contract). Eligibility for R2 MUST
NOT be established solely by an agent's or generated output's own claim that an action is
reversible.

Default review mode: `deferred_terminal`. The workflow MAY execute before human review.
Human review MUST occur before the workflow is considered accepted.

### R3 — Staged External

Actions that prepare an external or consequential effect while withholding final release:
draft an email without sending it, prepare a pull request without merging it, populate a
form without submitting it, prepare a deployment without releasing it, prepare a public
post without publishing it.

Default review mode: autonomous preparation followed by human approval at the commit or
publication boundary.

### R4 — Consequential

Material, externally visible, or insufficiently reversible effects: sending
communications, submitting applications or forms, merging pull requests, publishing
content, production mutations, substantial external data transmission.

Default review mode: explicit human authorization before the consequential effect.

### R5 — Privileged / Critical

Security-sensitive, destructive, financial, legal, identity, credential, or similarly
high-impact effects: ACL or authorization changes, credential or secret operations,
account deletion, destructive production operations, payment, broad sensitive-data
export, modification of TriageCore authorization policy.

Default review mode: deny by default unless separately and explicitly authorized.

**CR-AR-001 does not grant autonomous R4 or R5 authority.**

## Risk Escalation

Risk classification MUST be monotonic during an active capability claim.

- A workflow MAY escalate from a lower tier to a higher tier.
- A workflow MUST NOT silently de-escalate to a lower tier.

Example: `R2 → R3 → R4`.

If continued execution requires a tier above the claim's authorized ceiling, the mediated
executor MUST refuse the operation and return an escalation result, e.g.:

```text
CAPABILITY_ESCALATION_REQUIRED
current_tier: R2
required_tier: R3
reason: cumulative_target_count
```

The agent MUST NOT be permitted to override this result through natural-language
reasoning.

## Cumulative / Compositional Risk

TriageCore MUST evaluate cumulative workflow effects in addition to individual action
risk. Individually low-risk operations MAY collectively exceed the authorized risk
envelope — for example, many individually harmless reads followed by many individually
harmless sends can collectively amount to bulk outreach.

The initial implementation SHOULD support explicit budgets for at least:

- total tool calls;
- total mutations;
- number of modified resources;
- number of distinct external targets;
- execution duration;
- output or transfer size.

Exceeding a configured threshold MUST cause one of: denial, staging, capability
escalation, or terminal review transition.

The agent MUST NOT receive authority to reset its own counters. Budget consumption SHOULD
use the existing atomic capability-claim semantics where applicable.

## Risk Floors

Certain properties MUST impose a minimum risk tier regardless of an otherwise lower
calculated score. Risk floors MUST NOT be reduced by averaging them against lower-risk
attributes.

| Condition | Minimum treatment |
| --- | --- |
| Security-policy or permission mutation | R5 |
| Agent modifies its own authorization policy | R5 / deny |
| Credential or secret access beyond explicitly authorized use | R4/R5 |
| Destructive action without reliable compensation | R4 |
| Sensitive information leaving its trust boundary | R4 |
| Unknown or unbounded target set | R4 |
| External publication or submission | R4 |
| Mutation causally driven by untrusted content | R3 |
| Missing required audit evidence | autonomous mutation denied |
| Claimed R2 action without a policy-recognized compensation contract (see Compensation Contract) | R3 or higher |

## Untrusted-Input Escalation

TriageCore SHOULD track whether external or otherwise untrusted content influenced a
proposed mutation, e.g.:

```text
user intent
    ↓
agent
    ↓
retrieved email / webpage / document
    ↓
proposed mutation
```

Where untrusted content causally influences a mutation, the workflow MUST NOT treat the
action as ordinary user-originated R2 execution.

For the initial implementation: `R2 + untrusted causal input → minimum R3`.

The mechanism SHOULD depend on provenance and trust classification rather than requiring
the model to determine whether an input is malicious.

## Classification Basis

Risk-tier classification MUST be derived from policy-controlled or mediated observations of
the actual tool, resource, and effect type an action invokes — for example, the identity of
the file, branch, endpoint, or external target addressed, and the effect category a
mediated executor is defined to record for that effect type, where one exists — wherever
such an observation is available.

Classification MUST NOT rely solely on an agent's self-description, natural-language
intent, or narrated justification for an action. An agent's account of what it is doing or
why is evidence for human review; it is not an input the classifier may trust to determine
a risk tier. This does not require a specific detection technology — it requires that,
wherever a policy-controlled or mediated fact is available, that fact governs
classification rather than the agent's own account. Where no such observation exists for a
given tool or effect type, that gap is itself a reason to floor the classification upward
(see Risk Floors) rather than to trust agent-supplied description as a substitute.

## Capability Claim Extension

Capability claims supporting deferred review SHOULD contain fields equivalent to:

```yaml
authorization:
  review_mode: deferred_terminal
  effect_ceiling: R2
scope:
  tools: [...]
  resources: [...]
  denied: [...]
budgets:
  max_calls: ...
  max_mutations: ...
  max_resources: ...
  max_runtime_seconds: ...
  max_output_bytes: ...
reversibility:
  required: true
  compensation_required: true
terminal_review:
  required: true
  allowed_dispositions:
    - accepted
    - revised
    - rejected
evidence:
  record_tool_calls: true
  record_resource_deltas: true
  record_denials: true
  record_policy_hash: true
```

Exact schema naming is implementation-defined by a future implementation CR. Risk budget
should be claimed atomically, consistent with the existing atomic capability-claim work in
CR-YK-002, so that two concurrent agents cannot each believe they possess the remaining
mutation budget.

## Compensation Contract

"Compensable" and "reversible" are policy classifications, not runtime capabilities an
agent or its output may assert for itself.

A capability claim MUST NOT declare `reversibility.required: true` for a given effect type
unless a policy-recognized, testable compensation contract exists for that specific effect
type. A compensation contract, for the purposes of this CR, is a named, versioned
specification of: the effect type it covers, the inverse or restorative operation it
requires, and the test or evidence that demonstrates the inverse operation reliably
restores prior state for that effect type. Defining what such a contract must contain is in
scope for this CR; naming, implementing, or guaranteeing any concrete compensation
mechanism is not.

Where no policy-recognized compensation contract exists for an effect type, that effect
type is ineligible for R2 `deferred_terminal` treatment regardless of how reversible the
action appears, and classification MUST treat it at R3 or higher (staged, not executed
before review) instead. This is the gap the corresponding Risk Floors row exists to catch:
an agent's or generated output's own claim of reversibility is not evidence that a
compensation contract exists.

TriageCore has no implemented compensation or rollback mechanism for any effect type today
— `mediated_executor.py`'s single supported effect explicitly performs no automatic
rollback. This CR does not change that. AR-007 and AR-008 below describe what a
compensation contract must guarantee if and when one is implemented; they do not authorize
or assume the existence of one.

## Runtime Requirements

- **AR-001** — The mediated executor MUST enforce the capability claim on every tool
  invocation regardless of review mode.
- **AR-002** — `deferred_terminal` MUST alter human-review timing only. It MUST NOT
  bypass capability validation.
- **AR-003** — An R2 workflow MUST be restricted to resources, tools, and budgets
  explicitly authorized by its capability claim.
- **AR-004** — An action exceeding the claim's risk ceiling MUST be denied or staged
  before the excess effect occurs.
- **AR-005** — Risk tier MUST be monotonic within a capability claim.
- **AR-006** — Cumulative resource and mutation budgets MUST be enforced atomically
  where concurrent execution could otherwise exceed the authorized budget.
- **AR-007** — R2 eligibility MUST require a policy-recognized, testable compensation
  contract for the specific effect type (see Compensation Contract). Eligibility MUST NOT
  be established solely by an agent's or generated output's own claim that an action is
  reversible.
- **AR-008** — Failure of compensation MUST be recorded as a governance failure and
  MUST NOT be silently treated as successful rejection or rollback.
- **AR-009** — The agent MUST NOT be able to modify its active risk tier, its effect
  ceiling, its budget counters, its review requirement, or the policy governing its own
  authorization.
- **AR-010** — R3 external effects MUST remain staged until explicit human authorization
  permits the release or commit operation.
- **AR-011** — CR-AR-001 MUST NOT authorize autonomous R4 or R5 terminal effects.

## Terminal Evidence Bundle

Before requesting terminal review, TriageCore MUST construct an evidence package from
runtime records rather than relying solely on an agent-generated summary. The reviewer
MUST be able to distinguish mechanically observed effects from model-generated
interpretation.

The evidence bundle MUST include:

- workflow identifier;
- original intent digest or reference;
- capability-claim identifier;
- policy version or digest;
- effective risk tier;
- executor identity;
- tools invoked;
- resources read or mutated;
- exact or mechanically derived state deltas where available;
- budget consumption;
- denied operations;
- attempted risk escalations;
- external effects executed;
- external effects still staged;
- compensation availability;
- provenance/trust flags relevant to mutations;
- the specific risk-classification rule or floor that produced the effective tier, and the
  pre-floor calculated tier where a floor changed the outcome;
- the structured input facts the classification decision was based on (tool identity,
  resource identity, effect type), sourced per Classification Basis rather than from
  agent-supplied description.

A conceptual sketch of the review package:

```text
Intent          — original task digest, capability claim ID, policy version/hash,
                   executor identity, models/tools involved
Effects         — reads, local writes, commands, staged external actions,
                   privileged operations (should be zero), denied scope-expansion
                   attempts
Delta           — exact affected resources, before → after
External        — destination, pending operation, and an explicit list of what was
  boundary        NOT executed (e.g. NOT EXECUTED: merge, NOT EXECUTED: publish)
Provenance      — which retrieved inputs influenced which actions, trusted/untrusted
                   classification
Disposition     — [ Accept ] [ Revise ] [ Reject / Roll back ]
```

The final human decision SHOULD be capable of being cryptographically bound to the
effect digest, extending the existing Signed Intent lineage; the exact binding mechanism
is left to a future implementation CR.

## Terminal Dispositions

An R2 workflow MUST support:

- **Accepted** — effects remain in place and the workflow becomes complete.
- **Revised** — the existing workflow MUST NOT silently continue under the original claim.
  The original capability claim MUST reach the terminal claim-store state `failed` — never
  `completed`, and never left non-terminal — before or as part of recording the `Revised`
  disposition; `failed` here follows CR-YK-002's existing usage, where a terminal state
  records lifecycle completion or failure without judging correctness or quality, so
  recording `failed` for a revised-but-not-discarded workflow is consistent with, not a
  misuse of, that vocabulary. Effects already produced under the original claim are not
  automatically compensated and are not silently treated as an accepted baseline: they
  become provisional evidence attributed to the now-failed claim. A revised workflow MUST
  obtain a new or explicitly amended capability claim before any additional consequential
  execution, and that new claim's own evidence MUST explicitly reference which provisional
  effects, by original claim ID and effect digest, it retains, if any. Silently carrying
  forward unreferenced prior effects under new authority is prohibited; discarding effects
  that are not retained requires the same compensation contract as a `Rejected` disposition
  (see Compensation Contract).
- **Rejected** — TriageCore MUST invoke the configured compensation mechanism where
  compensation is required. The resulting state and compensation outcome MUST be
  recorded.

## Terminal-Review Assurance

This CR distinguishes four human-facing concepts that the Design Principle section above
introduces at a higher level:

- **Pre-effect human authorization** — a human act required before a specific effect may
  occur at all: R4/R5's "explicit human authorization," and the existing WebAuthn-bound
  `HumanAuthorizationReceipt` lineage documented in
  `docs/architecture/human_authorization_lifecycle.md`.
- **Deferred human review** — the R2/R3 mechanism this CR defines: review that occurs after
  bounded autonomous execution, before a workflow is considered accepted.
- **Retrospective disposition** — the specific recorded outcome of deferred human review
  (`Accepted` / `Revised` / `Rejected`), which is authorization-consequential: it determines
  the underlying capability claim's terminal state and, for `Rejected` and `Revised`,
  triggers compensation or re-authorization.
- **Acknowledgement/observation** — a human or operator being aware of or having looked at
  a record, with no authorization consequence at all.

**A retrospective disposition under this CR is not, by default, a pre-effect human
authorization.** Recording `Accepted`, `Revised`, or `Rejected` MUST at minimum be captured
as evidence attributable to a specific human principal. It MAY additionally be
cryptographically bound to the effect digest, extending the Signed Intent lineage, but this
CR does not require that binding, and absent it, a disposition MUST NOT be treated as
equivalent in assurance to a `HumanAuthorizationReceipt`. A future CR that binds terminal
review to that receipt lineage would need to say so explicitly; this one does not, so no
implementation should assume it.

**Relationship to the existing `human_review_required` route-evidence flag is preserved,
not superseded.** `human_review_required` (`docs/architecture/governed_run_flow.md`) keeps
its existing meaning and existing non-gating behavior for routes and workflows outside this
authorization mode. The deferred-terminal-review mechanism defined here is a separate,
authorization-consequential signal that applies specifically to workflows executing under a
`review_mode: deferred_terminal` capability claim. The two are not required to imply or
satisfy each other: a workflow can carry `human_review_required: true` in route evidence
and still separately require deferred terminal review under this CR, and completing one
MUST NOT be read as having satisfied the other.

**`REVIEW_PENDING` must remain observably distinct from `ACCEPTED`.** The underlying
invariant is that an unreviewed workflow must never silently become equivalent to an
accepted one — not that `REVIEW_PENDING` must expire after a fixed duration. This CR does
not impose a timeout. Any implementation MUST make `REVIEW_PENDING` durable, visible, and
queryable as its own state for as long as it persists, and MUST allow it to be a factor in
future budget or eligibility decisions for the same principal (see Cumulative /
Compositional Risk). Exact queue-age thresholds, staleness escalation, or reviewer-load
policy are implementation-time decisions or a later CR's scope, not this one's.

**Disposition vocabulary is deliberately distinct from, and does not replace, existing
evidence/review vocabularies.** `Accepted` / `Revised` / `Rejected` here govern the
authorization fate of a capability claim and its effects. They are a different concept from
`evidence_schema.md`'s `review_decision` (`accepted` / `accepted_with_minor_edits` /
`rejected`) and `supervisor_decision` (`accepted` / `rejected` / `needs_revision` /
`escalated`), which record quality or usefulness judgments with no authorization
consequence, and from the informal "operator disposition" language used in daily-use
evidence-window records, which is explicitly not a validation or authorization event. A
future implementation MUST NOT treat satisfying one of these vocabularies as having
satisfied this CR's Terminal Dispositions, or vice versa. This CR does not rename any of the
existing fields; it only draws the boundary between them.

## State Model

The workflow/review lifecycle below is a **separate state machine layered above** the
existing capability-claim lifecycle (`issued → claimed → completed | failed`,
`triage_core/capability_claims.py`). It does not extend, and this CR does not propose
extending, the claim store's closed state enum. This mirrors the existing pattern of
`RequestReservationStore` and `CapabilityClaimStore` as two separate SQLite stores with
explicit cross-references rather than one merged schema — the workflow/review layer is a
third such store, cross-referencing capability-claim IDs rather than absorbing them.

The claim-store lifecycle remains the sole representation of **authority consumption**: a
claim is `issued`, then `claimed` for the duration of both autonomous execution and any
subsequent review, then finalized `completed` or `failed`. The workflow/review layer below
is the sole representation of **post-execution review and disposition**; it never grants,
extends, or reinstates authority on its own.

| Workflow/review state | Underlying claim-store state | Notes |
| --- | --- | --- |
| `AUTHORIZED` | `issued` | Claim exists; execution has not begun. |
| `RUNNING` | `claimed` | Autonomous execution in progress under the claim. |
| `STAGED` (R3 only) | `claimed` | Preparation complete; external release withheld. |
| `REVIEW_PENDING` | `claimed` | Execution (and staging, if any) complete; the claim remains `claimed` — not yet terminal — until a disposition is recorded. See Terminal-Review Assurance for why this state must stay observably distinct from `ACCEPTED` without requiring an arbitrary timeout. |
| `ACCEPTED` | `completed` | Disposition recorded; claim reaches its terminal state. |
| `REJECTED` | `failed` | Disposition recorded; claim reaches its terminal state; compensation (see Compensation Contract) follows if required. |
| `REVISED` | `failed` | See Terminal Dispositions for the required treatment of the original claim and its effects. |
| `COMPENSATING` / `COMPENSATED` / `COMPENSATION_FAILED` | `failed` (already terminal) | Compensation is workflow-layer bookkeeping after the claim has already reached its terminal state; it never reopens the claim. |

A minimal lifecycle MAY be:

```text
AUTHORIZED
    ↓
RUNNING
    ↓
REVIEW_PENDING
   ├── ACCEPTED            (claim → completed)
   ├── REVISED             (claim → failed; see Terminal Dispositions)
   │      ↓
   │   new/amended authorization (new claim; explicit provisional-effect reference)
   │
   └── REJECTED            (claim → failed)
          ↓
      COMPENSATING
          ├── COMPENSATED
          └── COMPENSATION_FAILED
```

R3 workflows additionally require a staged state:

```text
RUNNING
   ↓
STAGED
   ↓
REVIEW_PENDING
   ├── approved → COMMIT / RELEASE   (claim → completed)
   └── rejected → DISCARD            (claim → failed)
```

## Security Invariants

The implementation MUST preserve the following invariants:

1. Deferred human review is not deferred authorization enforcement.
2. No agent may broaden its own active authority.
3. Risk escalation occurs before the higher-risk effect.
4. Cumulative low-risk actions cannot bypass a higher-risk boundary.
5. R2 effects are identifiable and sufficiently reversible.
6. R3 effects remain staged until approved.
7. Terminal review is grounded in execution evidence, not merely agent claims.
8. Denials and escalation attempts remain observable evidence.
9. Concurrency cannot multiply a single authorized risk budget.
10. R4 and R5 terminal effects remain outside autonomous authority in this CR.

## Non-Goals

CR-AR-001 does not attempt to:

- create a universal numerical agent-risk score;
- authorize autonomous high-impact activity;
- allow models to self-classify actions without policy enforcement;
- solve all prompt-injection detection;
- guarantee that every external system provides transactional rollback;
- automate human acceptance decisions;
- replace existing capability claims;
- replace mediated execution;
- remove evidence requirements;
- modify the current empirical evidence-window protocol;
- name, implement, or guarantee a concrete compensation mechanism for any effect type (see
  Compensation Contract);
- require or implement cryptographic binding of a terminal-review disposition (see
  Terminal-Review Assurance) — that remains optional and future-CR scope.

## Initial Implementation Slice

Should this CR be accepted, the first implementation SHOULD be deliberately constrained
to:

- R0–R3 risk classes;
- `deferred_terminal` review mode;
- an R2 effect ceiling;
- bounded mutation/resource/call budgets;
- monotonic risk escalation;
- denial when the ceiling would be crossed;
- terminal evidence-bundle generation;
- accepted/revised/rejected dispositions;
- tested R2 compensation;
- staged R3 effects with no autonomous release.

R4 and R5 remain enforcement boundaries, not autonomous execution modes. Acceptance of
this CR document does not itself authorize the Initial Implementation Slice; that slice
requires its own separate approval and bounded file allowlist, consistent with how
CR-DD-012B and CR-OC-001C–E were sequenced.

The risk classifier for this initial slice SHOULD remain primarily rule/policy-driven
rather than model-assisted; an LLM-assisted classifier is deferred until TriageCore has
ground-truth execution data from these tiers.

## Required Tests

At minimum, tests MUST demonstrate:

1. **Normal R2 execution** — a bounded reversible workflow performs multiple permitted
   mutations without intermediate human approval and reaches `REVIEW_PENDING`.
2. **Acceptance** — human acceptance preserves the resulting state and completes the
   workflow.
3. **Rejection and compensation** — human rejection invokes compensation and restores the
   defined prior state.
4. **Compensation failure** — a failed rollback is surfaced explicitly and leaves
   auditable evidence.
5. **Scope violation** — a tool or resource outside the capability claim is denied during
   autonomous execution.
6. **Risk ceiling** — an R2 workflow attempting an R3-or-higher operation is stopped
   before the higher-risk effect.
7. **Monotonicity** — a workflow escalated to R3 cannot resume as R2 under the same
   unchanged authorization.
8. **Cumulative risk** — a sequence of individually permitted operations crossing a
   configured cumulative threshold is stopped.
9. **Concurrency** — concurrent operations cannot collectively consume more mutation or
   resource budget than authorized.
10. **Self-modification** — an agent cannot change its active risk limit, budget, review
    policy, or authorization policy.
11. **Untrusted-input floor** — a mutation causally attributed to untrusted retrieved
    content receives at least R3 treatment.
12. **R3 staging** — an external effect can be completely prepared but cannot be
    committed without terminal human authorization.
13. **Evidence fidelity** — the terminal evidence bundle accurately represents actual
    executor-observed actions, including denied calls and staged-but-unexecuted effects.
14. **Revision handling** — a `Revised` disposition finalizes the original capability claim
    as `failed`, and a subsequent execution under a new or amended claim explicitly
    references which provisional effects from the original claim it retains, if any,
    rather than silently treating them as pre-existing baseline.

## Acceptance Criteria

CR-AR-001's Initial Implementation Slice, once separately authorized, is complete when:

- [ ] all defined runtime requirements (AR-001 through AR-011) are implemented;
- [ ] the focused test suite passes;
- [ ] concurrency budget enforcement is demonstrated;
- [ ] at least one R2 end-to-end workflow executes without intermediate approval;
- [ ] rejection demonstrably compensates that workflow;
- [ ] at least one R3 workflow reaches a staged external effect but cannot release it
      autonomously;
- [ ] at least one `Revised` workflow finalizes its original claim as `failed` and
      demonstrates explicit provisional-effect reference in the new claim's evidence;
- [ ] attempts to exceed the effect ceiling fail before the consequential mutation;
- [ ] the terminal evidence bundle is mechanically derived and independently verifiable;
- [ ] existing capability-claim and mediated-executor invariants remain passing;
- [ ] documentation clearly distinguishes deferred review from deferred enforcement.

## Research Questions Preserved for Later CRs

The following remain intentionally unresolved by this CR:

- whether risk classification should remain categorical or gain a quantitative
  component;
- how provenance taint should propagate through derived artifacts;
- when repeated R2 workflows should increase future scrutiny;
- whether historical execution reliability should affect authorization;
- how cross-agent cumulative risk should be budgeted;
- whether terminal evidence can be cryptographically bound to a Signed Intent approval;
- what R4 actions, if any, could eventually qualify for constrained autonomous
  execution;
- how policy should represent organizational versus individual risk tolerance;
- which effect types should receive the first policy-recognized compensation contracts,
  and what such a contract must specify beyond the minimum shape defined in Compensation
  Contract.

## Expected Outcome

CR-AR-001, if accepted and later implemented, should allow TriageCore to move from:

```text
agent proposes action → human approves → action → human approves → action → human approves
```

to:

```text
human authorizes bounded workflow
→ TriageCore continuously enforces
→ agent executes low-risk workflow
→ TriageCore records evidence
→ human reviews resulting workflow once
```

while preserving:

```text
higher-risk effect → stop / stage / escalate → human authorization → effect
```

The intended result is lower approval fatigue without reducing runtime governance. The
proposition is not "TriageCore makes agents ask permission" but "TriageCore makes the
frequency and location of human intervention proportional to the actual consequences of
agent action."
