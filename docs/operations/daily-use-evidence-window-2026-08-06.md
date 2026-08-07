# Daily-Use Evidence Window — Day 3, 2026-08-06

## Status

**Window open.** This is a Day-3 session record for the controlled daily-use evidence
window opened on 2026-08-01. It is not a closeout, readiness assessment, or readiness
claim.

The declared target window is **2026-08-01 through 2026-08-14**. Closeout must not occur
before evidence has been collected on at least **7 distinct days**. The target is **10–15
eligible real operator tasks**. These are trial parameters, not completion, quality,
safety, or readiness thresholds.

Evidence now exists on **3 distinct local operator days** (2026-08-01, 2026-08-02,
2026-08-06) and covers **8 independent eligible tasks** plus 1 paired retry. Both remain
below the declared parameters.

This session recorded **one** eligible real `tc run` execution, numbered **Trial 011** to
continue the window's sequence. Two governed previews were run beforehand; previews are
recorded here as session context and friction and are **not** eligible attempts.

### Predecessor-record dependency, and its state at merge time

At session time (2026-08-06/07), the Day-2 record existed only as commit `f891fcc` on
branch `claude/august-2-evidence-collection-4dcdf6`, not merged into `main`, and Trial 011's
review subject — the Next Gate correction — existed only as commit `1546776` on branch
`docs/daily-use-evidence-window-next-gate-correction`, also not merged. This Day-3 record
was drafted against `main` @ `3f1cce0`, before either had landed, and the window totals in
this record were computed from that unmerged predecessor.

