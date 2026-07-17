# CR-125: Honor Terminal Resilience Routes

## Status

Implemented

## Summary

Make the terminal resilience routes selected by `TriageClient.run_task` control
execution. A `human_handoff` route and the currently unimplemented
`deterministic` route now stop before any backend call, record a metadata-only
`worker_result` with `worker_result_status=not_attempted`, and return the
existing governed handoff result consumed by `tc run` as exit code 3.

## Scope

- Treat `human_handoff` as terminal at the governed execution boundary.
- Treat `deterministic` as terminal until a real deterministic executor exists.
- Preserve route-decision and worker-result evidence for terminal routes.
- Add offline sentinel-backend coverage proving terminal routes do not execute.
- Correct the daily-driver architecture note to match the enforced behavior.

## Non-Goals

- No approval-and-resume workflow.
- No change making every `human_review_required` flag pre-execution blocking.
- No deterministic executor implementation.
- No changes to cloud gating, privacy scanning, signatures, reducer behavior,
  other execution surfaces, or historical ledger records.

## Validation

- `python -m pytest -q tests/test_tc_run_cli.py tests/test_local_only_routing.py`
- `python -m pytest -q`
- `git diff --check`
