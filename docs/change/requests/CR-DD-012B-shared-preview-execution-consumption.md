# CR-DD-012B: Shared Preview/Execution Consumption

## Status

**Implementation acceptance GRANTED for exact head `bbe5336`. Merge, release,
and closeout authority are WITHHELD.**

### Lifecycle state

| Stage | State |
|---|---|
| design direction | accepted |
| implementation authority | incomplete originally; defect preserved below |
| corrective ratification | granted for exact `bbe5336` |
| implementation acceptance | **granted** for exact `bbe5336` |
| merge authority | withheld |
| release authority | withheld |
| closeout | withheld |

The accepted candidate is the code and test state at `bbe5336`. This document's
own status entries are inside the ratified path inventory, so recording the
grants here changes no code and no test; `git diff bbe5336..HEAD -- triage_core/
tests/` is empty by construction, and the acceptance attaches to that state
rather than to whatever the branch's tip commit happens to be.

### Authority record — the original defect, preserved

The operator opened the implementation phase with this instruction, quoted in
full:

> Begin Implementation phase for CR-DD-012B — Shared Preview/Execution
> Consumption.

That instruction granted implementation intent. **It named no bounded file
allowlist.** This document requires one — "that approval must name its own
bounded file allowlist" — so the grant as issued was incomplete against the
governance model this CR sets for itself.

What happened next, stated as what it was: the provisional list in **Settled
Question 8** was **inferred** to be the intended bound, and work proceeded under
it. That inference was not a grant. Two paths were then taken beyond even that
inferred list.

**This defect is not erased, relabelled, or reconstructed.** The operator's
recorded reasoning for preserving it rather than rebuilding: replaying the same
work later "would improve the appearance of the process without changing the
evidence," because the implementation did in fact begin under an incomplete
authorization, and that historical fact does not disappear by re-enacting the
work. Preserving the defect as evidence is more faithful to this project's
evidence doctrine than rewriting history.

### Corrective ratification — granted, recorded verbatim

The operator's disposition, recorded as issued:

> For CR-DD-012B, I grant a one-time corrective bounded implementation
> ratification for the exact candidate at `bbe5336`. The authorized scope is the
> complete cumulative changed-path inventory already recorded in CR-DD-012B at
> `bbe5336`, including the two necessary regression-test paths
> `tests/test_tc_run_cli.py` and `tests/test_tc_run_plan_cli.py`. This grant
> applies only to the exact candidate state at `bbe5336`; recognizes that the
> earlier instruction, "Begin Implementation phase for CR-DD-012B — Shared
> Preview/Execution Consumption," granted implementation intent but failed the
> CR's requirement for an explicit bounded allowlist; does not erase or relabel
> that earlier governance defect; authorizes the already-produced candidate to be
> evaluated for implementation acceptance without reconstruction; grants no
> authority for further implementation changes; is exhausted by this disposition;
> and grants no merge, release, or closeout authority. If the candidate changes
> by even one substantive commit, this ratification does not automatically follow
> the new head.

The ratification is exhausted. It authorized evaluation of the existing
candidate, not further implementation.

### Implementation acceptance — granted at `bbe5336`

Granted on the substantive grounds recorded in the acceptance review: the
canonical-decision boundary now holds, because execution no longer runs
`ProjectSteward` or `SpecialistRouter.route_task` as downstream decision-makers;
the runtime/policy separation is real, because medium-risk and oversized-context
behavior no longer changes route policy on live connectivity; the
ethical-firewall regression is repaired semantically rather than numerically; the
no-rebuild traps were strengthened by being installed after the seam, so they
test the property actually in dispute; and verification is 1802 passed / 6
skipped overall with 106 focused tests across the no-rebuild traps, gates 3
through 5, and terminal routing.

**No further modification is authorized under the implementation grant.** The
next gate is merge authority.

The sections that follow the implementation record are the proposal as written
before implementation, preserved unchanged so the recommendation and the outcome
can be compared. Where the built code diverges from a recommendation, the
divergence is named in **Implementation Record**, not silently edited into the
recommendation.

The sequencing prerequisites are satisfied:

- **CR-DD-012A** is complete and merged through PR #107 as `bccaaad`. The
  immutable snapshot and canonical decision contracts exist as an internal,
  non-integrated foundation that no public command consumes.
- **CR-YK-002** is complete and merged through PR #117 as `5155bbb`, satisfying
  the atomic-claiming prerequisite the parent CR named.

Satisfying a prerequisite was never approval, and neither foundation's merge was
the implementation gate; the operator's direct instruction was.

The three questions this proposal originally left open were settled by recorded
supervisor decision — see **Resolved Questions** — and five implementation
approval gates are recorded in **Implementation Approval Gates**. Gates 1 and 2
were proposal-stage preconditions, satisfied before implementation began. Gates 3
through 5 were implementation obligations and now pass; they were the condition
on *acceptance*, so their passing is evidence for that decision rather than the
decision itself.

This CR is scoped against `main` at `8bfb547`. Its parent architecture is
`CR-DD-012-shared-governed-run-decision.md`, which remains authoritative on the
contract model; this document settles only the consumption questions the parent
deferred to the implementation slice.

## Implementation Record

Recorded after the implementation phase. Everything here describes code that
exists on the branch. Nothing in *this section* grants anything; the recorded
grants live in **Status**, and merge, release, and closeout remain withheld.

