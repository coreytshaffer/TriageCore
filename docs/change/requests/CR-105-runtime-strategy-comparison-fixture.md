# CR-105: Runtime Strategy Comparison Fixture

## Status

Implemented

## Scope

- Add deterministic comparison fixtures for multiple runtime strategy shapes.
- Cover `heavy_only`, `small_first_compact`, `small_only`, and `over_orchestrated` for the same task id.
- Derive per-strategy model-call count, handoff count, estimated total tokens, estimated tokens by backend, and quality-gate status.
- Include `over_orchestrated` as a negative-control fixture showing that more orchestration can cost more than a heavy-only baseline.
- Update operator documentation for interpreting the fixture.

## Non-Goals

- No live Ollama, LM Studio, llama.cpp, or hosted model calls.
- No CLI report command yet.
- No routing behavior changes.
- No quality-improvement claims.
- No cost, energy, or emissions claims.

## Acceptance Criteria

- [x] Comparison fixtures share one task id.
- [x] Fixtures include `heavy_only`, `small_first_compact`, `small_only`, and `over_orchestrated`.
- [x] Derived metrics include strategy name, model calls, handoffs, estimated total tokens, estimated tokens by backend, and quality-gate status.
- [x] `over_orchestrated` is more expensive than both `heavy_only` and `small_first_compact` in the fixture.
- [x] Focused tests validate the comparison summary and backend totals.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
- `git status --short`