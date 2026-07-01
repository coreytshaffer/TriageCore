# CR-092: Experiment Observability Trace Contract

## Status

Implemented

## Scope

- Add a durable experiment trace record contract that links task fixture digest,
  experiment run, agent group, runtime backend profile, runtime efficiency
  record, quality gate result, claim validity, and baseline lineage.
- Add a focused helper for deriving trace records from existing synthetic
  runtime experiment results.
- Add a JSON schema for trace-record exports.
- Add focused tests for missing identifiers, quality-gate coupling, energy claim
  boundaries, failed-result failure reasons, and deterministic JSON output.
- Add operator documentation defining the observability trace purpose and
  fail-closed rules.

## Non-Goals

- No live model calls.
- No runtime benchmark harness.
- No ledger persistence path.
- No default routing changes.
- No runtime migration from Ollama to llama.cpp.

## Acceptance Criteria

- [x] `triage_core/experiment_traces.py` exists.
- [x] `schemas/experiment_trace_record.schema.json` exists.
- [x] `tests/test_experiment_traces.py` exists.
- [x] `docs/operations/experiment-observability-traces.md` exists.
- [x] Trace records reject missing `experiment_id`.
- [x] Efficiency-valid claims require a passed quality gate result.
- [x] Energy-valid claims require an energy-capable measurement tier and
  measured comparison values.
- [x] Failed quality gates require an explicit failure reason.
- [x] Trace lineage must match the candidate group.

## Validation

- `python -m pytest tests/test_experiment_traces.py tests/test_runtime_experiments.py tests/test_runtime_efficiency.py -q`
- `python -m py_compile triage_core/experiment_traces.py`
- `git diff --check`
