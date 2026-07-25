# CR-YK-002: Atomic Execution-Capability Claiming

## Status

- **Status:** Requirements approved. The standalone atomic-claiming foundation
  is implemented on branch `cr-yk-002-atomic-capability-claiming`. It has not
  been merged, and this document makes no claim that it has.
- **Implementation authority:** Granted for the standalone claim foundation
  only, within the allowlist recorded below.
- **Still unauthorized:** `tc authz` CLI surfaces, `tc authz exec`, `tc run`
  integration, `--confirmed-plan`, backend or model invocation, routing and
  worker changes, saved-plan execution, FIDO2 or YubiKey changes, and
  CR-DD-012B integration.
- **CR-DD-012B:** remains explicitly unauthorized and blocked pending its own
  separate approval.

This document records the requirements contract and the implementation
delivered against it. It grants no execution or integration authority.

## Scope

CR-YK-002 proposes a standalone, local SQLite claim registry that would close
the concurrency gap left by CR-YK-001. The current ledger-only consumption
sequence reads capability state and then appends an event, so concurrent
consumers can both observe an unused capability before either append becomes
visible.

The proposed slice is limited to atomic capability claiming, irrevocable
lifecycle transitions, metadata-only evidence, and focused validation of those
contracts. It grants no task-execution or integration authority.

## Objective

Provide a deterministic, fail-closed capability lifecycle foundation in which:

1. Exactly one execution attempt can claim a capability.
2. A claim is irrevocable.
3. Failed, abandoned, or crashed attempts do not restore capability usability.
4. SQLite controls concurrency.
5. The task ledger remains the durable evidence history.
6. No task execution occurs in this change.

The conservative invariant is binding: **a crash burns the authorization rather
than risking duplicate execution**. Retrying requires newly verified human
authorization and a new capability.

## State Model

```text
issued -> claimed -> completed
                  \-> failed
```

- `issued` may transition only to `claimed`.
- `claimed` may transition only to `completed` or `failed`.
- `completed` and `failed` are terminal.
- No transition may return a capability to `issued`.
- A crash after claiming burns the capability.
- Capability expiry determines whether a new claim may begin.
- A claim committed before expiry may be finalized after the original expiry.
- Recovery, retry, or replacement requires a new human authorization and a new
  capability.

## Authority Split

### SQLite claim registry

SQLite would be authoritative only for:

- atomic claim ownership;
- current capability lifecycle state;
- claimant and execution-attempt binding;
- terminal-transition enforcement.

SQLite would not prove authenticity, human approval, device identity, plan
correctness, execution safety, or ledger integrity.

### Task ledger

The task ledger would remain authoritative evidence for:

- capability issuance;
- successful claims;
- claim denials;
- completed or failed terminal outcomes;
- evidence gaps or later reconciliation events.

The ledger must not be used as the concurrency lock.

## Storage Contract

The proposed default path is:

```text
.triagecore/authz/capability_claims.sqlite3
```

The database must use a versioned schema. Minimum immutable capability bindings:

- `capability_id`
- `task_id`
- `decision_id`
- `receipt_digest`
- `artifact_byte_digest`
- `plan_body_digest`
- `scope_digest`
- `approver_identity_id`
- `expires_at`

Lifecycle fields:

- `state`
- `claimed_at`
- `claimant_id`
- `execution_attempt_id`
- `terminal_at`
- `terminal_outcome`

Required constraints and operating posture:

- `capability_id` is the primary key.
- `state` uses a closed SQLite `CHECK` constraint.
- `execution_attempt_id` is unique when non-null.
- Immutable bindings cannot change after insertion.
- Claimed and terminal rows cannot be deleted through the public API.
- Timestamps use canonical UTC ISO-8601 values.
- Digests retain the existing `sha256:<64 lowercase hex>` contract.
- Use Python's standard-library `sqlite3`; add no dependency.
- Use a bounded `busy_timeout`; never wait indefinitely.
- Use independent connections for independent consumers.
- Claim and terminal transactions use `BEGIN IMMEDIATE`.
- Enable `PRAGMA foreign_keys = ON` and prefer `synchronous = FULL`.
- Schema mismatch, malformed rows, failed integrity checks, and database I/O
  errors fail closed.
