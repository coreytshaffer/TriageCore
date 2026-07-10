# Local Backend Telemetry (Design Brief)

## Purpose

This document defines the boundaries for a future read-only local backend
telemetry slice: metadata-only observations about local backend availability
and model/runtime identity, collected so that future recorded runtime
strategy evidence can reference which backends were actually reachable and
what they reported about themselves.

Telemetry is the first non-deterministic contact point in the runtime
strategy lane. Everything before it (fixtures, deltas, reports, exports) is
deterministic arithmetic over declared records. This brief exists so that
boundary is crossed deliberately, with the record shape, failure vocabulary,
and privacy rules agreed before any probe code is written.

## Status

Partially implemented. The current read-only metadata probe surface is the
`triage_core/local_backend_probe.py` module and the `tc probe` command. They
produce metadata-only records against the endpoints below, with the closed
failure vocabulary, tiered evidence, and `base_url` redaction described here.
**CR-118 pins the serialized record contract** with
`schemas/local_backend_probe_record.schema.json` and a pure strict mapping
validator for synthetic fixtures and recorded metadata.
**CR-119 gates probe emission through that contract**: every probe result is
validated against the CR-118 mapper before the probe returns, renders, or
writes it as an observation.
**CR-120 records the post-merge release hygiene** for this lane and corrects
stale numbering: CR-114 is the July 7 reviewer checkpoint, not the probe
validation anchor.

Routing wiring, route-input population (`ResilienceRouteInput`), circuit
breakers, degraded modes, and any daily-driver enforcement **remain future
work** and are out of scope for the implemented telemetry contract and
probe-validation work. This document still describes the full telemetry
design; only the read-only probe and validation-contract slices are built.
Nothing here should be read as implying the whole telemetry design is
implemented.

## Supported Future Sources

| `source_type` | Backend | Candidate metadata endpoint |
|---|---|---|
| `ollama` | Ollama local endpoint | native model-listing endpoint (e.g. `/api/tags`) |
| `lm_studio` | LM Studio local endpoint | OpenAI-compatible model listing (e.g. `/v1/models`) |
| `llama_cpp` | llama.cpp server local endpoint | OpenAI-compatible model listing (e.g. `/v1/models`) |

`source_type` is a closed vocabulary. A probe against anything else fails
closed with `unsupported_backend` rather than guessing a protocol.

All probes target harmless metadata endpoints only — endpoints that describe
the backend without invoking a model. Probing is opt-in and explicit: an
operator runs a named command against an operator-supplied local endpoint.
There is no background polling, no automatic discovery, and no probing as a
side effect of any other command.

## Non-Goals

The implemented telemetry lane, and this brief, exclude:

- no live benchmark execution
- no model generation calls (no completions, chat, or embedding requests)
- no prompt or completion capture
- no raw context capture
- no automatic routing changes
- no ledger writes in this design slice
- no claims of energy savings, cost savings, quality improvement, or safety
  certification
- no cloud telemetry: local endpoints only, no data sent off the machine

## Candidate Metadata Fields

Candidate record fields, all metadata-only:

| Field | Design intent | Privacy consideration |
|---|---|---|
| `source_type` | Closed serialized vocabulary: `ollama`, `lm_studio`, `llama_cpp`, or the normalized `unsupported` sentinel. | None; arbitrary backend identifiers are not serialized. `unsupported_backend` records must use `source_type: "unsupported"` rather than preserving the raw requested backend. |
| `base_url` | The operator-supplied endpoint, stored for display only after a redaction check. | Store scheme, host, and port only. Reject or redact userinfo (`user:pass@`), query strings, and path segments beyond the documented endpoint path, so an endpoint URL cannot smuggle a token or private path into evidence. |
| `reachable` | `true`/`false` for the single metadata probe. | None; boolean. |
| `model_count` | Number of models the backend reported. | Preferred default: a count leaks less than names. |
| `observed_models` | Optional list of reported model identifiers. | Model identifiers can embed private filesystem paths (e.g. local GGUF paths) or project names. Candidate policy: off by default, opt-in flag, and identifiers that look like filesystem paths are redacted or dropped rather than recorded. |
| `response_latency_ms` | Latency of the single metadata probe request, if measured. | Explicitly not a benchmark: it measures one HTTP metadata round-trip, never model generation, and supports no performance claim. |
| `observed_at` | Timestamp policy is tiered: deterministic fixtures carry no timestamp (preserving byte-identical exports); real observations may carry a timestamp only with `evidence_tier` marking their provenance. | Timestamps are metadata but break determinism; they never appear in fixture-tier records. |
| `error_category` | Closed failure vocabulary below; present only when the probe did not succeed. | None; closed vocabulary, no raw error text with embedded paths or hosts. |
| `evidence_tier` | One of `synthetic_fixture`, `local_metadata_probe`, `operator_recorded`. | Keeps deterministic fixtures, actual probe output, and operator-typed claims distinguishable in every downstream report. |

