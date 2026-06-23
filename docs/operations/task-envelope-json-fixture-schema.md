# Task Envelope JSON Fixture Schema

This document defines the accepted shape of the JSON payload when drafting a Task Envelope from a fixture using `tc task-envelope draft --from-json`. 

> [!IMPORTANT]
> The JSON fixture represents a draft state. It is strictly used as input to render deterministic Markdown. 
> - `--from-json` is for **fixture input only**, not ledger replay. 
> - `.triagecore/ledger.jsonl` is explicitly **NOT** an accepted fixture source.

## Example Fixture

An example valid JSON fixture is available in the repository at: [docs/examples/task-envelope.example.json](../examples/task-envelope.example.json).

## Required Scalar Fields

The following fields must be present and must be non-empty strings.

* `task_id`: Unique identifier (e.g., `CR-010`)
* `title`: Title of the task
* `objective`: Detailed goal of the task
* `repo`: The repository targeted (e.g., `TriageCore`)
* `operator_agent_lane`: Lane context (e.g., `cli-operator`, `autonomous`)
* `route`: The designated system route (e.g., `local-cli`)
* `risk_level`: Estimated risk (`Low`, `Medium`, `High`)
* `requested_capability`: Permissions required (e.g., `read_only`, `read_write`)
* `approval_gates`: Description of required sign-offs
* `validation_plan`: How success will be measured or verified
* `current_status`: Status of the task (e.g., `proposed`)
* `operator_decision`: Operator's explicit stance (e.g., `Pending`)
* `next_allowed_action`: Allowed subsequent action (e.g., `review`)

## Required List Fields

The following fields define the boundaries of the envelope. They must be present, and must be arrays containing at least one non-empty string.

* `allowed_files`: Explicitly whitelisted files
* `forbidden_files_or_areas`: Explicitly blacklisted files or areas
* `explicit_non_scope`: Out-of-bounds tasks
* `evidence_to_produce`: Expected artifacts or validation output

## Optional Fields

The following fields are optional. They may be omitted, set to `null`, or set to a non-empty string.

* `failure_modes_or_blocked_reasons`: Detailed string of blockages/failures
* `approval_evidence`: Proof of approval
* `admission_evidence`: Proof of initial admission
