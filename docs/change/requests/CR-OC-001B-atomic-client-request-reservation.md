# CR-OC-001B: Atomic Client-Request Reservation

## Status

- **Status:** Proposed / requirements proposal only.
- **Implementation authority:** None.
- **Approval gate:** Explicit human approval is required before any code, test,
  schema, runtime, or integration change.

This document records requirements only. It does not authorize implementation,
execution, file access, IPC, OpenClaw installation, or modification of any
current path.

## Why This Slice Is Next

CR-OC-001A produces trustworthy identities and digests. It does not reserve
anything. `classify_request_replay` compares two bindings it is *handed*; it
cannot discover that a prior binding exists, and nothing stops two callers from
obtaining authority for the same logical operation.

CR-OC-001B closes that gap and nothing else. It is deliberately sequenced
before the executor (CR-OC-001C) and the broker (CR-OC-001D), because an
executor that can be driven twice for one request is worse than no executor.

## Objective

Provide one durable, atomic binding:

```text
client_request_id -> request_digest -> broker_connection_id -> capability_id
```

such that:

1. Exactly one reservation exists per `client_request_id`.
2. At most one capability is ever bound to that reservation.
3. A request ID is never rebound, reassigned, released, or expired.
4. An identical retry recovers the existing binding rather than creating a
   second one.
5. Any mismatch fails closed.
6. Uncertainty never produces duplicate authority.

The governing principle is inherited from CR-YK-002: **a crash burns the
authorization rather than risking duplicate execution.**

## The Decisions, Answered Exactly

### 1. Reservation happens before capability issuance

Reserve first, then issue, then bind.

```text
reserve(client_request_id, request_digest, broker_connection_id)
    -> issue capability
    -> bind capability_id into the existing reservation
```

The alternative — issue first, reserve second — is rejected. A crash between
those steps would leave an issued capability with no reservation, which is
unattributable authority: the capability exists and nothing records which
client request owns it. Reserving first inverts the failure into the safe
direction, leaving a reservation with no capability, which is inert.

### 2. The reserve/bind window is real and must not be hidden

`capability_id` cannot be known at reservation time, so the binding is a second
write. Capability issuance appends to the JSONL ledger while the reservation
lives in SQLite, so **no single transaction spans both**. A crash between
issuance and binding is therefore possible and must be specified rather than
wished away.

Rule: such a reservation is **burned**. It cannot be advanced, and no second
capability may be issued against it. A retry carrying the same digest does not
resume it; it fails closed with a distinct reason. Recovery requires a new
human authorization and a **new `client_request_id`**.

This intentionally destroys one authorization to avoid ever issuing two.

### 3. Claiming must be gated on the reservation

An issued-but-unbound capability must be unclaimable. CR-YK-002's claim path
checks `scope_digest` and lifecycle state; it knows nothing about reservations,
and **CR-OC-001B must not modify it**.

The gate therefore lives in a new mediating function that verifies the
reservation is in `authorized` state with a matching `capability_id` *before*
delegating to the existing claim API. `triage_core/authz.py` and
`triage_core/capability_claims.py` remain unmodified.

### 4. One-to-one binding is enforced by the schema, not the caller

Both directions, in SQLite, not in Python:

```text
client_request_id  PRIMARY KEY
capability_id      UNIQUE where non-null
```

The CR-YK-002 precedent is binding here: a schema that documents an invariant
it does not enforce is a false claim. Direct-SQL tests must prove both
constraints, exactly as the v2 claim-store lifecycle tests do.

### 5. Retry semantics

| Incoming | Result |
|---|---|
| No record for this `client_request_id` | reserve it; `new_request` |
| Same ID, same digest, reservation `authorized` | return the existing binding |
| Same ID, same digest, reservation `reserved` (unbound) | fail closed — burned |
| Same ID, different digest | `request_id_reuse_mismatch` |
| Same ID, different `broker_connection_id` | `request_id_reuse_mismatch` |
| Same ID, terminal reservation | return the recorded terminal outcome |

### 6. Connection binding must be asserted independently

