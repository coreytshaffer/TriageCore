# CR-011: Change Request Scaffold CLI

## Status
Implemented

## Scope
Introduce a `tc propose` subcommand to the `tc_cli` utility. This command will generate a new boilerplate Change Request markdown file in `docs/change/requests/` using an explicit CR ID.

## Implementation Authority
Implemented after operator approval. Future changes to this command require a new CR or explicit operator approval.

## Description
Currently, when proposing a new Change Request, the operator or agent must manually create the file, and copy-paste boilerplate markdown (Status, Scope, Implementation Authority, Description, Acceptance Criteria).

Adding `python -m triage_core.tc_cli propose [CR_ID] [NAME]` will:
1. Validate the provided explicit CR ID format.
2. Slugify the title into the request filename.
3. Generate the markdown file using a standard template.
4. Refuse to overwrite existing CR files.
5. Optionally update `docs/change/change_log.md` with `--changelog`.

This drastically reduces friction and ensures standardization across all Change Requests.

## Acceptance Criteria
- [x] `tc_cli.py` supports a new `propose` command.
- [x] Command accepts an explicit CR ID such as `CR-012` or `CR-004B`.
- [x] Command validates CR ID format.
- [x] Command slugifies the title into the request filename.
- [x] Command refuses to overwrite existing CR files.
- [x] Command generates a Markdown proposal template.
- [x] Command optionally updates `docs/change/change_log.md` with `--changelog`.
- [x] Tests verify scaffolding, validation, overwrite protection, CR-004B-style IDs, and changelog behavior.