- Apply restrictive file permissions where supported.
- Support local filesystems only. Do not claim correct locking semantics over
  NFS, SMB, cloud-synced folders, or unusual FUSE mounts.

## Issuance Contract

CR-YK-002 would version the `execution_capability_issued` payload and add the
bindings required by the atomic registry, particularly:

- `schema`
- `task_id`, or a reliable event-envelope task binding
- `plan_body_digest`
- `scope_digest`
- `issued_at`

**Amendment (implementation decision, approved after the fact).** Of the two
permitted task bindings above, the implementation uses the **ledger event
envelope**, and `task_id` is deliberately **not** duplicated into the issuance
payload. The envelope is authoritative:

- Issuance events are written with `append_event(task_id, ...)`, which always
  populates the envelope `task_id`, and are read back through
  `get_events(task_id)`, which matches the envelope value exactly. There is no
  path that returns an event belonging to another task.
- The value written into the claim database's immutable `task_id` column is
  the envelope value, not a payload copy, so there is no second source that
  could disagree with the first.
- A missing, blank, or non-string envelope `task_id` fails closed: the
  capability is unclaimable, and no row is ever materialized.
- A conflicting envelope `task_id` for an already-claimed capability fails the
  immutable-binding check and cannot rebind or hijack the row.

This deviates from the implementation handoff, which directed that `task_id` be
added to the payload. It was raised and approved as a deliberate amendment
rather than a silent substitution. The practical trigger was that adding
`task_id` to the payload broke two unchanged CR-YK-001 tests: the persistent
privacy scanner is value-based, and the fixture's synthetic non-UUID task
identifier matched its credit-card heuristic. Production task identifiers are
UUIDs and would not have tripped it, so the deviation is justified by the
single-source-of-truth argument above rather than by the test failure.

The existing issuance path already records capability ID, receipt digest,
decision ID, artifact digest, approver identity, expiry, and single-use status.

Pre-CR-YK-002 capability events that lack the new schema or required bindings
must fail closed as legacy and unclaimable. Historical capabilities must not be
migrated or upgraded into executable authority.

## Atomic Claim Contract

The future claim API must require:

- task ID;
- capability ID;
- expected artifact-byte digest;
- expected scope digest;
- normalized claimant ID;
- unique execution-attempt ID;
- injectable current time for tests.

Required algorithm:

1. Locate and validate exactly one compatible capability-issuance event.
2. Reject legacy, malformed, expired, missing, or binding-mismatched
   capabilities before granting a claim.
3. Open an independent SQLite connection.
4. Start `BEGIN IMMEDIATE`.
5. Insert the immutable capability row if it has not been materialized.
6. Verify that an existing row has exactly the same immutable bindings.
7. Atomically update the row from `issued` to `claimed` only when the current
   state is `issued`, the capability is not expired, and artifact and scope
   bindings match.
8. Require exactly one changed row.
9. Commit before reporting success.
10. Append the metadata-only successful-claim event to the ledger.

Two or more concurrent claimers must produce exactly one committed claim.

### Evidence-write failure after claim

The SQLite transaction must commit before the success ledger event is appended.
If SQLite commits but the ledger append fails:

- the capability remains irreversibly `claimed`;
- the operation must not report execution-ready success;
- the result must identify an evidence-write failure;
- a retry must not reclaim the capability;
- no execution may occur;
- later reconciliation may record missing evidence, but reconciliation is not
  required in the initial slice.

This ordering intentionally burns an authorization rather than permitting
duplicate execution.

### Closed claim-result vocabulary

Future claim outcomes must use a bounded vocabulary such as:

- `ok`
- `capability_not_found`
- `capability_legacy_unclaimable`
- `capability_expired`
- `artifact_digest_mismatch`
- `scope_digest_mismatch`
- `capability_already_claimed`
- `capability_binding_mismatch`
- `capability_store_busy`
- `capability_store_unavailable`
- `claim_evidence_write_failed`

