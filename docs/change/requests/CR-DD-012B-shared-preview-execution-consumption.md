# CR-DD-012B: Shared Preview/Execution Consumption

## Status

**Proposed; documentation only; implementation unauthorized.**

This document is a proposal. It grants no implementation authority, no file
allowlist, and no execution authority. Work may begin only after a separate,
explicit human implementation approval is recorded, and that approval must name
its own bounded file allowlist. Recording a recommendation here is not that
approval.

The sequencing prerequisites are satisfied:

- **CR-DD-012A** is complete and merged through PR #107 as `bccaaad`. The
  immutable snapshot and canonical decision contracts exist as an internal,
  non-integrated foundation that no public command consumes.
- **CR-YK-002** is complete and merged through PR #117 as `5155bbb`, satisfying
  the atomic-claiming prerequisite the parent CR named.

Satisfying a prerequisite is not approval. CR-DD-012B remains blocked on its own
explicit gate, and the merge of either foundation is not that gate.

This CR is scoped against `main` at `8bfb547`. Its parent architecture is
`CR-DD-012-shared-governed-run-decision.md`, which remains authoritative on the
contract model; this document settles only the consumption questions the parent
deferred to the implementation slice.

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
  **Open Question 1**; this is the sharpest unresolved design question in the
  slice and the proposal does not paper over it.

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

Its relationship to CR-DD-013 must be settled explicitly, because CR-DD-013
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

The unresolved half of this relationship is **Open Question 1** below, and it is
genuinely unresolved rather than deferred for tidiness.

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

**Provisional. Not authorized by this proposal.** A separate implementation
approval must confirm or replace this list. Any path beyond it is a stop
condition.

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
implementation that quietly deletes it should be rejected.

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

Work stops when this proposal PR is open. No implementation begins until a
separate human approval is recorded that names its own bounded file allowlist.
This document is not that approval, and neither is the merge of this proposal.

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

## Open Questions

These are genuinely unresolved and must be settled **before** implementation
approval, not during implementation.

1. **Does capability evidence constrain route policy or only route binding?**
   This is the load-bearing question of the slice. Today, CR-DD-013's resolution
   sets `lm_studio_ok`, `local_fast_available`, and `local_heavy_available`, which
   `choose_resilience_route` reads to choose a route — so a volatile observation
   currently participates in producing route *policy*. CR-DD-012B requires the
   logical route and envelope to come from the governed decision and to be stable
   across runtime-health changes. Those two facts cannot both hold unchanged.

   Two candidate resolutions, with materially different consequences:

   - **(a) Capability constrains binding only.** The decision computes the
     logical route and envelope from policy alone, assuming no capability
     knowledge; capability then filters which envelope member is bound at
     runtime. This preserves decision stability cleanly, but changes current
     `tc run` behavior: a run whose local capability is unknown would produce a
     decision naming local routes and fail at binding, where today it resolves
     to no local route earlier.
   - **(b) Capability is a decision-relevant input.** The resolution enters the
     snapshot binding and therefore the decision ID. This preserves today's
     routing behavior exactly, but breaks the parent CR's invariant that
     decision identity is stable across runtime-health changes — the same
     packet would produce different decision IDs before and after a probe went
     stale.

   The proposal recommends **(a)**, because the parent invariant is the more
   expensive one to give up and because (b) makes decision IDs non-reproducible
   for reviewers. But (a) is a real behavioral change to a merged, closed-out CR
   and must be approved on that basis rather than absorbed as an implementation
   detail. It is not settled here.

2. **Does the deterministic classifier fully replace the model-assisted one?**
   The parent CR requires builder classification without a model, network, or
   socket call, while ordinary `tc run` may currently use the model-assisted
   classifier. Whether execution loses that capability, or the model-assisted
   result becomes a non-decision-bearing annotation, is unresolved. It affects
   observable classification behavior and needs an explicit decision.

3. **Does `build_run_plan`'s current signature survive?** Projecting a decision
   may not need `prompt`, `data`, and `sources` at all. Whether the function is
   re-signatured or kept compatible for existing callers affects the allowlist,
   and repository inspection at implementation time should settle it rather than
   a guess here.

## Dependencies And Sequencing

- Depends on merged CR-DD-012A (`bccaaad`) for the snapshot and decision
  contracts, consumed without modification.
- Depends on merged CR-YK-002 (`5155bbb`) only for the sequencing gate the parent
  named; this slice adds no claiming, capability, or authorization behavior and
  imports no CR-YK module.
- Interacts with merged CR-DD-013 (`98df9c1`) through Open Question 1. Nothing
  here reopens CR-DD-013, whose implementation and merge authority are spent.
- Precedes any confirmed-plan execution CR, `governed_run_plan.v2`, and durable
  observation/execution schemas, none of which this slice authorizes.
- Does not block and is not blocked by G3 (per-route backend bindings) or G6
  (circuit breakers).
