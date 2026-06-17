# CR-036: Model Manifest Runtime Warning Gate

## Status

Implemented

## Scope

Add a warning-only comparison layer between route metadata and a validated model
route manifest.

This change:

- adds a pure `compare_route_to_manifest(route_payload, manifest)` function
- returns a metadata-only `ManifestRouteWarningReport`
- warns when selected backend, selected model, or selected route metadata does
  not match the manifest
- warns when the manifest uses alias-only model identity
- warns when manifest integrity status is incomplete
- adds focused unit tests

## Non-Scope

- Do not block routing.
- Do not wire this into runtime execution yet.
- Do not probe Ollama, LM Studio, Qwen Cloud, local files, or model artifacts.
- Do not hash model files.
- Do not expand signing.
- Do not mutate the ledger schema.

## Acceptance Criteria

- [x] Add a pure function that compares route metadata to a validated manifest.
- [x] Matching route/backend/model metadata produces no warnings.
- [x] Backend mismatch produces a warning.
- [x] Model mismatch or alias-only identity produces a warning.
- [x] Incomplete manifest integrity status produces a warning.
- [x] Warning report contains only metadata, no raw prompt/data.
- [x] Add focused unit tests.
- [x] No runtime blocking behavior.

## Validation

```powershell
python -m py_compile triage_core\model_manifest.py
python -m pytest tests\test_model_manifest.py -q
python -m pytest -q
git diff --check
git status --short
```