### Files changed

| Path | Change | On the provisional allowlist |
|---|---|---|
| `triage_core/tc_cli.py` | one snapshot/decision construction seam before the planning branch; sources read once as bytes; artifact fed from snapshot bytes | yes |
| `triage_core/run_plan.py` | the seam itself (`build_governed_run_context`); `build_run_plan` projects a completed decision | yes |
| `triage_core/client.py` | optional `snapshot`/`decision` pair; consumes decision policy; fail-closed verification | yes |
| `triage_core/routing/route_events.py` | additive bounded `decision_id` linkage | yes |
| `triage_core/runtime_observation.py` (new) | validated internal observation and envelope filter | yes |
| `tests/test_governed_consumption_parity.py` (new) | integrated shape, parity, no-rebuild traps, mutation, TOCTOU, privacy | yes |
| `tests/test_runtime_observation.py` (new) | envelope and observation separation, gates 4 and 5 | yes |
| `tests/test_governed_consumption_failclosed.py` (new) | fail-closed matrix | yes |
| `tests/test_governed_decision_integration_absence.py` (deleted) | retired per gate 3; coverage replaced, not removed | yes (named as a retirement decision) |
| this document, `CR-DD-012-shared-governed-run-decision.md`, `docs/current_backlog.md`, `docs/architecture/daily_driver_orchestrator_spec.md` | status | yes |
| `tests/test_tc_run_cli.py` | **beyond the inferred list** — two regression updates, below | no |
| `tests/test_tc_run_plan_cli.py` | **beyond the inferred list** — one regression update, below | no |

Every deliberately excluded module is untouched: `route_worker_ledger.py`,
`run_plan_artifact.py`, `capability_evidence.py`, `governed_run_snapshot.py`,
`governed_decision.py`, `task_ledger.py`, `engine.py`, `resilience_router.py`,
every CR-YK and CR-OC module, and `docs/change/change_log.md`.

### The two paths beyond the inferred allowlist

Both are existing regression tests that the slice's intended behavior
necessarily invalidates. Neither weakens an assertion; both were rewritten to
assert the new guarantee.

1. **`tests/test_tc_run_cli.py`.** Its injected `RecordingClient.run_task` has a
   fixed signature that the new `snapshot`/`decision` pair breaks, and
   `test_terminal_routes_exit_3_without_backend_execution` patched
   `triage_core.client.choose_resilience_route` — a call the governed path no
   longer makes, so the patch had become a silent no-op. The test now drives the
   router at the seam, and its `deterministic` arm asserts the stronger new
   fact: an unbindable member falls through to the next already-authorized
   envelope member rather than executing anything.
2. **`tests/test_tc_run_plan_cli.py`.** The governed snapshot bounds an explicit
   task ID to letters, marks, numbers and `._:+-`, so `--task-id 'tâsk-☃'` is now
   rejected at the seam instead of rendered. The unicode-escaping test keeps its
   snowman in the source path and the backend model and uses a non-ASCII
   *letter* in the task ID, so the escaping it exists to prove is still proven.

### Behavioral changes an accepting reviewer is approving

- **Capability no longer reaches route policy** (Resolved Question 1, as
  recorded). Both preview and execution now form the decision with
  capability-free availability. A run whose local capability is unknown produces
  a decision naming local routes and then fails at binding, where previously the
  router resolved to no local route earlier. The observable terminal outcome for
  `tc run` is unchanged — a local-only run with no usable local capability still
  exits 2 through the existing local-route guard — but the *reason* now arrives
  at binding rather than at routing.
- **`tc run --plan` output gains one line**,
  `permitted_fallback_envelope`, and its `route_required_checks` line now lists
  the governed verification codes rather than the router's (previously empty)
  list. The `governed_run_plan.v1` contract, its field set, `plan_body_digest`
  and `artifact_byte_digest` semantics are unchanged, and `decision_id` is
  absent from the artifact.
- **Plan-artifact digests change value.** The artifact's `assembled_input_binding`
  now digests the snapshot's authoritative assembled bytes
  (`instruction + b"\n\nDATA:\n" + task_data`) instead of a second independent
  `f"{prompt}\n{data}"` assembly. This is the point of the slice — one assembly
  rule for digests and execution alike — and it means a digest recorded before
  this change will not match one recorded after. No schema version changes.
- **`--model` is now validated on the execution path too.** An unknown profile
  exits 1 rather than being ignored, because a governed decision requires a
  resolved context/model profile.
- **An execution-path privacy failure now reports bounded finding codes.** The
  seam's scan runs before `verify_packet`, so the message is the plan path's
  `finding_codes=` form rather than the scanner's free text. Exit code is
  unchanged at 2.
- **A local-only run whose ethical firewall triggers now exits 2 rather than 3**
  in the narrow case where the firewall triggers but deterministic risk is low.
  The decision forces `human_handoff`, and the pre-existing local-route guard
  treats a non-local route on a local-only packet as fail-closed. Both are
  non-executing terminal outcomes; exit 2 is the more conservative of the two.

### Repairs after the `909838f` acceptance review

Acceptance was withheld at `909838f` with three required repairs. All three are
implemented.

