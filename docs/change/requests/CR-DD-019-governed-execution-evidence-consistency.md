# CR-DD-019: Governed Execution Evidence Consistency

## Status

- **Status:** Implementation accepted by the operator on 2026-10-31 after the read-only re-review confirmed both findings resolved. Acceptance is bound to the uncommitted candidate identified below. Latest recorded verification: 241 focused passes; full offline suite 2,605 passed, 6 skipped, 1 previously confirmed baseline failure. Commit and draft-PR preparation are now separately authorized below; merge, release, and closeout remain unauthorized.
- **Type:** Evidence / Observability (Governance kernel: evidence and reconstruction).
- **Documentation authority (historical):** The operator first authorized proposal preparation, then explicitly requested: "Go ahead with the design review for CR-DD-019. Settle the field names and validation rules, keeping this documentation-only. Don't change code or run models or backends." That review authorized changes to this CR document only. The subsequent implementation grant is recorded separately below.
- **Implementation authority:** On 2026-10-31, after the settled design and its exact six-file scope were presented, the operator instructed: "Implementation granted". This authorizes implementing this design in the six paths under Implementation Allowlist below, with offline verification. It does not authorize a commit, PR, merge, release, or closeout. The previous no-model/no-backend restriction remains in force; execution boundaries in tests are stubs or test doubles only.
- **Corrective authority:** Following the read-only implementation review, the operator instructed on 2026-10-31: "Go ahead and fix both CR-DD-019 findings: reject null fields during shape validation, compare validator and producer vocabularies, and rerun offline checks. Stay within the six-file scope. Don't run models or backends." This authorizes the two named corrections and verification within the same six paths; no broader implementation or acceptance is inferred.
- **Implementation acceptance:** On 2026-10-31 the operator replied "Accepted" directly to the read-only re-review recommendation to accept CR-DD-019's implementation. This records implementation acceptance of the corrected six-file candidate, not an inference from passing tests. The snapshot and remaining boundaries are recorded under Implementation Acceptance Record below.
- **Commit and draft-PR authority:** On 2026-10-31 the operator instructed: "Go ahead and prepare the commit and draft PR for CR-DD-019. Stay within the six-file scope. Don't merge, release, or run models or backends." This authorizes creating the review branch, committing exactly the six scoped files, pushing that branch, and opening a draft PR in `coreytshaffer/TriageCore` targeting `main`. It does not authorize a merge, release, closeout, additional implementation changes, or model/backend execution.
- **Human approval requirement:** Implementation acceptance and this bounded commit/draft-PR instruction are recorded above. Merge, release, and closeout remain separate under [change management](../change_management.md). Verification evidence grants no additional authority.
- **Evidence baseline:** Local `main` at `ffb47b1aafd44e43347e3c0b39a6f0f00a6460b4`, inspected 2026-10-30. The checkout was clean before proposal preparation. The findings below are from static source and test inspection; no application imports, tests, models, or backends were run.
- **Design-review baseline:** The same `main` revision above was rechecked on 2026-10-31. This proposal was the sole existing untracked change; no tracked changes were present. Review used source/test reads and static inspection only.
- **Namespace:** Local Markdown CR references and request filenames were censused before allocation. The existing daily-driver sequence ended at CR-DD-018; an exact repository search found no CR-DD-019 reference before this file was created. This is a local allocation, not a claim about uninspected remote branches or issues.

## Objective and Scope

Make the existing governed `tc run` execution evidence preserve the risk posture of its completed `GovernedDecision` and explain the actual binding selected from its closed fallback envelope.

This slice is limited to projecting already-established decision and runtime-observation facts into the existing open `route_decision` and `worker_result` payloads. It does not construct another decision, infer another cause, or change whether execution proceeds. Both the allowed path and the existing local-only blocked path must use the same evidence projection.

## Motivating Evidence

Source line numbers below are pinned to the baseline above, not future edits.

