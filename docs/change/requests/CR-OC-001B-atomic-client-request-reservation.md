# CR-OC-001B: Atomic Client-Request Reservation

## Status

- **Status:** Requirements approved and merged through PR #122 as `f22fee1`;
  bounded implementation authorized on 2026-07-28 and complete on branch; **not
  merged**.
- **Implementation authority:** Limited to the five-path allowlist recorded
  below — the reservation module, its tests, and this documentation.
- **Merge authority:** None.
- **Still unauthorized:** CR-OC-001C through CR-OC-001E, runtime integration,
  CLI or `tc run` surfaces, file access, IPC, named pipes, OpenClaw
  configuration, new dependencies, and any runtime module importing
  `triage_core.request_reservation`.
- **Approval gate:** Explicit human approval remains required before any change
  beyond that allowlist.

This document records the requirements contract and the bounded implementation
written against it. It authorizes no execution, file access, IPC, or OpenClaw
work, and does not claim the implementation has been reviewed or merged.

## Why This Slice Is Next

CR-OC-001A produces deterministic, syntactically validated, integrity-bound
representations and digests. It authenticates nothing — not the broker
connection, not the declared invocation context, not file-identifier
provenance — and it reserves nothing. `classify_request_replay` compares two
bindings it is *handed*; it cannot discover that a prior binding exists, and
nothing stops two callers from obtaining authority for the same logical
operation.

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
reserve -> begin issuance -> issue -> bind
```

In full:

```text
reserve(client_request_id, request_digest, broker_connection_id)
    -> begin_issuance      one-shot, owner-gated
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

Rule: such a reservation becomes permanently inert. It cannot be advanced by
anyone, and no second capability may be issued against it. Recovery requires a
new human authorization and a **new `client_request_id`**.

This intentionally destroys one authorization to avoid ever issuing two.

### 2a. An unbound reservation must have an owner

The rule above is not implementable as stated without a way to tell the
invocation that *created* the reservation from any other caller presenting the
same `client_request_id`. Without one, both available behaviours are wrong:

- a retry that marks the row inert **sabotages a legitimate in-flight issuer**
  that is still between reserve and bind;
- a retry that leaves the row alone permits a **later invocation to perform the
  bind the crashed invocation was supposed to own**.

A component observing an unbound row cannot distinguish a crashed invocation
from a live one. It never can — that is a property of the situation, not a gap
in the design.

The reservation therefore stores a durable **verifier** for an ephemeral
ownership token, mirroring CR-YK-002's `execution_attempt_id`:

```text
reservation_attempt_token    returned once, never persisted
reservation_attempt_digest   persisted, sha256(token)
```

- The insert winner receives the **raw token** once, at reservation time.
- Advancing the row — beginning issuance, binding, or denying — requires
  presenting the raw token, which is hashed internally and compared against the
  stored digest.
- Denying requires it too, so a stranger cannot deny someone else's live
  reservation. That would be the same sabotage vector.
- A retry may **inspect** the row. It never receives the token and never
  advances the row.

After a crash the raw token is lost, so the reservation is inert by
construction rather than by a policy decision taken on incomplete information.
The verifier survives in the database and grants nothing on its own.

#### The token is authority-bearing, not descriptive metadata

Possession of the raw `reservation_attempt_token` *is* the right to advance the
row. It
must therefore be specified with the care given to a credential rather than to
a label:

```text
Generation
    Opaque and internally generated, with at least 122 bits of OS-backed
    randomness (UUIDv4 or equivalent). Never caller-selected, never derived
    from client_request_id, request_digest, or any other request field.

Disclosure
    The raw token is returned only in the successful new-reservation result.
    Lookup, retry, denial, error paths, logging, and the persistent projection
    never disclose it. A retry learns that a reservation exists, never how to
    advance it.

Storage
    Only sha256(token) is persisted, as reservation_attempt_digest. The raw
    token never enters SQLite, projections, evidence, logs, or errors. The
    stored digest is never accepted as a substitute token.

Enforcement
    begin_issuance, bind, and deny each accept the raw token, hash it, and
    perform one atomic conditional write whose predicate includes
    client_request_id, the required current state, and the exact
    reservation_attempt_digest, requiring exactly one changed row. A prior read
    followed by an unconditional update is non-conforming: two callers could
    each read the row, each compare successfully, and both proceed.
```