**Repair 1 — scope record.** No implementation allowlist was ever granted, so the
lifecycle record was corrected rather than reconstructed. See **Authority
record** in **Status**. The repair recorded the defect and named the dispositions;
the operator subsequently chose corrective ratification, which is recorded
verbatim there. The defect itself is preserved, not closed retroactively.

**Repair 2 — remaining decision-bearing recomputation removed.** Both offenders
are gone from the governed path.

*`ProjectSteward`.* The governed path now consumes `ethical_firewall` from the
decision and never calls `evaluate()`. **A claim in the previous revision of this
record was wrong and is corrected here:** it said removing the steward "would
silently drop the credit-allowance and energy gates." It would not.
`ProjectSteward.__init__` does `self.budgets = budgets or {}`, so `ProjectSteward()`
and `ProjectSteward(budgets={})` are the same object state; `token_credit_allowance`
is therefore always `0` on this path and the credit gate is unreachable, and the
energy and validation gates require a non-empty `completed_orders`, which
`run_task` never supplies. The only live output was the ethical firewall on the
prompt text — which the decision already carries as a first-class field. So there
was no gate to lose, and the recomputation was pure duplication. The reviewer's
reading was correct and mine was not.

*`SpecialistRouter.route_task`.* Not invoked at all on the governed path. Its
offload verdict is a second policy decision: two of its three offload branches
turn on a live `is_internet_available()` probe, which Resolved Question 1
forbids from answering what route a task receives, and its third branch — high
risk — the decision already expresses as a preferred `human_handoff`. Only its
two execution *parameters* were still needed, and both are pure functions of the
classification the decision carries. `client._governed_execution_parameters`
returns them, and a parametrized drift guard asserts they equal `route_task`'s
own tables for every category the deterministic classifier can emit. The
executed timeout is now exactly the `specialist_timeout_forecast_seconds` the
preview published, so the budget a reviewer reads is the budget the worker gets.

Consequences worth naming: `tc run` no longer emits a `specialist_offload_decision`
event, because no specialist offload decision is made; the CR-DD-018 evidence
contract is untouched and still governs the direct-library path. And a
medium-risk or large-context task no longer offloads on the basis of live
connectivity — which is the corrected architecture, not a lost feature.

*`verify_packet` remains,* and is the one survivor. It produces the
`VerifiedTaskPacket` type token the routing boundary requires, so it is
validation rather than recomputation, it cannot alter policy, and it is itself
one of the decision's `required_checks`.

**Repair 3 — ethical-firewall exit 3 restored.** A firewall handoff is a governed
terminal outcome, not an unavailable route, and it now returns `handoff_required`
with a `worker_result` record at exit 3 rather than being caught by the
local-only guard at exit 2. The distinguishing fact is the binding outcome, not
the route name: `human_handoff` bound as **primary** with a triggered ethical
firewall is a governed handoff; `human_handoff` reached as an envelope
**fallback** means the authorized route could not bind and stays fail-closed at
exit 2. Both cases are pinned by regression tests.

One residual asymmetry, flagged rather than changed, and since **settled as
out of scope for this slice** by the accepting reviewer: a **high-risk**
local-only run also routes to a primary `human_handoff` and still exits 2,
because `test_high_risk_local_only_fails_closed_exit_2` pins that as a CR-DD-009
exit-code contract and it was not a regression this slice introduced. It is
recorded as a separate discovery in **Open Discovery: High-Risk Terminal Exit
Class** below. Folding it in here would have turned a convergence slice into a
semantic rewrite.

### Where the implementation is narrower than the recommendation

One item remains, stated plainly rather than absorbed: **`verify_packet` still
runs inside `run_task`**, for the reason given under repair 2. Everything else
in this section in the previous revision has been removed by that repair.

The no-rebuild traps now assert: neither consumer invokes a second deterministic
classifier, context planner, resilience router, ethical-firewall evaluator, or
specialist-policy selector; no live connectivity probe runs on the governed
path; and neither consumer constructs a second snapshot or decision.

### Two mechanical accommodations

- **`sensitivity_requires_human_review` is not in `ROUTE_REASON_CODES`.** The
  router emits it; the closed decision vocabulary in `governed_decision.py` does
  not enumerate it, and that module is deliberately excluded from the allowlist.
  The decision body records the generic `policy_selected` for that case. The
  operator-facing plan still renders the router's own spelling, so no fidelity is
  lost where a reader looks for it. Admitting the code to the closed vocabulary
  is a candidate for a later CR, not a widening made here.
- **The worker system message is duplicated in `run_plan.py`.** The snapshot
  binds its digest and `engine.py` owns the literal, but `engine.py` is outside
  the allowlist. `tests/test_governed_consumption_parity.py` asserts the two
  spellings have not drifted.

### Gate satisfaction

| Gate | Status | Evidence |
|---|---|---|
| 1 — recorded decision on capability volatility | satisfied at proposal stage | **Resolved Question 1** |
| 2 — seam before the `planning` branch, consumed by both | satisfied | `tc_cli.py` step 2b; `test_execution_receives_the_seam_snapshot_and_decision`, `test_preview_projects_the_seam_decision_without_recomputing_it` |
| 3 — guard retired, not deleted; positive integrated-shape tests in the same change | satisfied | `tests/test_governed_consumption_parity.py`, including the two purity tests carried over verbatim from the retired guard |
| 4 — capability change after decision formation changes nothing | satisfied | `test_capability_change_after_decision_formation_changes_no_policy` |
| 5 — unavailable capability yields only an authorized fallback or a closed failure | satisfied | `test_unavailable_capability_falls_back_or_closes`, `test_binding_never_leaves_the_governed_envelope` |

