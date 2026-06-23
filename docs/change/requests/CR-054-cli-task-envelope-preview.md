# CR-054: CLI Task Envelope Preview Command

## Status

Implemented

## Scope

- Add `tc task-envelope preview` CLI command to print a dummy task envelope for preview.
- Reuse existing pure markdown renderer from `triage_core.task_envelope`.
- Keep the boundary pure: no wizard, ledger reads/writes, file outputs, text UI dependencies, runtime actions.
- Testing only validates CLI stdout content and code 0 exit.

## Implementation Authority

Authorized as a bounded CLI preview slice. No wizard, ledger integration, file output, or runtime behavior is introduced.

## Description

Exposes the Markdown renderer via a new CLI command to test how the envelope outputs to operators' terminals. This preview validates that the CR-052 template visually works without building a complex CLI wizard yet.

## Acceptance Criteria

- [x] Command runs successfully with exit code 0.
- [x] Prints deterministic markdown matching CR-052 structure to stdout.
- [x] Empty items render correctly as `- None`.
- [x] No side-effects (file reads/writes, network calls).
- [x] Test coverage ensures `stdout` is deterministic.

## Validation

```powershell
python -m pytest tests/test_task_envelope.py -q
python -m pytest tests/test_task_envelope_cli.py -q
python -m py_compile triage_core/task_envelope.py
python -m py_compile triage_core/tc_cli.py
git diff --check
```
