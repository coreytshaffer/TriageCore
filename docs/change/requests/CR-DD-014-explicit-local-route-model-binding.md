# CR-DD-014: Explicit Local Route Model Binding

## Status

Approved for the separately authorized bounded correction described here. The implementation
candidate is prepared and verification is in progress. This record is not a closeout, merge
record, readiness claim, or source of standing authority.

## Problem Statement

The 2026-08-01 Day-1 daily-use evidence window exposed three related failures:

1. The checked-in Ollama base URL ended in `/v1`, while the native `OllamaBackend` appends
   `/api/chat`, so the baseline console reported HTTP 404. Source inspection, not console
   output, shows that the configured base and native suffix constructed `/v1/api/chat`.
2. The checked-in default model, `qwen2.5-coder-7b-instruct`, was absent from the metadata-only
   observed Ollama inventory. The observed identifiers were
   `qwen2.5-coder:7b-triagecore` and `deepseek-r1:latest`.
3. A governed `local_fast` route selected the hardcoded specialist identifier
   `deepseek/deepseek-r1-0528-qwen3-8b`, which was absent from that observed inventory.
   Reachability and route declarations therefore did not produce a coherent route-to-model
   binding.

The direct `ollama run qwen2.5-coder:7b-triagecore` control succeeded for the small Day-1
prompt. That control isolates one backend/model path only; it is not governed execution,
class-suitability evidence, or proof of general availability.

## Authorized Objective

Correct only the native Ollama endpoint configuration, replace stale model identifiers with
the observed installed identifiers, and bind each declared local route class to one explicit
model. The plan preview, route-decision evidence, and executed backend request must identify
the same bound model.

## Exact File Allowlist

Implementation may modify only:

- `triagecore.toml`
- `triage_core/config.py`
- `triage_core/capability_evidence.py`
- `triage_core/client.py`
- `triage_core/run_plan.py`
- `triage_core/routers.py`
- `triage_core/tc_cli.py`
- `tests/test_config.py`
- `tests/test_backends.py`
- `tests/test_capability_binding.py`
- `tests/test_client.py`
- `tests/test_tc_run_cli.py`
- `tests/test_tc_run_plan_cli.py`
- `docs/change/requests/CR-DD-014-explicit-local-route-model-binding.md`

No other production, test, documentation, workflow, schema, or generated file is authorized.
If the correction cannot be completed within this allowlist, stop and request a separately
approved scope change.

## Configuration Contract

The checked-in configuration must use the native Ollama root and the exact observed model
identifiers:

```toml
[backend]
default_type = "ollama"
default_model = "qwen2.5-coder:7b-triagecore"
base_url = "http://localhost:11434"

[capability]
declare_local_fast = true
declare_local_heavy = true
local_fast_model = "qwen2.5-coder:7b-triagecore"
local_heavy_model = "deepseek-r1:latest"
```

The two declaration flags are explicit operator authorization for the corresponding route to
be considered. They are not observed capability, model suitability, generation success,
human approval, or authorization for any task effect. The model strings bind route classes;
they do not choose the route or weaken privacy, review, target-file, or effect-authority
bounds.

The time-bound Day-1 probe path remains local evidence and must not be committed as a durable
configuration dependency. Environment overrides must not silently replace a route binding
without the resulting configured value being carried into preview and route evidence.

## Fail-Closed Binding Rules

1. A declared local route with a missing, blank, or malformed model binding is unavailable.
   It must not fall back to the backend default, a specialist-router constant, an alias, or
   the first model in an inventory response.
2. When a fresh, valid observed inventory is available, a route whose exact bound model is
   absent from that inventory is unavailable. The mismatch must remain distinguishable from
   endpoint unreachability and from missing or stale observation.
3. Fresh observed unavailability continues to override declarations and bindings.
4. With no usable observation, an otherwise complete declaration and binding may retain the
   existing `configured` consideration state, but it must not be reported as observed
   availability.
5. A selected local route without a resolved model binding must terminate before worker
   invocation and record the bounded missing-or-mismatch reason when a ledger is open.

## Execution, Evidence, and Plan Parity

- Route selection remains the responsibility of the existing resilience router. Bindings
  constrain only which model may serve an already selected local route.
- For a governed local attempt, one resolved binding must supply all of:
  - plan `configured_backend_binding`;
  - `route_decision.selected_model`;
  - the model sent to the local backend; and
  - worker-result model evidence.
- The backend's temporary model value must be restored after success, failure, or exception.
- Capability evidence must record the declared route classes, their privacy-safe configured
  bindings, evidence state, and any exact-inventory mismatch without storing prompts, task
  data, or secrets.
- Early-block capability binding issues are retained in `runner_selected` metadata because a
  `route_decision` event may not exist.
