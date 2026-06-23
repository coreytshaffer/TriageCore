# CR-060: Task Envelope Validate Command

## Goal
Add a `tc task-envelope validate --from-json <fixture>` command to validate a Task Envelope JSON fixture without rendering Markdown.

## Scope
* Add `validate` command to the `task-envelope` CLI module.
* Read a JSON fixture and invoke `task_envelope_from_mapping`.
* If validation succeeds, print "Validation successful." to stdout and exit 0.
* If validation fails, print the error to stderr and exit >0.
* Reject `.triagecore/ledger.jsonl`.
* Do not render Markdown or write any files.
* Update tests and documentation.
