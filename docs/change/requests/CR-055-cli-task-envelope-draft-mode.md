# CR-055: CLI Task Envelope Wizard Draft Mode

## Status

Implemented

## Scope

- Add `tc task-envelope draft` CLI command.
- Build `TaskEnvelope` using explicit CLI flags.
- Output deterministic Markdown via `render_task_envelope_markdown`.
- No interactive wizard yet.
- No files written or ledger modified.

## Implementation Authority

Authorized as a bounded CLI draft slice. No interactive wizard, ledger integration, or runtime behavior is introduced.

## Description

The `draft` mode provides the required data parsing to construct a `TaskEnvelope` object purely from command line flags. This ensures all the required fields match what the `TaskEnvelope` needs. It acts as the backbone for the upcoming interactive wizard.

## Acceptance Criteria

- [x] Command runs successfully with exit code 0 when all required flags are passed.
- [x] Prints deterministic markdown matching CR-052 structure to stdout.
- [x] Empty items render correctly as `- None`.
- [x] Missing required flags trigger an argparse error (exit code != 0).
- [x] `tc task-envelope preview` continues to work.
- [x] No side-effects (file reads/writes, network calls).

## Validation

```powershell
python -m pytest tests/test_task_envelope.py -q
python -m pytest tests/test_task_envelope_cli.py -q
python -m py_compile triage_core/task_envelope.py
python -m py_compile triage_core/tc_cli.py
git diff --check
```