1. **The high-risk override is lost in execution evidence.** The construction seam applies `sensitivity=high` when danger is high ([run_plan.py:359-392](../../../triage_core/run_plan.py#L359)). Execution rebuilds an input from classification and capability ([client.py:219-225](../../../triage_core/client.py#L219)); that mapping gives docs, bugfix, and refactor categories low sensitivity ([client.py:794-821](../../../triage_core/client.py#L794)). The payload then persists this reconstructed value as `task_sensitivity` ([route_events.py:238-242](../../../triage_core/routing/route_events.py#L238)). A docs task elevated to high risk can therefore have a high-risk decision and low-sensitivity route evidence. This establishes an evidence defect, not an execution bypass.
2. **The preferred policy reason is presented beside the actual fallback without its binding cause.** Execution selects the observation's route and model but uses `decision.policy.route_reason_codes[0]` as its reason ([client.py:230-251](../../../triage_core/client.py#L230)). Route and worker payloads persist that reason ([route_events.py:243-249](../../../triage_core/routing/route_events.py#L243), [route_events.py:288-294](../../../triage_core/routing/route_events.py#L288)). An unavailable `local_heavy` route followed by an authorized `local_fast` binding can retain a reason asserting local-heavy availability. The observation already contains the ordered causes; they are not carried into these payloads ([runtime_observation.py:249-276](../../../triage_core/runtime_observation.py#L249)).
3. **There is existing bounded evidence to reuse.** `RuntimeObservation` already defines a closed outcome and reason vocabulary ([runtime_observation.py:41-56](../../../triage_core/runtime_observation.py#L41)). Its fallback test asserts `local_capability_unavailable` and `bound_authorized_fallback` ([test_runtime_observation.py:165-175](../../../tests/test_runtime_observation.py#L165)). This is source/test evidence of the existing contract, not a current test result.

## Requirements Contract

1. **Single origin.** Consume the exact verified decision and validated runtime observation used by the attempt. Do not call a classifier, danger detector, steward, specialist selector, router, capability resolver, connectivity probe, or backend to reconstruct evidence.
2. **Risk and sensitivity remain distinct.** Preserve `decision.policy.risk_posture` losslessly. For governed evidence, retain the existing category-to-sensitivity mapping with the seam's high-risk override: high risk must yield `task_sensitivity=high`. Do not equate all sensitivity values with risk; an architecture task may have low detected risk and medium sensitivity.
3. **Policy reason and binding cause are distinguishable.** Preserve the existing governed `reason` as the policy reason for compatibility, and document that it explains the preferred policy route, not observed availability of the selected fallback. Carry the actual observation outcome and ordered reason codes separately. No cause may be parsed from free text or synthesized from the selected route.
4. **Additive, bounded payloads.** Use the existing open payload extension point. The three new keys are `governed_risk_posture`, `binding_outcome`, and `binding_reason_codes`, with the exact rules below. The operator authorized implementation against this settled technical contract; acceptance of the result is separate. Values come from the existing bounded vocabularies. Preserve reason-code order and copy the accepted governed extension from the route payload to any worker payload this attempt already produces. Validate the route extension before route persistence or worker invocation; validate it again before worker forwarding. Worker-stage failure may occur after execution, as specified below. Do not silently repair malformed evidence. This does not promise removal of a bounded audit event that already precedes payload construction.
5. **Linkage and privacy.** Keep the existing `decision_id` intact, require governed extension data to carry valid decision linkage, and preserve capability provenance. Add no prompts, data, source paths, output, raw exception text, timestamps, or entire snapshots/observations. The new evidence grants no approval or execution authority.
6. **Compatibility.** Direct `run_task` callers supplying no decision retain existing behavior and payloads; no governed metadata or synthetic decision ID is added. No new event type, durable observation record, closed ledger schema, schema-version change, or signing path is introduced. Existing signing calls and their provenance-only meaning remain unchanged.
7. **Control flow stays fixed.** Preserve decision identity, envelope order, selected route/model, checks, review flags, privacy/egress gates, exit codes, and existing event order/count. A blocked path remains blocked and creates no worker result; an existing terminal handoff retains `not_attempted`. Evidence-validation or persistence failure must not trigger repair, an additional worker invocation, or fallback to a different route. Pre-execution failures prevent execution; post-execution failures do not undo a completed attempt.

## Settled Design Contract (2026-10-31)

This section records the technical contract settled during the documentation-only review, before the operator's implementation grant. The subsequent grant permits preparation of the bounded candidate against this contract; it is not acceptance of that candidate.

### Approach and Compatibility

Use three flat, additive fields in the existing open payloads. Replacing `reason` with a binding cause would discard policy provenance and change existing consumers; a nested record, separate event, or versioned observation schema would expand this slice. Both alternatives are rejected here. Keep the implementation allowlist unchanged.

The existing governed `reason` remains exactly `decision.policy.route_reason_codes[0]`, including an existing `policy_selected` value. Its meaning is **preferred policy-route rationale**, not an observation that the selected fallback was available. `fallback_depth` remains the observation's envelope position; it is not a newly calculated router-candidate depth. Do not add a second policy-reason field or widen the decision vocabulary. Raw extended records provide the distinction; current task summaries still read only `reason` ([task_ledger.py:558-569](../../../triage_core/task_ledger.py#L558)). UI/report presentation is not repaired by this slice.

### Fields and Origin

Exactly these three new top-level keys appear together in both an extended `route_decision` and any `worker_result` already emitted for that attempt:

| Key | Exact JSON type and values | Sole source |
| --- | --- | --- |
| `governed_risk_posture` | String: `low`, `medium`, or `high` | The verified `decision.policy.risk_posture` |
| `binding_outcome` | String: `primary` or `authorized_fallback` | The validated `observation.binding_outcome` |
| `binding_reason_codes` | Array of 1 through 6 exact strings, in traversal order; sequence rules below | A list copy of `observation.reason_codes` |

`closed` remains an internal observation outcome and is **not** an allowed persisted value in this extension. The current consumer raises before a route payload exists ([client.py:237-242](../../../triage_core/client.py#L237)); do not introduce a closed-binding event or worker result. `no_authorized_binding_available` is correspondingly forbidden in a bound event's reason array. This restriction changes neither internal observation vocabulary nor its behavior.

Keep `task_sensitivity` on the route payload only. Project it from the already-governed classification using the existing table: `docs_update`, `bugfix`, `test_addition`, and `refactor` -> `low`; `packaging` and `architecture_planning` -> `medium`; `security_review` and `blocked_or_high_risk` -> `high`; then apply `risk_posture=high` -> `high`. Risk is not a synonym for sensitivity. Preserve the decision's existing review flag and checks, capability provenance, and selected route/model. A terminal handoff's existing `selected_backend` can still name the configured local backend; that does not establish worker execution, and this slice does not replace it with the observation's empty terminal backend binding.

### Builder Boundary and Presence Rules

- Add one optional keyword-only argument, `governed_evidence=None`, to `build_route_decision_payload`. Non-`None` input must be an exact `dict` with exactly the three keys above; extra/missing keys and an empty dict are invalid. This argument is not itself a persisted nested object. The route builder owns new copies of its dict/list values.
- The governed client must supply this argument on both current route-payload branches. Before projection, its existing decision verification and envelope-compliance check must succeed, and `observation.decision_id` must equal the verified decision ID. Use those same objects; do not form another decision, observation, or capability resolution. Convert the observation's validated tuple to a list once as defined serialization, not as repair of malformed builder input.
- With `governed_evidence=None`, add none of these fields. A `decision_id` without this extension remains valid historical/legacy linkage; it must not be inferred to be a partial new record or assigned default risk/outcome values. This generic-builder compatibility does not permit a new governed client attempt to omit its extension.
- Keep `build_worker_result_payload(route_payload, result)` unchanged in signature. It validates the extension in its source route payload and forwards it with the unchanged `decision_id` and a fresh list copy. The worker result supplies no authority to replace these values; identically named fields in `result` are ignored, as other unused result fields are. Do not resample policy or observation state.
- In route/worker payloads, the known three-field group is all-present or all-absent. Present `null` values are invalid. The surrounding legacy payload remains open: unrelated existing extension keys are not newly rejected. Only the optional three-key input dict is closed. Old records with none of the fields remain readable and are not backfilled.

### Validation Rules

Use one independent bounded validator in `route_events.py` for the new extension, separate from its producer. Its risk/code vocabularies must be declared independently of the producer's sets; drift tests compare them against the existing contracts rather than automatically accepting new producer vocabulary. This introduces no dependency or schema version. Validation must check primitive types before membership tests so unhashable input yields the bounded validation error, not a raw `TypeError`.

Apply checks in this order:

1. **Shape:** exact input dict/key set, or all-or-none presence of the recognized group in a route/worker payload. The optional argument `governed_evidence=None` is absence; an empty supplied dict, a partial recognized group, or a present field with `null` is invalid.
2. **Linkage:** an exact string `decision_id` matching `sha256:[0-9a-f]{64}` in full, with no newline, padding, or coercion. The client also performs the origin/ID equality checks above. A well-formed digest alone proves neither correspondence nor approval.
3. **Primitive values:** exact `str` values with case-sensitive vocabulary; exact `list` for the reason array; exact strings for its elements; length 1..6; exact `int` for `fallback_depth` in 0..5 (`bool` is invalid). A bound event's exact-string `selected_route` must be `local_fast`, `local_heavy`, `cloud_primary`, `cloud_secondary`, or `human_handoff`; `deterministic` cannot currently bind. On a route payload, sensitivity must be an exact string in `low`/`medium`/`high` and the review flag an exact boolean. Do not newly constrain legacy model/backend strings.
4. **Cross-field consistency:** apply the sequence table below and require `len(binding_reason_codes) == fallback_depth + 1`. In route evidence, high risk requires high sensitivity and `human_review_required=True`; other sensitivity/review combinations retain existing policy semantics. Forwarded worker evidence must preserve the source route's ID and three values exactly, with no list aliasing.

For nonterminal routes, the sequence is zero or more failure-prefix entries followed by exactly one success entry. For `human_handoff`, the last entry is always `terminal_human_handoff` instead. No success or handoff marker is allowed in a prefix.

| Outcome / selected route | Depth | Reason sequence |
| --- | --- | --- |
| `primary`, local/cloud route | 0 | Exactly `["bound_preferred_route"]` |
| `primary`, `human_handoff` | 0 | Exactly `["terminal_human_handoff"]` |
| `authorized_fallback`, local/cloud route | 1..5 | One failure per skipped envelope member, then `bound_authorized_fallback` |
| `authorized_fallback`, `human_handoff` | 1..5 | One failure per skipped envelope member, then `terminal_human_handoff` |

The failure-prefix vocabulary is exactly `deterministic_executor_not_wired`, `cloud_route_not_enabled`, `local_capability_unavailable`, `local_capability_unknown`, and `route_model_binding_missing`. Retain duplicates and order: two unknown local routes legitimately produce two `local_capability_unknown` entries. Never sort, deduplicate, stringify, trim, change case, or translate unknown into unavailable. Six is the bound because the existing closed logical-route set has six distinct members ([governed_decision.py:55-64](../../../triage_core/governed_decision.py#L55)); changing that bound or admitting new codes needs a later explicit contract change.

Validation checks shape and internal consistency, not truth of a historical backend claim. Payload-only validation cannot prove that a valid-valued dict was never replaced after construction or that its causes correspond to a particular historical decision. The same-instance client dataflow, owned copies, existing decision/envelope verification, and any existing signatures supply their respective provenance guarantees; none grants approval or proves model quality. Do not claim this validator independently reruns binding or verifies the full closed envelope.

Illustrative payload fragment (not a standalone valid event or execution record):

```json
{
  "selected_route": "local_fast",
  "fallback_depth": 1,
  "reason": "local_heavy_available_for_medium_or_complex_task",
  "governed_risk_posture": "low",
  "binding_outcome": "authorized_fallback",
  "binding_reason_codes": [
    "local_capability_unavailable",
    "bound_authorized_fallback"
  ]
}
```

Here `reason` preserves the preferred policy rationale; the binding fields explicitly report that the primary could not bind. Full events also require their unchanged linkage and existing event-specific fields.

### Errors, Event Order, and Execution Timing

Define `GovernedEvidencePayloadError(ValueError)` in `route_events.py`, imported directly where needed without expanding `routing/__init__.py`. Its `reason_code` and string form are the same one of four fixed codes, in validation order: `invalid_governed_evidence_shape`, `invalid_governed_evidence_linkage`, `invalid_governed_evidence_value`, `inconsistent_governed_evidence`. Do not include supplied keys/values, exception reprs, prompt text, paths, or model output in these errors. Existing errors for a legacy `decision_id` without new fields remain unchanged.

| Failure stage | Required disposition |
| --- | --- |
| New route-extension validation, before worker invocation | The client maps the typed error to existing `GovernedBindingError` with that bounded code. The CLI's existing exit-2 handler remains usable without a CLI change. No worker is invoked and no malformed route/worker event is appended. A preceding bounded audit/scaffolding event can remain. |
| Existing route persistence/signing | Propagate the original failure as today. No worker invocation, no synthetic worker event, and no repair/fallthrough. Existing write semantics are not upgraded to transactional or atomic guarantees. |
| Worker validation/persistence on a nonexecuting handoff | Propagate the failure; no worker has run and no replacement success/handoff event is synthesized. |
| Worker validation/persistence after local/cloud execution | Propagate the failure without converting it to a pre-execution `GovernedBindingError`. An attempt may already have completed. Do not retry, reroute, rerun the worker, mask the failure as success, or claim rollback/no execution. No new CLI exit classification is added for this existing post-execution integrity-failure path. |

This timing distinction corrects the proposal's earlier overbroad malformed-extension/persistence acceptance wording. The local execution call precedes worker evidence ([client.py:492-506](../../../triage_core/client.py#L492)), as does the cloud call ([client.py:442-461](../../../triage_core/client.py#L442)). Preflight all extension checks before invocation and revalidate before forwarding, but do not claim the second validation can undo execution.

Preserve the existing blocked order `route_audit -> route_decision -> LocalRouteUnavailableError`, with no worker event. Preserve allowed order `route_audit -> route_decision -> existing worker_result` (with a worker invocation between the latter two only where execution already occurs). A `closed` binding still terminates before those route events. Existing earlier `task_created`/`runner_selected` scaffolding and partial-write failure behavior remain unchanged. The `--no-ledger` path still constructs and validates bounded evidence without making a ledger write.

### Consumer and Privacy Boundary

The open records are distinct from the closed `route-worker-ledger.v1` events `route_decision_recorded` and `worker_result_recorded` ([route_worker_ledger.py:17-36](../../../triage_core/route_worker_ledger.py#L17)). Do not add fields to that schema. Existing task reduction ignores these new keys; accepting an open-payload addition does not make every dashboard/export show it. The existing ledger privacy check and signed-route writer remain in use ([task_ledger.py:189-196](../../../triage_core/task_ledger.py#L189), [task_ledger.py:247-269](../../../triage_core/task_ledger.py#L247)). Persist only the listed bounded primitives, never entire decision/observation objects. Add no timestamps, runtime-schema field, or separately persisted observation. `decision_id` remains unchanged because runtime evidence does not enter its body.

## Acceptance Criteria

This matrix defines the required implementation checks; none had been run during proposal/design preparation. Candidate results are now recorded under Actual Verification Results. Integration cases exercise the real governed consumer and payload builders with engine execution stubbed in memory; model generation, backend factories, live services, and network access are forbidden in those new cases.

| Case | Required evidence and unchanged behavior |
| --- | --- |
| High-risk docs task, such as `Update docs about sudo`, local-only | Decision risk is high; route evidence records that risk and `task_sensitivity=high`; primary terminal binding cause is preserved. The existing exit-2 outcome and absence of a worker event remain unchanged. |
| Low-risk architecture task | Risk stays low and sensitivity stays medium; the fix does not collapse these two meanings. |
| Available preferred local route | Primary outcome and the observation's exact ordered reason codes appear in route and existing worker evidence; route, model, and decision ID are unchanged. |
| Unavailable local-heavy primary, authorized local-fast fallback | Selected route/model match the observation; fallback depth remains its envelope position. The policy reason is distinguishable from `local_capability_unavailable` followed by `bound_authorized_fallback`; route and worker evidence agree. |
| Unknown/unusable local capability with a terminal fallback | Unknown is not relabelled observed-unavailable. Preserve the actual ordered observation codes, existing exit 2, blocked event order, and absence of worker execution/evidence. |
| Ethical-firewall primary handoff | Preserve primary terminal binding evidence, exit 3, and the existing worker result with `worker_result_status=not_attempted`; do not merge this with the high-risk exit-class question. |
| No-decision library caller | Existing payload shape and behavior remain unchanged; no new governed extension fields or decision linkage appear. |
| Malformed extension before execution | Reject partial/null/extra-key inputs; wrong primitive types (including bool depth, tuple/string arrays, unhashable entries); invalid linkage; out-of-range depth/length; unknown values; and inconsistent outcome/route/depth/suffix/risk. Bounded error, no malformed route/worker event, no worker invocation. |
| Ordered duplicate causes | Two skipped unknown local routes preserve `["local_capability_unknown", "local_capability_unknown", "terminal_human_handoff"]` with fallback depth 2; no deduplication or relabelling. |
| Legacy linkage-only payload / no-ledger attempt | An old valid `decision_id` without the new group remains accepted and gains no inferred metadata. A new governed no-ledger attempt still validates its extension without writing evidence. |
| Worker forwarding and ownership | Copy the exact ID and three-field group from the route payload; ignore conflicting result-side keys; changes to caller/worker lists do not mutate the route event. Reject a partial or internally inconsistent source extension. |
| Stage-specific validation/persistence failure | Before invocation: zero worker calls. After a stubbed completed attempt: exactly one call, propagated failure, no retry/reroute or returned success. No raw content or synthetic replacement evidence; do not assert rollback/no execution for the latter case. |

- [x] Add focused regression assertions that fail on the baseline evidence defects before making the correction; retain meaningful existing assertions.
- [x] Demonstrate the matrix above with deterministic, offline tests under the implementation grant.
- [x] Check new payloads with the existing persistent privacy invariant and verify JSON serialization and route-to-worker forwarding.
- [x] Pin all four sequence variants, forbidden `closed`/`deterministic`/`no_authorized_binding_available` values, exact error codes/check order, and unchanged legacy payload shape/reduction. Compare the independent validator vocabularies with the current producer contracts to catch drift.
- [x] Verify one shared projection serves both blocked and allowed paths without policy/observation reconstruction, and that decision-linked new attempts cannot silently omit the extension.
- [x] Show that the canonical decision, decision ID, and binding result are unchanged by evidence projection.
- [x] Record actual test commands, environment, revision, results, and remaining limitations below. The broader suite is not claimed green.

## Implementation Allowlist

The granted implementation slice is limited to exactly these six repository paths:

- `triage_core/client.py` -- govern the evidence projection and pass existing decision/observation facts on both current payload-building branches.
- `triage_core/routing/route_events.py` -- validate the optional bounded extension and forward it into existing worker payloads.
- `tests/test_governed_consumption_parity.py` -- consumer-level risk, primary/fallback, terminal, and legacy compatibility regressions.
- `tests/test_governed_consumption_failclosed.py` -- malformed-evidence and persistence-failure behavior without backend calls.
- `tests/test_route_events.py` -- bounded payload validation, serialization, forwarding, and absence of extensions for legacy inputs.
- `docs/change/requests/CR-DD-019-governed-execution-evidence-consistency.md` -- accepted field semantics, exact grants, and resulting evidence.

No additional repository path is authorized for mutation. Read-only inspection and offline verification may extend beyond this list under repository governance. Temporary test-environment artifacts are kept outside the repository.

## Implementation Progress (2026-10-31)

- Base: `ffb47b1aafd44e43347e3c0b39a6f0f00a6460b4`; isolated detached worktree at `C:/Users/corey/OneDrive/Documents/ChatGPT/AI Engineering Research/.worktrees/triagecore-cr-dd-019`. The original proposal in the main checkout is preserved. The desktop worktree tool rejected this repository because it is outside this chat's workspace folders; Git created the isolated worktree as the fallback.
- Sequence: establish the offline baseline; add failing payload/consumer/failure-stage regressions; implement validation and projection; run focused and broader offline checks; review the final diff and record results here. This CR carries the execution record rather than adding planning/ledger files outside the six-path grant.
- Tooling: Serena tools are not exposed in this client session. Structural navigation uses Python AST definitions and repository reference searches without creating a Serena project configuration outside the allowlist. No subagents are dispatched; the final review is an author self-review.
- Implementation: completed in the candidate. One projection of the existing decision/observation supplies both route branches; high-risk sensitivity is retained, bounded validation owns forwarding copies, and worker-stage errors are not misclassified as pre-execution errors. Current candidate locations are [client.py:254](../../../triage_core/client.py#L254), [route_events.py:242](../../../triage_core/routing/route_events.py#L242), and [route_events.py:373](../../../triage_core/routing/route_events.py#L373). Earlier source references remain evidence pinned to the baseline revision.
- Initial author self-review: reviewed the production diff and test matrix, but missed the null-field priority mismatch and incomplete vocabulary cross-check. The subsequent read-only implementation review identified both; the authorized corrective pass below addresses them. This remains author-conducted review, not an independent reviewer verdict or implementation acceptance.

### Actual Verification Results

The table below preserves the initial implementation results on 2026-10-31, before the corrective pass. Latest results are under Review Corrections and Verification below. Both stages use base `ffb47b1aafd44e43347e3c0b39a6f0f00a6460b4` plus their respective uncommitted changes. At that verification checkpoint, no candidate commit, PR, merge, release, or closeout had been created or performed.

| Check | Actual result |
| --- | --- |
| Existing six-file focused test selection before production edits | 145 passed |
| Initial new regression selection against unchanged production | 69 failed, 1 passed; failures exposed the missing optional evidence interface/fields, low sensitivity on the high-risk docs case, and missing worker-source validation. The already-passing case was the producer-vocabulary guard. |
| Additional blocked-path cases against original baseline modules | 2 failed as expected; baseline builder lacked `governed_evidence`. No implementation files were reverted for this check. |
| Final focused selection, including 72 new cases | 217 passed; last repeatable-harness run completed in 0.92 seconds |
| Full suite in a disposable local clone with matching code/tests | 2,581 passed, 6 skipped, 1 failed; exit 1. Only failure: `tests/test_mci_reference_reconciler.py::test_pins_match_the_specification_files`. |
| Same specification-pin test on unchanged original `main` | Same failure reproduced independently: `docs/research/monitoring-coverage-contract-v0.1.md` has SHA-256 `08f910d6dd24d5220c8f419df89522caad5cd97e99aa7be495ce4a17002fca1f`; the index expects `f8ece79edc562a30c413f7b3946151b6a87213ad4d5c6e67a4ebfc9b83e3d643`. Neither the specification nor its index is in this grant or was changed. |

The initial full-suite copy was created at `C:/Users/corey/AppData/Local/Temp/cr019-suite-nk9pp4n7/repo`; the six candidate files were copied and verified byte-for-byte before that run. Its independent Git metadata, editable-install artifacts, logs, and operational test data are disposable test artifacts, not changes to the implementation or original checkout. The production and test bytes matched that initial checkpoint; the later corrections have their own verified snapshot below.

Focused verification used `C:/Users/corey/AppData/Local/Temp/triagecore-cr-dd-019-validation/Scripts/python.exe` with `-B`, `PYTHONDONTWRITEBYTECODE=1`, disabled third-party pytest autoload, and `-p no:cacheprovider`. The saved temporary harness blocks production backend factories/generation, Requests I/O, and ordinary socket connections. From the isolated implementation root, the actual reproducible command is:

```powershell
& 'C:/Users/corey/AppData/Local/Temp/triagecore-cr-dd-019-validation/Scripts/python.exe' -B 'C:/Users/corey/AppData/Local/Temp/cr019-suite-nk9pp4n7/focused_runner.py' tests/test_route_events.py tests/test_runtime_observation.py tests/test_governed_consumption_parity.py tests/test_governed_consumption_failclosed.py tests/test_route_decision_audit.py tests/test_tc_run_cli.py -q --tb=short
```

The full-suite command was `pytest.main(['-p', 'no:cacheprovider', '--basetemp=C:/Users/corey/AppData/Local/Temp/cr019-suite-nk9pp4n7/pytest-verified', '--tb=short', '-q'], plugins=[results_recorder])` through the same temporary Python. Its subprocesses inherited temporary `sitecustomize.py` socket/Requests/HTTPX network guards; only the Windows stdlib socketpair self-pipe used a private loopback socket class for in-process async tests. No live model, model server, Uvicorn server, or backend service ran. Existing tests used their mocks/doubles; new execution tests stubbed `engine.execute_task` at the boundary.

Temporary `PIP_NO_INDEX=1` and a local `PIP_FIND_LINKS` wheelhouse let existing editable-install tests build without network access. Test tooling/dependencies were installed only into this temporary environment: Python 3.13.18, pytest 9.2.0, requests 2.34.2, python-dotenv 1.2.4, psutil 7.2.2, PyYAML 6.0.3, cryptography 50.0.2, FastAPI 0.162.0, Starlette 1.10.0, HTTPX 0.28.1, Uvicorn 0.54.0, fido2 2.2.1, setuptools 84.2.1, and wheel 0.48.0. Project manifests and account-wide packages were not changed.

Initial attempts surfaced Windows temporary-directory delete restrictions, then guards/dependency setup issues in legacy connectivity/web/editable-install tests. These were corrected in the temporary harness/environment, without changing out-of-scope tests or application code. The final full-suite result above includes those cases. The six skipped tests remain skips; no claim is made that they ran. Starlette emitted an existing HTTPX deprecation warning in this environment.

Temporary full-suite artifacts: `C:/Users/corey/AppData/Local/Temp/cr019-suite-nk9pp4n7/suite-verified.log`, `results-verified.json`, `guards/sitecustomize.py`, and `focused_runner.py`. These paths are local verification evidence, not a durable project memory system. The unresolved specification-pin mismatch requires a separately scoped decision; no re-pin or unrelated fix was attempted.

### Review Corrections and Verification (2026-10-31)

- **P2 corrected:** The shared route/worker extension validator now rejects a present null in any of the three governed fields during shape validation, before checking linkage. `governed_evidence=None` still means an absent optional extension; it is distinct from a present null-valued field. Non-null malformed primitive values still follow the existing linkage-then-value order. The correction is in [route_events.py:251](../../../triage_core/routing/route_events.py#L251).
- **Regression coverage:** [test_route_events.py:195](../../../tests/test_route_events.py#L195) exercises all three null fields through both builders with missing, malformed, and valid decision IDs. Existing null expectations now require `invalid_governed_evidence_shape`; the linkage-before-value case uses non-null invalid values. Four additional consumer cases verify that null data maps to the bounded shape error before execution on allowed/blocked paths, with and without a ledger.
- **P3 corrected:** The [vocabulary drift guard](../../../tests/test_route_events.py#L243) now directly compares the validator's five independently declared sets against the producer contracts: risk values, bound outcomes, bound routes, all bound reason codes, and failure-prefix codes. Existing literal producer pins remain, so a change cannot silently widen both sides. No producer or validator vocabulary was widened or imported into production from the other side.
- **Mutation evidence:** Before strengthening the test, widening each validator set in memory was missed (0/5 detected). The corrected guard rejected all five validator-only widenings (5/5 detected). Each mutation was restored in `finally`; no source file or persisted vocabulary was changed by the probe.
- **Scope:** This corrective pass changed only `triage_core/routing/route_events.py`, `tests/test_route_events.py`, `tests/test_governed_consumption_failclosed.py`, and this CR. The other two allowed files remain byte-identical to the initial candidate. No routing, model selection, decision identity, event ordering, or execution-stage error behavior was changed. The original checkout and its proposal remain preserved; no commit, PR, merge, or acceptance action was performed.
- **Original-checkout observation:** The final status check also showed an untracked `.serena/` directory in the original checkout, outside this implementation worktree. It was left untouched. Original tracked files and the original proposal's SHA-256 remain unchanged; this additional untracked directory is not part of the corrective candidate.

| Corrective-pass check | Actual result |
| --- | --- |
| Null-field regression selection before the production fix | 25 failed, 66 passed, 47 deselected; failures exposed value/linkage errors where shape errors were required. |
| Focused offline selection after the fix | 241 passed in 1.06 seconds; production backend factories/generation, Requests I/O, and ordinary sockets were blocked by the existing saved harness. |
| Full offline suite in a fresh disposable clone | 2,605 passed, 6 skipped, 1 failed; exit 1. The sole failure remains `tests/test_mci_reference_reconciler.py::test_pins_match_the_specification_files`, previously reproduced on unchanged `main`. Its specification and index were not changed. |

The focused command is the saved-harness command recorded above, rerun from the implementation worktree against the corrected files. No dependency installation was needed for this pass. The fresh full-suite clone is `C:/Users/corey/AppData/Local/Temp/cr019-review-fixes-xt_6nx3g/repo`; all six scoped files were copied byte-for-byte before testing. It reused copies of the verified offline guards and local build wheelhouse, with `PIP_NO_INDEX=1`. The full command used the same `pytest.main` arguments and results recorder as the initial run, with `--basetemp=C:/Users/corey/AppData/Local/Temp/cr019-review-fixes-xt_6nx3g/pytest-verified` and the fresh clone as its working directory. Python, package versions, bytecode/cache settings, and the Windows stdlib self-pipe exception are unchanged.

Corrective-pass full output and structured results are `C:/Users/corey/AppData/Local/Temp/cr019-review-fixes-xt_6nx3g/suite-verified.log` and `results-verified.json`; `guards/sitecustomize.py` records the inherited network restrictions. The CR received this results-only update after testing. No live model or backend service ran. The full suite is not claimed green, and neither these results nor the correction record constitutes implementation acceptance.

## Implementation Acceptance Record (2026-10-31)

The operator's exact response was **"Accepted"**, following the re-review recommendation to accept the implementation after both findings were verified resolved. The re-review made no file changes and ran no models/backends; its fresh in-memory probes confirmed 18/18 null-priority cases and detection of 5/5 validator-only vocabulary widenings. The source/test files matched the previously tested correction snapshot. The recorded verification limits remain visible: 241 focused passes and a full offline run with 2,605 passed, 6 skipped, and the known specification-pin failure previously reproduced on unchanged `main`.

At implementation acceptance, the candidate was the detached worktree at `C:/Users/corey/OneDrive/Documents/ChatGPT/AI Engineering Research/.worktrees/triagecore-cr-dd-019`, based on `ffb47b1aafd44e43347e3c0b39a6f0f00a6460b4` plus the uncommitted changes. No candidate commit SHA existed at that checkpoint. The separately authorized review branch is now `codex/cr-dd-019-governed-evidence`; the accepted Python-file bindings remain:

| Accepted file | SHA-256 |
| --- | --- |
| `triage_core/client.py` | `bfbd22759ca128797ac5c605b21af6220bdb646480cb6d213d79c214855b907d` |
| `triage_core/routing/route_events.py` | `eec8b7f20a08cae472e4cf1e2666db6a3a87b379faa46f98be2205e1d468d276` |
| `tests/test_route_events.py` | `e82753afe6ceee9d5ae03e185fdbb568a59a83ff7d4d2d84414e56e2ad4ea445` |
| `tests/test_governed_consumption_parity.py` | `95984ce8945beb65edea8b6af881ce648df5d4174678e16cfd1cdb63981a60ee` |
| `tests/test_governed_consumption_failclosed.py` | `d286174e1ebb76c2c3ee1305d128d98664025096d5c04ead7ecacda87adaa60c` |

The reviewed CR document, before this acceptance-only record update, had SHA-256 `06fc77d4e6f8ddaa88fda7e34a34c17e5d7aec826d8294905b1722f07bd64acf`. This update records the human decision; it changes no implementation or tests and does not claim a new test run.

Implementation acceptance itself covers this bounded implementation only. The later commit/draft-PR instruction is recorded separately above. Neither decision authorizes additional code changes, merge, release, closeout, or re-pinning the out-of-scope monitoring specification. No acceptance, release, or cleanup of unrelated artifacts is inferred. The original checkout and its untracked files are left untouched.

## Commit and Draft-PR Preparation Record (2026-10-31)

The current publication grant is limited to the six-file candidate on `codex/cr-dd-019-governed-evidence`, targeting `coreytshaffer/TriageCore:main`. Remote `main` was observed at `ffb47b1aafd44e43347e3c0b39a6f0f00a6460b4` before preparation, equal to the accepted implementation base. The five accepted Python-file hashes above are preserved. These hashes identify the reviewed Windows working files; Git's existing `core.autocrlf=true` stores LF-normalized blobs. Staged content was compared with each accepted file after line-ending normalization, with no other difference. This stage adds only authority/provenance wording to this CR; it introduces no runtime or test changes.

The commit uses the existing repository author identity `Corey Shaffer <78175888+coreytshaffer@users.noreply.github.com>` via per-command Git settings because no local/global author identity is configured. The identity matches the connected GitHub account and prior repository commits; account-wide settings are unchanged. No active Git hooks were found. The checked-in CI workflow defines test jobs, not live model/backend startup.

The known specification-pin failure is retained and must be disclosed in the draft PR alongside the passing scoped checks. The operator authorized draft publication after accepting this limitation; this neither fixes nor waives that unrelated failure. The draft remains subject to review and existing repository checks. Actual commit identity, branch publication, and PR metadata are recorded by Git and GitHub rather than inserting a commit's own hash into its content. No merge, release, closeout, or worktree cleanup is authorized or performed by this record.

Fresh pre-commit verification on 2026-10-31: 241 focused tests passed in 0.89 seconds; the full offline suite again reported 2,605 passed, 6 skipped, and only the same baseline specification-pin failure. The disposable snapshot is `C:/Users/corey/AppData/Local/Temp/cr019-pr-check-24t3ixka/repo`, with `suite-verified.log` and `results-verified.json` in its parent. All five Python files match the accepted hashes and this snapshot. This CR received only this results note after the run. The existing offline guards and local wheels were reused; no models or backend services ran.

## Verification Plan

Documentation-only review checks on 2026-10-31 verified the three-field table, compared its vocabulary and six-route bound with literal source constants without importing project modules, parsed the illustrative JSON fragment, and checked 22 local file/line/anchor links. These are document checks, not implementation verification.

No application tests were run during proposal preparation or the documentation-only design review. The later implementation grant permitted the offline runs recorded above. The planned focused selection is retained here for reference:

```powershell
python -m pytest tests/test_route_events.py tests/test_runtime_observation.py tests/test_governed_consumption_parity.py tests/test_governed_consumption_failclosed.py tests/test_route_decision_audit.py tests/test_tc_run_cli.py -q
```

The prospective allowlist does not authorize edits to every inspected or tested file. Broader verification follows [the verification guide](../../verification_guide.md) when appropriate to an authorized implementation; no live model/backend, `tc run`, probe, benchmark, or operational-ledger command is needed for this slice.

## Explicit Exclusions

- Routing, classification, capability resolution, model selection, privacy enforcement, approval/resume, or decision-contract changes.
- Resolution of the high-risk terminal exit asymmetry recorded in [CR-DD-012B](CR-DD-012B-shared-preview-execution-consumption.md#open-discovery-high-risk-terminal-exit-class).
- Preview connectivity-warning corrections, cloud-success wording, UI/report rewrites, or the separate privacy-declaration evidence questions in [the Track C investigation](../../operations/privacy-propagation-2026-08-29.md).
- New ledger schemas, event types, runtime-observation persistence, backend probes, dependencies, or external integration.
- Backfilling or rewriting historical records; existing records must not be treated as if they contain this proposed extension.
- Committing, opening a PR, merging, releasing, closing out, or expanding implementation beyond the named six paths under this bounded implementation grant.
