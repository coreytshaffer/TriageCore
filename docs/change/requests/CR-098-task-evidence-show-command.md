# CR-098: Add task evidence show command

## Summary
Implements `tc task show <task_id>`, a read-only CLI command to display one task's evidence chain in a reviewer-friendly way.

## Context
A reviewer needs a quick, non-destructive way to view a task's entire lifecycle events and status directly from the CLI. This command reads the append-only ledger events, reduces them into a `TaskRecord` display, and prints the timeline.

## Changes
- **CLI Command:** Added `task` command and `show` subcommand to `tc_cli.py`.
- **Display Output:** Prints stable fields (Task ID, Title, Status, Accepted value, Review decision, Ledger events count) followed by the chronological event timeline.
- **Explicit Instruction:** Prints `Signature verification: not checked by this command; run tc audit --verify-signatures` to maintain a clear security posture.
- **Fail-closed missing task check:** If a task is missing, exits nonzero with `reason=task_not_found` and no python traceback.

## Explicit Disclosures
- This is a read-only evidence inspection command, not a task mutation or execution command.
- It does not load the identity registry or perform signature verification.
- Historical ledger records are never mutated or rewritten.