### Verification

`python -m pytest tests/ -q` — **1802 passed, 6 skipped**, no failures. The count
rose from 1787 at `909838f` because the three repairs added 15 tests.

An earlier full run reported 13 `OSError` failures in
`tests/test_build_review_cli.py`. Those were Windows Smart App Control blocking
subprocess launch — environmental, not product failures — and the file passes
14/14 once it is disabled. Recorded here so a future reader does not
misattribute them.

The plan-artifact `assembled_input_binding` digest changes value across this
slice, for the reason given under **Behavioral changes**. Recorded explicitly so
a pre-CR-DD-012B digest that does not match a post-CR-DD-012B one is read as the
intended single-assembly change and never as evidence of corruption.

### Open Discovery: High-Risk Terminal Exit Class

Raised during CR-DD-012B implementation, **deliberately not resolved here**, and
carrying no authority of its own.

**Question.** Should the CLI outcome be determined by *why* `human_handoff` was
selected, or simply by the fact that the authoritative governed decision selected
terminal `human_handoff`?

Today the answer is "why". A firewall-triggered primary `human_handoff` exits 3
as a governed handoff; a high-risk primary `human_handoff` on a local-only packet
exits 2 as a fail-closed error. Both are primary bindings of the same terminal
route, and neither executes anything.

**The accepting reviewer's architectural lean**, recorded as a lean and not as a
decision:

```text
authoritative decision = human_handoff
              ↓
     no execution attempted
              ↓
       handoff_required
              ↓
            exit 3
```

with the safety reason carried in structured evidence rather than encoded
indirectly in the process exit class.

**Why it was not done here.** CR-DD-009 explicitly distinguishes exit 2 as a
privacy-or-safety fail-closed condition from exit 3 as a governed
`handoff_required` outcome, and a high-risk task routed to `human_handoff` sits
genuinely between those two meanings. The exit-2 behavior predates CR-DD-012B and
is already pinned by test. Changing it inside a convergence slice would have made
it a semantic rewrite.

**What it needs.** Its own read-only investigation against CR-DD-009, CR-125, the
high-risk tests, and downstream consumers of the exit class, before anything
changes.

## Objective

Make `tc run --plan` and ordinary `tc run` consume **one** immutable
`GovernedRunInputSnapshot` and **one** completed `GovernedDecision`, so that the
preview a reviewer reads and the decision execution honors are the same object
rather than two independently computed answers that happen to agree.

Explicitly **not** in the objective: a new decision contract, a new router, a
plan-artifact version, a durable observation schema, saved-plan execution, or any
new authority.

## Problem

The divergence is structural and currently observable in the code.

`tc_cli.tc_run` assembles arguments and maps privacy, then branches:

```text
if planning:
    plan = build_run_plan(prompt=..., data=..., sources=..., privacy=...)
    ... render / publish artifact ...
    return

privacy_metadata = privacy_metadata_for_run(...)
task_id = args.task_id or str(uuid.uuid4())
packet = TaskPacket(...)
```

The preview branch returns before the execution path constructs its packet.
Preview builds its own plan from the raw CLI arguments; execution builds a
separate packet from those same arguments and hands it to `TriageClient.run_task`,
which classifies, routes, and evaluates policy again. Two paths reach two answers
from one input. Nothing binds them.

Four concrete consequences follow:

- **Assembled bytes are reconstructed, not shared.** The preview artifact path
  assembles `f"{prompt}\n{data}"` for its digests while execution assembles the
  packet independently. Two assembly sites are two opportunities to drift.
- **Policy is evaluated twice.** Classification, privacy posture, context budget,
  and logical routing are computed once for preview and again for execution. They
  agree today by construction, not by contract.
- **A file may change between preview and execution.** Nothing pins the exact
  context bytes a reviewer saw to the bytes a worker receives — a TOCTOU gap
  the parent CR names directly.
- **Volatile runtime facts reach policy.** Since CR-DD-013, capability resolution
  sets the local availability booleans that `choose_resilience_route` reads. Route
  *policy* is therefore currently a function of a volatile observation. See
  **Resolved Question 1**; this was the sharpest design question in the slice
  and is now settled as a deliberate correction to CR-DD-013 semantics.

## Settled Questions

The parent CR deferred ten questions to this slice. Each is settled below as a
**recommendation**, subject to approval. Recording a recommendation grants
nothing.

### 1. Where the snapshot is constructed exactly once

**Recommendation.** One construction seam in `tc_cli.tc_run`, placed **after**
argument assembly and privacy mapping and **before** the `if planning:` branch.
Both paths descend from that single site; neither constructs a snapshot of its
own.

The seam performs, in order: normalize operator declarations, resolve the
canonical context/model profile, read each context source exactly once, and
construct the immutable snapshot. The preview branch and the execution path then
receive that snapshot as a parameter.

Two properties make the placement load-bearing rather than cosmetic:

- **Context sources are read exactly once per invocation**, at the seam. Neither
  branch may reopen a source afterward. This is what closes the TOCTOU gap; a
  seam placed after the branch would not.
