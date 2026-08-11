# CR-DD-017: Blocked Local-Only Route Evidence Parity

## Status

- **Status:** Proposed (requirements contract, merged to `main`); implementation
  candidate in review under a separate, single-slice implementation-authority grant.
  This status line does not assert merge, completion, or closeout of the
  implementation — see the implementation PR opened from this branch for the diff,
  test results, and CI outcome.
- **Type:** Evidence / Observability (Governance-kernel — evidence and reconstruction).
- **Priority:** Research backlog. Downstream of the CR-DD-016 investigation, which
  surfaced this gap while reconciling that CR's own motivating evidence; does not
  reopen or amend CR-DD-016, CR-DD-013, or any routing/capability-resolution CR.
- **Implementation authority:** Single-slice implementation authority explicitly
  granted by the human operator on 2026-08-11, scoped to the Provisional
  Implementation Allowlist below. The grant covers preparing a reviewable
  implementation candidate — branching, the bounded edits, tests, staging, commit,
  push, and opening the implementation PR. It does not include merge authority, which
  remains a separate, later human decision. The grant was amended once, in review, to
  add exactly one additional path (`tests/test_tc_run_cli.py`) to the allowlist — see
  that section for why.
- **Human approval requirement:** Explicit human review and approval of this Change
  Request is required before any implementation begins. For this Change Request,
  approval records acceptance of the requirements contract but does not by itself
  grant implementation authority. A separate, explicit human implementation-authority
  grant scoped to the Provisional Implementation Allowlist is required before code
  changes begin. Merge of the implementation PR is a distinct, still-pending human
  decision.

## Scope

The `route_audit` ledger event emitted from `TriageClient.run_task`
(`triage_core/client.py`) when a `local_only` packet's resilience-routed selection is
not in the explicitly local-safe set (`local_heavy`, `local_fast`, `deterministic`) —
the branch that raises `LocalRouteUnavailableError` with
`reason_code="ambiguous_or_remote_route"`. Nothing else.

## Problem Statement

When `choose_resilience_route` selects a route outside the local-safe set for a
`local_only` packet, `client.py` writes a `RouteDecisionAudit` event
(`reason_code="ambiguous_or_remote_route"`) and raises before ever calling
`build_route_decision_payload()` or appending a `route_decision` event. Both exist,
and both are used two branches later on the "allowed" path — they are simply never
reached on this one.

`RouteDecisionAudit` itself (`triage_core/route_audit.py`) carries only `privacy_level`,
`is_local_only`, `recommended_route`, `selected_backend`, `decision`, and `reason_code`.
It has no field for `task_class`, `task_sensitivity`, or capability availability. The
router already computes exactly this information: `ResilienceRouteDecision.reason` is
one of two values whenever a `local_only` packet is blocked this way —
`"sensitivity_requires_human_review"` (the sensitivity gate, checked first and
independent of capability) or `"no_reliable_automated_route_available"` (every local
candidate exhausted, which given `tc run`'s fixed `memory_headroom_mb`/failure-count
defaults means `lm_studio_ok` was false). That value, plus `task_class`,
`task_sensitivity`, `lm_studio_ok`, `local_heavy_available`, and `local_fast_available`,
is exactly what `build_route_decision_payload()` records — but only on the branch that
never executes here.

The result: two structurally different causes — a sensitivity-driven handoff that would
have happened regardless of capability, and a capability-exhaustion handoff that
wouldn't have happened with a working local backend — become indistinguishable in the
durable ledger. Reconstructing which one occurred requires re-deriving it from source
code and any incidentally-present, separately-recorded `runner_selected` evidence,
rather than reading it directly off the decision that was actually made.

## Motivating Evidence

- **CR-DD-016's corrective amendment** (PR #156): the Aug-8 trial motivating that CR's
  original draft was misdiagnosed as a capability-absence block. Its `runner_selected`
  event showed a fully-available capability resolution; the actual cause was only
  reachable by re-deriving `choose_resilience_route`'s internal logic from source,
  because the `route_audit` event that was written carries no causal field and no
  `route_decision` event was written at all. This CR repairs the exact evidence gap that
  produced that misdiagnosis.