No free-text denial or failure reason may enter persistent evidence.

## Terminal Contract

A terminal transition must require:

- capability ID;
- the same claimant ID;
- the same execution-attempt ID;
- requested terminal state `completed` or `failed`;
- injectable terminal timestamp.

The update must be conditional on current state `claimed` and on both claim
bindings matching. A second terminal transition must fail closed. Terminal
failure never restores capability usability.

Future terminal outcomes must use a bounded vocabulary such as:

- `ok`
- `capability_not_found`
- `capability_not_claimed`
- `capability_already_terminal`
- `claimant_mismatch`
- `execution_attempt_mismatch`
- `terminal_evidence_write_failed`

CR-YK-002 does not decide whether an execution result is acceptable, correct,
safe, or high quality. It records only lifecycle completion or failure.

## Privacy Contract

Before persistence, all database rows and ledger-emitted metadata must pass the
existing persistent privacy invariant. Neither store may contain:

- prompts or source data;
- rendered run-plan text;
- file contents or unrestricted paths;
- WebAuthn assertion payloads;
- public credential keys;
- PINs, private keys, authentication secrets, or recovery codes;
- arbitrary human notes.

The versioned claim database must contain only the bounded metadata needed for
bindings, lifecycle state, and evidence.

## Compatibility Contract

- The ledger-only read-then-append path must not remain an active claim path
  after a future implementation.
- A retained `consume_capability` compatibility function must delegate to the
  atomic store and must not preserve the old race.
- Historical ledger events remain readable.
- Existing CR-YK-001 receipt and credential formats remain unchanged.
- `fido2_adapter.py` requires no modification.
- No hardware ceremony is required to test the proposed slice.
- No runtime module may import or consume the claim store in this slice.

## Test Contract

A separately approved implementation must add focused tests demonstrating:

1. Two independent claimers produce exactly one success.
2. Higher-contention testing still produces one success.
3. The former strict concurrency `xfail` becomes a passing test.
4. Already claimed, completed, or failed capabilities are denied.
5. Expired capabilities cannot be claimed.
6. Artifact- and scope-digest mismatches are denied.
7. Conflicting ledger data cannot replace immutable database bindings.
8. Failed, abandoned, or crashed execution does not restore the capability.
9. Only the matching claimant and execution-attempt ID can finalize a claim.
10. Terminal states cannot transition again.
11. Ledger failure after SQLite commit burns the claim and prevents
    execution-ready success.
12. Busy, corrupt, missing-schema, and unsupported-version databases fail
    closed.
13. Persistent rows and ledger payloads pass privacy checks.
14. Separate capabilities remain independently claimable.
15. Existing CR-YK-001 receipt, credential, and hardware-adapter tests remain
    unchanged and passing.

No new expected failure may replace the resolved concurrency `xfail`.

## Acceptance Contract

CR-YK-002 may be considered implemented only when:

- explicit human implementation approval has been granted;
- the previous strict concurrency `xfail` is replaced by a passing atomicity
  test;
- exactly one claimant succeeds through real independent SQLite connections;
- failed, abandoned, and crashed attempts cannot restore capability reuse;
- all state and binding mismatches fail closed with closed reason codes;
- the full test suite passes with no new `xfail`;
- the privacy-invariant audit passes;
- SQLite integrity checking passes;
- `git diff --check` passes;
- the implementation diff stays within the approved allowlist;
- no runtime module imports or consumes the claim store.

Recording this proposal does not satisfy any acceptance item and does not claim
that implementation occurred.

## Explicitly Out of Scope

CR-YK-002 must not add:

- `tc authz` CLI commands;
- `tc authz exec`;
- `tc run` integration;
- `--confirmed-plan`;
- backend or model invocation;
- route or worker changes;
- saved-plan execution;
- automatic retry or capability restoration;
- execution recovery policy;
- distributed locking;
- networked databases;
- cloud authorization;
- signed capability ledger events;
- YubiKey enrollment or assertion changes;
- backup-YubiKey verification;
- CR-DD-012B implementation.