- **The preview branch's early `return` is preserved.** Preview must not acquire
  packet construction, ledger wiring, task-ID generation, or backend
  construction. The seam moves snapshot construction earlier; it does not move
  execution concerns into preview.

The generated execution-correlation task ID stays where it is — created in the
execution path only, after the branch — because the parent CR requires it to stay
out of `decision_body` and `decision_id`. A run without `--task-id` must produce
the same decision ID as an otherwise identical run.

### 2. How both paths consume the same decision

**Recommendation.** The decision is built once, at the same seam, immediately
after the snapshot, by the existing pure builder. Both consumers then accept
`(snapshot, decision)` as parameters.

- `build_run_plan` changes from computing a plan out of raw arguments to
  **projecting** a completed decision into the existing plan dictionary. It calls
  no classifier, privacy evaluator, context planner, specialist-policy selector,
  or router.
- `render_run_plan` and the CR-DD-011 artifact builder are unchanged in contract.
  They continue to publish `governed_run_plan.v1` with its current fields,
  `plan_body_digest`, and `artifact_byte_digest` semantics, and the artifact
  remains non-executable and free of `decision_id`.
- `TriageClient.run_task` accepts the completed decision and consumes its
  policy outputs instead of re-deriving them.

A consumer may **validate** the decision and its bindings. Validation is not
permission to rebuild: a stale or inconsistent decision terminates the attempt
(see question 7). Silent recomputation is the specific failure mode this slice
exists to make impossible, so "revalidate and repair" is forbidden even where it
would be convenient.

Assembled execution bytes come from the snapshot. The artifact path stops
assembling `f"{prompt}\n{data}"` independently and reads the snapshot's
authoritative assembled bytes, so one assembly rule serves digests and execution
alike.

### 3. The internal `RuntimeObservation` boundary, and CR-DD-013

**Recommendation.** `RuntimeObservation` is a validated internal value created
**after** a valid decision exists. It never enters `decision_body` or
`decision_id`, is never persisted as its own schema, and lives only long enough
to validate envelope compliance and populate bounded evidence.

Its relationship to CR-DD-013 is settled explicitly below, because CR-DD-013
already ships a pre-route volatile observation — `CapabilityResolution`, resolved
in `tc_run` step 6b and passed into `run_task`. Two runtime-observation surfaces
that each claim to describe local availability would be a governance defect, not
a redundancy.

The recommendation is **subsumption without re-derivation**:

- `CapabilityResolution` remains the **sole** source of local capability
  evidence. CR-DD-012B adds no probe, no second resolver, and no independent
  availability check, and it does not modify `capability_evidence.py`.
- `RuntimeObservation` **carries** the already-resolved capability state as
  provenance — its state, evidence tier, source type, and applied freshness
  bound — rather than recomputing it.
- `RuntimeObservation` adds only what CR-DD-013 does not model: the selected
  envelope member, the actual backend/model binding, whether a fallback
  occurred, and bounded reason codes.
- The observed/configured/unknown distinction CR-DD-013 established is preserved
  verbatim. `RuntimeObservation` may not flatten `Unknown` into unavailable, may
  not relabel `Configured` as observed, and may not promote unknown evidence to
  health.

The other half of this relationship — whether capability may reach route policy
at all — is settled in **Resolved Question 1** below: it may not. Capability
constrains binding only, so `RuntimeObservation` carries it as an execution-time
constraint and never as a policy input.

### 4. Constraining actual backend selection to the envelope

**Recommendation.** The decision carries a preferred logical route and an
ordered, closed set of permitted fallback routes with the bounded condition under
which each becomes permitted. Runtime binding is a **filter over that set**, not
a selection over the space of backends.

Concretely, the binding step may select a member only when it is already present
in the envelope **and** its stated condition is observed. It may not synthesize a
route, reorder the envelope, append to it, widen egress, downgrade privacy, waive
human review, or enable cloud when the decision did not permit it. If no
permitted member is available, the attempt produces the existing governed
terminal outcome or fails closed — it does not fall through to an unlisted route.

The envelope is a constraint surface, not an injection surface. No CLI flag,
configuration value, environment variable, or caller argument may extend it.

### 5. Which events receive bounded `decision_id` linkage

**Recommendation.** Exactly two payloads, through the **existing open extension
point** that CR-DD-013 already used successfully:

- the `route_decision` payload built by `build_route_decision_payload`, and
- the `worker_result` payload built by `build_worker_result_payload`.

Both are open dictionaries appended through `TaskLedger.append_event`, which
enforces the persistent-privacy invariant without restricting the field set.
Adding a bounded `decision_id` string is additive and needs no schema-version
bump.

The closed `route-worker-ledger.v1` contract in `route_worker_ledger.py` rejects
unknown keys and is **not** modified and **not** used by this path. That
separation is the reason no new durable schema is created, and the proposal
depends on it holding — if implementation review finds it does not, that is a
stop condition requiring new approval, not a reason to widen the contract.

Linkage is evidence only. A present `decision_id` records which governed decision
an attempt descended from. It asserts nothing about approval, admission, quality,
acceptance, or successful human review, and no consumer may read it as such.

### 6. Direct-library compatibility

**Recommendation.** `TriageClient.run_task` accepts the completed decision
through a **new optional parameter**, following the CR-DD-013 precedent exactly:
when the parameter is absent — every existing library caller — the current
behavior is preserved unchanged, and no decision is constructed on the caller's
behalf.

