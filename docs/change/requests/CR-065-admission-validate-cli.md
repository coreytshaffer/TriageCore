# CR-065: `tc admission validate --from-json`

## Goal
Add a pure validation CLI command for Admission Evidence, exposing the `admission_evidence_from_mapping` logic without runtime execution, ledger writes, or approval mutation.

## Scope
* Add `tc admission` top-level subcommand.
* Add `tc admission validate --from-json <path>` command.
* Parse JSON, pass to `admission_evidence_from_mapping`.
* Explicitly reject `.triagecore/ledger.jsonl` as input.
* Output `Validation successful.` on success (exit 0).
* Output specific `sys.stderr` error on JSON decode, mapping validation, or OS errors (exit 1).
* Add CLI validation tests.
* Add documentation for the CLI command.
