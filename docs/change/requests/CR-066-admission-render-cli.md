# CR-066: `tc admission render --from-json`

## Goal
Add a CLI command to render Admission Evidence fixtures as Markdown, leveraging the same mapping helper and rules introduced in CR-065.

## Scope
* Add `tc admission render --from-json <path>` subcommand.
* Reuse `admission_evidence_from_mapping` for identical strict validation.
* Render Markdown output to `stdout` upon success.
* Reject `.triagecore/ledger.jsonl`.
* Handle JSON, validation, and OS errors cleanly on `stderr` (exit 1).
* Add integration tests validating the CLI behavior.
* Update documentation, backlog, and changelog.