This makes the behavioral change scoped to `tc run` and `tc run --plan`, which
always supply one.

The honest statement of what does change: **a caller who supplies a decision gets
different behavior from one who does not**, because policy then comes from the
decision rather than from in-method computation. That is the point of the slice.
The compatibility claim is narrow and should be stated plainly rather than as
"inert" — existing callers are unaffected because they pass nothing, not because
the two paths are equivalent.

`triagecore run-pipeline` remains local-only and continues to bypass the router;
this slice does not bring it into the governed path.

### 7. Exact fail-closed behavior

**Recommendation.** Every condition below terminates the attempt **before backend
construction or invocation**, with no backend call and no privacy-unsafe ledger
write:

| Condition | Behavior |
|---|---|
| Snapshot malformed, mutated, or internally inconsistent | terminate |
| Digest, length, or assembled-bytes mismatch | terminate |
| Decision malformed, noncanonical, or `decision_id` mismatch | terminate |
| Unsupported schema, normalization, policy, or canonicalization version | terminate |
| Missing required field or unknown field present | terminate |
| Execution received a snapshot other than the one governed | terminate |
| Decision-relevant configuration or policy binding changed | terminate |
| Logical route absent or inconsistent with its envelope | terminate |
| Runtime binding outside the permitted envelope | terminate |
| Privacy, egress, cloud, ethical-firewall, or human-review inconsistency | terminate |
| Downstream recomputation detected | terminate |

Three rules govern all of them:

- **Termination is not repair.** The system must not rebuild transparently. The
  attempt ends; a new invocation may produce a new snapshot and decision.
- **Staleness is binding-defined, not clock-defined.** It is determined by the
  immutable snapshot binding and decision-relevant facts — never by elapsed wall
  time, current file contents, or backend health.
- **Missing observation is not unavailability.** Consistent with CR-DD-013, an
  absent or unknown runtime observation resolves to unknown. It does not become
  an observed failure, and it does not become health.

### 8. Implementation file allowlist and focused tests

**Provisional as written; this became the bound list.** The implementation
instruction named no replacement, so the table below is what bounded the work.
Two paths beyond it were taken and are named in **Implementation Record**; the
deliberate exclusions below were all honored.

| Path | Change |
|---|---|
| `triage_core/tc_cli.py` | one snapshot/decision construction seam before the planning branch |
| `triage_core/run_plan.py` | project a completed decision; remove independent computation |
| `triage_core/client.py` | accept and consume the completed decision; optional parameter |
| `triage_core/routing/route_events.py` | bounded `decision_id` linkage, additive |
| `triage_core/runtime_observation.py` (new) | validated internal observation value |
| `tests/test_governed_consumption_parity.py` (new) | parity and no-rebuild traps |
| `tests/test_runtime_observation.py` (new) | envelope and observation separation |
| `tests/test_governed_consumption_failclosed.py` (new) | fail-closed matrix |
| this document, `CR-DD-012-shared-governed-run-decision.md`, `docs/current_backlog.md`, `docs/architecture/daily_driver_orchestrator_spec.md` | status |

Deliberately excluded: `triage_core/route_worker_ledger.py`,
`triage_core/run_plan_artifact.py`, `triage_core/capability_evidence.py`,
`triage_core/governed_run_snapshot.py`, `triage_core/governed_decision.py`,
`triage_core/task_ledger.py`, every CR-YK and CR-OC module, and
`docs/change/change_log.md`.

`tests/test_governed_decision_integration_absence.py` guards the CR-DD-012A
foundation as unintegrated and **will fail by design** the moment this slice
integrates it. Retiring or narrowing that guard is part of the implementation
approval, not a silent side effect — the guard is doing its job, and an
implementation that quietly deletes it should be rejected. Per approval gate 3,
retirement is permitted **only in the same change** that adds positive tests
proving one snapshot, one governed decision, and two projections; the coverage is
replaced, never merely removed.

Focused tests, by category:

**Parity.** One fixture matrix across local routes, cloud-eligible posture,
terminal handoff, ethical-firewall cases, fitting and over-budget context, and
multiple ordered sources; assertions that preview and execution receive the same
snapshot object and the same canonical decision body and ID.

**No-rebuild traps.** Instrumented proof that neither consumer invokes a second
classifier, privacy evaluator, context planner, specialist-policy selector, or
router, and that neither constructs a replacement snapshot.

**Mutation.** Any decision-relevant change — content, source order, declared
privacy, cloud intent, model profile — changes the decision ID and cannot reuse
the prior decision.

**Runtime separation.** Simulated backend-health changes alter the observation
while the decision ID is unchanged; an actual route outside the envelope is
rejected; runtime facts cannot widen egress, cloud, or human-review posture.

**Capability volatility (approval gate 4).** A negative test in which runtime
capability changes *after* decision formation and cannot change the decision ID,
the route policy, or the envelope.

**Unavailable capability (approval gate 5).** A negative test in which
unavailable capability produces only an authorized envelope fallback or a closed
failure — never an unauthorized route. This is the forbidden fourth outcome in
**Runtime Outcome Model**, asserted directly rather than assumed.

**Integrated shape (approval gate 3).** Positive tests proving one snapshot, one
governed decision, and two projections. These must land in the same change that
retires `tests/test_governed_decision_integration_absence.py`; deleting that
guard without replacing its coverage is a rejection condition.

