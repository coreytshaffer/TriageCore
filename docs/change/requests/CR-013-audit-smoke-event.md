# CR-013: Audit Smoke Event

## Status
Implemented

## Scope
- Add `tc audit --self-test` as a narrow smoke path.
- Append exactly one privacy-safe `route_audit` event to `.triagecore/ledger.jsonl`.
- Preserve metadata-only output with no prompt, data, content, `raw_prompt`, or `raw_data` fields.

## Implementation Authority
Implemented in repo.

## Description
This change adds a boring, deterministic audit smoke event so operators can verify the ledger append path and the safe `tc audit` inspection path without executing a real task or triggering routing side effects.

## Acceptance Criteria
- [x] `tc audit --self-test` writes one `route_audit` event to `.triagecore/ledger.jsonl`.
- [x] The event is inspectable with `tc audit --kind route_audit --last 10`.
- [x] The event contains metadata only and excludes raw payload fields.
- [x] The self-test works when the ledger file and parent `.triagecore` directory do not yet exist.