Storing only the digest matters because the token is a bearer credential. If
the raw value sat in the database, **anyone who could read the reservation
store would obtain the right to bind or deny any live row** — the credential
would be as widely held as the file. Hashing at rest keeps the earlier claim
("credentials are never persisted") true rather than contradicted, and after a
crash the raw token is gone while database disclosure alone grants nothing.

The conditional-write requirement is the same discipline test 1 applies to the
insert, extended to all three guarded transitions:

```text
reserved -> issuing
reserved -> denied
issuing -> authorized
```

Non-disclosure is exercised by tests 9 through 11, which fail if a retry can
obtain or guess the token.

If the token were caller-supplied, predictable, or readable from a lookup, an
observer of an in-flight reservation could bind or deny it — reintroducing
exactly the sabotage and orphan-hijack failures this section exists to close.

**Naming follows observability.** A code such as `reservation_burned` would
assert that a crash occurred. No caller can know that — it may be looking at a
live operation. The observable condition is that the row exists and is
unbound, so the code is `reservation_unbound`. The policy is unchanged:
non-owner callers cannot resume it. Only the claim shrinks to what is true.

### 2b. The right to issue must be consumed before issuing

Owning the token is necessary but not sufficient. Two invocations holding the
**same valid token** could each call `issue_capability` and only then race to
bind. The uniqueness constraint permits just one binding — but by then the
second capability already exists.

That is not a harmless orphan. `issue_capability` mints the capability ID
internally and appends the issuance to the ledger immediately, and the
unchanged public claim path performs no reservation lookup. The unbound second
capability therefore **remains claimable through direct
`claim_capability`**, exactly as the narrowed gating boundary in decision 3
honestly admits. A one-to-one constraint on binding does not bound the number
of capabilities that exist.

The right to issue must therefore be consumed *before* the issuance call, not
reconciled after it:

```text
begin_issuance(client_request_id, reservation_attempt_token)
    reserved -> issuing        one shot, atomic, owner-gated
```

Only the winner of that transition may call `issue_capability`. Once a row is
`issuing`:

- no second issuance may begin;
- it never returns to `reserved`;
- denial is no longer permitted — the decision has already been made;
- a crash leaves the row permanently inert, as before;
- binding transitions `issuing -> authorized`, requiring the same token and the
  exact `capability_id`.

This is still reservation coordination. It records who holds the one-shot right
to obtain a capability for a client request, and it duplicates nothing in
CR-YK-002's claim lifecycle.

### 3. Reservation gating applies to the mediated entry point only

A tempting formulation is that an issued-but-unbound capability "must be
unclaimable." That is not achievable under this slice's own constraints, and
stating it would be a false claim.

`issue_capability` mints the capability ID internally and appends the issuance
directly to the JSONL ledger. `claim_capability` then locates that ledger
issuance and delegates straight to the CR-YK-002 claim store, performing no
reservation lookup. A new wrapper can refuse to delegate; it **cannot make the
existing public API incapable of claiming** the capability.

The honest boundary for this slice:

> An issued-but-unbound capability is rejected by the CR-OC mediated claim
> entry point. **CR-OC-001B does not alter or constrain direct callers of
> `triage_core.authz.claim_capability`.**

Every claim about gating is therefore scoped to the mediated reservation API,
never to TriageCore globally.

