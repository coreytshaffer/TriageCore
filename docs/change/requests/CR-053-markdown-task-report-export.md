# CR-053: Markdown Task Report Export

## Status

Implemented

## Scope

- Add a pure module (`triage_core.task_envelope`) for rendering task-envelope data to Markdown.
- Ensure renderer strictly adheres to the CR-052 template contract.
- No CLI command, TUI, or ledger reads/writes implemented.
- No runtime execution or external dependencies added.
- Add deterministic rendering tests.

## Implementation Authority

Code implementation slice defining a pure formatting boundary before any external orchestration triggers it. No live file mutation or network calls.

## Description

This change creates a pure Markdown rendering layer for Task Envelopes. By building `TaskEnvelope` as a frozen dataclass and providing a deterministic `render_task_envelope_markdown` function, this slice ensures future CLI wizards or ledger exports can present task context consistently without independently rewriting display logic.

## Acceptance Criteria

- [x] Pure dataclass and rendering function provided.
- [x] Tests confirm output matches required envelope sections.
- [x] Lists and blocked reasons render correctly.
- [x] Rendering is deterministic.
- [x] No side-effects (file writes, network calls) added.
- [x] Changelog and backlog updated.

## Validation

```powershell
python -m pytest tests/test_task_envelope.py -q
python -m py_compile triage_core/task_envelope.py
git diff --check
```