**TOCTOU.** A context file modified after snapshot construction, with a trap
proving execution does not reopen it and the worker receives exact snapshot
bytes.

**Privacy.** Bounded linkage passes the persistent-privacy invariant; no raw
prompt, inline data, context content, source path, matched value, secret, or
model output appears in any payload.

**Regression.** Existing CR-DD-009, CR-DD-010, CR-DD-011, CR-125, CR-126, and
CR-DD-013 coverage stays green, including `governed_run_plan.v1` confirmation and
inspection and the absence of `decision_id` from v1.

Every test injects deterministically with no network, socket, subprocess, model
call, or real runtime.

### 9. Explicit exclusions

- confirmed-plan execution and `--confirmed-plan`;
- execution from a saved CR-DD-011 plan artifact;
- `governed_run_plan.v2` or any plan-artifact schema change;
- durable `RuntimeObservation` or `ExecutionRecord` schemas, and any new ledger
  event shape;
- new cloud authority, or inference of authority from intent, digest agreement,
  or plan confirmation;
- acceptance, resume, approval-and-resume, checkpoint, queue, scheduler, retry,
  or background execution;
- quality scoring, evaluator invocation, or quality-gate interpretation;
- new backends, providers, live health probes, circuit breakers, or capability
  discovery — G3 and G6 remain untouched;
- changes to `choose_resilience_route`'s decision logic;
- CR-YK and CR-OC changes of any kind;
- token-budget enforcement, compaction, or context rewriting;
- TriageDesk or mobile surfaces;
- readiness-score recalculation.

### 10. Stop point

*As proposed:* work stops when this proposal PR is open, and no implementation
begins until a separate human approval is recorded.

*As it now stands:* implementation was instructed and is complete, so this stop
point is spent. The next stop point is implementation acceptance, which is a
separate gate and is not granted. Work stops here.

## Invariants This Slice Must Preserve

- One immutable snapshot serves normalization, decision building, preview, and
  execution.
- Execution consumes exact snapshot bytes and never reopens or reconstructs
  source content.
- Preview and execution consume the same canonical decision.
- A decision is built once per attempt and never independently recomputed
  downstream.
- Decision identity is stable across runtime-health changes.
- Runtime observations cannot relax or rewrite governed policy.
- Actual routing stays inside the envelope.
- Human handoff remains terminal where current policy requires it.
- Linkage is evidence, never approval or acceptance.
- CR-DD-013's observed/configured/unknown distinction survives unchanged.

## Risks And Mitigations

- **Silent recomputation reintroduced by convenience.** The most likely
  regression is a consumer that revalidates and quietly rebuilds. Mitigated by
  instrumented no-rebuild traps rather than by review discipline alone.
- **The 012A integration guard is deleted rather than retired.** Mitigated by
  naming the guard in this proposal, so its removal is a reviewable decision.
- **Two runtime-observation surfaces.** Mitigated by subsumption without
  re-derivation, and by leaving `capability_evidence.py` off the allowlist so it
  cannot be quietly forked.
- **The envelope becomes an injection surface.** Mitigated by making binding a
  filter over a closed ordered set with no caller-supplied extension.
- **Preview acquires execution concerns.** Mitigated by preserving the early
  `return` and keeping ledger wiring, task-ID generation, and backend
  construction after the branch.
- **`decision_id` read as approval.** Mitigated by stating in the CR, the linkage
  fields, and the tests that it is evidence only.
- **Scope creep into G3/G6.** Mitigated by excluding circuit breakers, probes,
  and per-route backend separation outright.

## Resolved Questions

All three questions raised in the first draft of this proposal have since been
settled by recorded supervisor decision. They are resolved as design direction
only; **implementation remains unauthorized** and still requires its own
explicit approval and bounded file allowlist.

### 1. Capability volatility — RESOLVED: binding only

**Decision: capability resolution constrains execution binding, not
governed-decision formation.**

The architectural split is:

```text
Stable inputs
  -> governed decision
  -> deterministic route intent + envelope + decision ID

Volatile runtime observations
  -> execution binding
  -> execute, use an already-authorized fallback, or fail closed
```

Capability availability answers exactly one question: **"Can the
already-authorized plan execute right now?"** It must never silently answer
"What policy or route should this task receive?"

The reason is concrete rather than aesthetic. If capability enters decision
formation, identical task and context inputs produce different decision IDs
because a model server briefly disappeared, a tool was temporarily unhealthy, or
a probe record went stale. That converts operational weather into policy input
and weakens replay, comparison, audit, and caching — all four of which depend on
a decision ID being a function of governed inputs alone.

**The behavioral cost is real and is recorded plainly as a deliberate
correction to CR-DD-013 semantics, not as an implementation detail.** Today
`tc run` may choose a resilience route from live capability state, because
CR-DD-013's resolution sets `lm_studio_ok`, `local_fast_available`, and
`local_heavy_available` before `choose_resilience_route` reads them. Under this
decision it no longer may. A run whose local capability is unknown will produce
a governed decision naming local routes and then fail at binding, where today it
resolves to no local route earlier. Anyone reviewing this slice should
understand they are approving that change, stated in those terms.

