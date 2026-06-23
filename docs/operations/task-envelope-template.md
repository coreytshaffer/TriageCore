# Task Envelope Template Contract

This document defines the minimal, reusable "Task Envelope" contract. Future CLI, Textual interfaces (TUI), and Markdown report generators will use this structure to render the state of any proposal traversing TriageCore's execution boundaries.

This contract ensures that operators are consistently presented with a calm, transparent, and authoritative view of the requested execution context, including risk, capabilities, and admission evidence.

> [!NOTE]
> This is a documentation-only specification. Future tools will parse, populate, and render this structure. In future phases, these envelopes will be hydrated historically from `.triagecore/ledger.jsonl`. No ledger reads/writes or runtime changes are implemented in this slice.

## Field Specifications

### Required Fields
- **Task ID / CR ID**: Unique identifier for the task or change request.
- **Title**: A human-readable name for the envelope context.
- **Objective**: A concise description of the task's intent.
- **Repo**: The repository context.
- **Operator / Agent Lane**: The identity of the requester.
- **Route**: The model or execution route handling the task.
- **Risk Level**: The classified risk level of the request (e.g., low, high, critical).
- **Requested Capability**: The specific execution capability requested (e.g., `read_only_summary`, `approved_mutation`).
- **Allowed Files**: Bounded scope of files the task is permitted to read or modify.
- **Forbidden Files or Areas**: Areas explicitly restricted from access.
- **Explicit Non-Scope**: Behaviors or files explicitly called out as out-of-bounds.
- **Approval Gates**: Any specific security or operator gates the task must clear before admission.
- **Validation Plan**: Steps needed to verify the task completed successfully.
- **Evidence to Produce**: The expected shape of the evidence record upon completion or admission.
- **Current Status**: The current envelope state (e.g., `proposed`, `blocked`, `approval_required`, `admitted`, `closed`).
- **Operator Decision**: The record of operator intervention (`Pending`, `Approved`, `Denied`).
- **Next Allowed Action**: Hints for the operator on how to unblock or proceed.

### Conditionally Required Fields
- **Failure Modes / Blocked Reasons**: Required when `Current Status` is blocked. Describes exact `RuntimeAdmissionError` reasons.
- **Approval Evidence**: Required when explicit approval was used.
- **Admission Evidence**: Required when a proposal was admitted.

---

## Copyable Blank Template

```markdown
# [Task ID] Task Envelope

**Title:** [Title]
**Objective:** [Objective]
**Repo:** [Repo]
**Operator / Agent Lane:** [Identity/Lane]
**Route:** [Route]

## Scope & Risk
**Risk Level:** [Risk Level]
**Requested Capability:** [Capability]
**Allowed Files:**
-
**Forbidden Files or Areas:**
-
**Explicit Non-Scope:**
-

## Governance
**Approval Gates:** [Gates]
**Validation Plan:** [Validation]
**Evidence to Produce:**
-

## Admission State
**Current Status:** [Status]
**Operator Decision:** [Decision]
**Failure Modes / Blocked Reasons:** [Reasons if blocked]
**Approval Evidence:** [If applicable]
**Admission Evidence:** [If applicable]
**Next Allowed Action:** [Next Action]
```

---

## Completed Example (CR-051)

```markdown
# CR-051 Task Envelope

**Title:** Operator UX and Task Envelope Console Design
**Objective:** Design the operator flow for how humans see task envelopes and admission evidence without adding live runtime power.
**Repo:** TriageCore
**Operator / Agent Lane:** codex-local
**Route:** local-planning

## Scope & Risk
**Risk Level:** Low
**Requested Capability:** read_only_summary
**Allowed Files:**
- docs/operator_console_design.md
- docs/change/requests/CR-051-operator-ux-task-envelope-console.md
- docs/change/change_log.md
- docs/current_backlog.md
**Forbidden Files or Areas:**
- triage_core/*.py (No Python modifications permitted)
**Explicit Non-Scope:**
- CLI/TUI logic
- Ledger reading/writing

## Governance
**Approval Gates:** Reviewer approval of implementation plan
**Validation Plan:** `git diff --check`
**Evidence to Produce:**
- docs/operator_console_design.md
- CR-051 request document
- changelog/backlog updates
- git diff --check result

## Admission State
**Current Status:** closed
**Operator Decision:** Approved
**Failure Modes / Blocked Reasons:** None
**Next Allowed Action:** Use CR-052 to define the reusable task-envelope contract.
```