Both have since merged: the Day-2 record via [PR #147](https://github.com/coreytshaffer/TriageCore/pull/147)
(`f891fcc`, now on `main`), and the Next Gate correction via
[PR #148](https://github.com/coreytshaffer/TriageCore/pull/148) (`1546776`, now on `main`),
in that order, before this record was opened as a pull request. This record's own window
totals were re-verified against `main` after both merges and are unchanged: no eligible
task, ledger record, or disposition in this document was added, removed, or reinterpreted by
either merge. Trial 011's baseline is unaffected by this note: it ran against `main` @
`3f1cce0` and reviewed the Next Gate correction as it existed at that time — an unmerged
candidate. That execution fact is historical and is not restated as having reviewed merged
content.

## Canonical References

- [Day-1 Evidence Record](daily-use-evidence-window-2026-08-01.md)
- [Day-2 Evidence Record](daily-use-evidence-window-2026-08-02.md) (merged via PR #147)
- [Daily-Driver Orchestrator Specification](../architecture/daily_driver_orchestrator_spec.md)
- [Reviewer Traceability](reviewer-traceability.md)
- [Evidence Schema](../evidence_schema.md)
- [CR-DD-014: Explicit Local Route Model Binding](../change/requests/CR-DD-014-explicit-local-route-model-binding.md)

## Window Protocol

This record inherits the Day-1 Window Protocol unchanged.

## Baseline and Evidence Isolation

As on Day 2, this session ran against merged `main` with **no temporary or uncommitted
capability configuration** and made no configuration change of any kind.

| Item | Day-3 observation |
| --- | --- |
| Code under test | `main` @ `3f1cce0` (PR #146 merge commit; `23bf17a` verified as an ancestor) |
| Configuration | Tracked `triagecore.toml`; backend `ollama`; base URL `http://localhost:11434`; `local_fast` → `qwen2.5-coder:7b-triagecore`; `local_heavy` → `deepseek-r1:latest`; `[backend] timeout_seconds = 30` |
| Temporary configuration | None. No uncommitted configuration was applied or restored |
| Configuration changes | 0 |
| Tracked tree | Clean before and after the session |
| `tc status` | Repository clean; main ledger `.triagecore/ledger.jsonl`; last event 2026-07-03 21:24; 100 pending reviews observed but not evaluated or attributed; backend Ollama; policy `human-review-required` |
| `tc doctor` | Overall OK; Python 3.14.5; external execution blocked; human approval `human-review-required`; network/tool execution unavailable |
| Metadata-only runtime probe | Not run this session. No probe record exists for Day 3 |
| Main ledger SHA-256, before and after | Unchanged: `4981E97B12BE3EE0D04B6C8CD98B85CB2C70FC7191B982507B094B66A3ADE619` |
| Isolated trial ledger | `.triagecore/daily-use-window/2026-08-06/ledger.jsonl`; SHA-256 `200417F32B615F6D045F2EF612F1685E708D8F9CF0577DC8462C082008CC07DD` |
| Isolated ledger audit | 5 records; the repository privacy-invariant function (`find_forbidden_persistent_fields`) reported 0 violations |
| Task input artifact | `.triagecore/daily-use-window/2026-08-06/input-next-gate-correction.diff`; SHA-256 `73F2DE2762A3FE3FF1362B440626D4A613205DB75BF6437A6C22A1EC8A4D041A`; 2,380 bytes |
| Superseded input artifact | `.triagecore/daily-use-window/2026-08-06/input-next-gate-correction.BLOCKED-preview-01.diff`; SHA-256 `D9AD24853D0935E594254F4BF36FA330E46EA93D402AF79202A0FBB943743021`; 3,410 bytes; retained so the preview-block observation stays reproducible |

The unchanged main-ledger hash establishes only that this session did not change that file.
The isolated artifact hashes establish byte identity only; they do not establish
correctness, authenticity, authorization, or provenance. The isolated evidence paths are
gitignored local artifacts and are not committed by this record.

All Day-3 UTC timestamps fall on **2026-08-07**. The session occurred within the local
operator day **2026-08-06** and is recorded as Day-3 evidence, distinct from the 2026-08-01
and 2026-08-02 local operator days.

## Inherited Control Findings

This session did not re-derive the Day-2 pre-run control findings. Three of them bear
directly on how this record must be read, and were re-verified by source inspection at
`3f1cce0`:

1. **Route timeout is not operator-controllable.** The worker `timeout_seconds` comes from
   the per-category table in `routers.py`, not from `[backend] timeout_seconds`. Day-2
   Derived Finding 4 established this from runtime evidence.
2. **`internet_ok` is not network state.** It is set from
   `default_config.get_qwen_enabled()` at `client.py:488`. A `false` value means Qwen cloud
   is disabled, not that the host is offline.
3. **Every governed run performs an unconditional metadata-only network connect.**
   `is_internet_available()` opens `8.8.8.8:53` at `routers.py:44` with no gate. This
   session captured no network trace of its own, so this is recorded as inherited from
   Day-2's source finding by the same code path rather than as an independent Day-3
   observation.

## Session Context and Friction — Not Attempts

Two governed previews preceded the single eligible attempt. Previews perform no model call
and write no ledger record, so neither appears in the isolated ledger; both are recorded
here from console observation only.

### Preview 01 — blocked fail-closed

| Field | Record |
| --- | --- |
| Outcome | Privacy preflight blocked before planning completed. Console reported `finding_codes=privacy_preflight_failed`; CLI exit code 2 |
| Cause | The input artifact was produced with `git show` without `--format=`, so it carried commit metadata: the `Author:` header and a `Co-Authored-By:` trailer. Both matched the scanner's email-address grammar while packet metadata declared `contains_pii=False` |
| Model call | None |
| Ledger write | None |
| Control posture | No privacy control was weakened, disabled, or bypassed. No `--no-ledger` or privacy override was used |
| Resolution | The input was narrowed to the actual review subject — the patch hunks — by regenerating it with `--format= --no-color --no-ext-diff`. The task purpose, success criterion, and prompt were unchanged |
| Claim limits | This records a valid control response to an over-broad input artifact. It is not evidence that the scanner misbehaved, and it is not an eligible attempt |

### Preview 02 — passed

| Field | Record |
| --- | --- |
| Context | `model_profile` `generic-32k`; 693 estimated input tokens against 27,648 usable; status `fits` |
| Privacy | `declared_privacy` `local_only`; preflight passed; `finding_codes: none`; `egress_eligible: False`; `cloud_authorized: False`; `cloud_posture: prohibited` |
| Advisory route | `local_fast`; reason `local_fast_available_for_small_or_repetitive_task`; `deterministic_classification` `docs_update`; risk `low`; `fallback_depth: 0`; `human_review_required: False` |
| Forecast | `configured_backend_binding` `ollama:qwen2.5-coder:7b-triagecore`; `specialist_model_forecast` `qwen2.5-coder:7b-triagecore`; `specialist_timeout_forecast_seconds` 120 |
| Declared preview boundaries | `advisory_only: true`; `deterministic_classification_is_preview_assumption: true`; `backend_probe_performed: false`; `live_health_observed: false`; `execution_performed: false`; `ledger_or_artifact_written: false`; `approval_granted: false` |
| Claim limits | Preview estimates are context-planning evidence only and are not execution usage. The route is an advisory assumption, not a guarantee. The forecast is not an observation of runtime state |

### CLI friction observed this session

1. `--files` is declared with `nargs="*"`. A positional prompt placed after `--files` is
   absorbed into the file list, and the invocation fails with `error: the following
   arguments are required: prompt`. The prompt was moved ahead of `--files` for all
   subsequent invocations. Recorded as an operator-ergonomics observation only.
2. Before execution the CLI printed: *local capability: unknown (no usable observation);
   proceeding on the explicit declaration in `triagecore.toml:[capability]`*. The warning is
   recorded as observed and is consistent with this session running no probe.

## Day-3 Attempt Record

### Trial 011 — Temporal-accuracy and claim-boundary review of the Next Gate correction

**Eligibility:** Eligible real operator task. Not a retry of any earlier trial. One
invocation; no retry was performed or authorized.

| Field | Record |
| --- | --- |
| Project lane, downstream use, disposition | Daily-use evidence window operations and documentation governance; used to inform the merge decision on branch `docs/daily-use-evidence-window-next-gate-correction` @ `1546776`; operator disposition **`rejected`** |
| Purpose and success criterion | Review the proposed Next Gate correction for temporal accuracy, claim boundaries, and unsupported implications. Success required at least one concrete, checkable finding the operator could act on. Prose agreement containing no checkable finding was defined in advance as `not_useful` |
| Plan and context | Preview 02 above. Prompt length 316 characters; supplied file data recorded by the ledger as `data_length` 2,455. Privacy passed as `local_only` |
| Configuration and capability | Tracked `main` configuration; no temporary configuration. `capability_state` `configured`; `capability_source_type` `operator_config`; `capability_config_reference` `triagecore.toml:[capability]`; declared classes `local_fast` and `local_heavy`; recorded bindings matched CR-DD-014; `capability_route_binding_issues` empty; `capability_freshness_seconds` 300 |
| Actual route and terminal outcome | Route audit allowed `local_fast` with `decision` `allowed` and `reason_code` `route_allowed`. `task_class: docs_update`, complexity `low`, sensitivity `low`. The route decision selected `qwen2.5-coder:7b-triagecore` at `fallback_depth: 0`, matching the declared binding. Worker status `success`; `worker_result_status` **completed**; `backend_failure` false. Advisory route and actual route agreed |
| Evidence completeness | Five ledger events: `task_created`, `runner_selected`, `route_audit`, `route_decision`, `worker_result`. `task_created` withheld prompt content and recorded lengths only. Validation `not_run`; `validator_name`, `validator_version`, and `validator_scope` null; `required_checks` empty |
| Privacy and egress | `privacy_scan_passed` true; `is_local_only` true. No model or task-payload cloud egress was observed. `internet_ok: false` reflects Qwen cloud being disabled, not network state (Inherited Control Finding 2). The unconditional `8.8.8.8:53` metadata-only connect described in Inherited Control Finding 3 applies to this run by code path; no network trace was captured this session |
| Tokens and validation | 728 input, 209 output, 937 total tokens; 34.40 tokens per second; `elapsed_seconds` 27.24 against `timeout_seconds` 120. Full execution telemetry exists. No validator was supplied, so no validation was performed. The operator review described below is a manual disposition, **not** a validation event |
| Usefulness | Operator disposition `rejected`. The output followed the requested findings-only structure but produced no actionable true defect in the proposed correction. It generated multiple consequential false positives, including treating historically accurate statements and explicit authority disclaimers as defects, and identified one issue only in text already removed by the diff. The output was not used to support the merge decision; the documentation correction remains supported by the operator's independent verification |
| Friction and bypass | No bypass was used. Session friction is recorded above and did not affect this invocation |
| Claim limits | Successful governed execution establishes completion of one `local_fast` docs-class task through the merged CR-DD-014 route/model binding with recorded execution telemetry. It does not establish review quality or correctness. The generated review was rejected by the operator, validation did not run, and the documentation correction was evaluated independently |

### Rejection basis

The disposition is `rejected` rather than `revised` because no part of the output was
incorporated or edited into usefulness. The specific defects observed:

1. A historically accurate statement — that Trials 006–008 remain evidence about the
   then-unmerged candidate — was classified as now false.
2. The explicit authority disclaimer was classified as implying new authority, inverting its
   meaning.
3. A baseline requirement for future sessions was classified as a readiness claim.
4. The one correct observation concerned a sentence already deleted by the proposed
   correction.
5. No true finding affecting the merge decision was produced.

A competent review of this correction would need to be redone independently.

## Day-3 Aggregate

| Measure | Day-3 result |
| --- | --- |
| Eligible real `tc run` executions | 1 (one task purpose; no retries) |
| Completed | 1/1 |
| Blocked | 0/1 |
| Handoff after worker failure | 0/1 |
| Operator disposition | `rejected` (1/1) |
| Useful output through `tc run` | 0/1 |
| Validation completed | 0/1 |
| Model/task-payload cloud egress | 0/1 observed |
| External metadata-only network contact | Applies by code path; not independently captured this session |
| Execution token linkage | 1/1 with full token and elapsed telemetry |
| Route/binding coherence | 1/1 route decisions selected the model declared for the chosen route class |
| Advisory-to-actual route agreement | 1/1 |
| Route classes exercised | `local_fast` only; `local_heavy` deliberately not exercised |
| Governed previews | 2 (1 privacy-blocked, 1 passed); not eligible attempts |
| Synthetic controls | 0 |
| Direct bypass controls | 0 |
| Configuration changes | 0 |

## Window Progress

| Measure | Cumulative |
| --- | --- |
| Distinct local operator days with evidence | 3 of the required ≥7 (2026-08-01, 2026-08-02, 2026-08-06) |
| Eligible real `tc run` executions | 9 (6 on Day 1 including 1 retry; 2 on Day 2; 1 on Day 3) |
| Independent tasks against the 10–15 target | 8 |
| Completed | 4/9 |
| Blocked | 2/9 |
| Handoff after worker failure | 3/9 |
| Validation completed | 0/9 |
| Operator dispositions on completed runs | 1 `accepted`, 2 `revised`, 1 `rejected` |
| Model/task-payload cloud egress | 0/9 observed |

## Derived Findings — Not Fixes

1. **The four completions in this window have now produced three distinct operator
   dispositions.** Trial 008 `revised`, Trial 009 `revised`, Trial 010 `accepted`, Trial 011
   `rejected`. All four completed technically, all on `local_fast` under `docs_update`, all
   with `validation_status: not_run`. With four observations this is not a quality-rate
   estimate, but it demonstrates that execution completion and operator usefulness are
   empirically distinct outcomes across the full range: a completed run has been accepted,
   revised, and rejected. `worker_result_status` `completed` is not acceptance, usefulness,
   correctness, or readiness.
2. Trial 011 is the window's **first `rejected` disposition**. Day-2 Derived Finding 2
   established that completion is not correctness, using a completed run containing a
   factual error. Trial 011 extends that: a completed run can produce output that is
   structurally compliant and substantively unusable in its entirety.
3. `validation_status: not_run` has now been recorded for **9 of 9** eligible real tasks in
   the window. Validation has never run. The `tc run` path supplies no validator.
4. Route/binding coherence held for a fourth consecutive completion under committed
   configuration, and the advisory route from the preview matched the actual route. One
   agreement does not establish that previews predict routes generally; the preview declares
   `deterministic_classification_is_preview_assumption: true`.
5. Route class is derived from `TaskClassifier.classify_deterministic(prompt)` — the prompt
   only. The `--model` value supplies a context budget and does not participate in route
   selection, and supplied data size affects the fits computation rather than route class.
   Combined with Day-2 Pre-Run Control Finding 3, which established that `docs_update` is
   the only category reaching `local_fast`, this means varying input size does not vary
   route class and does not broaden route-class coverage. Recorded as a source-traced
   observation bearing on experiment design.
6. `--model` controls context budgeting while the CR-DD-014 bindings control
   route-to-backend selection. `generic-32k` and `qwen2.5-coder-7b` are distinct profile
   names with identical budgets (32,768 context, 4,096 reserved, 1,024 margin, 27,648
   usable). `generic-32k` was used to avoid conflating the context-profile layer with the
   backend-model layer. The separation was confirmed by source inspection rather than
   assumed.
7. Privacy preflight blocked an over-broad input artifact whose sensitive-shaped content was
   irrelevant to the task. The control behaved as specified; the input was wrong.
8. The returned text rendered an en-dash as a replacement character in console output.
   Console output was not captured to a file this session, so console codepage handling and
   a pipeline defect are not distinguished by this record. The cause is unestablished.
9. Byte count on disk (2,380), preview-reported source character count (2,374), and ledger
   `data_length` (2,455) are three different measurement layers for the same file and are not
   directly interchangeable. This record states each with its layer.
10. `route_decision` again recorded `lm_studio_ok: true`, alongside `memory_headroom_mb`
    4096, `local_heavy_available` true, `local_fast_available` true,
    `deterministic_tool_available` false, and zero recent-failure counters. Nothing in this
    session verified any of those states. This is the third consecutive session in which
    `lm_studio_ok: true` entered a route decision unverified, matching Day-1 Derived Finding
    12 and Day-2 Derived Finding 7. It remains unresolved.
11. The Day-3 `route_decision` and `runner_selected` payloads contain
    `capability_declared_route_classes` and contain **no** `capability_supported_route_classes`
    field, reproducing Day-2 Derived Finding 6 exactly and differing from the Day-1 corrected
    session, where the field was present but empty. The population path for supported-class
    evidence remains unestablished.
12. The worker recorded `timeout_seconds` 120 while the tracked `[backend] timeout_seconds`
    is 30, and the preview independently forecast 120. This is the third runtime confirmation
    of Day-2 Derived Finding 4 and Day-2 Pre-Run Control Finding 1: the value comes from the
    per-category table in `routers.py`, not from configuration. Day-1 Derived Finding 13,
    which recorded the timeout source as unestablished, is **superseded** by that Day-2
    finding rather than by this record.

These findings do not authorize implementation changes and recommend none.

## Next Gate

`local_heavy` was deliberately not exercised in this session, and remains unexercised
end to end across the entire window.

On the `local_heavy` pre-generation failures: a read-only diagnosis was performed on
2026-08-01 and its primary evidence is preserved in the gitignored, uncommitted directory
`.triagecore/daily-use-window/2026-08-01-diagnostics/`; that directory is local-only by
design and its merge status is not applicable. Related structural findings are recorded in
the Day-2 record, merged into `main` via PR #147 before this record was opened as a pull
request. The Day-1 record's own statement of this gate is unamended by that merge and
remains as written on `main`; this record does not amend it either. No fix was authorized
by the diagnosis or by the Day-2 findings, and this record authorizes none.

Remaining gates otherwise unchanged: continue the declared evidence window across distinct
days with materially useful tasks — 3 of at least 7 days and 8 of 10–15 independent tasks
so far; and, when Docker Desktop is available, verify actual container topology and
in-container LM Studio and Ollama reachability before any claim that the supervisor/council
architecture is retained as a working containerized deployment.

The Next Gate correction that Trial 011 reviewed, `1546776`, was unmerged and unpushed at
session time; it has since merged into `main` via PR #148, before this record was opened as
a pull request. That merge does not retroactively make Trial 011's review an evaluation of
merged content — Trial 011 reviewed the candidate as it existed at session time — and it
does not change the `rejected` disposition, which rests on the review's content, not on the
correction's merge status. The candidate's content was ultimately reviewed and accepted for
merge by the operator independently, not by the rejected Trial 011 output.

The Day-2 record at `f891fcc` merged via PR #147 ahead of both the Next Gate correction and
this record, per the operator's stated merge order; sequencing is resolved and required no
further decision by this record.

No cloud trial has been performed or authorized by this record. This record creates no model
aliases, routing changes, or configuration changes, and grants no fix, readiness, cloud, or
implementation authority.

## Uncertainty and Limitations

- This record covers one session on one local operator day. The window remains open with
  evidence on 3 of at least 7 required distinct days.
- One eligible attempt is not a sample. No rate, distribution, or reliability statement is
  supported by this session, and four completions across the window support none either.
- Window totals were computed from the Day-2 record at `f891fcc`, unmerged at session time
  and merged into `main` via PR #147 before this record was opened as a pull request. The
  totals were re-verified against the merged Day-2 record and are unchanged.
- No validation completed for any eligible real task in this window, across all three days.
- Previews are not attempts. Preview estimates are not execution usage, and the passing
  preview establishes no execution result.
- The privacy block in Preview 01 was caused by input construction, not by task content. It
  establishes handling of one email-shaped grammar match and does not establish complete
  scanner coverage.
- No metadata-only runtime probe was run this session, so no Day-3 observation of runtime
  reachability or self-reported model inventory exists, and `capability_state` was
  `configured` from operator configuration rather than observed.
- Runtime reachability, configured declarations, route-class support, class-to-model
  binding, and successful generation remain distinct claims and are not substituted for one
  another.
- Route/model coherence observed here holds for one `local_fast` `docs_update` attempt and is
  not generalized to other route classes or task classes. Per Day-2 Pre-Run Control Finding
  3, `local_fast` evidence in this window is structurally confined to one task category.
- The unconditional `8.8.8.8:53` metadata-only connect is recorded as inherited from Day-2's
  source finding by code path. This session captured no independent network evidence.
- LM Studio did not supervise any trial in this record; the supervisor/council containerized
  topology remains source-level design intent and is unverified.
- Human-review minutes and workload were not measured. The operator time spent rejecting
  Trial 011 and independently redoing that review was not recorded.
- The 100 pending reviews reported by `tc status` are legacy accumulation, were not evaluated
  or attributed, and were not modified by this session.
- Hashes establish byte identity only, not correctness, authenticity, authorization, or
  provenance.
- This record supports no readiness percentage and makes no safety, alignment, containment,
  certification, production-readiness, general model-quality, cost, energy, or authorization
  claim.
- This document grants no implementation, execution-expansion, cloud, approval, or merge
  authority.
