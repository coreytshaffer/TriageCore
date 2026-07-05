# Reviewer Smoke Runbook

## Purpose

This runbook gives reviewers a short, repeatable validation path for the current TriageCore stabilization checkpoint. It is intended to confirm that the documented command surface is present, locally runnable, and still framed within the current safety boundaries.

This is a smoke runbook, not a release certification.

## Before Starting

Start from the repository root and confirm the tree is clean:

```powershell
git status --short
```

Expected clean output:

```text
```

If this prints changed files, pause and identify them before treating smoke results as reviewer evidence. A dirty tree may be expected while reviewing an active branch, but it should be named explicitly in the review notes.

## Smoke Commands

Run the commands in this order:

```powershell
tc --help
tc doctor
triagecore benchmark --list-only
tc audit --privacy-invariants
```

Optional focused test command:

```powershell
python -m unittest discover tests
```

Use the optional unittest command only when the local environment has the project dependencies installed and the reviewer wants a broader code-level smoke check. For ordinary docs-only review, `git diff --check` plus the CLI smoke commands above is enough.

## If `tc` Is Blocked Or Not Found

Every `tc ...` command in this runbook can also be run as `python -m triage_core.tc_cli ...` when the `tc` console-script shim is unavailable — for example, when it is not on `PATH` or a local application-control policy blocks the installed `Scripts\tc.exe` shim. Both forms invoke the same CLI entry point.

Example:

```powershell
python -m triage_core.tc_cli doctor
```

This substitution changes only how the CLI is launched; it does not change command behavior or expected output.

## Expected Output Notes

### `tc --help`

Expected interpretation:

- The command should print the TriageCore operator workflow help.
- The command list should include core surfaces such as `doctor`, `audit`, `identity`, `demo`, `task-envelope`, `admission`, `eval`, `context`, `review`, `packet`, and `workspace`.
- This confirms the `tc` entry point is installed and reachable from the current shell.

### `tc doctor`

Expected interpretation:

- The command should print grouped environment, repository, ledger, handoff, config/test, and runtime safety sections.
- A clean reviewer baseline should report the current repo root and branch.
- `Result - Overall: OK` is ideal.
- `Result - Overall: WARN` can be acceptable when the warning is explained, such as a dirty tree during an active docs branch.

Dirty-tree warning interpretation:

- `Git status: dirty` means local files differ from the last commit.
- During active review, this can simply reflect the files under review.
- Before final reviewer evidence or release packaging, rerun after commit or cleanup so `git status --short` is clean.
- A dirty-tree warning is not a runtime failure by itself, but it means the smoke result is tied to the current working copy.

### `triagecore benchmark --list-only`

Expected interpretation:

- The command should list benchmark fixture ids and expected outcomes.
- It should not contact a backend.
- It confirms benchmark fixtures are discoverable without running a model.

### `tc audit --privacy-invariants`

Expected interpretation:

- The command should report that the privacy invariant audit passed.
- It should include the number of ledger records checked and the ledger path.
- It checks persisted ledger records for forbidden raw-content fields.

### `python -m unittest discover tests`

Expected interpretation:

- This is an optional broader smoke command.
- Passing results provide extra confidence that standard library test discovery can execute the test suite in the current environment.
- If the environment is missing optional project dependencies, prefer the project-standard full validation command from packaging docs:

```powershell
python -m pytest -q
```

## What This Smoke Runbook Does Not Claim

- It does not prove production readiness.
- It does not prove safety, legal compliance, or correctness of model outputs.
- It does not add or verify new cryptographic behavior.
- It does not make route-decision signing automatic.
- It does not grant approval or execution authority.
- It does not validate Qwen, cloud, GUI, or live backend integration.
- It does not publish or package the project.

## Reviewer Record Template

```text
Repo root:
Branch:
Commit:
Initial git status --short:
tc --help:
tc doctor:
triagecore benchmark --list-only:
tc audit --privacy-invariants:
Optional unittest:
Notes on warnings:
Final git status --short:
```
