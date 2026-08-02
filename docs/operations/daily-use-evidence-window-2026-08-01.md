# Daily-Use Evidence Window — 2026-08-01

## Status

**Window open.** This is a Day-1 kickoff record for a controlled daily-use evidence
window. It is not a closeout, readiness assessment, or readiness claim.

The declared target window is **2026-08-01 through 2026-08-14**. Closeout must not
occur before evidence has been collected on at least **7 distinct days**. The target is
**10–15 eligible real operator tasks**. These are trial parameters, not completion,
quality, safety, or readiness thresholds.

The window includes every eligible attempt: successful execution, failure, privacy or
policy block, governed handoff, no-ledger or bypass path, and retry. Previews, synthetic
controls, and direct-backend controls are recorded separately and do not count as eligible
real `tc run` executions. No new readiness percentage is assigned; the percentages in the
canonical specification remain historical planning estimates.

This record was amended later on the same local operator day to add the corrected-binding
session (Trials 006–008), which ran under the separately authorized, unmerged CR-DD-014
correction candidate. The window remains open, and this remains a Day-1 record.

## Canonical References

- [Daily-Driver Orchestrator Specification](../architecture/daily_driver_orchestrator_spec.md)
- [Daily-Driver Quickstart](../daily_driver_quickstart.md)
- [Reviewer Traceability](reviewer-traceability.md)
- [Evidence Schema](../evidence_schema.md)
- [CR-DD-009: Governed `tc run` Planning Surface](../change/requests/CR-DD-009-governed-tc-run-planning-surface.md)
- [TriageCore Identity](../architecture/triagecore_identity.md)

## Window Protocol

An eligible real task must be materially useful to a current or plausible future project. It
must support an actual deliverable, bounded decision, review, evidence analysis, or planned
next action that the operator would reasonably pursue without the trial. A task invented only
to exercise `tc run` is a synthetic control and does not count. Paired retries may diagnose a
failure but are not independent material-use observations.

Each eligible attempt records:

- project lane, intended downstream use, and operator disposition (`accepted`, `revised`,
  `rejected`, `bypassed`, or `not produced`);
- task purpose and observable success criterion;
- plan and context posture;
- configuration and capability evidence used;
- actual route and terminal outcome;
- completeness or absence of ledger, worker, token, and validation evidence;
- privacy result and external-egress status;
- result usefulness to the operator;
- failure, friction, retry, and bypass details; and
- bounded claim limits.

Evidence is metadata-only where the repository privacy rules require it. An absent event is
recorded as absent rather than inferred. Preview estimates are not execution usage. Runtime
reachability, configured declarations, route-class support, class-to-model binding, and
successful generation are distinct claims and are not substituted for one another.

## Baseline and Evidence Isolation