Because CR-OC-001A places `broker_connection_id` inside
`triagecore.mediated_client_request.v1`, a different connection already yields a
different `request_digest`. The connection check is therefore **subsumed** by
the digest comparison today.

That is precisely why it must be tested on its own. If a future change removed
`broker_connection_id` from the request-digest object, a test that only compares
digests would keep passing while cross-connection reuse silently became legal.
This is CR-OC-001A mutant M2 restated at the reservation layer, and it needs its
own designated killer.

### 7. Concurrency

`BEGIN IMMEDIATE` before any decision is read, independent connections per
consumer, bounded `busy_timeout`, never an unbounded wait — the same discipline
CR-YK-002 established. Two threads reserving the same new request must produce
exactly one insert, proven with real threads over independent connections, not
monkeypatched interleaving.

### 8. Store failure is not absence

`reservation_not_found` means the store was read successfully and no row
exists. A locked, corrupt, or unsupported-schema store never reports absence.

This carries the CR-YK-002 terminal-reason correction forward **before** the
defect can be written, rather than after. The distinction matters because a
caller told "no reservation exists" may reasonably create one; a caller told
"the store is unavailable" must not.

### 9. Nothing is deleted, reassigned, or expired

Reservations are permanent. No public API deletes one, and rows must be
undeletable at the schema level.

**Capability expiry must not free the request ID.** CR-YK-002 capabilities
expire; if an expired capability released its reservation, expiry would become a
reuse channel — a caller could simply wait it out and re-reserve the same
`client_request_id`. An expired capability's reservation stays bound forever,
and recovery requires a new client request ID.

### 10. Persisted metadata

Only:

```text
client_request_id
request_digest
broker_connection_id
capability_id          (null until bound)
task_id
state
reserved_at
bound_at
terminal_at
terminal_outcome
```

Never: `proposed_bytes` in any form, prompt or model text, tool arguments,
credentials, file contents, or free-text reasons. The row must pass the
existing persistent privacy invariant before it is treated as evidence-safe.

## State Model

```text
reserved -> authorized -> claimed -> completed
                                  \-> failed
reserved -> denied
```

- `reserved` carries no `capability_id`.
- `authorized` carries exactly one, and it never changes.
- Terminal states are absorbing.
- No transition returns a reservation to `reserved`.
- A `reserved` row that is retried is burned, not resumed.

Legal transitions must be enforced by a schema trigger and row shape bound to
state by a table-level `CHECK`, following the v2 claim-store pattern rather than
repeating its v1 mistake.

## Cross-Object Binding

CR-OC-001A shipped with a transplant defect: a plan linkage could be assembled
from one effect and an unrelated request, and a capability bundle could pair one
effect's `scope_digest` with another effect's `plan_body_digest`. Each digest
was individually valid. Both were caught only in review.

**Valid component digests are not evidence that the components belong
together.** CR-OC-001B inherits that lesson as a requirement, not a hope.

Binding a capability into a reservation must verify, before the write, that the
effect, request, and linkage describe one transition — reusing CR-OC-001A's
`assert_linkage_binds` rather than re-deriving the check — and that the
reservation's own `request_digest` and `broker_connection_id` match the request
being bound.

## Closed Reason Vocabulary

```text
ok
reservation_not_found          store read successfully, no row
request_id_reuse_mismatch      same id, different digest or connection
reservation_burned             unbound reservation retried after a crash window
reservation_already_bound      a different capability is already bound
capability_already_reserved    that capability is bound to another request
reservation_binding_mismatch   effect/request/linkage do not describe one transition
reservation_store_busy
reservation_store_unavailable
reservation_evidence_write_failed
```

Each is reserved narrowly. Conditions this slice cannot observe — path safety,
broker authenticity, execution outcomes — stay absent. A code naming a
condition the component cannot detect is a false capability claim in vocabulary
form.

## Required Tests

1. Two threads reserve the same new request simultaneously; exactly one creates
   it, using real threads over independent SQLite connections.