Making reservation authorization an enforced prerequisite for *all* claiming
would require changing `authz.py` or the claim store. That is a materially
larger authority change, it is not in this slice's candidate allowlist, and it
must not be smuggled in under this one. If it is wanted, it needs its own
proposal and its own approval.

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
| Same ID, same digest, reservation `reserved`, owner token | the owner may begin issuance |
| Same ID, same digest, reservation `reserved`, non-owner | `reservation_unbound` |
| Same ID, same digest, reservation `issuing`, any caller | `reservation_already_issuing` |
| Same ID, different digest | `request_id_reuse_mismatch` |
| Same ID, different `broker_connection_id` | `request_id_reuse_mismatch` |
| Same ID, reservation `denied` | return the recorded denial |

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
reservation_attempt_digest    sha256 of the token; never the raw token
request_digest
broker_connection_id
capability_id                 (null until bound)
task_id
state
reserved_at
issuing_at
bound_at
denied_at
```

Only `reservation_attempt_digest` is persisted. The raw token is
authority-bearing, so it never enters the database, any projection, evidence
record, log line, or error payload — disclosing it would hand the right to
advance the row to whoever reads the output, and storing it would hand that
right to whoever can read the file.

Never: `proposed_bytes` in any form, prompt or model text, tool arguments,
credentials, file contents, or free-text reasons. The row must pass the
existing persistent privacy invariant before it is treated as evidence-safe.

## State Model

```text
reserved -> issuing -> authorized
reserved -> denied
```

That is the whole lifecycle. It stops at `authorized` deliberately.

### Why it stops there

Continuing `authorized -> claimed -> completed | failed` with terminal fields
would create a **second lifecycle authority** mirroring CR-YK-002's claim
store, with no transaction spanning the two stores and no specified ordering
for: claim-store commit versus reservation update, a crash between them,
terminal commit versus reservation terminal update, or reconciliation when one
store says `authorized` and the other says `claimed`.

Answering all of that would mean a full two-store ordering and
crash-reconciliation matrix — unnecessary complexity for the stated acceptance
claim, and a second place for the truth about a claim to live.

**Claim and execution lifecycle stay exclusively in CR-YK-002.** This store
answers one question: which client request owns which capability.

### Rules

- `reserved` carries no `capability_id`, no `issuing_at`, and no `bound_at`.
- `issuing` records that the one-shot right to obtain a capability has been
  consumed. It still carries no `capability_id`.
- `authorized` carries exactly one `capability_id`, and it never changes.
- `denied` carries no `capability_id`; it records that authorization was
  refused, which is distinct from an orphaned `reserved` row and is why the
  state exists at all. It is not a mirror of any claim-store state.
- `denied` is reachable only from `reserved`. Once issuance has begun the
  decision is made, so `issuing -> denied` is illegal.
- `authorized` and `denied` are absorbing.
- No transition returns a reservation to `reserved` or to `issuing`.
- Every transition out of `reserved` or `issuing` requires the owner's raw
  `reservation_attempt_token`.

Legal transitions must be enforced by a schema trigger, and row shape bound to
state by a table-level `CHECK`, following the v2 claim-store pattern rather than
repeating its v1 mistake of documenting an invariant the schema did not
enforce.

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
reservation_not_found            store read successfully, no row
request_id_reuse_mismatch        same id, different digest or connection
reservation_unbound              row exists, unbound, caller is not the owner
reservation_attempt_mismatch     token does not match the stored digest
reservation_already_issuing      the one-shot issuance right is already consumed
reservation_issuance_not_begun   bind attempted while the row is still reserved
reservation_already_bound        a different capability is already bound
capability_already_reserved      that capability is bound to another request
reservation_binding_mismatch     effect/request/linkage are not one transition
reservation_denied               authorization was refused for this request
reservation_store_busy
reservation_store_unavailable
```

`reservation_evidence_write_failed` is deliberately absent. Such a code would
have to name which evidence write it refers to, its ordering relative to the
SQLite commit, and whether the committed reservation stays usable afterwards.
**The SQLite row is itself the durable evidence for this slice**; no separate
ledger event is specified, so no such failure arises. A
code for a condition that cannot occur is as dishonest as one that names the
wrong condition.

Each remaining code is reserved narrowly. Conditions this slice cannot observe
— path safety, broker authenticity, execution outcomes, claim lifecycle — stay
absent. A code naming a
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
   second capability; the row stays unbound and a non-owner same-digest retry
   fails closed as `reservation_unbound`.
9. A concurrent retry cannot sabotage the insert winner: the loser receives no
   attempt ID, cannot deny the row, and the winner can still bind afterwards.
10. A later invocation cannot bind an orphaned row.
11. A wrong `reservation_attempt_token` cannot begin issuance, bind, or deny.
12. Individually valid request, reservation, and capability records from
    different operations cannot be combined.
13. **Direct-SQL duplicate-insert tests** prove the schema itself rejects a
    second row for the same `client_request_id` and a second binding of the same
    `capability_id`. Separate direct-SQL tests prove the legal-transition
    whitelist, row shape per state, and undeletability. These must bypass the
    Python layer entirely, or removing a constraint would leave the suite green
    on Python-side checks alone.
14. An expired capability does not release its reservation.
15. The persisted row passes the persistent privacy invariant, **and the raw
    `reservation_attempt_token` appears nowhere in the database, any
    projection, evidence record, log line, or error payload, while
    `reservation_attempt_digest` is present and equals `sha256(token)`.**
16. **Transition race**, real threads over independent connections, covering at
    minimum:
    - `begin_issuance` versus `begin_issuance` — exactly one wins;
    - `begin_issuance` versus `deny` — exactly one transition applies;
    - bind capability A versus bind capability B from `issuing` — exactly one
      capability becomes bound.

    Test 1 proves the *insert* is atomic. It proves nothing about later
    transitions, which is why this is separate rather than folded into it.

