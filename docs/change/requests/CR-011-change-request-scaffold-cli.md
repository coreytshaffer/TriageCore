# CR-011: Change Request Scaffold CLI

## Status
Proposed

## Scope
Introduce a `tc propose` (or `tc scaffold`) subcommand to the `tc_cli` utility. This command will automatically generate a new boilerplate Change Request markdown file in `docs/change/requests/` and correctly assign the next sequential CR number.

## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Description
Currently, when proposing a new Change Request, the operator or agent must manually identify the next available CR number by scanning `docs/change/requests/`, create the file, and copy-paste boilerplate markdown (Status, Scope, Implementation Authority, Description, Acceptance Criteria).

Adding `python -m triage_core.tc_cli propose [NAME]` will:
1. Scan the `requests/` directory for the highest existing CR number.
2. Increment the number to establish the new CR ID.
3. Generate the markdown file using a standard template.
4. Optionally prompt the user for a description or automatically append a trailing identifier (e.g., `CR-012-my-new-feature.md`).

This drastically reduces friction and ensures standardization across all Change Requests.

## Acceptance Criteria
- [ ] `tc_cli.py` supports a new `propose` (or `scaffold`) command.
- [ ] Command accurately determines the next available CR number.
- [ ] Command generates a valid Markdown file with standard headers (Status, Scope, Implementation Authority, Description, Acceptance Criteria).
- [ ] The generated file defaults to `Proposed` status.
- [ ] The command accepts an optional slug parameter (e.g., `tc propose my-new-feature` -> `CR-012-my-new-feature.md`).
- [ ] Tests verify sequence generation and correct scaffolding.
