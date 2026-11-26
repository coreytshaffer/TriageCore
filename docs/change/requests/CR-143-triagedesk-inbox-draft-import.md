# CR-143 TriageDesk inbox draft import

## Status

Proposal, design and bounded implementation approved on November 26, 2026.
The verified base is TriageCore `main` at
`31e6bd3a5c730f55c1e6f56e7bfb43f9217be571`. Implementation is for
review in a separate draft pull request. Implementation acceptance and
merge require separate human decisions.

## Scope

A workspace inbox previously supplied text directly to the TriageDesk
composer and could schedule task dispatch. The workspace file had no
operator authority to create tasks, read attachments or start a runner.
TriageDesk now leaves legacy inbox files inert.

The existing CLI command creates one prompt-only draft at a new path:

```powershell
triagecore push-task --prompt "Summarize the synthetic garden notes." --output garden-draft.json
```

Old `--auto-dispatch` and nonempty `--files` options produce migration
guidance. In TriageDesk, open **Import Draft**, inspect the read-only
preview, then choose **Load Draft** to replace the composer prompt and
clear its attachments. **Cancel** preserves the composer. Use the
existing controls to choose attachments and explicitly start a runner.

The file format is a UTF-8 JSON object with exactly two fields. The
`version` field is the integer `1` and `prompt` is nonempty text. The
maximum encoded file size is 64 KiB. The reader rejects duplicate fields,
invalid text, nonregular files, hard-linked files and paths through
symbolic links or reparse points. It uses the repository's native handle
checks on Windows and directory-relative, no-follow opens on Linux.
It refuses files when those checks cannot establish safe access.
File and format errors use fixed diagnostics. Export uses exclusive
creation and verifies the open file and its name before reporting
success. A write failure after creation can leave an incomplete file,
and the diagnostic directs the operator to choose a new filename.

## Implementation authority

The operator authorized this implementation, synthetic verification and
a separate draft pull request in the November 26, 2026 CR-143 chat. The
grant covers these five paths:

- `triage_core/cli.py`
- `triage_core/ui/app.py`
- `triage_core/triagedesk_draft.py`
- `tests/test_triagedesk_draft.py`
- `docs/change/requests/CR-143-triagedesk-inbox-draft-import.md`

General context-pack file policy, direct submission, model routing,
unattended IPC, release and deployment are outside this grant.

## Acceptance and verification

- Workspace file arrival and retired CLI options produce zero automatic
  dispatches, attachment reads, context packs or task ledger writes.
- Import previews the entire draft before touching the composer.
  Confirmation replaces only the prompt and clears the prior attachments.
  Dispatch uses the runner and attachments the operator explicitly chose.
- Invalid, oversized and linked inputs leave the active draft and task
  ledger untouched. Export preserves existing destinations.

The Windows desktop smoke used CPython 3.12.16, Tcl/Tk 8.6 and
CustomTkinter 5.2.2 with all model runners stubbed. It exercised the
actual import control and read-only scrolling preview, Cancel, Load
Draft, inert workspace arrival and a separate manual dispatch with a
synthetic attachment. It also verified that a reviewed prompt matching
the composer placeholder remains usable as text. Native Windows
hard-link and junction rejection tests passed. The focused Windows run
passed 67 tests. It skipped two symlink cases because the host lacks
symlink-creation privileges and two cases that require POSIX.

The clean Windows full regression on candidate `a5aef2a` passed 3,415
tests, skipped 18, failed 62 and reported 13 errors. All 75 failures and
errors matched the clean `31e6bd3` base by test and outcome. A follow-up
isolates the Linux output-identity test fixture.

Verify the Linux file boundary in the Ubuntu regression matrix.
Reassess the Daybreak finding on the merged revision after human
acceptance.