- **The existing test suite has the same blind spot it would need to prove is closed.**
  `tests/test_route_decision_audit.py::test_local_only_remote_route_blocked_audit` and
  `::test_ambiguous_route_blocked_audit` both mock `choose_resilience_route` directly and
  inject `ResilienceRouteDecision(reason="", ...)`. Neither test has ever exercised what
  real `.reason` value flows through for either cause, because the mock discards it
  before the assertion.

## Determination

**Evidence-fidelity gap, not a routing-behavior gap.** No routing decision, capability
resolution, or privacy-enforcement outcome is wrong; `ambiguous_or_remote_route`
correctly and accurately describes the policy gate that fired (a `local_only` packet
received a non-local-safe route). What's missing is the causal layer underneath that
policy gate, which the router already computed and which the evidence schema's own
reconstruction-and-human-interpretation design goal treats as a first-class concern.
Persisting a decision that was already made and already labeled internally is a
governance/evidence-contract decision, not a "just add a field" patch — hence a CR
rather than an unreviewed fix.

## Objective

Give blocked local-only routing decisions the same `route_decision` evidence fidelity
already available to allowed routing decisions, without changing routing behavior,
capability resolution, or privacy enforcement in any way.

## Invariants Preserved

This CR MUST NOT weaken, and its acceptance criteria must not be satisfiable in a way
that weakens, any of the following:

1. `route_audit.reason_code` on this branch remains exactly `ambiguous_or_remote_route`,
   byte-identical to current behavior — it is not renamed, split, or parameterized.
2. No routing decision, capability resolution, or privacy-enforcement outcome changes
   for any input.
3. When required evidence persistence succeeds, `LocalRouteUnavailableError` continues
   to be raised under the same routing/privacy conditions and with the same message.
   An evidence-persistence or signing failure MUST NOT permit worker execution or fall
   through to an allowed route; such an integrity failure may propagate rather than
   being masked as `LocalRouteUnavailableError`.
4. Distinguishing `Unknown` from `ObservedUnavailable` capability evidence remains the
   job of the existing capability-evidence payload fields carried on `route_decision`,
   not a new reason-code vocabulary on `route_audit`.
5. No new ledger event type is introduced; only an existing event type
   (`route_decision`), already used on the allowed path, is emitted on a path that
   currently skips it.
6. Blocked-route evidence MUST use the existing `_append_route_decision_event` path
   rather than a direct `ledger.append_event(...)` call, preserving the same optional
   route-decision signing behavior as the allowed path. `_append_route_decision_event`
   is not a convenience wrapper: when a signing registry and agent ID are supplied it
   switches to `ledger.append_signed_route_decision_event(...)`; a direct append would
   silently degrade evidence authenticity on exactly the branch this CR newly covers.

## In Scope

1. On the `selected_route not in {"local_heavy", "local_fast", "deterministic"}` branch
   in `client.py`:
   - Preserve the existing `RouteDecisionAudit` construction and
     `reason_code="ambiguous_or_remote_route"` exactly as-is.
   - Build the `route_decision` payload via the existing
     `build_route_decision_payload(resilience_input, resilience_decision, ...)` — the
     same call already made on the allowed branch, using values already computed on
     this branch.
   - Persist that payload via the existing `_append_route_decision_event` helper —
     never a direct `ledger.append_event(..., "route_decision", ...)` call, which would
     bypass the helper's optional-signing switch to
     `ledger.append_signed_route_decision_event(...)`. When evidence persistence
     succeeds, evidence order is exact: one `route_audit`, then one `route_decision`,
     then the `LocalRouteUnavailableError` raise. No `worker_result` is synthesized.
   - Change no routing, privacy-enforcement, or worker-execution control flow. The only
     newly reachable exceptional outcome is the evidence-persistence/signing failure
     permitted by Invariant 3, which propagates without worker execution or
     fallthrough.
