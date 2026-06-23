# CR-059: Task Envelope JSON Schema Documentation

## Goal
Document the JSON fixture shape accepted by `tc task-envelope draft --from-json` so operators, tests, and future agent handoffs can produce valid TaskEnvelope fixtures without relying on source-code inspection.

## Scope
* Add a docs-only JSON schema/reference document for Task Envelope fixtures.
* Document all required scalar fields.
* Document all required list fields and note that they must be non-empty arrays of non-empty strings.
* Document optional nullable/string fields.
* Reference the existing fixture at `docs/examples/task-envelope.example.json`.
* Update `docs/operations/task-envelope-cli.md` to link to the JSON fixture reference.
* Update changelog and backlog.
* No Python code changes.
* No validation logic changes.
* No ledger reads/writes.
* No persistence behavior.
* No runtime execution.
