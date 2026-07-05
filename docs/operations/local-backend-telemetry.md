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

Design brief only. No telemetry code, CLI surface, schema module, or fixture
exists for this lane yet. Nothing in this document describes current
behavior; every statement below is future design intent.

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

The future telemetry slice, and this brief, exclude:

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
| `source_type` | Closed vocabulary above. | None; closed vocabulary. |
| `base_url` | The operator-supplied endpoint, stored for display only after a redaction check. | Store scheme, host, and port only. Reject or redact userinfo (`user:pass@`), query strings, and path segments beyond the documented endpoint path, so an endpoint URL cannot smuggle a token or private path into evidence. |
| `reachable` | `true`/`false` for the single metadata probe. | None; boolean. |
| `model_count` | Number of models the backend reported. | Preferred default: a count leaks less than names. |
| `observed_models` | Optional list of reported model identifiers. | Model identifiers can embed private filesystem paths (e.g. local GGUF paths) or project names. Candidate policy: off by default, opt-in flag, and identifiers that look like filesystem paths are redacted or dropped rather than recorded. |
| `response_latency_ms` | Latency of the single metadata probe request, if measured. | Explicitly not a benchmark: it measures one HTTP metadata round-trip, never model generation, and supports no performance claim. |
| `observed_at` | Timestamp policy is tiered: deterministic fixtures carry no timestamp (preserving byte-identical exports); real observations may carry a timestamp only with `evidence_tier` marking their provenance. | Timestamps are metadata but break determinism; they never appear in fixture-tier records. |
| `error_category` | Closed failure vocabulary below; present only when the probe did not succeed. | None; closed vocabulary, no raw error text with embedded paths or hosts. |
| `evidence_tier` | One of `synthetic_fixture`, `local_metadata_probe`, `operator_recorded`. | Keeps deterministic fixtures, actual probe output, and operator-typed claims distinguishable in every downstream report. |

Exact schema, field names, and validation rules are decided by the
implementation CR, which should route the record through the same strict
mapping/validation pattern as runtime strategy evidence (unknown fields
rejected, persistent privacy invariant enforced).

## Failure Categories

A closed vocabulary; probes fail closed with a category, never with raw
error text:

| `error_category` | Meaning |
|---|---|
| `endpoint_unreachable` | Connection refused or no route to the endpoint. |
| `timeout` | The metadata request exceeded its bounded timeout. |
| `malformed_response` | The endpoint answered but the body did not match the expected metadata shape. |
| `unsupported_backend` | The requested `source_type` is outside the closed vocabulary. |
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
  through the strict mapping path and render through whatever report surface
  the implementation CR adds, with no backend present at all.
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

- This document adds no runtime behavior, CLI surface, schema, or fixture.
- A future telemetry record proves only that a metadata endpoint answered at
  one moment; it is not a benchmark, an availability guarantee, a quality
  claim, or a safety claim.
- Nothing here changes routing, admission, approval, identity, signing, or
  ledger behavior.

## Related Docs

- [runtime-strategy-evidence.md](runtime-strategy-evidence.md)
- [runtime-efficiency-ledger.md](runtime-efficiency-ledger.md)
- [token-efficiency-evidence.md](token-efficiency-evidence.md)
