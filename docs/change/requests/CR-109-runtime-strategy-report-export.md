# CR-109: Runtime Strategy Report Export

## Status

Implemented

## Scope

- Add `--output <path>` to `tc runtime-strategy report` to write the delta
  report as a metadata-only JSON artifact to an explicit path.
- Reuse the exact `runtime_strategy_delta_report.v2` report dict and a single
  shared serialization (`render_strategy_delta_report_json`) for both stdout
  JSON and file artifacts, so the two can never drift apart.
- Fail closed: no default write location, parent directory must exist
  (`reason=output_directory_missing`), and existing files are never
  overwritten without `--force` (`reason=output_exists`).
- Make `--json` and `--output` mutually exclusive; `--force` requires
  `--output`.
- Make overwrites atomic (temp file plus replace) so a failed write cannot
  destroy a prior artifact.
- Keep artifacts deterministic: sorted keys, trailing newline, no generation
  timestamp — repeated exports are byte-identical.
- Add focused tests for exact artifact bytes, byte-determinism, metadata-only
  and untimestamped content, existing-file failure, `--force` overwrite,
  missing-parent failure, and flag mutual exclusion.

## Non-Goals

- No default report directory.
- No generation timestamps (a future opt-in flag may add provenance
  separately).
- No live model calls, telemetry adapters, or automatic routing.
- No strategy ranking or recommendation engine.
- No new report schema: the artifact is the existing v2 report unchanged.

## Description

CR-107 and CR-108 made the runtime-strategy deltas operator-visible with cost
and quality as independent axes. This slice adds durable artifacts for
iterative data collection: the same deterministic report, written to a file
the operator explicitly names. The command stays read-only unless `--output`
is passed, existing evidence artifacts are never silently overwritten, and
the artifact serialization is shared with the stdout JSON path so there is
exactly one report shape everywhere.

## Acceptance Criteria

- [x] `tc runtime-strategy report --output <path>` writes the artifact and
  prints one confirmation line.
- [x] Artifact bytes equal the shared serialization of the v2 report dict;
  repeated exports are byte-identical.
- [x] The artifact contains no prompts, raw context, model outputs, or
  timestamps.
- [x] Existing files fail closed with `reason=output_exists`; `--force`
  overwrites atomically.
- [x] A missing parent directory fails closed with
  `reason=output_directory_missing` and creates nothing.
- [x] `--json`/`--output` are mutually exclusive and `--force` without
  `--output` is rejected.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py tests/test_runtime_strategy_cli.py`
- `python -m py_compile triage_core/runtime_strategy_evidence.py triage_core/tc_cli.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
