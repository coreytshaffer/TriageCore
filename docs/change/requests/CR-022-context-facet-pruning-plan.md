# CR-022: Context Facet Pruning Plan

## Status
Implemented

## Scope

Add deterministic metadata-first facet planning to the context budgeting layer.
Allow explicit facet exclusion without changing routing, `TaskPacket`, or model execution.

## Implementation Authority
Authorized for implementation.

## Description

This change extends `context_budget.py` with explicit facet metadata on context
items and a deterministic facet-pruning path. The planner can now mark items as
included or excluded by facet before deeper routing or compression logic sees
them, while keeping event payloads metadata-only.

## Acceptance Criteria
- [x] Context items have explicit `facet` metadata.
- [x] The context pack can exclude a facet deterministically.
- [x] Excluded facets appear in `excluded_items` with a rationale.
- [x] Event payloads remain metadata-only.
- [x] Existing tests pass.
- [x] New tests prove pruning behavior.
- [x] No routing behavior changes were introduced.
- [x] No `TaskPacket` schema changes were introduced.

## Non-Goals

- `TaskPacket` refactors.
- Scatter-gather or async execution.
- New model calls.
- Cloud handoff changes.
- Privacy relaxation.

## Validation

```powershell
python -m py_compile triage_core/context_budget.py
python -m pytest tests/test_context_budget.py -q
python -m pytest -q
```
