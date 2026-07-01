# CR-093: Experiment Trace Export Smoke

## Status

Implemented

## Scope

- Add a deterministic smoke exporter for one synthetic experiment trace record.
- Write reviewer-facing artifacts to an explicit output directory.
- Keep the slice pure and local: no CLI wiring, no ledger writes, and no live
  model calls.
- Add focused tests for fail-closed output handling, deterministic export
  content, and CR-092 validation boundaries.
- Add operator documentation clarifying what the smoke artifact proves and what
  it does not prove.

## Non-Goals

- No live benchmark execution.
- No runtime migration.
- No routing changes.
- No identity or signature mutation.
- No measured energy claims.
- No writes to `.triagecore/ledger.jsonl`.

## Acceptance Criteria

- [x] `triage_core/experiment_trace_smoke.py` exists.
- [x] `tests/test_experiment_trace_smoke.py` exists.
- [x] `docs/operations/experiment-trace-smoke.md` exists.
- [x] `docs/change/requests/CR-093-experiment-trace-export-smoke.md` exists.
- [x] Export requires an explicit output directory.
- [x] Export rejects file paths used as output directories.
- [x] Export writes deterministic `experiment_trace_record.json` output.
- [x] Export writes deterministic reviewer-facing summary markdown.
- [x] Exported traces use `token_proxy` evidence and do not claim measured
  energy savings.

## Validation

- `python -m pytest tests/test_experiment_trace_smoke.py tests/test_experiment_traces.py tests/test_runtime_experiments.py tests/test_runtime_efficiency.py -q`
- `python -m py_compile triage_core/experiment_trace_smoke.py triage_core/experiment_traces.py`
- `git diff --check`
