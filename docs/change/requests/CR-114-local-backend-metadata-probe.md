# CR-114: Read-Only Local Backend Metadata Probe

## Status

Implemented in branch; pending review/merge

Implements the read-only local backend metadata probe slice bounded by the
CR-113 design brief (`docs/operations/local-backend-telemetry.md`). This is the
first non-deterministic contact point in the runtime-strategy/telemetry lane: it
observes local backend availability and model/runtime identity via metadata
endpoints only. It adds no model generation, no routing changes, no
`ResilienceRouteInput` wiring, no circuit breakers, no background polling, no
ledger writes, and no default artifact writes. It is also the observation
foundation the daily-driver M1 milestone will later consume.

## Scope

- Add `triage_core/local_backend_probe.py` providing:
  - a metadata-only `LocalBackendProbeRecord` (closed `source_type`,
    `error_category`, and `evidence_tier` vocabularies) whose `to_dict()`
    enforces the persistent privacy invariant on every emitted record;
  - `redact_base_url()` (validation rule: reject userinfo/query/fragment, strip
    path, store `scheme://host[:port]` only);
  - `probe_local_backend()` which hits a metadata endpoint only
    (`ollama -> /api/tags`, `lm_studio` / `llama_cpp -> /v1/models`), fails
    closed with a closed `error_category`, and accepts an injectable transport
    for offline testing;
  - `render_probe_record()` for a privacy-safe human-readable summary.
- Add a `tc probe` command:
  `tc probe --source-type {ollama|lm_studio|llama_cpp} --base-url <url>`
  with `--timeout`, `--include-model-names`, `--disabled`, and `--output`.
- Add offline tests in `tests/test_local_backend_probe.py`.
- Update `docs/operations/local-backend-telemetry.md` Status to record that
  CR-114 implements the probe slice only.

### Exit codes

- `0` — the probe produced a valid metadata record, including `reachable=false`
  records and `probe_disabled` records.
- `1` — argument / input / validation error, including a secret-bearing
  `base_url` (userinfo or query present).

There is no exit `2` for this slice; there is no config/policy gate that makes
the command unable to run. `--disabled` is a valid record outcome (exit `0`),
not a crash.

## Non-Goals

- No model generation, completions, or embeddings; metadata endpoints only.
- No cloud/frontier probing; local endpoints only, nothing leaves the machine.
- No routing changes and no `ResilienceRouteInput` wiring (future M1 slice).
- No circuit breakers or degraded-mode states (future M1 slice).
- No background polling and no automatic discovery; probing is opt-in and
  explicit against an operator-supplied URL.
- No ledger writes and no default artifact write location; only `--output`
  writes an operator-named file.
- No new dependencies beyond the existing `requests`.
- No claim that the full telemetry design is implemented; only the probe slice
  is built.

## Description

The runtime-strategy lane is otherwise deterministic. The CR-113 brief bounded a
future read-only probe as the point where that determinism boundary is crossed,
fixing the record shape, closed failure vocabulary, redaction rules,
evidence-tier provenance, opt-in posture, and reviewer path before any probe
code existed. CR-114 implements exactly that slice and nothing beyond it.

The probe observes; it does not act. It never feeds routing, never mutates
state, and never invokes a model. `base_url` redaction is enforced as a
validation rule (secret-bearing URLs are rejected, not stored), path-like model
identifiers are dropped, `observed_models` is off by default, and every emitted
record passes the persistent privacy invariant. Fixture-tier records carry no
timestamp so deterministic exports stay byte-identical; only probe/recorded
tiers may carry `observed_at`.

## Acceptance Criteria

- [x] `probe_local_backend()` returns a metadata-only record and never invokes a
  model endpoint.
- [x] Closed vocabularies are enforced for `source_type` (via the CLI choices
  and an `unsupported_backend` record), `error_category`, and `evidence_tier`.
- [x] `base_url` is stored redacted as `scheme://host[:port]`; userinfo/query
  URLs are rejected with an input error (exit `1`); paths are stripped.
- [x] `observed_models` is off by default; path-like identifiers are dropped
  when names are requested.
- [x] Every emitted record passes `assert_persistent_privacy_safe`.
- [x] `tc probe` exits `0` for valid records (including `reachable=false` and
  `probe_disabled`) and `1` for argument/validation errors.
- [x] `--output` is the only write path; there is no default artifact and no
  ledger write.
- [x] Tests run offline (injected transport plus a closed local port), covering
  each failure category, redaction/rejection, determinism, and the privacy
  invariant.

## Validation

- `python -m pytest -q tests/test_local_backend_probe.py`
- `tc audit --privacy-invariants` (CR-021 invariant remains clean)
- `git diff --check`
- Manual (optional): `tc probe --source-type ollama --base-url http://localhost:11434`
  against a live local backend.

## Dependencies / Sequencing

- Implements the CR-113 telemetry design brief's probe slice.
- Precedes the M1 slices that wire probe output into `ResilienceRouteInput`,
  bind `local_fast`/`local_heavy` to distinct models, and add circuit breakers /
  degraded modes. None of those are started here.
