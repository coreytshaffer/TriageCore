# Build Review Artifact Contract

Build Review produces a local evidence directory. JSON files are the
machine-readable contract; Markdown and HTML are deterministic derived views.

## `review.json`

Required top-level fields:

- `schema_version`
- `packet_id`
- `created_at`
- `repository`
- `request`
- `comparison`
- `expected_scope`
- `change_summary`
- `changed_files`
- `validations`
- `findings`
- `recommendation`
- `working_tree_clean`
- `decision` (always `pending` in the authoritative evidence record)
- `evidence_sha256`

The evidence hash is SHA-256 over canonical JSON excluding `decision` and
`evidence_sha256`. Canonical JSON uses sorted keys, compact separators,
preserved Unicode, and UTF-8 encoding.

## Derived files

`diff-summary.json` contains the review ID, resolved comparison, expected scope,
aggregate line counts, and changed-file records.

`validation-results.json` contains validations declared by the request plus the
commands actually run, exit codes, durations, bounded output, and timeout
state.

`review.md` and `review.html` are deterministic human views reconstructed from
the authoritative evidence plus an optional separate decision.

## `decision.json`

Created once after human review:

```json
{
  "schema_version": "1.0",
  "decision_id": "example",
  "review_packet_id": "example",
  "evidence_sha256": "example",
  "status": "needs_revision",
  "reviewer": "Build Week reviewer",
  "note": "Resolve the undeclared file before approval.",
  "decided_at": "2026-07-17T20:15:00+00:00"
}
```

Allowed statuses are `approved`, `rejected`, and `needs_revision`. TriageCore
refuses to overwrite an existing decision. The deterministic decision ID
covers every field except `decision_id`.

## Independent verification

```powershell
tc build-review verify <review-directory-or-review.json>
```

Verification performs no writes. It fails closed on missing artifacts,
symlinks, malformed JSON, duplicate keys, non-standard JSON constants, evidence
hash drift, derived-view drift, invalid decision enums, or a decision pointing
at different evidence.

Exit `0` means internally intact. Exit `1` is a specific verification or
operation failure. Exit `2` means malformed command use.

An intact packet can document an unacceptable code change. Verification is not
a signature, authorship proof, or external timestamp; coordinated replacement
of every artifact can produce a new internally consistent packet.

## Persistence boundary

Packets and decisions pass TriageCore's persistent privacy invariant before
write. Validation commands are trusted local inputs and can expose captured
output, so operators should run only commands appropriate for the packet.