The CR-118 schema and pure validator define the exact v1 serialized contract:
unknown fields are rejected, the persistent privacy invariant is enforced,
`synthetic_fixture` records carry no timestamp, and `source_type:
"unsupported"` is reserved for `error_category: "unsupported_backend"`.

## Failure Categories

A closed vocabulary; probes fail closed with a category, never with raw
error text:

| `error_category` | Meaning |
|---|---|
| `endpoint_unreachable` | Connection refused or no route to the endpoint. |
| `timeout` | The metadata request exceeded its bounded timeout. |
| `malformed_response` | The endpoint answered but the body did not match the expected metadata shape. |
| `unsupported_backend` | The requested backend is outside the supported probe vocabulary; serialized records use `source_type: "unsupported"` and do not persist the raw requested backend identifier. |
| `permission_or_policy_blocked` | A local permission or policy prevented the probe (e.g. an application-control or firewall block). |
| `probe_disabled` | Probing is disabled in the current configuration; the default posture is disabled until explicitly invoked. |

## Relationship to the Runtime Strategy Lane

- Future telemetry records may inform recorded runtime strategy evidence:
  an operator building a recorded strategy record could cite a telemetry
  record as the basis for claiming a backend was available. The telemetry
  record itself remains a separate record kind.
- Fixture report determinism must remain separate. Telemetry never feeds the
  fixture report; the fixture report's byte-identical export claims stay
  independent of any probe output, exactly as recorded reports are already
  kept separate.
- Recorded report export remains operator-named and explicit: no default
  write location, no automatic artifact creation from probe output.

## Privacy Boundary

Telemetry records must never contain:

- prompts or completions
- embeddings
- file contents
- API keys, tokens, or other credentials
- private filesystem paths

Local endpoint URLs must not leak secrets: the `base_url` redaction policy
above is a validation rule, not a display convention — a record whose URL
carries userinfo or query parameters fails validation rather than being
stored verbatim. Telemetry records are expected to pass the same persistent
privacy invariant as every other persisted evidence record.

## Reviewer Path

What a future reviewer should be able to verify without running a model:

- **Record shape.** Deterministic `synthetic_fixture`-tier examples validate
  through the strict mapping path and schema contract, with no backend
  present at all.
- **Probe emission gate.** Every emitted probe result, including fail-closed
  observations, round-trips through the CR-118 validator before it is treated
  as a successful observation.
- **Fail-closed behavior.** Each failure category is reachable in tests
  without a live backend (unsupported source type, disabled probe, and
  malformed fixture responses need no network; unreachable/timeout can use a
  closed local port).
- **Privacy rules.** Tests demonstrate that records carrying prompts, raw
  context, credentials, or secret-bearing URLs fail validation, and that
  path-like model identifiers are redacted or dropped.
- **Opt-in posture.** No command probes an endpoint unless explicitly
  invoked with an operator-supplied URL; the reviewer can confirm the
  default posture is `probe_disabled`.
- **Determinism boundary.** Fixture-tier records carry no timestamps and
  export byte-identically; only probe/recorded tiers may carry
  `observed_at`.

Verifying an actual `local_metadata_probe` record against a live local
backend is optional reviewer work, not required for the slice to be
reviewable.

## Non-Claims

- This brief is not a routing, ledger, or enforcement switch; docs-only hygiene
  updates to it add no runtime behavior, CLI surface, schema, or fixture.
- A future telemetry record proves only that a metadata endpoint answered at
  one moment; it is not a benchmark, an availability guarantee, a quality
  claim, or a safety claim.
- Nothing here changes routing, admission, approval, identity, signing, or
  ledger behavior.

## Related Docs

- [runtime-strategy-evidence.md](runtime-strategy-evidence.md)
- [runtime-efficiency-ledger.md](runtime-efficiency-ledger.md)
- [token-efficiency-evidence.md](token-efficiency-evidence.md)
