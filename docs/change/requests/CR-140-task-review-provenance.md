# CR-140 — Establish provenance for task review decisions

## Status

**Proposed.** Proposal and design acceptance are pending.

## Scope

Define how TriageCore records, verifies, and presents evidence of a human
decision about a task review. The contract should cover desktop and mobile
review entry points and the task, queue, report, and metric views that consume
the resulting decisions.

Use the authority boundaries in the [current system architecture](../../architecture/current_system_architecture.md).
Treat a recorded decision and its verification status as separate facts. A
verified review receipt provides evidence about the decision it binds.
Execution authorization, artifact correctness, and research validity retain
their own controls.

## Proposed design requirements

- Define which human identities may record reviews and how the verifier
  establishes that authority. The receipt must bind the reviewer identity,
  task and review event identifiers, exact decision, digest of the reviewed
  evidence, and time under a versioned contract.
- Assess whether existing credential verification can support a dedicated
  review receipt. Design acceptance should cover the receipt format, storage
  boundary, authorized reviewer enrollment, and credential lifecycle.
- Preserve historical rows without rewriting or automatically authenticating
  them. Keep historical decisions inspectable with clear provenance. Count
  only verified decisions in any result presented as verified human review.
- Define how a review write handles unavailable credentials or persistence
  failures. A reader should distinguish unverified evidence from a verified
  decision and retain the last verified decision when a newer record cannot
  be verified. Task views, queues, and reporting should use the same rules.
- Keep private evidence and credential material local. Limit the receipt and
  diagnostics to the fields needed to establish provenance.

Changes to execution authorization, other signed event types, and the private
checklist-review store are outside this proposal.

## Implementation authority

**Pending.** This change request asks for proposal review. A later grant must
name the accepted design, the source and test paths, and the permitted
implementation actions. The initial design scope is the review writers,
receipt verification and task projection, and review consumers.

## Human approval requirement

Record proposal acceptance and design acceptance before implementation
authority. Record implementation acceptance, merge authority, release
authority, and closeout as separate decisions under the
[change-management policy](../change_management.md).

## Acceptance criteria

- [ ] The accepted design specifies the reviewer identity, receipt binding,
  trust and failure rules, historical-row treatment, and bounded rollout.
- [ ] Synthetic fixture tests show that verified decisions made through both
  review entry points agree across task views, queues, and reporting.
- [ ] Fixture tests cover legacy and unverifiable evidence, credential and
  persistence failures, and retention of an earlier verified decision.
  Unverified evidence stays inspectable and remains outside verified totals.
- [ ] Verification preserves the append-only history, existing signed event
  behavior, and the separation between review and execution authority.

## Identifier census

On 2026-11-23, GitHub `main` at `ad2aa69` contained
numbered CRs through CR-139. The GitHub heads and open pull requests checked
showed no reservation for CR-140.
