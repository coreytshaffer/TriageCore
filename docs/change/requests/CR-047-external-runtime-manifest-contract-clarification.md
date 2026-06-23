# CR-047: External Runtime Manifest Contract Clarification

## Status

Implemented

## Scope

- clarify the external runtime manifest contract now that `schema_version` is explicitly enforced
- explicitly detail why aliases and wrappers are not trust boundaries
- link manifest requirements back to the runtime integrity and model provenance policy
- add inline minimal valid and invalid examples

## Non-Scope

- no changes to runtime behavior
- no changes to `external_runtime_adapter.py`
- do not expand cloud or runtime functionality

## Implementation Authority

Documentation-only repo slice with test validation.

## Description

This change updates the `external_runtime_manifest_schema.md` to explicitly list `schema_version` as enforced, link the manifest shape to the broader runtime integrity and model provenance policy, and explain why convenience aliases are not trust boundaries. Inline minimal examples for valid and invalid manifests are added for clarity. It also adds a reference to the active `change_log.md` and backlog.

## Acceptance Criteria

- [x] Documentation updated explaining `schema_version` requirement and what the adapter rejects.
- [x] Added connection to runtime integrity and model provenance policy.
- [x] Explicit explanation of why aliases/wrappers are not trust boundaries.
- [x] Minimal valid and invalid (missing `schema_version`) manifest examples added.
- [x] `triage_core/external_runtime_adapter.py` compiled cleanly.
- [x] `pytest tests/test_external_runtime_adapter.py` passes cleanly.

## Validation

```powershell
python -m py_compile triage_core\external_runtime_adapter.py
python -m pytest tests\test_external_runtime_adapter.py -q
git diff --check
```