- Preview remains deterministic and non-executing. It may read checked-in configuration but
  must not probe, call a backend, write a ledger event, or convert configured evidence into
  observed evidence.
- Direct `run_task` callers that omit capability evidence retain their existing compatibility
  behavior. This CR does not expand that compatibility lane or make it daily-driver evidence.

## Focused Verification Plan

Run only the focused offline tests covering the authorized seams:

```powershell
python -m pytest tests/test_config.py tests/test_backends.py tests/test_capability_binding.py tests/test_client.py tests/test_tc_run_cli.py tests/test_tc_run_plan_cli.py tests/test_routers.py
```

The focused tests must establish:

- native Ollama generation uses `http://localhost:11434/api/chat`;
- both exact route bindings load from configuration;
- missing bindings and fresh inventory mismatches fail closed before generation;
- observed-unavailable precedence remains unchanged;
- `local_fast` and `local_heavy` use and record their respective exact bindings;
- plan, route-decision, backend, and worker model values agree; and
- previews make no network, backend, ledger, or execution call.

After focused tests pass, run the existing full offline suite to detect unintended routing,
privacy, evidence, and compatibility regressions. Test success is implementation evidence,
not live backend or readiness evidence.

## Live Verification Plan

Live verification remains local-only and operator initiated:

1. Confirm the tracked worktree and main-ledger hash before the trial.
2. Create a fresh metadata-only Ollama probe record in an isolated, gitignored evidence
   directory. Validate it with the existing repository contract and confirm that both exact
   configured identifiers appear in its self-reported inventory.
3. Preview the paired small and large materially useful tasks. Confirm the configured binding
   matches the selected local route and that preview performs no execution.
4. Execute each task through `tc run` against an isolated ledger with `local_only` privacy and
   no cloud authorization.
5. Inspect route, worker, token, validation, privacy, usefulness, friction, and bypass evidence.
   Confirm plan, route-decision, backend, and worker model parity for every worker attempt.
6. Run the repository privacy-invariant audit on the isolated ledger and confirm the tracked
   tree and main-ledger hash afterward.

Both success and failure must be retained. A direct Ollama command may be used only as a
separately labeled control and never counted as governed `tc run` evidence.

## Exclusions

This CR does not authorize:

- model aliases, model installation, model download, or automatic selection of an inventory
  entry;
- automatic probes, background polling, runtime discovery, or post-resolution runtime
  revalidation;
- cloud configuration, cloud authorization, provider expansion, egress, or fallback changes;
- routing-policy, classifier, offload, circuit-breaker, budget-enforcement, privacy-scanner,
  approval, resume, target-file, or effect-authority changes;
- parser, ingestion, TriageDesk, workflow, schema-version, or unrelated documentation work;
- claims of model suitability, comparative quality, context capacity, speed, safety,
  alignment, containment, certification, production readiness, or daily-driver readiness.

## Rollback

Rollback is the exact inverse of the bounded implementation:

1. Restore the previous configuration values and remove the new route-binding getters and
   binding flow only through a reviewed revert of the bounded change.
2. Restore the prior governed execution and preview behavior without editing or deleting
   existing ledger or trial evidence.
3. Re-run the same focused offline tests and verify the worktree diff contains only the
   authorized rollback.
4. Record that the correction was rolled back and stop live success-path trials until a new
   bounded decision is approved.

Do not rewrite evidence to make a rollback appear successful.

## Authority Boundary

This CR grants one bounded implementation and verification pass within the exact allowlist.
It grants no standing authority for follow-up correction, refactoring, integration, branch
expansion, merge, push, release, model installation, configuration drift, or future daily-use
execution. Human review of the exact resulting diff and verification evidence remains
required before any separately authorized integration action.

Local route declarations authorize consideration only. They do not authorize mutation,
external egress, consequential effects, artifact acceptance, or bypass of task-specific human
approval.

## Uncertainty and Limitations

- The observed inventory is one self-reported metadata snapshot and may become stale.
- Only `qwen2.5-coder:7b-triagecore` has a successful Day-1 direct-generation control;
  `deepseek-r1:latest` was observed in inventory but was not generation-tested in that window.
- Assigning the observed models to `local_fast` and `local_heavy` is an operator configuration
  decision, not empirical evidence that either model satisfies the class label.
- A fresh inventory match proves name presence only, not loadability, capacity, output
  quality, latency, safety, or task suitability.
- The correction does not close the known post-resolution revalidation gap.
- No successful governed execution, nonzero execution-token record, completed validation, or
  measured human-review burden existed at authorization time.
- Passing focused or live checks supports only the named configuration, routes, models,
  tasks, environment, and evidence window. It does not support generalized readiness or
  safety claims.
