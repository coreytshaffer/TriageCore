# Monitoring Coverage Integrity — Research Candidate

Status: **draft nomination / not accepted for implementation**

Recorded: 2026-10-22 (Pacific time)

Source baseline: `610c13f253ba631d7052727abe3d68845bb09bb5`

## Purpose and scope

Determine whether a bounded set of execution observations can be reconciled
with monitor evidence while making omissions, exemptions, and uncertainty
visible. The proposed first deliverable is a versioned contract and fixture
specification. This file does not implement that contract, register a new CR,
promote the candidate into an active backlog slice, or authorize execution.

The candidate strengthens evidence and reconstruction, evaluator independence,
decision integrity, and privacy/provenance under the
[backlog taxonomy](../../current_backlog.md#backlog-scope-taxonomy).
Process isolation, credential custody, and provider adapters are supporting
dependencies to review separately.

The [source inventory](../../operations/monitoring-coverage-baseline-2026-10-22.md)
is the baseline for its scope. Current route/worker events and signatures do
not establish an independent execution census. CR-135's transport foundation
remains disconnected from `tc run`; even integration would not by itself
prevent execution through another interface with equivalent credentials.

## Research motivation

[METR's October 22 monitoring investigation](https://metr.org/blog/2026-10-22-red-teaming-openai-agent-monitoring/)
describes gaps between traffic intended for monitoring and traffic actually
evaluated, including compaction and delayed monitoring triggers. Its historical
findings motivate testing coverage accounting as a separate property from
the accuracy of a behavioral monitor. They do not establish TC vulnerabilities
or validate the design proposed here.

## Three distinct claims

| Question | Evidence required | What a synthetic contract cannot establish |
|---|---|---|
| Are observations reconciled? | Valid receipts or explicit unresolved/exempt states for eligible observed event units | That observations include every real execution |
| Is the census complete within a boundary? | An inventoried and enforced observation boundary, with tested bypass exclusions | That a simulated observation source is non-bypassable in deployment |
| Can execution be inhibited? | A separately enforced gate with tested timing, refusal, and recovery semantics | That reporting a missing receipt stops a side effect |

An event invisible to every observation source cannot be recovered by joining
those sources. The result must retain an unknown census-assurance state rather
than claiming universal coverage. A receipt proves neither authorization nor
safety; a reported reason for missing coverage does not make it compliant.

## Proposed first profile

Start with synthetic event streams describing one explicitly enrolled,
local-only governed `tc run` profile with one backend protocol and fixed model
identity. Specify inference attempts separately from named tool-effect attempts;
tool-effect attempts are synthetic model-only units in this increment, not a
claim that the first runtime profile includes a tool mediator. Model plan-only
outcomes, admission, dispatch, cancellation, completion, unknown outcomes,
retries, compaction, and restart separately.

The optional cloud lane, other CLI paths, GUI dispatch, direct library callers,
metadata probes, and injected backends remain explicit exclusions. A future
runtime pilot must resolve their access to equivalent capabilities before
claiming a non-bypassable boundary. No host-wide, whole-repository, or live monitoring claim is proposed
for this first contract.

## Detailed contract draft

The [contract v0.1](../monitoring-coverage-contract-v0.1.md) and
[fixture specification v0.1](../monitoring-coverage-fixture-spec-v0.1.md) now
provide the reviewable design increment. They remain unaccepted, unimplemented
specifications; their closed record shapes are not installed TC schemas.
The contract defines these five record families:

1. **Scope manifest:** versions, session/epoch, event eligibility, observation
   identities, known bypasses, exclusions, and checkpoint/deadline policy.
2. **Observation:** event/attempt identity, causal parent, source and sequence,
   lifecycle stage, and commitment to the relevant observable context.
3. **Monitor receipt:** monitor/configuration identity, exact event membership,
   independently calculated context commitment, processing stage, and result.
4. **Exemption:** prospective human issuer, bounded scope, reason, expiry, and
   explicit treatment of any consequential actions.
5. **Reconciliation report:** watermarks and window status, coverage counts,
   unmatched admissions/dispatches, invalid evidence, and historical violations.

For observed in-scope event units eligible before exemptions, a proposed
accounting identity is:

`observed = reviewed + exempt_unreviewed + pending_within_deadline + uncovered`

The categories must be disjoint. A completed valid review can count regardless
of its behavioral verdict; a received-but-unevaluated item cannot.
Exempt-unreviewed events are not counted as monitored. A zero denominator is
not 100% coverage. Duplicate receipts cannot increase coverage.
Late receipts may resolve the current state without
erasing missed-deadline or unadmitted-dispatch violations.

Reconcile admissions and dispatch separately. Queued work and proven
pre-dispatch cancellation are legitimate; unexplained execution outcomes after
the evidence deadline remain unresolved. An observed-but-unadmitted execution
remains a boundary violation even if it later receives a review.

## Fixture specification

Use a fake clock and separately authored synthetic admission, execution-witness,
and monitor streams. Freeze the expected classifications before implementing a
reference reconciler. Include benign controls, missing and reordered events,
and exact content/version identities.

| Scenario | Expected design obligation |
|---|---|
| Endless activity | Checkpoint becomes due without an end-of-turn signal |
| Compaction or restart | Link epochs and retain outstanding review obligations |
| Unauthorized policy change | Preserve eligibility; report the change and never apply it to accounting |
| Monitor outage | Pending becomes an explicit gap after the deadline |
| Different worktree or no ledger | Local evidence absence cannot erase independently observed events |
| Divergent context | Receipt fails the specified context binding |
| Replay, duplicates, retries, or late delivery | Stable identities and explicit timing rules prevent false coverage |
| Invalid or retrospective exemption | Preserve the original obligation and violation |
| Bypass of all synthetic observation sources | Census assurance stays unknown |
| Plan-only or pre-dispatch cancellation | No invented inference and no vacuous success claim |

An optional modeled dispatch gate may later test refusal semantics. It must
remain labeled simulation; it does not constitute TC runtime enforcement.

## Privacy and independence requirements

Ordinary governance records must not acquire raw prompts, completions,
credentials, or private paths. Define the actual observable invocation context,
including effective system/user messages and relevant tool traffic, rather than
assuming the initial task snapshot is the complete invocation. Exclude hidden
provider internals from any same-context promise.

A monitor must derive a commitment from the context it received, not echo an
agent-supplied hash. Compaction links do not reconstruct discarded content.
Specify context availability, retention/deletion, canonicalization, and possible
guessing leakage from low-entropy content digests before runtime work.

Independence concerns authority and capabilities: separate process names are
insufficient if the agent can rewrite monitor configuration, read its signing
keys, erase its evidence, or use unobserved credentials. A future coverage gate
may only add constraints; it must not replace existing human authorization.

## Dependencies and open decisions

- Reconcile backlog state and inventory actual invocation paths before freezing
  the profile. CR-DD-012B is merged; its stale lifecycle wording is a record
  discrepancy, not unfinished implementation.
- CR-132 concerns the architecture map. Its documentation work does not itself
  remove operational bypasses. This candidate does not implement that CR.
- CR-135 integration is a dependency only for a runtime pilot that relies on
  its governed transport. It is not a prerequisite for a pure synthetic contract.
- Resolve the old evidence window's disposition before changing its execution
  or evidence semantics. Keep all synthetic work outside natural-use evidence.
- Reconcile any separately governed monitoring study, including TC-AM-001,
  before implementation. This candidate adopts no off-repository decision text,
  renews no earlier grant, and authorizes no live observation or intervention.
- Export, external-evaluator, and key-lifecycle work become dependencies only
  when the selected profile actually uses them. Do not require the whole backlog.

Decide the trusted observation point, session/attempt identity authority,
checkpoint and lateness policy, exact context representation, exemption rules,
named consequential actions, incident owner, and recovery procedure. The
contract must expose unresolved choices rather than invent defaults that imply
runtime protection.

## Review and promotion

The detailed contract and fixture specification (revision r1, after an agent
review of the r0 handoff draft) are ready for design review.
Review their frozen identities, partition rules, original deadlines, prospective
exemptions, independent checkpoint obligations and explicit unknowns before
acceptance. The fixture outcomes are manually specified expectations, not test
results. A later test-only reference implementation and any runtime pilot
require their own bounded scope and authority under
[change management](../../change/change_management.md).

This nomination assigns no new identifier and changes no ledger, runtime,
configuration, evaluator, approval, deployment, or evidence-window state.
