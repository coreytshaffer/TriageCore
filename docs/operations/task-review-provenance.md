# Local task review provenance

CR-140 pairs a local task ledger with a private review database and an
operator-managed evidence manifest. A verified receipt describes the exact
evidence and decision an enrolled reviewer confirmed. Ordinary task
execution and supervisor reporting keep their own controls.

## Provision a review scope

Use a local Linux filesystem or Windows NTFS. Provision
`~/.triagecore-review` in the operating-system account that runs the
desktop and mobile components. On Linux use owner-only directories
(mode `0700`) and owner-only profile, manifest, enrollment, and evidence
files (mode `0600`). On Windows provision an owner-private DACL and have
new files and SQLite sidecars inherit its protections. Use genuine local
directories outside checkouts, imported ledgers, and synchronized storage.
Review paths and their ancestry must be verifiable. Scope provisioning is
an operator action.

Create `profiles.json` in that private root. Example with synthetic
values. Use absolute canonical ledger directories and credentials enrolled
under the local TriageCore relying party.

```json
{
  "schema": "triagecore.task_review_profiles.v1",
  "profiles": [
    {
      "ledger_dir": "/home/operator/projects/example/.triagecore",
      "scope_id": "example",
      "reviewer_id": "local-reviewer",
      "grants": {
        "local-reviewer": ["replace-with-the-enrolled-credential-id"]
      }
    }
  ]
}
```

The example scope uses the `example` subdirectory. An optional
`scope_directory` picks a different single directory name for an existing
store. Give each pairing its own scope and directory. Within that directory
provision `state/`, `evidence/`, and `authz/credentials.json` with the
existing enrollment format. Keep the configured review grants explicit
even when an enrolled credential can also authorize execution.

## Select the evidence revision

Create `evidence.json` in the scope directory. Each item maps a stable
display identifier to a filename under the scope's `evidence/` directory.

```json
{
  "schema": "triagecore.task_review_manifest.v1",
  "tasks": {
    "synthetic-task": {
      "revision": "revision-1",
      "items": {
        "worker-draft": "worker-draft.txt",
        "validation-notes": "validation-notes.txt"
      }
    }
  }
}
```

Use up to 16 regular UTF-8 text files and at most 1 MiB per task. Publish
complete evidence files before advancing the manifest entry. Use a new
revision ID whenever the bytes change. Readers recheck the current
binding, and stale receipts stay visible in the task's receipt history.
Ledger paths and mobile requests carry no authority to select evidence.

## Initialize or migrate

Run the following command locally with the explicitly paired ledger's
path. Close review clients first and make a protected backup of an
existing review database for recovery planning. The command initializes
an empty private store or migrates the first-slice schema. Existing
receipts, evidence bindings, heads, and scope are preserved. Deployment
and backup restoration follow their own authorization.

```console
python -m triage_core.task_review_service migrate --ledger-dir /absolute/path/to/.triagecore
```

## Confirm or inspect a review

Use a desktop review action or submit a mobile request through the
existing authenticated interface. A mobile request stays pending for up
to 24 hours. Open the task locally, inspect the requested decision and
the entire evidence snapshot, and use the designated reviewer
credential when prompted. The desktop reports success after the private
database commits. **Approve & Load** fills the task fields for the
operator's next action.

Use `tc task show` to inspect current verification and receipt history.
An unpaired ledger can still show historical observations. Required
reviews stay actionable when the current decision is absent, needs
revision, or cannot be established. Keep an unavailable sample distinct
from an empty verified sample when using review metrics or exports.

If a profile, verifier, or store becomes unavailable, check the
operator-controlled pairing, file permissions, enrollment, and
migration state. Reopen the same store to resolve an ambiguous request.
A repeated mobile submission uses the original request ID. Review
status updates are confined to the private store. Retain the original
ledger and previously exported data for historical review.

[CR-140 change request](../change/requests/CR-140-task-review-provenance.md)
