# `local_heavy` Diagnostic Session — 2026-08-07

## Status and Scope

**Bounded diagnostic session. Not daily-use evidence.** This record is deliberately outside
the daily-use evidence window's day and trial numbering. It is not Day 4, not Trial 012, and
it does not advance the window's distinct-day count or eligible-task count.

The session answered one bounded question:

> Can the currently configured `local_heavy → deepseek-r1:latest` path complete one
> materially useful, source-grounded architecture-analysis task end to end through governed
> TriageCore execution?

**Answer: no, for this invocation.** The invocation did not complete through the currently
configured governed `local_heavy` path within the 120-second read timeout.

One governed invocation was performed under explicit operator authorization. No retry was
performed or authorized. No trivial control run was performed. No implementation change was
made during the session.

This record makes no implementation recommendation beyond the observations below.

## Why This Session Exists

The daily-use evidence window had, at the time of this session, recorded four governed
completions, all on `local_fast` under `docs_update`, and two `local_heavy` attempts
(Day-1 Trials 006 and 007), both of which failed before returning a completed response.
`local_heavy` remained unobserved end to end.

A genuinely needed architecture-analysis task became available: comparing current TriageCore
against a published agent-sandbox control set. Source inspection established that such a task
cannot reach `local_fast` under the current classifier (see Precondition Finding 1), so it
was routed to `local_heavy` deliberately, as a diagnostic, rather than reworded to satisfy
the router.

The alternative approaches were considered and rejected: running it as ordinary daily-use
evidence would have entangled a Day-4 observation with an already-open `local_heavy`
reliability question, and manufacturing a `docs_update`-shaped surrogate task would have
optimized for the router rather than tested TriageCore honestly.

## Precondition Findings — Source Inspection Before Execution

Established read-only against `main` @ `3f1cce0` before the invocation.

### 1. Substantive architecture work cannot naturally exercise `local_fast`

`TaskClassifier.classify_deterministic` (`triage_core/classifier.py:61-78`) assigns a category
by ordered keyword match on the prompt text. `client.py`'s `sensitivity_map`
(`triage_core/client.py:464-467`) then assigns `security_review` the sensitivity `high`, and
`HIGH_SENSITIVITY_VALUES` (`triage_core/routing/resilience_router.py:11`) contains `high`, so
`choose_resilience_route` appends `ROUTE_HUMAN_HANDOFF` as the first and only candidate
(`resilience_router.py:106-107`) before any other routing logic is evaluated.

`architecture_planning` maps to complexity `high` (`client.py:456`) and sensitivity `medium`.
`_prefers_local_heavy` (`resilience_router.py:224-225`) returns true for any medium or high
complexity, so `local_heavy` is the preferred candidate.

Consequence: at current `main`, substantive architecture and containment work cannot
naturally exercise `local_fast`. A task reading as `security_review` terminates at human
handoff before generation; a task reading as `architecture_planning` prefers `local_heavy`.
This is a constraint on the current division of cognitive labor between route classes, not
merely prompt-engineering friction.

### 2. Route class is determined by prompt lexicon, not by evidenced execution policy

The category assignment is a substring match over the prompt only. Supplied file data does
not participate. Legitimate control-boundary analysis is therefore divertible to human
handoff, or to a different route class, by word choice rather than by any independently
evidenced property of the task.

`DangerDetector.SECRETS_AUTH` (`classifier.py:94`) applies the same mechanism to risk: the
standalone words `secret`, `password`, `auth`, `credentials`, `token`, and the literal `.env`
raise `risk_level` to `high` and `recommended_profile` to `blocked` when present in prompt
text, irrespective of intent.

### 3. The `SpecialistRouter` category timeout is on the live execution path

`tc_cli.py:1229` calls `TriageClient.run_task`. At `client.py:117-118`, `run_task` calls
`self.router.specialist.route_task(category, prompt, data)` and at `client.py:119` sets
`use_timeout = route_decision.get("timeout", self.engine.timeout)`. That is
`SpecialistRouter.route_task` in `triage_core/routers.py`, whose per-category table assigns
`architecture_planning` a `timeout` of 120 (`routers.py:95-102`).

This resolves a question left open by earlier sessions, which recorded the timeout source as
unestablished. The table is live code on the execution path, not dead code.

### 4. The unconditional reachability probe is on the live execution path

`is_internet_available()` (`routers.py:6`) opens a socket to `8.8.8.8:53`. It is called at
`routers.py:44`, the first statement of `SpecialistRouter.route_task`, before any risk or
category branch. By the call chain in Precondition Finding 3, it executes on every governed
`tc run`, including `--privacy local_only` runs.

**This is source-confirmed behavior, not runtime-observed behavior.** No network capture was
taken during this session. The distinction is preserved deliberately.

## Baseline and Evidence Isolation