2. Same request ID and same digest returns the existing reservation.
3. Same request ID with a different digest fails as reuse mismatch.
4. Same request and digest on a different broker connection fails — asserted
   independently of the digest comparison.
5. One capability cannot bind to two client request IDs.
6. One client request ID cannot bind to two capabilities.
7. Store locked, corrupt, and unsupported-schema each report their own
   condition, never `reservation_not_found`.
8. A crash after reservation but before capability evidence cannot produce a
   second capability; the reservation is burned and a same-digest retry fails
   closed.
9. Individually valid request, reservation, and capability records from
   different operations cannot be combined.
10. Direct-SQL tests prove the schema itself enforces both uniqueness
    directions, the legal-transition whitelist, row shape per state, and
    undeletability — not the Python layer.
11. An expired capability does not release its reservation.
12. The persisted row passes the persistent privacy invariant.

## Mutants

Each must be demonstrated **failing** against its defective version, per the
standing acceptance bar. Controls that pass against both intended and mutated
versions are identified as controls, not counted as evidence.

| Mutant | Must be killed by |
|---|---|
| Remove the `client_request_id` uniqueness constraint | concurrent-reserve test |
| Remove the `capability_id` uniqueness constraint | one-capability-two-requests test |
| Drop `request_digest` from the reuse comparison | different-digest test |
| Drop `broker_connection_id` from the reuse comparison | independent connection test |
| Allow a burned reservation to be resumed | crash-window test |
| Allow rebinding a second capability | already-bound test |
| Report store failure as `reservation_not_found` | store-condition tests |
| Skip the effect/request/linkage verification before binding | transplant test |
| Release a reservation on capability expiry | expiry test |

## Explicitly Out of Scope

- file reads or writes, path resolution, atomic replacement;
- named pipes, DACLs, broker processes, or any IPC;
- OpenClaw configuration, tool registration, or schema capture;
- `tc` CLI surfaces, `tc run` integration, `--confirmed-plan`;
- modification of `triage_core/authz.py`, `triage_core/capability_claims.py`,
  or `triage_core/task_ledger.py`;
- any runtime module importing the reservation store;
- CR-OC-001C, CR-OC-001D, or CR-OC-001E work of any kind.

## Candidate Future Implementation Allowlist

Subject to separate explicit human approval:

- `docs/change/requests/CR-OC-001B-atomic-client-request-reservation.md`
- `triage_core/request_reservation.py`
- `tests/test_request_reservation.py`
- `docs/current_backlog.md`
- `docs/change/change_log.md`

This candidate list is not implementation authority.

## Acceptance Claim

A completed CR-OC-001B may support only:

> TriageCore can atomically reserve a client request, bind at most one
> capability to it, recover an identical retry, and fail closed on any mismatch,
> with the reservation lifecycle enforced by the database rather than by the
> caller.

It may **not** be used to support:

- that the broker connection is authenticated;
- that the client request originated where it claims;
- that any file was read, written, or protected;
- that OpenClaw is constrained;
- that execution occurred or was safe;
- that duplicate execution is impossible outside this store's local scope.

## Limitations and Uncertainty

- This proposal has implemented and exercised nothing.
- The reserve/issue/bind sequence spans two stores with no shared transaction.
  The window is bounded by burning, not eliminated.
- Local SQLite semantics establish nothing about distributed locking; local
  filesystems only.
- A burned reservation is deliberately unrecoverable and may leave an evidence
  gap, exactly as CR-YK-002 accepts for capabilities.
- Reserving a request proves nothing about who sent it. That remains
  CR-OC-001D's problem, and merging this slice must not be read as progress on
  it.

## Sequencing

```text
CR-OC-001A  pure effect contract                    complete and merged
CR-OC-001B  atomic request reservation              this proposal
CR-OC-001C  constrained replacement executor        unauthorized
CR-OC-001D  privilege-separated broker and pipe     unauthorized
CR-OC-001E  exclusive OpenClaw tool and schema      unauthorized
```

Each slice retains its own requirements approval, implementation approval, merge
approval, and closeout. There is no combined "finish the OpenClaw integration"
authorization, and this document grants none.
