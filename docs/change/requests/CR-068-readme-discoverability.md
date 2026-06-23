# CR-068: Operator Documentation Consolidation / README Discoverability

## Goal
Update the main `README.md` to properly highlight the newly built operator admission workflow and CLI tools, making them easily discoverable to new users or reviewers.

## Scope
* Update the "What It Does Today" section to mention offline governance tools.
* Update the "Start here" section to link to `docs/operations/external-runtime-admission.md`.
* Add a dedicated "External Runtime Admission Governance" section explaining the tri-part model.
* Include explicit non-execution guardrails (does not execute external runtimes, write to the ledger, or mutate approval state).
* Provide short, copy-pasteable command examples for `task-envelope` and `admission`.
* Update changelog and backlog.