| Item | Day-1 observation |
| --- | --- |
| Repository baseline | Commit `e0bf0d5` (merged PR #144), branch `codex/daily-use-evidence-window` |
| Tracked tree | Clean before and after the trials |
| `tc status` | Repository clean; main ledger `.triagecore/ledger.jsonl`; 100 pending reviews observed but not evaluated or attributed; backend Ollama; policy `human-review-required` |
| `tc doctor` | Overall OK; Python 3.14.5; external execution blocked; human approval `human-review-required`; network/tool execution unavailable |
| Checked-in backend configuration | Ollama; model `qwen2.5-coder-7b-instruct`; base URL `http://localhost:11434/v1` |
| Metadata-only runtime probe | `http://localhost:11434` reachable; two self-reported models: `qwen2.5-coder:7b-triagecore` and `deepseek-r1:latest`; recorded latency 2035 ms; observed `2026-08-02T04:13:06.136055+00:00` |
| Main ledger SHA-256, before and after | `4981E97B12BE3EE0D04B6C8CD98B85CB2C70FC7191B982507B094B66A3ADE619` |
| Isolated trial ledger | `.triagecore/daily-use-window/2026-08-01/ledger.jsonl`; SHA-256 `9BD643CF531465543AB586F4B5B2C97879EEADB0A969CF501CEA7FBC4AFF294B` |
| Isolated probe record | `.triagecore/daily-use-window/2026-08-01/ollama_probe_record.json`; SHA-256 `C0875539035EB6F2164B7B534B928501E56E83E001FD11A37FFE6A3308D67060` |
| Isolated ledger audit | 14 records; repository privacy-invariant function found 0 violations |

The unchanged main-ledger hash establishes only that the isolated trials did not change that
file. The isolated artifact hashes establish byte identity only; they do not establish
correctness, authenticity, authorization, or provenance. The probe establishes observed
reachability and self-reported inventory at one time. It does not establish class-to-model
binding, generation success, or general runtime health.

The isolated evidence paths are gitignored local artifacts and are not committed by this
record.

## Day-1 Attempt Records

### Trial 001 — Large docs-grounded operator checklist

**Eligibility:** Eligible real operator task.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Produce a usable operator checklist grounded in three named documents. Success required a substantive checklist returned through the governed `tc run` path. Input context totaled 31,789 characters. |
| Plan and context | Preview estimated 8,007 input tokens against 27,648 usable tokens; `fits`. Privacy was `local_only` and passed. Advisory route was `local_heavy`; the preview included no live health evidence. |
| Configuration and capability | Checked-in baseline configuration. Capability evidence was missing or unknown. |
| Actual route and outcome | Console reported HTTP 404. The governed path blocked with recommended `human_handoff`, decision `blocked`, and reason `ambiguous_or_remote_route`. |
| Evidence completeness | Three ledger events: `task_created`, `runner_selected`, and `route_audit`. No `route_decision`, `worker_result`, token-usage event, or validation evidence exists. |
| Privacy and egress | Privacy preflight passed as `local_only`; no cloud egress was observed. |
| Tokens and validation | Preview estimate only. No execution token evidence. Validation was not completed. |
| Usefulness | `not_useful`; no checklist output was produced. |
| Friction and bypass | Baseline path reached a console HTTP 404 and then a governed block. No bypass was used for this attempt. |
| Claim limits | Shows one baseline failure and a partial evidence chain. It does not establish that Ollama or the target local model was unavailable, nor that local execution generally fails. |

### Trial 002 — Large-task retry with temporary capability configuration

**Eligibility:** Eligible retry of Trial 001; not an independent task.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Retry the same checklist task after supplying bounded runtime and capability information. The success criterion remained a usable checklist returned through governed `tc run`. |
| Plan and context | Same task and context as Trial 001. The prior preview remained advisory and was not treated as execution evidence. |
| Configuration and capability | Temporary, uncommitted trial configuration used the root Ollama URL, the observed probe record, explicit `local_fast` and `local_heavy` declarations, and an actual observed local model name. The configuration was fully restored afterward. The declarations are operator assertions and do not prove class-to-model binding. |
| Actual route and outcome | Actual route was `local_heavy`, then blocked as `offload_recommended_for_local_only`. |
| Evidence completeness | Three ledger events only. No worker result, execution token record, or validation evidence exists. |
| Privacy and egress | `local_only`; no external egress was observed. |
| Tokens and validation | No execution token evidence. Validation was not completed. |
| Usefulness | `not_useful`; no checklist output was produced. |
| Friction and bypass | Reachability and declarations did not yield a local worker attempt because the governed route terminated on the local-only offload recommendation. No direct bypass was used in this attempt. |
| Claim limits | Shows the governed outcome under temporary declarations. It does not show that either declared route class was bound to the supplied model or that the configuration was suitable for permanent use. |

### Trial 003 — Small docs-only PR review checklist

**Eligibility:** Eligible real operator task.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Produce a five-item docs-only pull-request review checklist with no file inputs. Success required five usable checklist items returned through governed `tc run`. |
| Plan and context | Preview estimated 65 input tokens against 27,648 usable tokens; `fits`. Privacy passed as `local_only`. Advisory route was `local_fast`; forecast model was `deepseek/deepseek-r1-0528-qwen3-8b`. |
| Configuration and capability | Used the same temporary trial capability configuration as Trial 002. The observed Ollama inventory contained only `qwen2.5-coder:7b-triagecore` and `deepseek-r1:latest`, not the forecast specialist identifier. Configuration was restored afterward. |
| Actual route and outcome | Governed route allowed `local_fast` and the ledger selected `deepseek/deepseek-r1-0528-qwen3-8b`. The worker then recorded `worker_failed` / `backend_error` at `local_backend_generate`; terminal outcome was `handoff_required`. |
| Evidence completeness | Five ledger events, including a route decision and worker result. Validation was `not_run`. Worker usage recorded 0 input, 0 output, and 0 total tokens because failure occurred before generation. |
| Privacy and egress | `local_only`; no cloud egress was observed. |
| Tokens and validation | Preview estimate is not execution usage. Worker record contains zero token usage due to pre-generation failure. No validation completed. |
| Usefulness | `not_useful` through `tc run`; no checklist output was returned by the governed path. |
| Friction and bypass | Selected specialist model identifier was absent from the observed inventory. A separate direct-backend control was run after this governed failure and is recorded below. |
| Claim limits | Demonstrates one route/model binding mismatch and a governed handoff after worker failure. It does not prove the backend or an inventory-listed model could not perform the task. |

### Direct local control — Trial 003 prompt

**Eligibility:** Control/bypass only; not eligible `tc run` evidence.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Isolate direct backend/model usability using the Trial 003 prompt. Success required five checklist items from the observed local model. |
| Plan, route, and configuration | Direct `ollama run qwen2.5-coder:7b-triagecore`; bypassed TriageCore planning, routing, privacy, ledger, validation, and authority surfaces. |
| Outcome and usefulness | Succeeded in 35.6 seconds and returned five checklist items; `useful` as a backend-isolation control only. |
| Evidence completeness | No TriageCore ledger, route, privacy, token, validator, review, or authority evidence. |
| Claim limits | Supports direct usability of this backend/model for this small prompt at this time. It does not count as governed execution or support any TriageCore success, privacy, safety, authorization, or readiness claim. |

### Trial 004 — Unsupported credential-shaped privacy control

**Eligibility:** Synthetic control; excluded from the real-task count.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Test a credential-shaped form not supported by the current scanner grammar. The synthetic value is intentionally not reproduced here. |
| Plan, configuration, and route | Run after baseline configuration restoration. The scanner did not match the unsupported form; processing continued to the same governed route block seen on the baseline path. |
| Outcome and evidence | Three safe metadata-only ledger events were created. No external egress was observed. |
| Usefulness | Useful only for bounding the tested scanner grammar. |
| Claim limits | This does not prove that a real secret was supplied, that a secret leaked, or that all unsupported shapes behave identically. |

### Trial 005 — Repository-documented credential-shape privacy control

**Eligibility:** Synthetic control; excluded from the real-task count.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Verify fail-closed handling for a repository-documented credential shape. The synthetic value is intentionally not reproduced here. |
| Outcome and evidence | Privacy preflight blocked before the ledger opened. Exact CLI exit code was 2. No Trial 005 ledger record exists. |
| Privacy and egress | Fail-closed before persistence; no external egress was observed. |
| Usefulness | Useful only as one supported-grammar control. |
| Claim limits | Demonstrates handling of one documented synthetic shape. It does not establish complete secret-detection coverage or general privacy safety. |

## Day-1 Aggregate — Baseline Session (Trials 001–005)

| Measure | Baseline-session result |
| --- | --- |
| Eligible real `tc run` executions | 3 |
| Completed | 0/3 |
| Blocked | 2/3 |
| Handoff after worker failure | 1/3 |
| Governed previews | 2 |
| Synthetic privacy controls | 2 |
| Direct bypass controls | 1 |
| Local-only eligible attempts | 3/3 |
| Cloud egress | 0/3 |
| Useful output through `tc run` | 0/3 |
| Useful direct-control output | 1/1, ineligible for governed-execution evidence |
| Execution token linkage | 1/3 has a worker record with zero tokens due to pre-generation failure; 2/3 have no worker/token event |
| Validation completed | 0/3 |
| Human-review burden | Minutes and workload were not measured and are not inferred |

Preview token estimates are context-planning evidence only. They are not execution usage.
Retry results are included for completeness but are not independent-task observations.

## Corrected-Binding Session (Trials 006–008)

The Day-1 Next Gate required a separately approved correction before success-path trials
resumed. That correction was authorized and implemented as
[CR-DD-014: Explicit Local Route Model Binding](../change/requests/CR-DD-014-explicit-local-route-model-binding.md)
on the isolated branch `codex/daily-use-local-binding-correction` at commit `23bf17a` in a
separate local worktree. At trial time that commit was unmerged and unpushed; these trials
therefore exercise the CR-DD-014 candidate, not `main`. The candidate replaces the `/v1`
base URL with the native Ollama root, replaces the stale default model identifier with
`qwen2.5-coder:7b-triagecore`, and binds `local_fast` to `qwen2.5-coder:7b-triagecore` and
`local_heavy` to `deepseek-r1:latest`.

All corrected-session UTC timestamps fall on 2026-08-02. Every trial occurred within the
same local operator day as Trials 001–005, and this session is recorded as Day-1 evidence.

### Corrected-Session Baseline and Isolation

| Item | Observation |
| --- | --- |
| Code under test | `codex/daily-use-local-binding-correction` @ `23bf17a` (CR-DD-014 candidate; unmerged and unpushed at trial time) |
| Metadata-only runtime probe | `http://localhost:11434` reachable; the same two self-reported models as the baseline probe; recorded latency 2068 ms; observed `2026-08-02T05:13:50.761981+00:00` |
| Isolated trial ledger | `.triagecore/daily-use-window/2026-08-01-corrected/ledger.jsonl`; SHA-256 `4A768C666658F3476EEFD9C4962FADBD09424CBC26AB4AAFD173D3954326810A` |
| Isolated probe record | `.triagecore/daily-use-window/2026-08-01-corrected/ollama_probe_record.json`; SHA-256 `62365AA273F404CA6BB10B6C7DB545661441CC51A94184C1A80EBA73D651C839` |
| Isolated ledger audit | 15 records; the repository privacy-invariant function found 0 violations |
| Main ledger SHA-256, before and after | Unchanged: `4981E97B12BE3EE0D04B6C8CD98B85CB2C70FC7191B982507B094B66A3ADE619` |
| Capability evidence in all three runs | `observed_available`; declared classes `local_fast` and `local_heavy`; recorded bindings matched CR-DD-014 with no binding issues; evidence tier `local_metadata_probe`; `capability_supported_route_classes` remained empty |
| Temporary probe configuration | Removed after the session; the tracked tree was restored |

The unchanged main-ledger hash establishes only that these trials did not change that file.
Hashes establish byte identity only. The probe establishes observed reachability and
self-reported inventory at one time. The isolated evidence paths are gitignored local
artifacts and are not committed by this record.

### Trial 006 — CR-DD-014 correction-record review

**Eligibility:** Eligible real operator task.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Produce a review of the CR-DD-014 correction record to support that change's pending human review. Prompt length 202 characters; supplied data 11,111 characters; the target file was the CR-DD-014 document. Success required a substantive review returned through governed `tc run`. |
| Plan and context | The corrected-session ledger contains no preview events; preview observations from the session were not preserved as evidence and are not reconstructed here. Privacy passed as `local_only`. |
| Configuration and capability | CR-DD-014 candidate configuration. Capability evidence recorded `observed_available` with both declared route classes bound to observed models and no binding issues. |
| Actual route and outcome | The route audit allowed `local_heavy`; the route decision selected `deepseek-r1:latest`, matching the declared binding. The worker recorded `worker_failed` / `backend_error` at `local_backend_generate`; terminal outcome was `handoff_required`. |
| Evidence completeness | Five ledger events, including a route decision and worker result. The worker payload recorded `elapsed_seconds` 0.0, `timeout_seconds` 30, and zero tokens. The console-observed ~30-second timeout is not a ledger field; the wall-clock gap between the route-decision and worker-result events was approximately 32.0 seconds. Validation was `not_run`. |
| Privacy and egress | `local_only`; no cloud egress was observed. |
| Tokens and validation | Zero token usage due to pre-generation failure. No validation completed. |
| Usefulness | `not_useful`; no review output was produced. |
| Friction and bypass | The selected model matched the declared binding and observed inventory, so this failure is distinct from the Day-1 binding mismatch. No bypass was used. |
| Claim limits | Shows one `local_heavy` generation failure under the corrected binding with a 30-second worker timeout configured. It does not identify the failure cause or establish that `deepseek-r1:latest` cannot serve the route. |

### Trial 007 — Evidence-claim matrix for this record

**Eligibility:** Eligible real operator task.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Produce a claim matrix distinguishing supported from unsupported claims in this evidence record. Prompt length 234 characters; supplied data 17,882 characters; the target file was this document. Success required a usable matrix returned through governed `tc run`. |
| Plan and context | No preview events exist in the corrected-session ledger. Privacy passed as `local_only`. |
| Configuration and capability | Same CR-DD-014 candidate configuration and capability evidence as Trial 006. |
| Actual route and outcome | The route audit allowed `local_heavy`; the route decision selected `deepseek-r1:latest`, matching the declared binding. The worker recorded `worker_failed` / `backend_error` at `local_backend_generate`; terminal outcome was `handoff_required`. |
| Evidence completeness | Five ledger events. The worker payload is identical in every recorded field to Trial 006's, including `elapsed_seconds` 0.0 and zero tokens. The console-observed HTTP 400 is not a ledger field; the wall-clock gap between the route-decision and worker-result events was approximately 4.3 seconds, consistent with a fast failure rather than a timeout. Validation was `not_run`. |
| Privacy and egress | `local_only`; no cloud egress was observed. |
| Tokens and validation | Zero token usage due to pre-generation failure. No validation completed. |
| Usefulness | `not_useful`; no matrix output was produced. |
| Friction and bypass | Two differently caused failures (console-observed timeout versus HTTP 400) produced identical worker payloads; only event timing distinguishes them in persistent evidence. No bypass was used. |
| Claim limits | Shows a second `local_heavy` pre-generation failure with a different console-observed cause. The HTTP status is a session observation, not ledger evidence, and no cause is established. |

### Trial 008 — Multimodal-canary research scoping notes

**Eligibility:** Eligible real operator task.

| Field | Record |
| --- | --- |
| Purpose and success criterion | Draft research-scoping notes supporting the multimodal-canary backlog candidate recorded in this slice. Prompt length 398 characters; no file data supplied. Success required usable scoping notes returned through governed `tc run`. |
| Plan and context | No preview events exist in the corrected-session ledger. Privacy passed as `local_only`. |
| Configuration and capability | Same CR-DD-014 candidate configuration and capability evidence as Trials 006–007. |
| Actual route and outcome | The route audit allowed `local_fast`; the route decision selected `qwen2.5-coder:7b-triagecore`, matching the declared binding. The worker completed with status `success`; this is the first governed completion of the evidence window. |
| Evidence completeness | Five ledger events, including a complete worker result: `elapsed_seconds` 13.88, `timeout_seconds` 120, 104 input tokens, 470 output tokens, 574 total tokens, 41.3 tokens per second. Validation was `not_run`. |
| Privacy and egress | `local_only`; no cloud egress was observed. |
| Tokens and validation | Full execution token and elapsed-time telemetry exists for this run. No validation completed. |
| Usefulness | Operator disposition `revised`: the output was directionally useful but requires operator revision before any backlog use. |
| Friction and bypass | None observed in the governed path. The worker `timeout_seconds` differed from Trials 006–007 (120 versus 30); the ledger does not record the source of the timeout value. |
| Claim limits | One completed small docs-class generation under the corrected binding. It supports no reliability, latency-distribution, validation, or readiness claim, and completion is not acceptance: validation did not run and the output required revision. |

### Corrected-Session Aggregate

| Measure | Result |
| --- | --- |
| Eligible real `tc run` executions | 3 (three distinct task purposes; no retries) |
| Completed | 1/3 |
| Handoff after worker failure | 2/3 |
| Blocked | 0/3 |
| Useful output through `tc run` | 1/3, operator disposition `revised` |
| Validation completed | 0/3 |
| Cloud egress | 0/3 |
| Execution token linkage | 1/3 with full token and elapsed telemetry; 2/3 zero-token pre-generation failures |
| Route/binding coherence | 3/3 route decisions selected the model declared for the chosen route class |

### Day-1 Combined Aggregate

| Measure | Combined result |
| --- | --- |
| Eligible real `tc run` executions | 6 (5 independent tasks and 1 retry) |
| Completed | 1/6 |
| Blocked | 2/6 |
| Handoff after worker failure | 3/6 |
| Useful output through `tc run` | 1/6, operator disposition `revised` |
| Validation completed | 0/6 |
| Cloud egress | 0/6 |

## Derived Findings — Not Fixes

1. The console reported HTTP 404. Source inspection shows that the checked-in Ollama base
   URL includes `/v1` and the native backend appends `/api/chat`, constructing
   `/v1/api/chat`; that constructed URL is an inference from configuration and source, not
   console output from the trial.
2. The checked-in default model identifier was absent from the observed runtime inventory.
3. The `local_fast` route selected a hardcoded specialist model identifier absent from the
   observed inventory. The capability record listed no supported route classes despite the
   temporary declarations; declarations alone do not establish class-to-model binding.
4. The large `local_only` task was blocked when specialist offload was recommended, even
   with a reachable runtime and temporary route-class declarations.
5. The direct backend control succeeded. The Day-1 failures therefore provide evidence of
   TriageCore configuration, binding, and routing problems; they do not prove that Ollama or
   `qwen2.5-coder:7b-triagecore` was unavailable.
6. Early governed blocks create partial evidence chains. Privacy preflight blocks
   intentionally create no ledger chain. This operator record preserves those missing-
   evidence facts without treating absence as success or failure evidence.
7. Scanner coverage is grammar-bounded: the unsupported synthetic shape and the documented
   supported shape followed different paths.
8. Under the CR-DD-014 candidate, all three route decisions selected the model declared for
   the chosen route class, and the Day-1 selection of an uninstalled specialist identifier
   did not recur.
9. The first governed completion of the window occurred on `local_fast` with full token and
   elapsed-time telemetry (574 total tokens; 13.88 seconds recorded in the ledger).
10. Both `local_heavy` failures produced worker payloads identical in every recorded field,
    including `elapsed_seconds` 0.0 and `failure_type` `backend_error`. The console-observed
    distinction — an approximately 30-second timeout versus a fast HTTP 400 — survives only
    in wall-clock gaps between ledger events (approximately 32.0 versus 4.3 seconds) and in
    unpersisted console output. HTTP status, timeout expiry, and elapsed wall time at
    failure are telemetry gaps.
11. `capability_supported_route_classes` remained empty in all three corrected-session runs
    even though bindings were declared, recorded, and matched; the population path for that
    field remains unestablished.
12. Route decisions recorded `lm_studio_ok: true` as an input; nothing in these trials
    verified LM Studio state, so that flag's provenance is unestablished by this record.
13. Worker `timeout_seconds` was 30 for Trials 006–007 and 120 for Trial 008; the ledger
    does not record the source of the timeout value.

These findings do not authorize implementation changes.

## Future Task Selection Gate

Before each future run, record the project lane, material outcome sought, why the task is
timely, its observable usefulness criterion, its privacy class, and the ordinary tool or path
the operator would use if `tc run` is not useful. Keep prompt contents and sensitive project
data out of persistent evidence. Project diversity is useful but does not override privacy,
authority, or file-scope boundaries.

## Next Gate

The original Day-1 gate required a separately approved correction before success-path
trials resumed. That correction now exists as the CR-DD-014 candidate on
`codex/daily-use-local-binding-correction` at commit `23bf17a`, and the corrected-binding
session above reran governed tasks under it. The candidate remains unmerged; its human
review and merge decision are a separate gate that this record does not grant. This slice
still creates no model aliases, routing changes, or committed configuration fixes.

Remaining gates: diagnose the `local_heavy` pre-generation failures without inferring a
cause from this record; continue the declared evidence window across distinct days with
materially useful tasks; and, when Docker Desktop is available, verify actual container
topology and in-container LM Studio and Ollama reachability before any claim that the
supervisor/council architecture is retained as a working containerized deployment. No cloud
trial has been performed or authorized by this record.

## Uncertainty and Limitations

- This record covers one day only; the declared 7–14 day window remains open.
- Baseline-session tasks produced no governed output. The corrected-binding session
  produced one governed output whose operator disposition was `revised`, so material
  usefulness through `tc run` rests on a single revised observation.
- Retry attempts are not independent observations.
- There was no successful governed execution in the baseline session, and exactly one in
  the corrected-binding session.
- The successful direct control bypassed TriageCore governance and is not eligible
  daily-driver execution evidence.
- Probe inventory is self-reported metadata observed at one time, not independently verified
  capability or class-to-model binding.
- Temporary route-class declarations were operator assertions, were uncommitted, and were
  restored after the trials.
- Human-review minutes and workload were not measured.
- Baseline-session worker token evidence contains only zeros because generation did not
  begin; the corrected-binding session added one successful execution token record.
- No validation completed for an eligible real task.
- Corrected-session trials ran under the unmerged CR-DD-014 candidate in a separate
  worktree; they are evidence about that candidate, not about `main`.
- Corrected-session UTC timestamps fall on 2026-08-02; all trials occurred within one local
  operator day and are recorded as Day-1 evidence.
- The corrected-session ledger contains no preview events; preview observations from that
  session were not preserved as evidence and are not reconstructed here.
- The timeout and HTTP 400 characterizations of Trials 006 and 007 are console observations
  from the session; the ledger records both failures only as `backend_error`.
- `local_heavy` generation remains unobserved end to end; both corrected-session attempts
  failed before generation.
- LM Studio did not supervise any trial in this record; the supervisor/council
  containerized topology remains source-level design intent and is unverified.
- The privacy controls sample two synthetic grammar shapes and do not establish complete
  scanner coverage or arbitrary free-text safety.
- Hashes establish byte identity only, not correctness, authenticity, authorization, or
  provenance.
- This record supports no readiness percentage and makes no safety, alignment, containment,
  certification, production-readiness, general model-quality, cost, energy, or authorization
  claim.
- This document grants no implementation, execution-expansion, cloud, approval, or merge
  authority.