## Mutants

Each must be demonstrated **failing** against its defective version, per the
standing acceptance bar. Controls that pass against both intended and mutated
versions are identified as controls, not counted as evidence.

| Mutant | Must be killed by |
|---|---|
| Remove the `client_request_id` uniqueness constraint | **direct-SQL duplicate-insert test** (13) |
| Remove the `capability_id` uniqueness constraint | **direct-SQL duplicate-binding test** (13) |
| Drop `request_digest` from the reuse comparison | different-digest test (3) |
| Drop `broker_connection_id` from the reuse comparison | independent connection test (4) |
| Remove the token check from a transition | orphaned-row and wrong-token tests (10, 11) |
| Allow a non-owner to deny a `reserved` row | sabotage test (9) |
| Allow rebinding a second capability | already-bound test (6) |
| Report store failure as `reservation_not_found` | store-condition tests (7) |
| Skip the effect/request/linkage verification before binding | transplant test (12) |
| Release a reservation on capability expiry | expiry test (14) |
| Skip or weaken the one-shot `reserved -> issuing` gate | transition-race test (16) |
| Persist the raw attempt token instead of only its digest | token-secrecy test (15) |

The two uniqueness mutants point at direct-SQL tests deliberately. A
concurrency or public-API test can stay green after the schema constraint is
removed, because the Python layer still refuses the duplicate — which would make
the mutant look killed while the invariant the schema claims to enforce is gone.
That is the exact CR-YK-002 v1 failure, and pointing the mutant at the wrong
test would reproduce it in the evidence rather than in the code.

## Implementation Record

Implemented on branch `cr-oc-001b-request-reservation-implementation`, open for
review, **not merged**. Two code paths, both new:

- `triage_core/request_reservation.py` — the versioned SQLite store, closed
  result objects and the exact merged reason vocabulary, atomic
  `reserved -> issuing`, `reserved -> denied`, and `issuing -> authorized`
  transitions, idempotent recovery of an authorized binding, the mediated
  issuance and claim entry points, and a projection carrying neither the raw
  token nor its verifier.
- `tests/test_request_reservation.py` — 63 tests covering all 16 named
  obligations, the operation x state truth table, and the request-aware gate.

The database enforces the invariants, not the Python layer: `client_request_id`
primary key, a partial unique index on `capability_id`, a table-level `CHECK`
binding row shape to state, and triggers for immutable identity, the legal
transition whitelist, bound-capability immutability, and undeletability. Public
prechecks exist for clearer outcomes and are never the enforcement.

### Mutant evidence, as required and as exercised

The requirements above name **twelve** mutants and that contract is unchanged.
Implementation review surfaced three further defective variants worth
exercising, recorded separately rather than backfilled into the requirements:

```text
12 required mutants
+ 4 review-found defective variants
= 16 exercised variants
```

The four additions are `M8b` (lookup failure reported as absence on the
mediated claim path), `M9b` (reservation-to-request verification removed from
the issuance gate), `M13` (the state classifier collapsed to one generic code),
and `M14` (any insert integrity failure reported as a lost race). All sixteen
were demonstrated failing against their defective versions with the module hash
pristine after each cycle.

### Review-round corrections

Five findings, each confirmed behaviourally against the pre-fix head before
being changed:

- **The reservation was not bound to the trio being issued.** `begin_issuance`
  checked only id, state, and token, so a valid token for reservation A could
  advance A while a capability was issued for a coherent request B sharing the
  client request id, and bound into A's row. The gate now carries
  `request_digest` and `broker_connection_id` in its atomic predicate; `bind` is
  protected transitively, since only the request-aware gate produces `issuing`.
- **Mediated claiming reported store failure as absence.** A decision-bearing
  `lookup` now distinguishes not-found from busy and unavailable, and
  `projection` raises rather than flattening an operational failure into `None`.
- **One generic wrong-state code per operation.** A state-aware classifier
  replaces it, ordered request-mismatch, then state, then token. Binding the
  same capability twice now recovers the existing binding as `ok` rather than
  reporting that issuance never began.
- **Obligation 15 tested the projection, not the persisted row.** The exact row
  payload is now privacy-checked before insertion, and a test runs the invariant
  over every persisted column.
- **The concurrency helpers could lose a worker.** They now capture worker
  exceptions, join with a bounded timeout, and assert the result count before
  any outcome assertion, so a crashed worker fails the test rather than
  disappearing from the evidence.

