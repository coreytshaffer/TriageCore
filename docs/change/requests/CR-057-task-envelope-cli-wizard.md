# CR-057: Interactive CLI Task Envelope Wizard

## Status

Implemented

## Goal

Add an interactive CLI wizard for creating TaskEnvelopes that prompts the operator for all required boundaries before rendering deterministic Markdown.

## Scope

- Add `tc task-envelope wizard` subparser to `tc_cli.py`.
- Use built-in Python `input()` to prompt for required fields sequentially.
- Loop for multi-value (list) fields and enforce that at least one value is provided.
- Build and print the TaskEnvelope Markdown using the existing CR-053 renderer.
- No textual/TUI libraries.
- No file writing.
- No ledger integrations.
- Existing `preview` and `draft` commands remain unchanged.

## Implementation Authority

Authorized as a bounded interactive CLI collection slice. No TUI, ledger integration, file output, or runtime behavior is introduced.

## Acceptance Criteria

- [x] Wizard prompts for all required fields sequentially.
- [x] Wizard strictly requires at least one entry for `allowed_files`, `forbidden_files_or_areas`, `explicit_non_scope`, and `evidence_to_produce`.
- [x] Wizard outputs deterministic Markdown to stdout identical to `draft` command.
- [x] Add automated test simulating input.
- [x] Existing preview and draft commands continue working untouched.
- [x] Documentation updated.
