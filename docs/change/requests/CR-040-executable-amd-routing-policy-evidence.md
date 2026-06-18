# CR-040: Executable AMD Routing Policy Evidence

## Status

Implemented

## Scope

Add a minimal pure-Python routing policy that classifies tasks across:

- `local`
- `deterministic`
- `amd_cloud`
- `blocked`

This change:

- adds `triage_core/routing/policy.py`
- adds focused routing-policy tests
- keeps routing behavior pure and manifest-driven
- preserves the existing Qwen and demo flow without runtime integration changes

## Non-Scope

- Do not add AMD credentials.
- Do not add ROCm SDK calls.
- Do not add live API calls.
- Do not add cloud deployment scripts.
- Do not add backend client code.
- Do not add async worker orchestration.
- Do not change existing Qwen routing behavior.

## Acceptance Criteria

- [x] A pure routing policy module exists.
- [x] The policy can return `local`, `deterministic`, `amd_cloud`, and `blocked`.
- [x] The policy can return `allowed`, `blocked`, and `approval_required`.
- [x] AMD routing behavior is driven by task-packet and manifest fields.
- [x] Focused tests prove local, deterministic, AMD approval-required, AMD blocked, and AMD allowed-after-approval paths.
- [x] No live AMD credentials or network calls are introduced.
- [x] Existing Qwen/demo behavior remains untouched.

## Validation

```powershell
python -m py_compile triage_core\routing\policy.py
python -m pytest tests\test_routing_policy.py -q
python -m pytest -q
git diff --check
git status --short
```
