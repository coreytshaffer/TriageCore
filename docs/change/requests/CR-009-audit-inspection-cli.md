# CR-009: Ledger Query / Audit Inspection CLI

## Status
Implemented

## Scope
Provide a safe, read-only CLI command (`tc audit`) to inspect recent route decision audit events. This command must only display metadata and explicitly exclude raw task payloads, prompts, or data contents to preserve privacy constraints.

## Implementation Authority
Implemented implicitly by request.

## Description
To make the `RouteDecisionAudit` records from CR-008 visible and actionable to operators without exposing raw task content, a new `audit` subcommand is added to the `triage_core.tc_cli` utility.

Usage:
`python -m triage_core.tc_cli audit --kind route_audit --last 10`

It streams the end of `.triagecore/ledger.jsonl`, filters by the given `event_type`, and prints a human-readable metadata summary.

## Acceptance Criteria
- [x] `audit` subcommand added to `tc_cli`.
- [x] Parses the `.triagecore/ledger.jsonl` file gracefully.
- [x] Provides filters like `--last` and `--kind`.
- [x] Does not print `prompt`, `data`, or `content` fields even for generic events.