## Candidate Future Implementation Allowlist

Subject to separate explicit human approval, the candidate implementation
allowlist is:

- `triage_core/capability_claims.py`
- `triage_core/authz.py`
- `tests/test_capability_claims.py`
- `tests/test_authz.py`
- `docs/change/requests/CR-YK-002-atomic-capability-claiming.md`
- `docs/current_backlog.md`
- `docs/change/change_log.md`

No README, CLI, FIDO2 adapter, router, worker, backend, or dependency-file
change should be necessary. This candidate list is not implementation authority.

## Recommended Sequencing

1. Approve this requirements contract as a docs-only proposal.
2. Separately approve and implement the standalone SQLite claim foundation.
3. Review and merge CR-YK-002 independently.
4. Scope CR-DD-012B separately to consume the merged claim API.
5. Require a new authorization before any recovery or retry policy is
   considered.

## Implementation Record

Delivered on branch `cr-yk-002-atomic-capability-claiming` (not merged):

- `triage_core/capability_claims.py` — the standalone SQLite registry:
  versioned schema, closed `CHECK` constraint over the four lifecycle states,
  partial unique index on `execution_attempt_id`, and triggers enforcing
  immutable bindings, absorbing terminal states, and undeletable claimed rows.
  `BEGIN IMMEDIATE` is taken before any decision is read.
- `triage_core/authz.py` — the sole authorized compatibility boundary. It
  versions the issuance payload to `triagecore.execution_capability.v2`, adds
  `claim_capability` and `finalize_capability`, and delegates the legacy
  `consume_capability` to the atomic store.
- `tests/test_capability_claims.py` and the replaced concurrency tests in
  `tests/test_authz.py`.

Two deliberate reporting decisions, recorded rather than left to discovery:

- **The persisted `execution_capability_denied` reason vocabulary widens from
  five values to nine**, adding `capability_legacy_unclaimable`,
  `capability_store_busy`, `capability_store_unavailable`, and
  `claim_evidence_write_failed`. Collapsing these into the five legacy values
  would report an operational store failure as a lifecycle or binding
  decision, which would be untrue.
- **The `consume_capability` compatibility boundary intentionally maps
  artifact, scope, and immutable-binding mismatches to the single legacy
  `REASON_DIGEST_MISMATCH` value.** A caller reading only that boundary cannot
  distinguish them; `claim_capability` retains the precise reason. This is a
  known reporting limitation and was not redesigned in this slice.

Two implementation details worth a reviewer's attention:

- The task binding comes from the ledger event envelope and is not duplicated
  into the payload. See the amendment recorded under *Issuance Contract*; the
  four fail-closed properties it lists are covered by tests.
- A denied claim rolls back the row it may have inserted, so only committed
  claims persist. Committing denied attempts would let bogus bindings
  materialize a row that permanently locks out the legitimate claimer.

## Limitations and Uncertainty

- Concurrency is proven with threads over independent SQLite connections on a
  local filesystem. Multi-process and cross-host behavior is not exercised.
- Expiry is enforced in Python inside the same `BEGIN IMMEDIATE` transaction
  rather than in the SQL predicate, because ISO-8601 text is not a reliable
  total order across differing sub-second precision. The check is still inside
  the write lock, so it is not a race, but it is not a database constraint
  either.
- The persistent-privacy scanner is value-based and can flag non-UUID synthetic
  identifiers as false positives; production task identifiers are UUIDs.
- Reconciliation of an evidence gap left by a burnt claim is still not
  implemented and remains out of scope.
- Local SQLite behavior does not establish safe distributed locking semantics.
- A committed claim followed by a crash or evidence-write failure intentionally
  creates an unusable authorization and may leave an evidence gap.
- Reconciliation, recovery, execution-result semantics, and integration with
  `tc run` or CR-DD-012B remain unspecified or separately gated.
- The claim registry would prove atomic lifecycle state only; it would not prove
  authenticity, approval, device identity, plan correctness, safety, quality,
  or ledger integrity.