2. **Tests.** At least two end-to-end routing tests in `tests/test_route_decision_audit.py`
   that exercise the real `choose_resilience_route` (not a mock returning
   `reason=""`):
   - **Sensitivity case:** a usable local capability plus high task sensitivity resolves
     to `human_handoff`; the ledger contains `route_audit.reason_code:
     ambiguous_or_remote_route` and `route_decision.reason:
     sensitivity_requires_human_review`.
   - **Capability-exhaustion case:** normal sensitivity plus no usable local capability
     resolves to `human_handoff`; the ledger contains the same `route_audit` code, but
     `route_decision.reason: no_reliable_automated_route_available`, with capability
     evidence fields sufficient to reconstruct whether the underlying state was
     `Unknown` or `ObservedUnavailable`.
   - Existing tests in this file continue to pass; where a test's own assertions need
     updating to account for the new `route_decision` event now being present (for
     example, an event-count assertion that previously assumed only `route_audit` was
     written on this branch), the update may only make the assertion match reality — it
     may not weaken or remove any existing `reason_code` assertion.
   - **Evidence-persistence-failure case:** with `_append_route_decision_event` (or the
     ledger call it makes) forced to raise, prove no worker executes, no `worker_result`
     event is synthesized, and control does not fall through to an allowed route or a
     masked `LocalRouteUnavailableError`; the failure propagates instead. No
     signing-specific sub-case is required.

## Explicitly Out of Scope

- **No change to `route_audit.reason_code` vocabulary.** `ambiguous_or_remote_route`
  stays exactly as-is; no split, rename, or parameterization.
- **No new reason code distinguishing `Unknown` from `ObservedUnavailable`** at the
  `route_audit` layer. That distinction already exists on `route_decision`'s capability
  fields; duplicating it into a second vocabulary would create drift between the two,
  not resolve it.
- **No change to `choose_resilience_route`, `resolve_capability`, or any other
  routing/capability-resolution logic.** This CR persists a decision already made; it
  does not change how any decision is made.
- **No change to the sibling `offload_recommended_for_local_only` branch** immediately
  below this one in `client.py`, which raises before any `route_decision` payload is
  built for the same structural reason. That branch has an identical gap and is a
  plausible follow-up candidate, but bundling it here would mix two separate
  acceptance-evidence surfaces into one CR; it is named here and left untouched.
- **No change to privacy enforcement, execution gating, or whether execution
  proceeds.**
- **No implementation authority of any kind.** Acceptance of this CR does not authorize
  implementation; a separate, explicit human implementation-authority grant, scoped to
  the Provisional Implementation Allowlist, is required before any code change begins.

## Provisional Implementation Allowlist

If this requirements contract is separately approved, the bounded implementation is
authorized to touch exactly these four paths — nothing else:

```text
triage_core/client.py
tests/test_route_decision_audit.py
tests/test_tc_run_cli.py
docs/change/requests/CR-DD-017-blocked-route-evidence-parity.md
```

Within `triage_core/client.py`, the change is limited to the
`ambiguous_or_remote_route` branch described above: adding the
`build_route_decision_payload` call and `_append_route_decision_event` call already
used elsewhere in this same function, in the same form. No other branch, function, or
file changes. The CR file itself would receive only implementation/status/evidence
updates.

**`tests/test_tc_run_cli.py` was added to this allowlist during implementation, by an
explicit scope-amendment grant, not assumed at drafting time.** Running the full test
suite against the candidate implementation surfaced one pre-existing test,
`test_early_local_block_records_binding_issue_on_runner_selected`, whose purpose is
unrelated to this CR (it verifies `runner_selected` records capability
declared-route-classes and binding issues on an early local-only block) but which also
carried an incidental negative assertion — `assert not any(event["event_type"] ==
"route_decision" for event in events)` — asserting the absence of exactly the evidence
this CR adds. The fix touches only that one assertion line, inverting it to `assert
any(...)`; no other assertion, fixture, or behavior in that test changed.

Named exclusions — files a future implementer might be tempted to touch, and explicitly
must not, because this CR persists existing evidence rather than changing what is
decided:

```text
triage_core/routing/resilience_router.py
triage_core/routing/route_events.py
triage_core/capability_evidence.py
triage_core/route_audit.py
```

