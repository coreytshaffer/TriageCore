# CR-119: Local Backend Telemetry Probe Validation Gate

## Status

Implemented (probe-observability hardening)

## Summary

Require every local backend telemetry probe result to satisfy the CR-118
`local_backend_probe_record.v1` contract before the probe treats it as an
emitted observation. The probe still contacts only explicit local metadata
endpoints, never invokes a model, never writes the ledger, and does not feed
routing or execution.

## Scope

- Add a shared emitted-record validation gate in `triage_core/local_backend_probe.py`.
- Validate each `LocalBackendProbeRecord.to_dict()` through
  `local_backend_probe_record_from_mapping(...)` before returning it from the
  probe path.
- Apply the gate to both reachable and fail-closed records such as
  `timeout`, `endpoint_unreachable`, `malformed_response`,
  `permission_or_policy_blocked`, `probe_disabled`, and
  `unsupported_backend`.
- If record-contract validation fails, raise `ProbeInputError` so CLI callers
  exit 1 instead of rendering or writing an invalid observation.
- Add offline tests using injected transports and monkeypatched validators;
  no CR-119 test contacts a real backend or model endpoint.

## Non-Goals

- No new backend source types.
- No model generation calls, chat calls, completion calls, or embeddings.
- No routing integration, route-input population, circuit breakers, degraded
  modes, daily-driver enforcement, or ledger writes.
- No new serialized fields or changes to the CR-118 schema.
- No background polling or automatic endpoint discovery.

## Validation

- `tests/test_local_backend_probe.py` proves reachable and failed probe
  results pass through the CR-118 validator before being emitted.
- A validator failure raises `ProbeInputError`, preserving fail-closed CLI
  behavior.

## Notes

This slice keeps telemetry as explicit-endpoint observability only. A valid
probe record says that a metadata endpoint produced a contract-valid
observation at one moment; it is not a benchmark, routing authorization,
availability guarantee, model-quality claim, or safety claim.