| Item | Observation |
| --- | --- |
| Code under test | `main` @ `3f1cce0` |
| Configuration | Tracked `triagecore.toml`; `local_fast` → `qwen2.5-coder:7b-triagecore`; `local_heavy` → `deepseek-r1:latest`; `[backend] timeout_seconds = 30` |
| Configuration changes | 0. No temporary or uncommitted configuration was applied |
| Tracked tree | Clean before and after |
| Isolated diagnostic ledger | `.triagecore/local-heavy-diagnostic/2026-08-07/ledger.jsonl`; SHA-256 `E8837C1241315B70C4DB69AD28700476353609538C238A7B8C5B2FCDCC122B6F` |
| Isolated ledger audit | 5 records; repository `find_forbidden_persistent_fields` reported 0 violations |
| Main ledger SHA-256, before and after | Unchanged: `4981E97B12BE3EE0D04B6C8CD98B85CB2C70FC7191B982507B094B66A3ADE619` |
| Task input artifact | `.triagecore/local-heavy-diagnostic/2026-08-07/containment_matrix_evidence_bundle.md`; SHA-256 `A8A598F51D803528EF22832D8239735A094E2C966404FAAFF832176E6DBB3473`; 5,010 bytes |
| Metadata-only runtime probe | Not run this session |

The isolated evidence paths are gitignored local artifacts and are not committed by this
record. The diagnostic directory is separate from `.triagecore/daily-use-window/` so that
this session's evidence cannot be mistaken for window evidence.

## Preview Record

Two previews were run. Previews perform no model call and write no ledger record.

### Preview 01 — blocked fail-closed

Privacy preflight blocked before planning completed; `finding_codes=privacy_preflight_failed`,
CLI exit code 2.

Cause: the prepared evidence bundle described the privacy scanner's own credential-shaped
match patterns, and in doing so contained a literal bearer-style authorization phrase that
matched `SECRET_KEYS_REGEX` in `triage_core/privacy_scanner.py`. Packet metadata declared
`contains_sensitive_content=False`, so the scanner fail-closed.

No model call, no ledger write. No privacy control was weakened, disabled, or bypassed; no
`--no-ledger` or privacy override was used. The bundle's item 8 was reworded to describe the
match patterns without reproducing them, and the whole file was re-scanned clean before
retry. The task purpose, success criterion, and prompt were unchanged.

This is a valid control response to an over-broad input artifact. It is the second such block
in two sessions, both caused by input construction rather than task content.

### Preview 02 — passed

| Field | Value |
| --- | --- |
| Context | 1,498 estimated input tokens against 27,648 usable; `fits` |
| Privacy | `local_only`; preflight passed; `finding_codes: none`; `egress_eligible: False`; `cloud_posture: prohibited` |
| Advisory route | `local_heavy`; reason `local_heavy_available_for_medium_or_complex_task` |
| Classification | `architecture_planning`; `deterministic_risk_level: low` |
| Forecast | `configured_backend_binding` `ollama:deepseek-r1:latest`; `specialist_model_forecast` `deepseek-r1:latest`; `specialist_timeout_forecast_seconds` 120 |
| Review flag | `human_review_required: True` |
| Declared boundaries | `advisory_only: true`; `backend_probe_performed: false`; `live_health_observed: false`; `execution_performed: false`; `ledger_or_artifact_written: false`; `approval_granted: false` |

## Invocation Record

**One invocation. No retry.**

| Field | Record |
| --- | --- |
| `task_id` | `be26065b-fb7c-4011-ab30-2e9aa65f14f9` |
| Purpose | Produce a control-by-control comparison of current TriageCore against a published agent-sandbox control set, from a supplied source-evidence bundle. Real downstream use: selecting the next TriageCore architecture slice |
| Prompt and data | Prompt length 900 characters; ledger `data_length` 5,091 |
| Classification | `task_class: architecture_planning`; `task_complexity: high`; `task_sensitivity: medium` — matching the preview exactly |
| Route audit | `decision: allowed`; `reason_code: route_allowed`; `privacy_scan_passed: true`; `is_local_only: true` |
| Route decision | `selected_route: local_heavy`; `selected_backend: ollama`; `selected_model: deepseek-r1:latest`; `fallback_depth: 0`; reason `local_heavy_available_for_medium_or_complex_task` |
| Route/binding coherence | The selected model matches the `local_heavy` binding declared in `triagecore.toml:[capability]` and recorded in `capability_route_model_bindings` |
| Review flag versus terminal route | `human_review_required: true` was recorded while the terminal route remained `local_heavy`. The flag did not divert the run |
| Terminal outcome | `worker_result_status: worker_failed`; `status: handoff_required`; `failure_type: backend_error`; `failure_stage: local_backend_generate`; `backend_failure: true` |
| Console observation | `Local runtime error: Ollama backend unavailable at http://localhost:11434/api/chat: HTTPConnectionPool(host='localhost', port=11434): Read timed out. (read timeout=120)`. CLI exit code 3 |
| Ledger `elapsed_seconds` | 0.0 |
| Event wall-clock gap | `route_decision` 09:24:27.830902 → `worker_result` 09:26:29.874457 = approximately 122.04 seconds |
| `timeout_seconds` | 120, matching the preview forecast and the `routers.py` category table |
| Tokens | 0 input, 0 output, 0 total; `tokens_per_second` 0.0 |
| Validation | `validation_status: not_run`; `validator_name`, `validator_version`, `validator_scope` all null |
| Privacy and egress | `privacy_scan_passed: true`; `is_local_only: true`; `internet_ok: false`, which reflects Qwen cloud being disabled rather than network state. No model or task-payload cloud egress observed |
| Evidence completeness | Five ledger events: `task_created`, `runner_selected`, `route_audit`, `route_decision`, `worker_result`. `task_created` withheld prompt content and recorded lengths only |
| Capability | `capability_state: configured`; `capability_source_type: operator_config`; `capability_route_binding_issues` empty. The CLI printed: *local capability: unknown (no usable observation); proceeding on the explicit declaration in `triagecore.toml:[capability]`* |
| Output | None returned |

