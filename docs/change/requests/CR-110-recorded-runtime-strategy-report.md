# CR-110: Recorded Runtime Strategy Evidence Report

## Status

Implemented

Pushed and CI verified: `origin/main` at `16b25f0`, GitHub Actions run `28732865961` passed on Python 3.10, 3.11, and 3.12 (Node 20 deprecation annotations only; no failures). CR-110 adds a separate recorded runtime strategy report path for operator-supplied metadata-only evidence records, validating every record through the existing privacy-invariant-preserving mapping path, keeping fixture determinism separate from recorded evidence, and making all failure paths bounded and reason-coded.

## Scope

- Add `tc runtime-strategy recorded-report --input <path>` to render strategy
  deltas from operator-supplied evidence records in an explicit JSON file.
- Input contract: a top-level JSON list of runtime strategy evidence record
  objects, each validated through the existing
  `runtime_strategy_evidence_from_mapping` path (unknown fields rejected,
  persistent privacy invariant enforced).
- Add `--baseline <strategy>` (defaults to the first record's strategy) and
  `--json` output.
- Render a separate report kind (`recorded_runtime_strategy_delta_report.v1`)
  with record count, strategies in input order, deltas, quality-gate
  statuses, and the quality non-claim note; recorded records are never mixed
  into the fixture report.
- Fail closed with bounded reason-coded output: `input_not_found`,
  `input_read_failed`, `malformed_json`, `unsupported_top_level_shape`,
  `invalid_record`, `too_few_records`, `mixed_task_ids`,
  `duplicate_strategy`, `baseline_not_found`.
- Add canonical valid and intentionally invalid example input files under
  `docs/examples/`.
- Share the existing table renderer and JSON serialization; output stays
  ASCII-only.

## Non-Goals

- No live model calls.
- No routing changes.
- No telemetry adapters.
- No ledger writes.
- No identity, signature, key-rotation, or authority changes.
- No artifact export for the recorded report (durable export can be CR-111).
- No claim that recorded estimates match real execution.

## Description

CR-104 through CR-109 built the fixture measurement loop: strategy shape,
estimated cost, comparison, operator-visible report, and deterministic
artifact export. This slice opens the loop to operator data: recorded
evidence records loaded from an explicit file, validated through the same
strict path as every other record, and compared with the same delta
arithmetic and two-axes interpretation.

Recorded records remain operator-supplied claims about strategy shapes. The
report computes deterministic arithmetic over them; it does not verify the
estimates against any real execution, and it keeps the fixture report
untouched so fixture determinism claims stay independent of operator data.

## Acceptance Criteria

- [x] Valid recorded file renders a text report and deterministic JSON.
- [x] Every record passes through `runtime_strategy_evidence_from_mapping`;
  unknown fields and raw-content fields fail closed without echoing content.
- [x] Missing file, malformed JSON, non-list top level, invalid record,
  fewer than two records, mixed task ids, duplicate strategies, and missing
  baseline all fail closed with stable reason codes and exit 1.
- [x] `--baseline` overrides the default first-record baseline.
- [x] The command never writes the ledger or mutates the input file.
- [x] Canonical valid and invalid examples exist and are regression-tested.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py tests/test_runtime_strategy_cli.py`
- `python -m py_compile triage_core/runtime_strategy_evidence.py triage_core/tc_cli.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
