# CR-104: Runtime Strategy Evidence Record

## Status

Implemented

## Scope

- Add a deterministic runtime strategy evidence record.
- Represent one orchestration strategy as typed model/runtime steps.
- Derive total estimated tokens, model-call count, and handoff count.
- Add focused tests for the small-first compact fixture, derived totals, handoff bounds, deterministic JSON, and privacy invariants.
- Add operator documentation for the measurement-only boundary.

## Numbering Note

The source planning note referred to this as CR-094, but this checkout already uses CR-094 for token-efficiency evidence records. This implementation uses CR-104, the next open number after the current CR-100 through CR-103 route/worker telemetry lane.

## Non-Goals

- No live model calls.
- No automatic routing changes.
- No quality-improvement claims.
- No model comparison dashboard.
- No cost-dollar, energy, or emissions claims.
- No persistence of raw prompts, raw context, raw model outputs, secrets, or stack traces.

## Acceptance Criteria

- [x] `triage_core/runtime_strategy_evidence.py` exists.
- [x] The record can represent `small_first_compact` with Ollama worker and LM Studio reviewer steps.
- [x] Totals are derived and validated against step estimates.
- [x] Handoff counts are bounded by step transitions.
- [x] The record remains metadata-only and passes persistent privacy checks.
- [x] Focused tests cover record shape, deterministic JSON, invalid totals, invalid handoff counts, and mapping round trip.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
- `git status --short`