This allowlist is provisional and proposed only. Listing it here grants no
implementation authority; a separate, explicit approval is still required before any
file on it may be modified.

## Acceptance Criteria

- [x] `route_audit.reason_code` for the `ambiguous_or_remote_route` branch remains
      exactly `ambiguous_or_remote_route`, unchanged from current behavior.
- [x] When evidence persistence succeeds, a `route_decision` ledger event is persisted
      on this branch, via the existing
      `build_route_decision_payload`/`_append_route_decision_event` path, before
      `LocalRouteUnavailableError` is raised.
- [x] For an `ambiguous_or_remote_route` block where evidence persistence succeeds,
      evidence order and integrity are exact:
      emit exactly one existing `route_audit` event, then exactly one existing
      `route_decision` event via `_append_route_decision_event` (never a direct
      `ledger.append_event(..., "route_decision", ...)` call, so optional route-decision
      signing is preserved unchanged), then raise `LocalRouteUnavailableError`. No
      `worker_result` event is synthesized, because no worker was attempted.
- [x] A sensitivity-case end-to-end test (real `choose_resilience_route`, not mocked)
      proves: usable local capability + high sensitivity → `human_handoff`; ledger shows
      `route_audit.reason_code=ambiguous_or_remote_route` and
      `route_decision.reason=sensitivity_requires_human_review`.
- [x] A capability-exhaustion-case end-to-end test (real `choose_resilience_route`, not
      mocked) proves: normal sensitivity + no usable local capability → `human_handoff`;
      ledger shows the same `route_audit` code, `route_decision.reason=
      no_reliable_automated_route_available`, and capability evidence fields sufficient
      to reconstruct whether the state was `Unknown` or `ObservedUnavailable`.
- [x] No distinct reason codes are introduced for `Unknown` vs `ObservedUnavailable`.
- [x] No change to `choose_resilience_route`, `resolve_capability`, capability
      resolution, or any routing decision.
- [x] The sibling `offload_recommended_for_local_only` branch is not modified and is not
      referenced as resolved by this CR.
- [x] When `_append_route_decision_event` (or the ledger call it makes) raises on this
      branch, no worker executes, no `worker_result` event is synthesized, control does
      not fall through, and the failure propagates rather than being masked as
      `LocalRouteUnavailableError`.
- [x] All six invariants listed above remain true and unmodified by this slice.
- [x] The full test suite passes on the candidate, including the one pre-existing test
      (`tests/test_tc_run_cli.py::test_early_local_block_records_binding_issue_on_runner_selected`)
      whose stale negative assertion required the one-line scope-amendment fix recorded
      in the Provisional Implementation Allowlist above.

## Non-Goals

- Redesigning the reason-code vocabulary for blocked local-only routes.
- Adding a distinguishing reason code for capability sub-states
  (`Unknown` vs `ObservedUnavailable`).
- Extending this evidence-parity fix to the `offload_recommended_for_local_only` branch.
- Any change to routing, capability resolution, or privacy-enforcement behavior.
- Any change to `route_audit.reason_code` values or vocabulary.

## Sequencing

Downstream of CR-DD-016 — the investigation that surfaced this gap while reconciling
that CR's Aug-8 motivating-evidence misdiagnosis. Independent of CR-DD-015A/B (the
separate evidence-fidelity lane proposed for `local_heavy` timeout/failure-
classification evidence). Per `docs/operations/daily-use-evidence-window-2026-08-02.md`,
neither `CR-DD-015A` nor `CR-DD-015B` exists as a record, and CR-DD-015A's drafting is
not authorized — it remains proposed only, pending separate authorization to draft.
This CR does not draft, authorize, or depend on that sequence. Also independent of
Tracks B and C named in
CR-DD-016 (classifier terminal fallback; `privacy_level` normalization) — related in
spirit (all are evidence-fidelity gaps) but each independently scoped, evidenced, and
authorized, per the standing correction-lane sequencing rule: do not bundle unrelated
evidence-fidelity fixes into one CR merely because they share a category.
