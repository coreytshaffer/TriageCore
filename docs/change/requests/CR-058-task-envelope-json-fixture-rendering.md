# CR-058: Task Envelope JSON Fixture Rendering

## Goal
Add a read-only `--from-json` path to `tc task-envelope draft` so an operator or test can load a TaskEnvelope from a local JSON fixture and render deterministic Markdown to stdout.

## Context
- CR-052 defined the Task Envelope contract.
- CR-053 added the `TaskEnvelope` dataclass and Markdown renderer.
- CR-054 added `tc task-envelope preview`.
- CR-055 added explicit flag-based `tc task-envelope draft`.
- CR-057 added interactive `tc task-envelope wizard`.
- CR-058 adds reproducible fixture loading without adding persistence, ledger integration, or writes.

## Scope
- Added optional `--from-json <path>` to `tc task-envelope draft`.
- Implemented pure validation helper `task_envelope_from_mapping()` in `task_envelope.py`.
- Rejects missing required scalars, missing required lists, and empty lists.
- Optional fields may be absent or null.
- Exits nonzero on missing fields, invalid JSON, or `.triagecore/ledger.jsonl` inputs.
- Preserves existing strictly typed flag-based boundaries if `--from-json` is absent.
- Disallows mixed usage of `--from-json` with explicit field flags.
- stdout-only Markdown output.
- No new dependencies, no file writes, no runtime execution.