Nothing here reopens CR-DD-013 or spends new authority on its behalf. Its
implementation and merge authority remain spent; this is a change in what
consumes its output, made under CR-DD-012B's own approval.

### 2. Classifier — RESOLVED: deterministic is authoritative

**Decision: the deterministic classifier is authoritative for all
decision-relevant fields.**

A model-assisted classifier may remain **advisory** — producing suggestions,
confidence notes, or review evidence — but it may not alter the governed result.
It may become decision-bearing only if its normalized output is later promoted
to an explicit, stable decision input by a separate CR, which this slice does
not do.

This keeps builder classification free of any model, network, socket, or
subprocess call, as the parent CR requires, without silently deleting the
model-assisted path.

### 3. `build_run_plan` signature — RESOLVED: coherence over compatibility

**Decision: preserve the signature only if it still represents one coherent
projection from the shared snapshot and governed decision.**

A backward-compatible signature is not worth keeping if it leaves callers able
to recompute context, route, or envelopes independently. A narrow signature
break is preferable to preserving an attractive second integration path, which
is precisely the failure mode this slice exists to close. Repository inspection
at implementation time determines which applies; either outcome stays inside the
provisional allowlist.

## Runtime Outcome Model

The governed decision must encode the allowable execution envelope richly enough
to support exactly three outcomes:

1. **Primary binding succeeds** — execute the selected route.
2. **Primary unavailable, authorized fallback exists** — bind to that fallback
   **without changing the governed decision**, its ID, its route policy, or its
   envelope.
3. **No authorized binding exists** — fail closed and require a new decision or
   explicit operator action.

There is a fourth outcome, and it is the one this slice exists to make
impossible:

> **Forbidden:** runtime capability resolution inventing a different route that
> the governed decision never authorized.

Any implementation in which a runtime observation can produce a route outside
the envelope — by synthesis, reordering, widening, or fallback to an unlisted
option — has failed the slice regardless of what its tests report.

## Implementation Approval Gates

The five gates bind at **two different stages**, and conflating them would be a
timing error: gates 3 through 5 assert properties of code that does not exist
yet, so they cannot be satisfied before the authority to write that code is
granted.

The governance model is therefore two-stage:

| Stage | What it grants | Gates |
|---|---|---|
| **Permission to implement** | a bounded implementation approval with an explicit file allowlist and mandatory test obligations | gates 1–2 must already be satisfied; gates 3–5 must be **bound by** the approval |
| **Permission to accept** | acceptance, merge, and closeout of the implementation | gates 3–5 must **actually pass** |

An approval that grants permission to implement without binding gates 3 through
5 as obligations is incomplete, and an implementation that reaches acceptance,
merge, or closeout without them passing must be rejected.

**Stage reached.** Permission to implement was given and is spent. Gates 3
through 5 were treated as bound obligations and now pass — see **Gate
satisfaction** in **Implementation Record**. Permission to accept has not been
given; gates passing is evidence for that decision, not the decision.

### Proposal-stage preconditions — satisfied

1. **A recorded decision on capability volatility and its CR-DD-013 behavioral
   consequence.** Satisfied above: binding-only, with the behavioral change to
   current `tc run` route selection stated explicitly rather than absorbed.
2. **An explicit statement that the seam is constructed before the `planning`
   branch and consumed by both preview and execution.** Satisfied in **Settled
   Question 1**: the seam sits after argument assembly and privacy mapping and
   before `if planning:`, context sources are read exactly once there, and both
   paths receive `(snapshot, decision)` as parameters.

### Implementation obligations — bound at approval, satisfied before acceptance

3. **[satisfied] Replacement of the integration-absence guard with positive
   tests** proving one snapshot, one governed decision, and two projections —
   **not merely deletion of the old guard.** `tests/test_governed_decision_integration_absence.py`
   may be retired only in the same change that adds positive tests asserting
   the integrated shape. An implementation that deletes the guard without
   replacing its coverage is rejected.
4. **[satisfied] A negative test where runtime capability changes after decision
   formation** and cannot change the decision ID, the route policy, or the
   envelope.
5. **[satisfied] A negative test showing unavailable capability causes only an
   authorized fallback or a closed failure** — never an unauthorized route.

Gates 3 through 5 are additive to the focused tests listed in **Settled
Question 8**. Satisfying gates 1 and 2 grants nothing on its own: implementation
authority still requires a separate explicit approval and its own bounded file
allowlist, and this document is not that approval.

## Dependencies And Sequencing

- Depends on merged CR-DD-012A (`bccaaad`) for the snapshot and decision
  contracts, consumed without modification.
- Depends on merged CR-YK-002 (`5155bbb`) only for the sequencing gate the parent
  named; this slice adds no claiming, capability, or authorization behavior and
  imports no CR-YK module.
- Interacts with merged CR-DD-013 (`98df9c1`) through Resolved Question 1, which
  deliberately corrects what consumes its capability resolution: capability
  constrains execution binding and no longer reaches route policy. Nothing here
  reopens CR-DD-013, whose implementation and merge authority remain spent; the
  correction is made under CR-DD-012B's own approval and is a change to the
  consumer, not to `capability_evidence.py`.
- Precedes any confirmed-plan execution CR, `governed_run_plan.v2`, and durable
  observation/execution schemas, none of which this slice authorizes.
- Does not block and is not blocked by G3 (per-route backend bindings) or G6
  (circuit breakers).