A third round narrowed two remaining reason-code claims:

- **`reserve` misclassified arbitrary integrity failures.** Every insert
  `IntegrityError` reported `reservation_unbound`, asserting that a valid
  reservation exists and merely lacks this caller's ownership. Because
  `BEGIN IMMEDIATE` serialises conforming writers, a loser sees the winner's
  row during its `SELECT` rather than reaching a duplicate insert, so an error
  there can equally be an incompatible trigger or an unexpected constraint on a
  same-version database. Only a `client_request_id` uniqueness conflict now
  re-reads and classifies the actual row; anything else reports
  `reservation_store_unavailable`.
- **A locked-store test accepted either busy or unavailable.** It now requires
  exactly `reservation_store_busy`, which is what proves the busy classifier
  survives through the mediated boundary.

### Two findings from the first evidence pass, recorded rather than smoothed over

**A test was passing for the wrong reason.** The connection-mismatch test
compared a reservation against a request built on a different broker
connection — but `broker_connection_id` is inside the request digest, so the
digests already differed and the test passed with the connection comparison
deleted. Mutant M4 survived and exposed it. The check is now observed on a row
seeded by direct SQL whose digest *matches* while the connection differs, which
the public builder cannot produce. The original test is kept as the realistic
reconnect path.

This is exactly the trap the contract predicted, and predicting it was not
enough to avoid it. Only the mutant caught it.

**Two mutants were killing for the wrong reason.** Removing a SQL statement by
text left dangling quotes, so M2 and M7 failed at collection with a syntax
error rather than a missing constraint. The harness now removes whole tuple
elements located at runtime, and treats a pytest exit code of 4 as *not* a
clean kill. Both now fail with `DID NOT RAISE IntegrityError`, which is the
constraint actually being absent.
## Explicitly Out of Scope

- file reads or writes, path resolution, atomic replacement;
- named pipes, DACLs, broker processes, or any IPC;
- OpenClaw configuration, tool registration, or schema capture;
- `tc` CLI surfaces, `tc run` integration, `--confirmed-plan`;
- modification of `triage_core/authz.py`, `triage_core/capability_claims.py`,
  or `triage_core/task_ledger.py`;
- any runtime module importing the reservation store;
- CR-OC-001C, CR-OC-001D, or CR-OC-001E work of any kind.

## Implementation Allowlist

Subject to separate explicit human approval:

- `docs/change/requests/CR-OC-001B-atomic-client-request-reservation.md`
- `triage_core/request_reservation.py`
- `tests/test_request_reservation.py`
- `docs/current_backlog.md`
- `docs/change/change_log.md`

Bounded implementation authority was granted on 2026-07-28 and has been
exercised within exactly this list. It confers no merge authority, and it
extends to nothing outside these five paths.

## Acceptance Claim

A completed CR-OC-001B may support only:

> Through the CR-OC mediated reservation API, TriageCore can atomically reserve
> a client request, bind at most one capability to it, recover an identical
> retry by its owner, and fail closed on any mismatch, with the reservation
> lifecycle enforced by the database rather than by the caller.

The scoping to the mediated API is load-bearing, not hedging. It may **not** be
used to support:

- that direct callers of `triage_core.authz.claim_capability` are constrained
  in any way;
- that an issued-but-unbound capability is unclaimable in general;
- that the broker connection is authenticated;
- that the client request originated where it claims;
- that any file was read, written, or protected;
- that OpenClaw is constrained;
- that execution occurred or was safe;
- that duplicate execution is impossible outside this store's local scope.

## Limitations and Uncertainty

- The bounded implementation exists on branch and is unmerged. Everything
  below remains true of it, and none of it is resolved by having written
  code.
- The reserve/issue/bind sequence spans two stores with no shared transaction.
  The window is bounded by burning, not eliminated.
- Local SQLite semantics establish nothing about distributed locking; local
  filesystems only.
- An unbound reservation whose owner is gone is deliberately unrecoverable and
  may leave an evidence gap, exactly as CR-YK-002 accepts for capabilities. No
  component can tell that case from a live in-flight one, which is why the
  raw attempt token decides rather than a heuristic.
- Reservation gating binds only the mediated entry point. Direct use of the
  existing capability API is unchanged, and this slice makes no claim about it.
- The one-shot gate bounds how many capabilities this store will *cause* to be
  issued for one client request. It cannot retract a capability that some other
  path issues, because issuance appends to the ledger outside this store's
  control.
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
