# CR-118: Local Backend Telemetry Record Schema

## Status

Implemented (contract-only)

## Summary

Harden the existing local backend probe's serialized record contract before
any further probe or routing work. This slice adds a JSON Schema artifact and
a pure strict mapping validator for `local_backend_probe_record.v1` records.
It does not execute probes, call models, write the ledger, change CLI
behavior, or wire telemetry into routing.

## Scope

- Add `schemas/local_backend_probe_record.schema.json` for the v1 record
  shape emitted by `LocalBackendProbeRecord.to_dict()`.
- Add `local_backend_probe_record_from_mapping(...)` as a pure validator and
  mapper for already-serialized telemetry records.
- Keep `source_type` closed to `ollama`, `lm_studio`, `llama_cpp`, and the
  normalized `unsupported` sentinel.
- Require `source_type: "unsupported"` when `error_category:
  "unsupported_backend"`; do not persist arbitrary requested backend names.
- Preserve metadata-only privacy rules: no prompts, completions, raw context,
  credentials, private paths, or path-like model identifiers.
- Preserve deterministic fixture rules: `synthetic_fixture` records carry no
  `observed_at` timestamp.

## Non-Goals

- No new probe execution path.
- No endpoint calls in new tests.
- No routing integration, `ResilienceRouteInput` population, circuit
  breakers, degraded modes, or daily-driver enforcement.
- No ledger writes.
- No model, completion, chat, or embedding calls.
- No CLI behavior changes.

## Validation

- `tests/test_cr_118_local_backend_probe_contract.py` covers synthetic
  fixture round-trip validation, unknown-field rejection, persistent privacy
  invariant enforcement, closed `source_type`, the `unsupported` sentinel
  relationship, path-like model identifier rejection, base URL normalization,
  and timestamp exclusion for fixture-tier records.
- Existing local backend probe tests continue to run offline; the unsupported
  backend record now serializes as `source_type: "unsupported"`.

## Notes

This slice intentionally hardens the evidence shape before expanding
behavior. CR-119+ remains the lane for any future probe-behavior changes,
routing use, or operational telemetry integration.
