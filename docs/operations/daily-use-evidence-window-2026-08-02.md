# Daily-Use Evidence Window — Day 2, 2026-08-02

## Status

**Window open.** This is a Day-2 record in the daily-use evidence window declared on
2026-08-01. It is not a closeout, readiness assessment, or readiness claim.

The declared target window remains **2026-08-01 through 2026-08-14**, requiring evidence on
at least **7 distinct days** and targeting **10–15 eligible real operator tasks**. These are
trial parameters, not completion, quality, safety, or readiness thresholds.

This session was deliberately narrow: **two eligible `local_fast` tasks, no `local_heavy`
runs, and no retries.** The rationale is recorded under Pre-Run Control Findings below.

All Day-2 UTC timestamps fall on **2026-08-03**. Every trial occurred within the local
operator day **2026-08-02**, which is the day this record counts toward the distinct-day
requirement. This is the same local/UTC offset situation recorded on Day 1.

## Canonical References

- [Day-1 Evidence Record](daily-use-evidence-window-2026-08-01.md)
- [Daily-Driver Orchestrator Specification](../architecture/daily_driver_orchestrator_spec.md)
- [Daily-Driver Quickstart](../daily_driver_quickstart.md)
- [Evidence Schema](../evidence_schema.md)
- [CR-DD-014: Explicit Local Route Model Binding](../change/requests/CR-DD-014-explicit-local-route-model-binding.md)

## Window Protocol

This record inherits the Day-1 Window Protocol unchanged. An eligible real task must be
materially useful to a current or plausible future project, must support an actual
deliverable or bounded decision, and must be one the operator would reasonably pursue
without the trial. Paired retries diagnose failures but are not independent material-use
observations. Evidence is metadata-only where repository privacy rules require it. An absent
event is recorded as absent rather than inferred.

## Baseline and Evidence Isolation

