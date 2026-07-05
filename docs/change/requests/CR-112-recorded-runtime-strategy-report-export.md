# CR-112: Recorded Runtime Strategy Report Export

## Status

Implemented

Pushed and CI verified: `origin/main` at `a3d7bd0`, GitHub Actions run `28733487377` passed on Python 3.10, 3.11, and 3.12 (Node 20 deprecation annotations only; no failures). CR-112 (renumbered from a draft CR-111 after the reviewer runbook note consumed that number) adds `--output <path>` and `--force` to `tc runtime-strategy recorded-report`, reusing the report-kind-agnostic CR-109 export path unchanged so fixture and recorded artifacts share one deterministic serialization and atomic write implementation, with fail-closed reason-coded handling and no modification of the input file.

## Scope

- Add `--output <path>` and `--force` to
  `tc runtime-strategy recorded-report --input <path>`.
- Reuse the existing report-kind-agnostic CR-109 export path
  (`export_strategy_delta_report` and `render_strategy_delta_report_json`)
  unchanged, so fixture and recorded artifacts share one deterministic
  serialization and one atomic write implementation.
- With `--output`, print one confirmation line and suppress the report body.
- Fail closed with the same reason codes as the fixture export:
  `output_exists` (with the `--force` hint), `output_directory_missing`, and
  `output_write_failed`.
- Make `--json` and `--output` mutually exclusive; reject `--force` without
  `--output` at parse time.
- Keep artifacts deterministic, metadata-only, and untimestamped; repeated
  exports of the same input are byte-identical; the input file is never
  modified.

## Non-Goals

- No live model calls.
- No routing changes.
- No telemetry adapters.
- No ledger writes.
- No identity, signature, key-rotation, or authority changes.
- No default output location.
- No changes to fixture report output bytes.
- No mixing of recorded reports into fixture reports.

## Description

CR-110 added the recorded report for operator-supplied evidence records;
CR-109 established the deterministic artifact-export contract for the fixture
report. This slice closes the gap: recorded reports can now be written as
durable, metadata-only JSON artifacts under exactly the same rules, because
the CR-109 export helper was already report-kind agnostic and is reused
without modification. The recorded lane now supports iterative data
collection end to end: operator records in, validated comparison out, durable
deterministic artifact on disk — still with no live model calls.

## Acceptance Criteria

- [x] `--output` writes the exact recorded report dict via the shared
  serialization; repeated exports are byte-identical.
- [x] With `--output`, the command prints one success line and no report
  body.
- [x] The artifact contains no timestamps, prompts, raw context, or model
  outputs.
- [x] Existing files fail closed with `reason=output_exists`; `--force`
  overwrites atomically; missing parent directories fail closed with
  `reason=output_directory_missing` and create nothing.
- [x] `--json`/`--output` are mutually exclusive and bare `--force` is
  rejected at parse time.
- [x] The input file's bytes are never modified and no files besides the
  named output are created.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py tests/test_runtime_strategy_cli.py`
- `python -m py_compile triage_core/runtime_strategy_evidence.py triage_core/tc_cli.py`
- `python -m pytest`
- `python -m triage_core.tc_cli doctor`
- `git diff --check`
