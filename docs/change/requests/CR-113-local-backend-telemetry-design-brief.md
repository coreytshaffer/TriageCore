# CR-113: Local Backend Telemetry Design Brief

## Status

Implemented

Pushed and CI verified: `origin/main` at `88c9cfb`, GitHub Actions run `28733743705` passed on Python 3.10, 3.11, and 3.12. CR-113 is a docs-only design brief for future read-only local backend telemetry; it adds no telemetry implementation, no endpoint probing, no runtime code, no ledger writes, no model calls, and preserves fixture-report determinism while defining the metadata-only boundary for a future CR-114+ probe slice.

## Scope

- Docs-only. Add a design brief at
  `docs/operations/local-backend-telemetry.md` defining the boundaries for a
  future read-only local backend telemetry slice before any probe code is
  written.
- The brief defines: purpose (metadata-only availability and model/runtime
  identity observations for future recorded runtime strategy evidence);
  supported future sources (Ollama, LM Studio, and llama.cpp local
  endpoints, metadata endpoints only); candidate metadata-only fields with
  per-field privacy considerations; a closed failure-category vocabulary
  (`endpoint_unreachable`, `timeout`, `malformed_response`,
  `unsupported_backend`, `permission_or_policy_blocked`, `probe_disabled`);
  a tiered `observed_at`/`evidence_tier` policy separating deterministic
  fixtures from real observations; the relationship to the existing runtime
  strategy lane; the privacy boundary; and the reviewer path for verifying
  the future slice without running a model.
- Cross-link the brief from the runtime strategy evidence operations doc.
- Update the current backlog and changelog.

## Non-Goals

- No telemetry implementation: no probe code, no HTTP calls, no new CLI
  surface, no schema module, no fixtures.
- No runtime code changes of any kind; current behavior is preserved.
- No new dependencies.
- No live benchmark execution, model generation calls, or prompt/completion
  capture — excluded here and in the future slice the brief bounds.
- No automatic routing changes.
- No ledger writes.
- No cloud telemetry.
- No claims of energy savings, cost savings, quality improvement, or safety
  certification.
- No commitment that the future slice will be implemented exactly as
  drafted; the brief records design intent, and the implementation CR owns
  final field names and validation rules.

## Description

The runtime strategy lane (CR-104 through CR-112) is deterministic end to
end: fixtures, deltas, reports, and exports are arithmetic over declared
records, and recorded reports are operator-supplied claims validated through
a strict mapping path. The next candidate slice — a read-only local backend
telemetry probe — would be the lane's first non-deterministic contact point:
it would observe something about the machine rather than compute over
declared inputs.

This CR writes the design brief before that boundary is crossed, so the
record shape, closed failure vocabulary, redaction rules, evidence-tier
provenance, opt-in posture, and reviewer path are agreed while the slice is
still docs-only. The future implementation CR (CR-114+ candidate) can then
be reviewed against these boundaries instead of defining them mid-flight.

## Acceptance Criteria

- [x] `docs/operations/local-backend-telemetry.md` exists and covers
  purpose, status, supported future sources, non-goals, candidate metadata
  fields with privacy considerations, failure categories, lane relationship,
  privacy boundary, reviewer path, and non-claims.
- [x] The brief states plainly that no telemetry code, CLI surface, schema,
  or fixture exists yet and that every statement is future design intent.
- [x] The runtime strategy evidence doc links to the brief.
- [x] The backlog carries a CR-113 entry and names the telemetry probe
  implementation as a gated future candidate.
- [x] No files outside `docs/` are changed.

## Validation

- `git diff --check`
- No tests are run or added: this slice adds no code, fixtures, schemas, or
  documented commands that any existing test asserts against, and the
  repo's docs-only review convention (reviewer smoke runbook) requires only
  `git diff --check` for docs-only slices.
