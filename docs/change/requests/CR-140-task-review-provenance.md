# CR-140 — Establish provenance for task review decisions

## Status

**Proposal accepted by Corey Shaffer on 2026-11-23 (America/Los_Angeles).**
Design revision 1 was accepted by Corey Shaffer on 2026-11-23
(America/Los_Angeles), at PR head
`37bceec44a360f40bddc127182f94fa7b174de2f`.

> I accept the CR-140 proposal.

> Design and implementation approved.

The second decision records design acceptance and approval to proceed with
implementation in principle. The exact writable paths and permitted actions
for the first slice are proposed below for confirmation.

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

**Implementation approved in principle.** The bounded implementation grant
is pending confirmation of the exact paths and actions below. The integration
slice requires a separate grant.

### Proposed first-slice grant

Implement the review-receipt foundation from accepted design revision 1 in an
isolated checkout. Use synthetic fixtures, run focused and regression tests,
and publish the candidate on the existing draft PR #212 branch for review.

| Writable path | Purpose |
| --- | --- |
| `triage_core/task_review_receipt.py` | Canonical review request, receipt and evidence manifest. Verify reviewer eligibility and proof against trusted inputs. |
| `triage_core/task_review_store.py` | Local SQLite persistence for challenges, verified receipts and per-task review heads. |
| `triage_core/fido2_adapter.py` | Share only the low-level assertion verification needed by both receipt types. Preserve the execution receipt API and policy. |
| `tests/test_task_review_receipt.py` | Synthetic evidence and credential verification tests. |
| `tests/test_task_review_store.py` | SQLite admission, failure and isolation tests. |
| `docs/change/adr/ADR-CR-140-task-review-authority.md` | Record the accepted review-store trust boundary and its consequences. |
| `docs/change/requests/CR-140-task-review-provenance.md` | Record the grant and evidence for this slice. |

The slice ends with the foundation and its tests. Desktop and mobile
writers, task projection, reporting, migrations of existing data, runtime
ledger writes, hardware operations, merge, and release require later
authority.

### First-slice implementation plan

1. **Receipt contract.** Start with synthetic tests in
   `test_task_review_receipt.py` for canonical evidence digest and request
   construction. Test that a change to any bound field changes the
   challenge, and reject unknown versions, invalid decision values, and
   noncanonical identifiers. Implement the versioned request, receipt
   and manifest in `task_review_receipt.py`. The manifest builder accepts
   the already-captured item bytes and stable item identifiers. It never
   resolves a path or reads a live evidence source.
2. **Proof verification.** Test signed synthetic assertions, purpose and
   scope separation, reviewer grant and enrollment checks, user-presence
   and user-verification requirements, and wrong origin or relying party.
   Share the existing FIDO2 primitive through `fido2_adapter.py`. Review
   verification uses the review challenge and trusted policy supplied by
   the caller. Run `tests/test_authz.py` as the execution-receipt regression
   check.
3. **Transactional admission.** Start with synthetic SQLite tests for
   competing confirmations, expiry, idempotent retry and ambiguous
   commit, cross-scope access, stale evidence and predecessor, and an
   inaccessible store. Implement one transaction in
   `task_review_store.py` to check trusted scope, current evidence
   binding and predecessor, consume the challenge, persist the verified
   receipt and admission time, and advance the head. Test historical
   verification at the admission time under current eligibility policy,
   and preserve failure outcomes without restoring superseded decisions.
4. **Handoff.** Record the authority boundary in the ADR. In a disposable
   test environment run
   `python -m pytest tests/test_task_review_receipt.py tests/test_task_review_store.py tests/test_authz.py tests/test_capability_claims.py`,
   then `python -m pytest` and `git diff --check`. Confirm the candidate
   changes only the allowed paths and has no writer or projection call
   sites. Record the exact base, candidate revision and observed results
   in the CR before requesting implementation acceptance.

## Human approval requirement

Record design acceptance before granting implementation authority. Record
implementation acceptance, merge authority, release authority, and closeout
as separate decisions under the
[change-management policy](../change_management.md).

## Acceptance criteria

- [ ] The accepted design specifies the reviewer identity, receipt binding,
  trust and failure rules, historical-row treatment, and bounded rollout.
