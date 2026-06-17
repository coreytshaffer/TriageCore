# CR-037: Model Manifest Warning CLI Surface

## Status

Implemented

## Scope

Implement only:

```powershell
tc model warn --manifest <path> --route <path>
```

This change:

- loads a model route manifest JSON file
- loads a route metadata JSON file
- calls `compare_route_to_manifest(route_payload, manifest)`
- prints a concise pass/warn summary
- exits `0` when warnings exist
- adds a small route payload fixture for reviewer demos

This change does not probe Ollama, LM Studio, Qwen Cloud, filesystems, or live
model artifacts. It does not block runtime routing, mutate the ledger, or wire
the warning layer into runtime execution yet.

## Acceptance Criteria

- [x] `tc model warn --manifest <path> --route <path>` loads both JSON files.
- [x] Calls `compare_route_to_manifest(route_payload, manifest)`.
- [x] Matching manifest and route metadata prints a pass summary.
- [x] Mismatched metadata prints warnings but still exits `0`.
- [x] Missing or malformed files exit nonzero.
- [x] No backend probing or routing enforcement.
- [x] No ledger mutation.
- [x] Add focused tests and a small example route payload fixture.

## Validation

```powershell
python -m py_compile triage_core\model_manifest.py triage_core\tc_cli.py
python -m pytest tests\test_model_manifest.py tests\test_model_cli.py -q
python -m pytest -q
tc model warn --manifest docs\security\examples\model_route_manifest_local_ollama.json --route docs\security\examples\route_payload_local_ollama.json
$LASTEXITCODE
tc model warn --manifest docs\security\examples\model_route_manifest_cloud_qwen.json --route docs\security\examples\route_payload_local_ollama.json
$LASTEXITCODE
git diff --check
git status --short
```