### Statement of what the token record does and does not establish

Zero token usage was recorded because no completed backend response was returned. This record
does not establish whether the model performed internal inference before the read timeout.

For a reasoning model in particular, an absent usage record is evidence about what TriageCore
received, not about what the backend did. No claim is made here about backend-internal
activity during the 120 seconds.

## Observations

1. **The invocation did not complete through the currently configured governed `local_heavy`
   path within the 120-second read timeout.** This is the third recorded `local_heavy`
   attempt in the project's evidence and the third that did not return a completed response.
2. **The earlier 30-second ceiling is not a sufficient explanation for the `local_heavy`
   failures.** Day-1 Trials 006 and 007 ran against a 30-second budget. This invocation had
   120 seconds, four times larger, against a substantially larger and more complex task, and
   still reached a read timeout.
3. **CR-DD-014 route/model binding worked.** `architecture_planning` → `local_heavy` →
   `deepseek-r1:latest` selected the model declared for the route class, with no binding
   issues recorded. Binding coherence is not the failing element.
4. **The advisory preview matched the actual execution on every predicted field**: route,
   model, classification, complexity, and timeout.
5. **The ledger still collapses an observed read timeout into a generic `backend_error` with
   `elapsed_seconds: 0.0`.** The recorded `worker_result` payload is not distinguishable in
   any field from Day-1 Trial 007's fast HTTP 400. The mechanism survives only in console
   output and in the wall-clock gap between ledger events.
6. **The wall-clock gap corroborates the console mechanism.** Approximately 122.04 seconds
   against a stated 120-second read timeout is consistent with the timeout plus connection
   overhead. This is the strongest failure-cause evidence recorded in the project so far, and
   it still exists only outside the durable ledger record.
7. **`human_review_required` and terminal `human_handoff` are separate concepts in the current
   architecture.** `resilience_router.py:101` sets a review flag when sensitivity is medium or
   high; `resilience_router.py:106` selects the human-handoff route only when sensitivity is
   in `HIGH_SENSITIVITY_VALUES`. This invocation was flagged for review and still routed to
   `local_heavy` for generation. Confirmed at runtime, not only by source reading.
8. **The unconditional reachability probe is source-confirmed on the live execution path and
   was not runtime-observed in this session.** See Precondition Finding 4. The distinction
   between source-confirmed and runtime-observed behavior is preserved deliberately and
   should not be collapsed in any downstream synthesis.
9. The intended analytical output was not produced, so no evaluation of it against
   independently established repository ground truth was possible.

## What This Session Does Not Establish

- It does not establish a cause for the timeout. Backend-internal activity, model reasoning
  expansion, memory pressure, and load behavior were not instrumented.
- It does not establish what timeout budget, if any, would be sufficient.
- It does not establish whether budget is the binding constraint at all, as opposed to
  another factor.
- It does not establish that `deepseek-r1:latest` cannot serve this route class. One
  invocation at one configuration does not support a capability claim about the model.
- It does not establish anything about `local_heavy` under different input sizes, different
  task classes, or a different configured model.
- It does not establish a reliability rate. Three non-completing attempts across two sessions
  are not a rate.
- It does not observe the unconditional reachability probe's network traffic.

## Relationship to Other Work

This session strengthens the motivation for the previously sequenced failure-fidelity
correction, because Observation 5 reproduces exactly the condition that correction addresses.
It does not authorize, draft, or scope that correction, and telemetry repair and
containment architecture remain separate work lanes.

This record grants no implementation, execution-expansion, cloud, configuration, approval, or
merge authority, and recommends no fix. No timeout was changed, no model was changed, and no
code was modified during or as a result of this session.

## Claim Limits

This record covers one governed invocation, at one configuration, on one host, on one date.
Hashes establish byte identity only, not correctness, authenticity, authorization, or
provenance. This record supports no readiness percentage and makes no safety, alignment,
containment, certification, production-readiness, general model-quality, cost, energy, or
authorization claim.
