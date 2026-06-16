# CR-033: Model Manifest Check CLI

## Status

Implemented

## Scope

Implement only:

```powershell
tc model check --manifest <path>
```

This change:

- loads a model route manifest JSON file
- validates required sections and fields from CR-032
- passes the valid local Ollama example
- passes the valid cloud Qwen example
- fails the invalid alias-only example
- prints a concise pass/fail summary

This change does not probe Ollama, LM Studio, Qwen Cloud, filesystems, or live
model artifacts. It does not block runtime routing yet.

## Acceptance Criteria

- [x] `tc model check --manifest <path>` loads a manifest JSON file.
- [x] Validates required top-level sections and fields from CR-032.
- [x] Passes the valid local Ollama example.
- [x] Passes the valid cloud Qwen example.
- [x] Fails the invalid alias-only example.
- [x] Prints a concise pass/fail summary.
- [x] Does not probe live backends or artifacts.
- [x] Does not block actual routing yet.

## Validation

```powershell
python -m py_compile triage_core\model_manifest.py triage_core\tc_cli.py
python -m pytest tests\test_model_manifest.py -q
python -m pytest tests\test_model_cli.py -q
python -m pytest -q
tc model check --manifest docs\security\examples\model_route_manifest_local_ollama.json
tc model check --manifest docs\security\examples\model_route_manifest_cloud_qwen.json
tc model check --manifest docs\security\examples\model_route_manifest_invalid_alias_only.json
tc identity check
tc audit --privacy-invariants
tc audit --verify-signatures
```
