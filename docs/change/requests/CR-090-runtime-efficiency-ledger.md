# CR-090: Runtime Efficiency Ledger

## Status

Implemented

## Scope

- Add a deterministic runtime efficiency record builder.
- Add backend profile support for `ollama`, `llama_cpp`, and
  `generic_openai_compatible`.
- Add a JSON schema for runtime efficiency records.
- Add focused tests for token savings, latency savings, backend profiles,
  energy-claim rejection, budget rejection, and token-proxy null energy fields.
- Add operator documentation for comparing Ollama and llama.cpp before any
  migration decision.

## Numbering Note

The original pasted request used CR-088, but this checkout already contains
CR-088 and CR-089. This implementation uses CR-090 to avoid reusing an existing
change-request number.

## Non-Goals

- No default runtime behavior changes.
- No live benchmark execution.
- No Ollama, llama.cpp, or OpenAI-compatible network calls.
- No crypto token, custody, payment, API-spend, or wallet behavior.
- No autonomous execution loop.
- No migration from Ollama to llama.cpp.

## Acceptance Criteria

- [x] `triage_core/runtime_efficiency.py` exists.
- [x] `triage_core/runtime_backends.py` exists.
- [x] `schemas/runtime_efficiency_record.schema.json` exists.
- [x] Runtime backend profiles support Ollama, llama.cpp, and generic
  OpenAI-compatible runtimes.
- [x] Records reject selected routes that exceed their declared token budget.
- [x] Records reject token-savings claims without baseline and selected token
  totals.
- [x] Records reject measured energy-savings claims without measurement
  evidence.
- [x] Token-proxy records allow null energy fields.
- [x] Documentation states that token reductions are proxy evidence, not
  measured energy savings.

## Validation

- `python -m pytest tests/test_runtime_backend_profile.py tests/test_runtime_efficiency.py -q`
- `git diff --check`