| Item | Day-2 observation |
| --- | --- |
| Code under test | `main` @ `3f1cce0` (CR-DD-014 bindings merged via PR #146) |
| Execution location | Git worktree `clear-lake-evidence-closeout-feabea`, branch `claude/august-2-evidence-collection-4dcdf6`, tree identical to `main` @ `3f1cce0` |
| Tracked tree | Clean before the trials |
| `tc status` | Repo clean; worktree ledger `.triagecore/ledger.jsonl` does not exist; 0 pending reviews; backend Ollama; policy `human-review-required` |
| `tc doctor` | Overall **WARN**; Python 3.14.5; external execution blocked; human approval `human-review-required`; network/tool execution unavailable |
| Checked-in configuration | Ollama; default model `qwen2.5-coder:7b-triagecore`; base URL `http://localhost:11434`; `timeout_seconds = 30`; `[capability]` binds `local_fast` → `qwen2.5-coder:7b-triagecore` and `local_heavy` → `deepseek-r1:latest` |
| Metadata-only runtime probe | `http://localhost:11434` reachable; two self-reported models `qwen2.5-coder:7b-triagecore` and `deepseek-r1:latest`; latency 2054 ms; observed `2026-08-03T04:12:02.971114+00:00` |
| Main ledger SHA-256, before | `4981E97B12BE3EE0D04B6C8CD98B85CB2C70FC7191B982507B094B66A3ADE619` (primary repo; unchanged since Day 1) |
| Isolated trial ledger | `.triagecore/daily-use-window/2026-08-02/ledger.jsonl` |

**Isolation deviation from Day 1, recorded deliberately.** Day-1 trials ran in the primary
repository with an isolated ledger directory. Day-2 trials ran in a separate git worktree, so
the primary repository's main ledger is in a different directory tree and cannot be reached
by the trial commands at all. This is stronger isolation than Day 1, not weaker, but it is a
difference in method and is recorded as such. It also explains the two `tc doctor` /
`tc status` differences from Day 1: the worktree has no `.triagecore/ledger.jsonl`, which
produces `Overall: WARN` and `Pending reviews: 0` rather than Day-1's 100.

The `tc doctor` WARN is attributable to the absent worktree ledger and the non-`main` branch
name. It is not evidence of a runtime fault.

The isolated evidence paths are gitignored local artifacts and are not committed by this
record. Hashes, where recorded, establish byte identity only — not correctness,
authenticity, authorization, or provenance.

## Pre-Run Control Findings

These findings were established by **source inspection before any Day-2 run** and are
recorded here so the achievability of each intended experimental control is fixed in
advance rather than reconstructed afterward. They are readings of code at `3f1cce0`. They
are not runtime observations, and they authorize no implementation change.

### 1. Route timeout is not operator-controllable, and is not deterministic

The session plan intended to "hold timeout constant" across paired runs. **That control is
not achievable at `3f1cce0`.**

- `triage_core/routers.py` (~L87–L110) selects the timeout from a **per-task-category**
  table, not from the route class and not from `triagecore.toml`. Code-shaped categories
  yield 30 s; `docs_update` and `architecture_planning` yield 120 s; the fallback branch
  yields 45 s.
- `triage_core/client.py` (~L119) takes the timeout from that category decision, while
  (~L132–L137) it takes the **model** from the CR-DD-014 capability binding. Model follows
  the binding; timeout does not. This is the mechanism behind Day-1 Derived Finding 13.
- `triage_core/classifier.py` (~L13–L58) determines the category by **calling the default
  Ollama model with a 1.5-second budget**, falling back to a regex classifier only when that
  call fails or returns an unrecognized string. The category — and therefore the timeout —
  can differ between two runs of an identical prompt depending on backend latency.

Consequence: the recorded `timeout_seconds` value is an *observation*, not a controlled
variable. Day-2 records which value each run received; it does not claim the value was held
fixed by operator action.

Related: `structured_extraction` and `log_summary` appear in the `routers.py` 120-second
branch but are absent from `TaskClassifier.CATEGORIES`, so `classify` cannot return them.
Only `docs_update` and `architecture_planning` reach that branch.

### 2. Failure-fidelity capture is structurally unavailable, not merely unrecorded

The session plan intended to "preserve failure fidelity manually" — HTTP status, timeout
classification, and elapsed wall time — pending CR-DD-015A. **The first two cannot be
recovered from the governed path at `3f1cce0` by any operator action.**

- `triage_core/backends.py` (~L307, ~L343) wraps every `requests.exceptions.RequestException`
  — which includes `Timeout` and `HTTPError` — into `BackendUnavailableError`.
- Consequently `triage_core/engine.py` (~L98) `except requests.exceptions.Timeout` is
  **unreachable on the Ollama path**. All backend failures land in the generic handler at
  (~L114), which sets `failure_type: backend_error` and `worker_result_status: worker_failed`.
- That generic handler never computes elapsed time, which is why both Day-1 `local_heavy`
  failures recorded `elapsed_seconds` 0.0.

Consequence: HTTP status and timeout-versus-error classification survive only as operator
console observation. This is a code-level explanation of Day-1 Derived Finding 10, and it is
the condition CR-DD-015A is sequenced to correct. **CR-DD-015A does not exist in the
repository; its drafting is not yet authorized.**

### 3. `docs_update` is the only category that reaches `local_fast`

`triage_core/client.py` (~L449–L458) maps every category to a complexity, and
`triage_core/routing/resilience_router.py` (~L224–L229) prefers `local_heavy` whenever
complexity is `medium` or `high`. Only `docs_update` carries complexity `low`;
`security_review` and `blocked_or_high_risk` carry sensitivity `high` and divert to
`human_handoff`. Therefore a `local_fast` run at `3f1cce0` requires a prompt that classifies
as `docs_update`.

This is why both Day-2 tasks are documentation tasks. That is a **constraint of the routing
code, not a free choice of task lane**, and it bounds what Day-2 evidence can generalize to:
Day-2 observes the `local_fast` path only under `docs_update`, which is the same category
that also sets the 120-second timeout branch.

### 4. Runtime context ceiling is below the planner's stated budget

Recorded on Day 1 and re-stated here as a pre-run constraint: Ollama loads models at a
default `num_ctx` of 4096, and TriageCore sends only `options.temperature` — never
`num_ctx`. The context planner's "27,648 usable tokens" is therefore **not** the runtime
ceiling. Day-2 inputs were sized against 4096 total (input plus output), not against the
planner's figure.

### 5. Every governed run performs an outbound network connect

`triage_core/routers.py` (~L6–L14) calls `is_internet_available()`, which opens a TCP
connection to `8.8.8.8:53` on every `route_task` call, before any route or privacy gate
completes. This is a reachability probe carrying no task content, and it is not model or
cloud egress. It is recorded because Day-1 evidence states "no cloud egress was observed"
without noting that a non-cloud outbound connect occurs unconditionally on the governed
path. Day-2 makes the same narrow egress claim, with this qualification attached.

**Correction established after the Day-2 runs, recorded here to prevent a wrong inference.**
The `internet_ok` field in the `route_decision` payload is **not** the result of that TCP
probe. `triage_core/client.py` (~L488, ~L491) sets `internet_ok` and `cloud_credit_state`
from `default_config.get_qwen_enabled()`. Both Day-2 runs recorded `internet_ok: false` and
`cloud_credit_state: "none"`, which reflects **Qwen cloud being disabled in configuration**,
not a failed or absent network connect. The outcome of the `8.8.8.8:53` probe is not
recorded in the ledger at all, so this record makes no claim about whether it succeeded.

## Day-2 Task Selection Gate

The Day-1 Future Task Selection Gate requires the project lane, material outcome, timeliness,
observable usefulness criterion, privacy class, and ordinary fallback path to be recorded
**before** each run. Both Day-2 tasks were declared as follows before execution.

### Trial 009 (planned) — Quickstart troubleshooting documentation gap

| Field | Pre-run declaration |
| --- | --- |
| Project lane | Daily-driver operator documentation |
| Material outcome sought | A checklist of troubleshooting entries the quickstart is missing regarding backend configuration and route-model bindings, to seed a future docs change request |
| Why timely | CR-DD-014 landed route-model bindings on `main`; the quickstart Troubleshooting section documents no backend, model, route-binding, or context failure mode at all |
| Observable usefulness criterion | A checklist whose items are grounded in the supplied configuration and quickstart excerpt, and which the operator would carry into a docs CR without inventing the content from scratch |
| Privacy class | `local_only`; inputs are tracked public repository documentation and configuration |
| Ordinary fallback path | Write the checklist by hand from the same two files |
| Planned inputs | `triagecore.toml` (953 chars) and a 597-char quickstart Troubleshooting excerpt |

### Trial 010 (planned) — Evidence-record completeness checklist

| Field | Pre-run declaration |
| --- | --- |
| Project lane | Daily-use evidence window operations |
| Material outcome sought | A completeness checklist for what a daily-use evidence record must contain, derived from the declared Window Protocol |
| Why timely | This Day-2 record is being written now and must satisfy the protocol; a derived checklist is used to check it before commit |
| Observable usefulness criterion | A checklist that reproduces the protocol's required fields without adding invented requirements, usable as a pre-commit check against this record |
| Privacy class | `local_only`; input is a tracked excerpt of the Day-1 record |
| Ordinary fallback path | Re-read the Window Protocol section manually and check the record against it |
| Planned inputs | A 1,373-char excerpt of the Day-1 Window Protocol section |

Neither task is a retry. Neither was invented to exercise `tc run`; both have a stated
fallback the operator would otherwise use.

## Day-2 Attempt Records

Both runs used the checked-in configuration at `3f1cce0`. **No configuration was modified,
declared, or restored during this session**, which is a difference from Day-1 Trials 002–008.
The tracked tree was clean before and after.

### Trial 009 — Quickstart troubleshooting documentation gap

**Eligibility:** Eligible real operator task.

| Field | Record |
| --- | --- |
| Project lane, downstream use, disposition | Daily-driver operator documentation; intended to seed a future docs change request; operator disposition **`revised`** |
| Purpose and success criterion | Identify troubleshooting entries missing from the quickstart regarding backend configuration and route-model bindings. Prompt 273 characters; supplied data 1,550 characters across `triagecore.toml` and a quickstart Troubleshooting excerpt. Success required grounded checklist items the operator would carry into a docs CR without inventing content. |
| Plan and context | No `--plan` preview was run, so no preview event exists and none is reconstructed. Privacy passed as `local_only`. Inputs were sized against the 4096-token runtime ceiling, not the planner's 27,648-token figure. |
| Configuration and capability | Checked-in `triagecore.toml`. The CLI reported `local capability: unknown (no usable observation); proceeding on the explicit declaration`. The ledger recorded `capability_state: configured`, `capability_source_type: operator_config`, `capability_config_reference: triagecore.toml:[capability]`, declared classes `local_fast` and `local_heavy`, bindings matching CR-DD-014, and `capability_route_binding_issues: {}`. |
| Actual route and terminal outcome | `task_class: docs_update`, complexity `low`, sensitivity `low`. Route audit allowed; route decision selected `local_fast` with `qwen2.5-coder:7b-triagecore`, matching the declared binding, at `fallback_depth: 0`. Worker status `success`; terminal outcome **completed**. |
| Evidence completeness | Five ledger events: `task_created`, `runner_selected`, `route_audit`, `route_decision`, `worker_result`. Full worker telemetry: `elapsed_seconds` 9.86, `timeout_seconds` 120, 550 input, 222 output, 772 total tokens, 78.30 tokens/second. **Validation `not_run`.** |
| Privacy and egress | `local_only`; privacy preflight passed; no cloud egress was observed, subject to the Pre-Run Control Finding 5 qualification. |
| Tokens and validation | Full execution token evidence exists. No validator was supplied by the `tc run` path, so no validation was performed. |
| Usefulness | Partially useful. The output reproduced the four existing troubleshooting entries verbatim and added exactly the two gap areas sought (backend configuration; route-model bindings). Both new items are thin, and one is **inaccurate**: it states route-model bindings are set "in your application code", when `triagecore.toml:[capability]` is where they are configured. The operator would rewrite both items before use. |
| Failure, friction, retry, bypass | No failure, no retry, no bypass. Friction: the timeout of 120 s was received because `docs_update` falls in the `routers.py` docs branch, not because the operator selected it — see Pre-Run Control Finding 1. |
| Claim limits | One completed `local_fast` `docs_update` generation under the merged CR-DD-014 bindings on `main`. It supports no reliability, latency-distribution, validation, accuracy, or readiness claim. The inaccurate checklist item is direct evidence that completion is not correctness. |

### Trial 010 — Evidence-record completeness checklist

**Eligibility:** Eligible real operator task. Not a retry of Trial 009 — a distinct purpose,
distinct inputs, and a distinct downstream use.

| Field | Record |
| --- | --- |
| Project lane, downstream use, disposition | Daily-use evidence window operations; used to check this Day-2 record before commit; operator disposition **`accepted`** |
| Purpose and success criterion | Derive a completeness checklist from the declared Window Protocol. Prompt 232 characters; supplied data 1,373 characters. Success required reproducing the protocol's required fields without adding invented requirements. |
| Plan and context | No `--plan` preview was run; no preview event exists. Privacy passed as `local_only`. |
| Configuration and capability | Identical to Trial 009: checked-in configuration, `capability_state: configured`, `capability_source_type: operator_config`, bindings matching CR-DD-014, no binding issues. |
| Actual route and terminal outcome | `task_class: docs_update`, complexity `low`. Route decision selected `local_fast` with `qwen2.5-coder:7b-triagecore` at `fallback_depth: 0`. Worker status `success`; terminal outcome **completed**. |
| Evidence completeness | Five ledger events, same shape as Trial 009. Worker telemetry: `elapsed_seconds` 5.26, `timeout_seconds` 120, 366 input, 141 output, 507 total tokens, 96.48 tokens/second. **Validation `not_run`.** |
| Privacy and egress | `local_only`; privacy preflight passed; no cloud egress was observed, with the Finding 5 qualification. |
| Tokens and validation | Full execution token evidence exists. No validator was supplied, so no validation was performed. The operator check described below is a manual disposition, **not** a validation event. |
| Usefulness | Useful. The output reproduced all ten protocol-required fields in order and added no invented requirement, meeting the stated criterion. It was then applied against this record: each Day-2 attempt table above carries all ten fields. |
| Failure, friction, retry, bypass | No failure, no retry, no bypass, no friction observed on the governed path. |
| Claim limits | One completed `local_fast` `docs_update` generation whose output was a faithful restatement of supplied text. Faithful restatement of a short supplied document is a substantially easier task than the synthesis attempted in Trial 009, and this result should not be generalized to synthesis tasks. It supports no reliability, validation, or readiness claim. |

## Day-2 Aggregate

| Measure | Day-2 result |
| --- | --- |
| Eligible real `tc run` executions | 2 (two distinct task purposes; no retries) |
| Completed | 2/2 |
| Blocked | 0/2 |
| Handoff after worker failure | 0/2 |
| Useful output through `tc run` | 2/2, dispositions `accepted` (1) and `revised` (1) |
| Validation completed | 0/2 |
| Model/task-payload cloud egress | 0/2 observed |
| External metadata-only network contact | 2/2 runs performed the unconditional `8.8.8.8:53` reachability probe (see Pre-Run Control Finding 5) |
| Execution token linkage | 2/2 with full token and elapsed telemetry |
| Route/binding coherence | 2/2 route decisions selected the model declared for the chosen route class |
| Route classes exercised | `local_fast` only; `local_heavy` deliberately not exercised |
| Configuration changes | 0 |

## Window Progress

| Measure | Cumulative |
| --- | --- |
| Distinct local operator days with evidence | 2 of the required ≥7 (2026-08-01, 2026-08-02) |
| Eligible real `tc run` executions | 8 (6 on Day 1 including 1 retry; 2 on Day 2) |
| Completed | 3/8 |
| Validation completed | 0/8 |
| Operator dispositions on completed runs | 1 `accepted`, 2 `revised` |

## Derived Findings — Not Fixes

1. Both `local_fast` runs completed with full token and elapsed telemetry under the merged
   CR-DD-014 bindings on `main`, and both selected the model declared for the route class.
   This extends the Day-1 corrected-session observation from one completion to three, all on
   `local_fast`, all under `docs_update`.
2. **Completion is still not acceptance, and now not correctness either.** Trial 009
   completed with `status: success` and full telemetry while producing a checklist item that
   misstates where route-model bindings live. No governed surface detected this; the only
   thing that caught it was operator reading. `validation_status` remained `not_run` for both
   runs because the `tc run` path supplies no validator.
3. `validation_status: not_run` has now been recorded for **every eligible real task in the
   window** — 8 of 8. Validation is not an intermittent gap; it has never run.
4. The observed `timeout_seconds` of 120 in both runs is explained by the pre-run source
   reading, not by configuration: `docs_update` falls in the `routers.py` docs branch. The
   configured `triagecore.toml` value of `timeout_seconds = 30` was **not** the value used by
   either run, which is direct runtime confirmation of Pre-Run Control Finding 1.
5. `capability_state` recorded `configured`, not `observed_available`, because no probe
   record was supplied to the runs. The separately captured probe record in the Day-2
   isolation directory was **not** consumed by either run and is baseline evidence only.
6. The Day-2 `route_decision` payloads contain `capability_declared_route_classes` populated
   with both classes and contain **no** `capability_supported_route_classes` field at all —
   distinct from the Day-1 corrected session, where that field was present but empty. The
   population path for supported-class evidence remains unestablished.
7. `lm_studio_ok: true` again entered both route decisions as an input. Nothing in this
   session verified LM Studio state; LM Studio supervised no trial. The flag's provenance
   remains unestablished, exactly as on Day 1.
8. Day-2 exercised only `local_fast` under `docs_update`. Per Pre-Run Control Finding 3, that
   is the **only** category reaching `local_fast` at `3f1cce0`, so window evidence for that
   route class is structurally confined to one task category.

These findings do not authorize implementation changes.

## Closeout Verification

| Check | Result |
| --- | --- |
| Main ledger SHA-256, before and after | Unchanged: `4981E97B12BE3EE0D04B6C8CD98B85CB2C70FC7191B982507B094B66A3ADE619` |
| Isolated Day-2 ledger | `.triagecore/daily-use-window/2026-08-02/ledger.jsonl`; SHA-256 `EE5740095A2E58F67AFC4B7BA37AFB834432D0C19BED8C589D9B5BDF82EE7F83` |
| Isolated ledger audit | 10 records; repository `find_forbidden_persistent_fields` reported **0 violations** |
| Tracked tree after trials | Clean except this untracked record |
| Configuration restored | Not applicable — configuration was never modified |
| Stop conditions triggered | None |

The unchanged main-ledger hash establishes only that these trials did not change that file.
Hashes establish byte identity only.

**Stop conditions reviewed and not triggered:** no prompt or sensitive source content in
persistent telemetry (invariant check clean); main ledger unchanged; selected model matched
the declared binding in both runs; no unexpected external egress observed; configuration
never modified so restoration was not required; no two failures produced indistinguishable
evidence, because there were no failures; no retry occurred; and troubleshooting produced no
additional runs.

## Uncertainty and Limitations

- This record covers one local operator day. The declared 7–14 day window remains open, with
  2 of ≥7 required distinct days recorded.
- Two eligible tasks is a deliberately small sample and supports no rate, reliability, or
  latency-distribution claim of any kind.
- **Both tasks were documentation tasks, and this was forced by the routing code**, not
  chosen for convenience: `docs_update` is the only category reaching `local_fast` at
  `3f1cce0`. Day-2 evidence therefore says nothing about `local_fast` behavior on any other
  task category.
- `local_heavy` was deliberately not exercised. `local_heavy` generation remains unobserved
  end to end across the entire window.
- No validation completed, for either Day-2 task or any earlier eligible task in the window.
- Trial 009's disposition is `revised` and its output contained a factual error. Trial 010's
  disposition is `accepted`, but its task was faithful restatement of a supplied document,
  which is materially easier than synthesis.
- Trial 010 is partly self-referential: it produced a checklist used to check this record.
  It is recorded as eligible because it supported an actual deliverable with a stated manual
  fallback, but a reader should weigh the self-reference.
- No `--plan` preview was run for either task, so this record contains no preview evidence
  and reconstructs none.
- Capability evidence was `configured` (operator declaration), not `observed_available`.
  Declarations do not establish class-to-model binding at runtime; the matching
  `selected_model` values are what was actually recorded.
- The probe establishes observed reachability and self-reported inventory at one time. It
  does not establish capability, binding, or generation success, and it was not consumed by
  the runs.
- The Pre-Run Control Findings are readings of source at `3f1cce0`, not runtime measurements,
  except where a Day-2 runtime observation is explicitly cited as confirming one.
- Day-2 ran in a git worktree rather than the primary repository; this is a recorded method
  difference from Day 1.
- Day-2 UTC timestamps fall on 2026-08-03; all trials occurred within local operator day
  2026-08-02.
- CR-DD-015A does not exist and its drafting is not authorized by this record. The
  failure-fidelity telemetry gap it is sequenced to address remains fully open.
- This record supports no readiness percentage and makes no safety, alignment, containment,
  certification, production-readiness, general model-quality, cost, energy, or authorization
  claim.
- This document grants no implementation, execution-expansion, cloud, approval, or merge
  authority.

## Next Gate

Continue the declared window on later distinct local days. The `local_heavy` diagnosis is
complete and no further diagnostic runs are justified before the corrective slices; the
remaining `local_heavy` work is the **proposed** CR-DD-015A → CR-DD-015B sequence, whose
drafting requires separate authorization. Neither identifier exists as a record.
Docker/microVM execution-venue evaluation remains research-only until real container topology
is observed.