- [ ] Synthetic fixture tests show that decisions initiated through either
  review entry point agree across task views, queues, and reporting after
  the enrolled reviewer confirms them locally.
- [ ] Fixture tests cover legacy and unverifiable evidence, credential and
  persistence failures, and retention of an earlier verified decision.
  Unverified evidence stays inspectable and remains outside verified totals.
- [ ] Verification preserves the append-only history, existing signed event
  behavior, and the separation between review and execution authority.

## Proposed design revision 1

### Current behavior and trust boundary

At the proposal head `8527cacd1db0bde88f28bf5de2d4a057c6565efc`,
the [ledger reducer](../../../triage_core/task_ledger.py#L501) derives review
state from unsigned events. Both [desktop actions](../../../triage_core/ui/app.py#L1964)
and the [mobile endpoint](../../../triage_core/web/server.py#L147) write those
events. The [mobile screen](../../../triage_core/web/static/app.js#L36) shows
task metadata. The [existing FIDO2 adapter](../../../triage_core/fido2_adapter.py#L254)
verifies execution-authorization receipts against the local relying party.

Assume ledger rows, imported records, and values submitted through either
review entry point can be untrusted. Trust the local operator-managed reviewer
configuration, credential registry, review store, and confirmation process.
Compromise or rollback of that trusted state is outside the guarantee.
Verification attests to an identified human's decision on specific evidence.
Artifact correctness, research validity, and execution authorization keep
their existing controls.

### Design choice

A receipt stored alongside a mutable ledger can authenticate an individual
record. Establishing the current decision also requires a trusted commit
record so that ledger edits cannot change which decision is current. Use a
dedicated local SQLite review store for committed receipts and review state,
with the ledger carrying optional audit references. This adds a local store
and keeps review state independent of ledger availability and row order.

Use the existing local FIDO2 confirmation flow as the model. Reuse its
credential lookup and low-level assertion verification where they can be
shared without changing execution authorization semantics. A browser-native
mobile ceremony would require an approved origin, a browser-compatible
enrollment model, and a mobile evidence view. Keep that deployment work
outside this design. The mobile endpoint submits a pending review request
for local confirmation and returns that status to the caller.

### Reviewer and evidence binding

- The local operator grants review authority to named human identities
  and their enrolled credentials. Review authority requires an explicit
  review grant even when an enrolled credential can authorize execution.
  Enrollment and grants come from trusted local configuration. A shared
  mobile token, actor string, supervisor result, or agent identity cannot
  supply the reviewer identity.
- The local confirmation shows the exact decision and an immutable snapshot
  of the evidence the person is reviewing. Version the manifest and hash
  canonical manifest. Each entry identifies one item shown and contains a
  digest of its exact bytes. Use stable item identifiers and deterministic
  ordering. Bind the expected task and evidence revision. Do not resolve a path supplied by a ledger row or
  mobile request. Use an operator-selected local evidence source or an
  explicitly trusted producer. Keep raw evidence outside the receipt and
  operational logs. Missing, unreadable, or changed evidence requires a new
  preparation and confirmation.
- Define a versioned review-specific request and receipt. The signed
  challenge binds the review policy and purpose, workspace review scope,
  task ID, evidence revision and SHA-256 digest, review event ID,
  predecessor receipt ID, exact decision, reviewer ID, relying party,
  nonce, and UTC issue and expiry times. Verify with a pinned local origin,
  enrolled credential and matching reviewer identity, user presence, and
  required user verification. Validate the challenge against the request
  held by the local service. Review assertions and execution authorization
  assertions are valid only for their respective purposes.
- Use a closed decision vocabulary of `accepted`, `accepted_with_minor_edits`,
  `needs_revision`, and `rejected`. Preserve each entry point's decision
  choices. Derive any compatibility acceptance flag from that decision
  once. Keep task resolution, artifact validation, workload, and review
  time independent. Label optional workload and timing as observations
  and leave missing values unknown. Ledger values cannot set acceptance,
  resolution, or review-derived artifact status.

### Recording and projection

1. Desktop prepares a review directly. Mobile submits an intent containing
   the requested decision and task reference. Local confirmation resolves
   the task and evidence again and displays both. The proposed validity
   windows are five minutes for the reviewer challenge and 24 hours for the
   mobile intent. An intent cannot reserve or advance verified state.
   Pending intent metadata stays local and outside review metrics.
2. On confirmation, verify the challenge, evidence revision, enrollment,
   and review grant. In one store transaction, consume the challenge,
   commit its receipt and trusted admission time, and advance the review
   head only if the task's evidence revision and expected predecessor
   still match. An authorized exact retry returns the committed result
   without creating a second review. An expired challenge or stale
   predecessor requires a fresh confirmation. On an ambiguous commit,
   resolve the original event ID before allowing a retry.
   An unavailable store or failed commit cannot produce a verified result.
3. Keep assertions, credential identifiers, reviewer identity, and the
   admission record in the access-restricted local store. If the optional
   audit reference fails to append, report that separately from the
   committed decision. The reference contains only privacy-approved
   identifiers and digests. Reconcile by the stable review event ID so
   mirror retries never create a second decision. Do not create a ledger
   reference for an uncommitted decision or import the store from ledger
   data.
4. Full verification at admission checks expiry against the local clock.
   At read time, verify historical proof against the stored admission time
   and apply current local credential and review-grant policy. Loss of trust
   in a credential or review grant removes its current verified status
   while preserving attributable history. A failure to open the trusted
   store or load its policy yields verification unavailable. Do not
   silently reinstate a superseded decision if the committed head cannot
   be verified. Opening a custom ledger without an explicitly paired
   review scope yields historical observations only.
5. Use one projection for desktop, mobile, `tc task show`, queues, and
   task-review metrics. Distinguish no decision, historical unverified
   observation, pending intent, verified decision, and verification
   unavailable. Later unsigned or unverifiable records leave an earlier
   verified decision intact while that decision remains valid under current
   policy and for the same evidence revision. A change to the review
   evidence leaves earlier receipts inspectable for their own revision and
   returns a required current review to the queue. Without a trusted
   current evidence binding, show historical receipt status only.
   Acceptance or rejection closes a verified review of that revision.
   `needs_revision` stays actionable. Keep it out of binary acceptance
   metrics and training labels. Ordinary task display applies these rules
   by default, independent of the optional signed-event audit.
6. Preserve existing JSONL and exported data. The first release will show
   unsigned reviews as historical and unverified, and some previously
   closed tasks may return to the review queue. Current metrics and
   training exports require explicit verified labels. Report verified
   sample size and excluded observations where relevant. An unavailable
   verifier cannot produce an apparently empty verified report. Keep
   supervisor-review reporting and operational outcomes distinct from
   human task-review verification.

### Bounded delivery and verification

- First slice for future approval: review request and receipt, local trust
  and persistence boundary, and synthetic contract tests with no writer
  or projection integration. Record the accepted authority boundary in an
  ADR and name exact source and test paths in the grant for this slice.
- Integration slice for future approval: integrate both desktop actions and
  the mobile intent flow, switch task views and dependent consumers to the
  shared projection, and cover the read and write paths together. Keep the
  prior output available with an unverified-history label. Avoid an
  intermediate release with different authority rules across entry points.
  No new network exposure or mobile transport configuration belongs to
  this change.
- Verify decision-to-evidence binding, credential and review-grant
  eligibility, cross-scope isolation, expiry and retries, competing
  confirmations, store and mirror failure, and reproducible historical
  verification. Use synthetic fixtures to verify that pending, unsigned,
  and stale records cannot supply verified output or training labels. Test
  that an unavailable verifier is surfaced explicitly. Cover single-task
  and list parity, queue behavior and metrics,
  unchanged JSONL bytes, and compatibility of existing signed events.
  Before implementation acceptance, run the focused suites and full
  regression checks, then exercise local confirmation on supported desktop
  hardware and the authenticated mobile intent flow with synthetic data.

Design review should explicitly settle three choices: local confirmation for
mobile requests, the independent review store as the source of committed
review state, and current-policy re-evaluation of past receipts. Approval of
the design covers these choices. Each implementation slice still requires
its own bounded grant.

## Identifier census

On 2026-11-23, GitHub `main` at `ad2aa69` contained
numbered CRs through CR-139. The GitHub heads and open pull requests checked
showed no reservation for CR-140.
