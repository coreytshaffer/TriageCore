# CR-034: Repository Consistency and Secrets Hygiene

## Status

Implemented

## Scope

Implement a narrow repository hygiene baseline after CR-033:

- align the declared Python floor with syntax used by the codebase
- make `pyproject.toml` the canonical packaging metadata source
- expand CI coverage across the supported Python versions
- require Qwen API keys to come from the environment, not tracked project config
- extend persistent artifact privacy invariants to secret-bearing field names
- sanitize backend HTTP error logging
- add a minimal `SECURITY.md`

## Non-Scope

- Do not remove or rename the existing CR-033 model manifest work.
- Do not change the `httpx2` mobile dependency without separate dependency
  verification.
- Do not implement runtime model-integrity enforcement.
- Do not add broad repository consistency automation yet.

## Acceptance Criteria

- [x] Package metadata declares Python 3.10+ consistently.
- [x] `setup.py` no longer duplicates dependency metadata.
- [x] CI tests Python 3.10, 3.11, and 3.12.
- [x] `Config.get_qwen_api_key()` ignores tracked `triagecore.toml` secrets and
  reads `TRIAGE_QWEN_API_KEY`.
- [x] Persistent artifact invariants reject common secret-bearing field names.
- [x] Backend HTTP error output reports status metadata without raw response
  bodies.
- [x] `SECURITY.md` documents alpha security policy and known limitations.

## Validation

```powershell
python -m py_compile triage_core\config.py triage_core\privacy_invariants.py triage_core\backends.py
python -m pytest tests\test_config.py tests\test_privacy_invariants.py tests\test_backends.py tests\test_qwen_backend.py tests\test_qwen_cloud_routing.py -q
git diff --check
```
