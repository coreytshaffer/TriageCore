# CR-106: Strategy Delta Calculation

## Status

Implemented

## Scope

- Add `compute_strategy_delta(baseline, candidate)` to compare two existing
  runtime strategy evidence records for the same task id.
- Compute estimated token delta, percent delta, model-call delta, and handoff
  delta relative to the baseline.
- Add a closed, deterministic interpretation vocabulary: `token_saving`,
  `token_saving_with_added_handoff`, `token_neutral`,
  `orchestration_overhead`, and `invalid_comparison`.
- Add `compute_fixture_strategy_deltas()` to derive all candidate deltas
  against the `heavy_only` fixture baseline.
- Update operator documentation with the delta record shape, label rules, and
  quality non-claims.

## Non-Goals

- No live Ollama, LM Studio, or hosted model calls.
- No model telemetry adapters.
- No dashboards.
- No routing behavior or strategy selection changes.
- No signing semantics or governance surface changes.
- No quality-improvement claims while quality gates are `not_evaluated`.

## Description

CR-105 produced deterministic comparison fixtures for four orchestration
shapes. This slice adds the comparison arithmetic: a candidate strategy record
is measured against a baseline record and the result is a metadata-only delta
record with boring, closed interpretation labels. Invalid comparisons
(mismatched task ids, identical strategies, zero-token baselines) return
`invalid_comparison` with null deltas instead of raising, so downstream
consumers get one deterministic shape.

The fixture deltas against `heavy_only` show `small_first_compact` saving an
estimated 51.5% of tokens at the cost of one added handoff,
`small_only` saving 64.2% with no added handoff, and the `over_orchestrated`
negative control costing 37.3% more — confirming the delta calculation can
report when extra orchestration loses to the baseline.

## Acceptance Criteria

- [x] `small_first_compact` vs `heavy_only` reports a negative token delta and
  `token_saving_with_added_handoff`.
- [x] `over_orchestrated` vs `heavy_only` reports a positive token delta and
  `orchestration_overhead`.
- [x] `small_only` vs `heavy_only` reports `token_saving`.
- [x] Equal-token candidates report `token_neutral`.
- [x] Mismatched task ids, identical strategies, and zero-token baselines
  report `invalid_comparison` with a closed reason vocabulary and null deltas.
- [x] Delta records are deterministic, metadata-only, and pass the persistent
  privacy invariant.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py`
- `python -m py_compile triage_core/runtime_strategy_evidence.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
