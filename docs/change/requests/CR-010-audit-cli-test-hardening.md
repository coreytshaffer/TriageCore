# CR-010: Audit CLI Test Hardening

## Status
Implemented

## Scope
Add robust regression tests for the `tc audit` CLI subcommand introduced in CR-009 to ensure it fails gracefully on missing files, ignores malformed JSONL lines, applies filters correctly, and never displays raw task content.

## Implementation Authority
Implemented implicitly by request.

## Description
This CR hardens the `tc audit` command against edge cases and strictly enforces privacy rules in the CLI output.

## Acceptance Criteria
- [x] Test verifies missing ledger file fails gracefully.
- [x] Test verifies malformed JSONL lines do not crash the CLI.
- [x] Test verifies `--kind route_audit` filters correctly.
- [x] Test verifies `--last 10` limits output correctly.
- [x] Test verifies raw fields (`prompt`, `data`, `content`, `raw_prompt`, `raw_data`) are never displayed.
