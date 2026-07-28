# CR-OC-001A: Mediated Single-File Effect Contract

## Status

- **Status:** Proposed / requirements proposal only.
- **Implementation authority:** None.
- **Approval gate:** Explicit human approval is required before any code, test,
  schema, runtime, or integration change.

This document records requirements only. It does not authorize implementation,
execution, IPC, persistence, file access, capability issuance, OpenClaw
installation, or modification of any current path.

## Scope

CR-OC-001A proposes a pure module that defines how one exact single-file
content transition is represented, validated, and bound to the identifiers that
a later mediated-execution stack will authenticate.

The proposed slice is limited to representation and binding. It performs no
authorization, no persistence, no IPC, and no mutation. It reads no file and
writes no file.

## Objective

Provide a deterministic, privacy-safe contract in which:

1. A replacement is described by a syntactically validated file identifier, not
   a caller-supplied path.
2. The intended transition is pinned to an exact pre-content digest and an
   exact post-content digest over exact bytes.
3. Client-declared invocation context is structurally separated from the
   broker-connection identifier field.
4. Every bound field participates in a single canonical effect digest.
5. Replay semantics are defined in terms of a unique client request on a
   specific connection, not merely a capability.
6. The persistent projection carries metadata only and never file content.

## What This Slice Can and Cannot Establish

This distinction is binding and belongs in the module docstring, not only here.

A completed CR-OC-001A may support exactly this claim:

> TriageCore can deterministically represent a single-file content-replacement
> effect and bind it to exact pre- and post-content digests, a unique client
> request, a client-declared invocation context, and a distinct
> broker-connection identifier field whose provenance and connection binding
> are not established by this slice, while producing a privacy-safe persistent
> projection.

It may not be used to support any of:

- that OpenClaw is contained;
- that the invocation context is authenticated;
- that the broker-connection identifier was broker-generated;
- that the target file identifier came from a trusted allowlist;
- that replay is prevented in practice;
- that paths are safe;
- that a capability was claimed;
- that any file was actually changed;
- that OS privilege separation exists.

### Provenance is asserted, never established

Three fields carry provenance that this slice validates *syntactically* and
cannot validate *substantively*. The positive claim must match the limitation
in every place both appear.

| Field | This slice establishes | This slice cannot establish |
|---|---|---|
| `broker_connection_id` | it is a distinct field participating in the effect digest | that it was broker-generated or bound to any connection |
| `declared_invocation_context` | its canonical shape and digest | that any declared value is true |
| `target_file_id` | its syntax and descriptor shape | that it came from the trusted allowlist |

**A pure module cannot tell a broker-minted identifier from a forged one**, and
digesting a value makes it tamper-evident after the fact without making it true
when first supplied.

The terms **broker-generated** and **broker-authenticated** are reserved for
CR-OC-001D and must not appear as properties of this slice. Wherever this
document describes what CR-OC-001A achieves, the correct phrasing is *a
distinct broker-connection identifier field whose provenance and connection
binding are not established here*. Any wording implying otherwise is false and
must be rejected in review.

## Allowlisted File Descriptor

The tool-facing identifier is `target_file_id`. A caller-supplied path is never
accepted where a file ID is required.

```text
target_file_id
canonical_relpath
encoding = "utf-8"
maximum_size_bytes
```

The descriptor is produced by a later trusted allowlist-enumeration phase.
CR-OC-001A defines and validates only its canonical representation and syntax.
It does not enumerate, resolve, verify that the described file exists, or
establish that `target_file_id` actually originated from the allowlist.

### The canonical_relpath rule, stated precisely

`canonical_relpath` **is** part of the authorized effect and therefore does
affect `scope_digest`. It is integrity-bound so that evidence stays consistent
and a later executor cannot silently disagree about which file was meant.

What it must never be is a **resolution channel**:

> `canonical_relpath` is integrity-bound for evidence consistency but must
> never be used to select, resolve, or open the target file. Resolution is
> exclusively through `target_file_id`.

A proposal presenting a path where a file ID belongs fails closed as
`invalid_target_file_id`. A later slice that opens a file by joining
`canonical_relpath` onto a root, rather than resolving `target_file_id` through
the allowlist, violates this contract even if the resulting path is identical.

## Replacement Proposal

```text
task_id
client_request_id
target_file_id
expected_pre_digest
proposed_bytes          # transient; hashed in memory, never retained
expected_post_digest
declared_invocation_context
```

The contract must reject:

- malformed identifiers or digests;
- non-UTF-8 content;
- content exceeding `maximum_size_bytes`;
- a post-digest that does not match `proposed_bytes`;
- unknown operations;
- path-like values where only a file ID is permitted.

### How proposed_bytes are handled

`proposed_bytes` **are hashed transiently** to compute and verify:

```text
sha256(exact_proposed_bytes) == expected_post_digest
```

That verification necessarily digests the exact bytes; any claim that they are
"never digested" is false. What holds instead is a retention rule: the raw
bytes are never embedded in canonical JSON, the authorized-effect digest, the
request digest, the persistent projection, or durable evidence. They exist in
memory long enough to be verified and are then dropped.

Downstream digests therefore bind the content transitively through
`expected_post_digest`, which is why no later structure needs the bytes.

### Exact-byte treatment is binding

The byte sequence hashed is the byte sequence proposed. No transformation may
occur between receipt and hashing:

- UTF-8 validity is a **gate, not a normalization step** — invalid input is
  rejected, valid input is passed through unchanged;
- no Unicode normalization (NFC, NFD, NFKC, NFKD);
- no newline conversion in either direction;
- no BOM insertion or removal;
- `content_size_bytes` is the length of the original exact byte sequence, not
  of any decoded, re-encoded, or normalized form.

Without this, two conforming implementations could hash different post-content
from identical input and both claim compliance. A test must show that content
differing only by newline style, BOM presence, or Unicode normal form produces
different post-digests and is never silently reconciled.

`expected_pre_digest` always describes existing content. File creation is out
of scope, so there is no null or sentinel pre-state in this slice.

## Context Distinction

Two structurally separate values, never merged into one identity field:

```text
declared_context_digest = hash({
    runtime_id,
    runtime_version,
    openclaw_config_digest,
    agent_id,
    session_id,
    tool_name,
    client_request_id
})
```

These are **client-declared facts, not authenticated identity.** Every one of
them arrives from the untrusted side. The digest makes them tamper-evident
after the fact; it does not make them true.

```text
broker_connection_id
```

A distinct identifier field that CR-OC-001D will generate in the broker and
bind to an authenticated IPC connection. In this slice its provenance is
asserted by the caller, not established — see the provenance table above.

The two must remain distinct fields in the effect, in the projection, and in
the API. Collapsing them, or exposing any accessor that presents declared
context as authenticated identity, is a contract violation.

## Authorized Content Effect

```text
operation = "replace"
target_file_id
canonical_relpath
expected_pre_digest
expected_post_digest
content_size_bytes
declared_context_digest
broker_connection_id
client_request_id
```

The core claim is exactly:

> The exact authorized pre-content digest became the exact authorized
> post-content digest.

This is **not** a claim about exact filesystem state. Atomic replacement may
change modification and creation timestamps, file identity, and other
filesystem attributes. Those changes are permitted incidental metadata.

A later executor must separately preserve, and must be separately tested for:

```text
owner unchanged
DACL not broadened
file remains a regular file
file remains inside the repository workspace
```

CR-OC-001A does not check any of those. It only fixes the vocabulary so that a
later slice cannot quietly upgrade a content claim into a filesystem claim.

## Canonical Objects

Every digest above is taken over a versioned, closed-field object. Vague
phrasing such as "digest of the canonical linkage" is not implementable and is
replaced here with exact schemas.

### Shared rules

- **Canonical JSON** is the existing `canonical_json_bytes` form: sorted keys,
  `(",", ":")` separators, `ensure_ascii=True`, `allow_nan=False`, ASCII-encoded.
- **Domain separation follows the house pattern** established by
  `triage_core/governed_decision.py`: the domain is a field *inside* the
  canonicalized envelope, not a byte prefix. Each object carries a `schema`
  field holding its versioned discriminator, and that field is part of the
  digest input.
- **Closed field sets.** Every object rejects unknown fields. No object accepts
  free-form extension.
- **Optional values are forbidden, not omitted.** Every field listed is
  required and must be present and non-null. There is no implicit default, no
  omitted-key form, and no `null` sentinel. Two proposals that differ only in
  whether a key was omitted cannot exist, so they cannot digest differently.
- **Digests** retain `sha256:<64 lowercase hex>`.

### The five objects

```text
triagecore.mediated_file_descriptor.v1
    schema
    target_file_id
    canonical_relpath
    encoding                  # literal "utf-8"
    maximum_size_bytes

triagecore.mediated_declared_context.v1
    schema
    runtime_id
    runtime_version
    openclaw_config_digest
    agent_id
    session_id
    tool_name
    client_request_id
        -> declared_context_digest

triagecore.mediated_file_effect.v1
    schema
    operation                 # literal "replace"
    target_file_id
    canonical_relpath
    expected_pre_digest
    expected_post_digest
    content_size_bytes
    declared_context_digest
    broker_connection_id
    client_request_id
        -> effect_digest, used as scope_digest

triagecore.mediated_client_request.v1
    schema
    task_id
    client_request_id
    broker_connection_id
    target_file_id
    canonical_relpath
    expected_pre_digest
    expected_post_digest
    content_size_bytes
    declared_context_digest
        -> request_digest        # every proposal field except raw bytes

triagecore.mediated_plan_linkage.v1
    schema
    task_id
    decision_id
    client_request_id
    broker_connection_id
    effect_digest
    request_digest
        -> plan_body_digest
```

`triagecore.mediated_plan_linkage.v1` is what `plan_body_digest` digests. It
binds the governed decision to the exact effect and the exact request, so an
authorization cannot be transplanted onto a different effect, request, or
connection while keeping its decision identity.

### Cross-domain distinctness

Because `schema` participates in each digest, two objects with coincidentally
identical remaining fields still produce different digests. A test must prove
this rather than assume it: construct payloads that are field-for-field equal
across two schema domains and assert their digests differ. Without that check,
domain separation is an intention rather than a property.

## Existing Capability Mapping

The proposal maps onto the merged CR-YK-002 capability without changing
`AuthorizationRequest`, the capability schema, or any claim-store behavior.

```text
artifact_byte_digest = expected_post_digest
scope_digest         = effect_digest
                       (triagecore.mediated_file_effect.v1)
plan_body_digest     = linkage digest
                       (triagecore.mediated_plan_linkage.v1)
task_id              = existing ledger-envelope binding
```

The existing canonical JSON and digest utilities are reused unchanged. No new
capability schema is introduced. Digests retain the `sha256:<64 lowercase hex>`
contract.

### Connection binding runs through the whole sequence

`scope_digest` covers the whole authorized effect, which includes
`broker_connection_id`. CR-YK-002 binds `scope_digest` immutably at claim time
and rejects a mismatch as `scope_digest_mismatch`. **A capability is therefore
bound to one broker connection** and cannot be claimed across a reconnect.

`request_digest` must carry the same binding. If request identity omitted
`broker_connection_id`, the same `client_request_id` and `request_digest` could
recur unchanged after a reconnect while the effect and scope digest had
changed — and a reservation store would report an idempotent replay for
authority issued against a connection that no longer exists. That is why
`triagecore.mediated_client_request.v1` includes `broker_connection_id`.

**Consequence: a repeated `client_request_id` on a different connection is
`request_id_reuse_mismatch`, not an idempotent replay.**

The required ordering is therefore integrated, and reservation sits *after*
connection establishment rather than merely issuance:

```text
connection established
  -> broker_connection_id assigned
  -> proposal/effect canonicalized
  -> request_digest calculated
  -> client request reserved
  -> authorization/capability issued
  -> capability claimed
  -> effect executed
```

Every step from `request_digest` onward is downstream of the connection. This
constrains CR-OC-001B and CR-OC-001D and should not be discovered during their
implementation.

## Request Replay Contract

`request_digest` is the digest of `triagecore.mediated_client_request.v1` —
every proposal field except raw `proposed_bytes`, and including
`broker_connection_id`, `expected_post_digest`, and `content_size_bytes`.

```text
reserved -> authorized -> claimed -> completed
                                  \-> failed
reserved -> denied
```

### A pure classification function, not a store

A stateless module cannot both own `request_id_reuse_mismatch` and store
nothing — it has no way to discover that a prior request exists. The resolution
is to split comparison from storage: the comparison is pure and lives here, the
storage is external and lives in CR-OC-001B.

```text
classify_request_replay(
    existing_client_request_id,
    existing_request_digest,
    incoming_client_request_id,
    incoming_request_digest,
) -> new_request
   | idempotent_replay
   | request_id_reuse_mismatch
```

The function receives both bindings as arguments. It performs no lookup, no
persistence, and no I/O. CR-OC-001B supplies the stored values atomically and
owns every decision about what to do with the classification. This keeps the
reason code in A — where the comparison logic lives and can be tested — while
leaving enforcement entirely in B.

Required rules:

- Same `client_request_id`, same `request_digest` → `idempotent_replay`; the
  existing recorded outcome may be returned.
- Same `client_request_id`, different digest → `request_id_reuse_mismatch`.
  Because the digest includes `broker_connection_id`, this covers a repeat on a
  different connection.
- No existing binding → `new_request`.
- An interrupted reservation is never silently treated as new. Representing
  that is CR-OC-001B's obligation, since it requires durable state.

### A requirement CR-OC-001A cannot represent

The rule that *one capability must not be reachable through two distinct client
requests* is **not representable in any structure defined here**, because
`capability_id` appears nowhere in this slice's replay model — capability
issuance is out of scope.

It is therefore recorded as a CR-OC-001B obligation: **the reservation row must
bind the assigned `capability_id` one-to-one with `client_request_id`**, with a
uniqueness constraint in both directions. Stating the rule in A without the
field to express it would be a contract that no implementation could satisfy.

Nothing in this slice prevents replay in practice.

## Persistent Projection

A method returning evidence-safe metadata only:

```text
target_file_id
canonical_relpath
expected_pre_digest
expected_post_digest
content_size_bytes
client_request_id
declared_context_digest
broker_connection_id
effect/scope digest
```

It must never include:

- `proposed_bytes`, in whole or in part;
- prompt text, model messages, or tool arguments;
- credentials, tokens, or authentication material;
- arbitrary filesystem contents.

The projection must pass the existing persistent privacy invariant before it is
treated as evidence-safe.

## Closed Validation Vocabulary

House style: no free-text reason enters evidence.

```text
ok
invalid_operation
invalid_target_file_id
invalid_client_request_id
invalid_digest
invalid_declared_context
invalid_broker_binding
content_not_utf8
content_size_exceeded
post_digest_mismatch
request_id_reuse_mismatch
```

Deliberately absent, because this module cannot detect them: path traversal,
symlink and junction handling, alternate data streams, repository-boundary
violations, broker availability, capability lifecycle outcomes, SQLite store
conditions, and execution results. Each belongs to the component that can
actually observe it. Adding a code here for a condition this module cannot
detect would be a false capability claim in vocabulary form.

## Explicitly Out of Scope

CR-OC-001A must not implement:

- file reads or writes;
- path resolution or allowlist enumeration;
- symlink, junction, ADS, or repository-boundary checks;
- atomic replacement;
- workspace locking;
- request-reservation persistence;
- capability issuance, claiming, or finalization;
- named pipes, DACLs, `PIPE_REJECT_REMOTE_CLIENTS`, or pipe-server
  verification;
- MCP, OpenClaw configuration, hooks, plugins, or tool-schema capture;
- a recording proxy;
- unified diffs, patches, file creation, deletion, renaming, or multi-file
  effects.

### Recorded downstream requirements (CR-OC-001D)

These are recorded so they are not lost, and are **not** features of this pure
module. None is satisfied by CR-OC-001A or by any slice before D.

Named-pipe hardening:

- `PIPE_REJECT_REMOTE_CLIENTS` on creation;
- an explicit security descriptor, never the default pipe security;
- `FILE_FLAG_FIRST_PIPE_INSTANCE` with a cryptographically random per-run pipe
  name, so a squatter cannot pre-create the expected name;
- DACL permitting **only** Account A, Account B, and explicitly selected
  operator or service identities;
- no `Everyone` ACE and no anonymous-access ACE;
- explicit denial of `NT AUTHORITY\NETWORK` and of anonymous access;
- a broker-owned rendezvous artifact carrying the pipe name and the expected
  broker identity;
- shim-side verification of **both** the pipe-server process and its expected
  account before any `proposed_bytes` are transmitted;
- a negative test demonstrating that a remote-style client is rejected.

The server-verification requirement matters for confidentiality even though the
shim holds no mutation authority: a squatter that wins the pipe name would
otherwise receive proposed file contents.

CR-OC-001D is also where `broker_connection_id` acquires the provenance this
slice only asserts.

## Test Contract

A separately approved implementation must demonstrate:

1. Canonical representation and digest are deterministic across runs and
   independent of input field order.
2. Altering any bound field changes the scope digest.
3. Client-declared context and the broker-connection identifier remain distinct
   in the effect, the projection, and the API surface.
4. `proposed_bytes` must match `expected_post_digest` exactly; a mismatch fails
   closed.
5. Non-UTF-8 content fails closed.
6. Content exceeding `maximum_size_bytes` fails closed.
7. Exact-byte treatment holds: content differing only by newline style, BOM
   presence, or Unicode normal form produces different post-digests and is
   never silently reconciled.
8. `content_size_bytes` equals the original byte length, not that of any
   decoded or re-encoded form.
9. A path cannot substitute for a `target_file_id`.
10. `classify_request_replay` returns `new_request`, `idempotent_replay`, and
    `request_id_reuse_mismatch` for the corresponding input pairs, and performs
    no I/O.
11. A repeated `client_request_id` on a different `broker_connection_id`
    classifies as `request_id_reuse_mismatch`, not `idempotent_replay`.
12. Every one of the five canonical objects rejects unknown fields, missing
    fields, and null values.
13. Field-for-field identical payloads in two different schema domains produce
    different digests.
14. The persistent projection contains no file content under any input,
    including content crafted to resemble metadata.
15. The projection passes the persistent privacy invariant.
16. A malformed object never produces a partially valid effect; construction is
    all-or-nothing.
17. The module performs no file, network, subprocess, IPC, or database access,
    demonstrated by test rather than asserted.

### Mutant checks

Each mutant must be killed by a designated, named test. Per the CR-YK-002
precedent, a mutant check counts only when the test is shown to **fail** against
the mutated version.

| Mutant | Expected killer |
|---|---|
| Remove `broker_connection_id` from the effect digest | scope-digest sensitivity test |
| Remove `broker_connection_id` from the request digest | cross-connection reuse test (item 11) |
| Remove `client_request_id` from the digest | scope-digest sensitivity test |
| Omit `expected_pre_digest` from the effect | effect-completeness test |
| Accept `proposed_bytes` that mismatch the post-digest | post-digest verification test |
| Normalize newlines or strip a BOM before hashing | exact-byte treatment test (item 7) |
| Persist `proposed_bytes` in the projection | projection privacy test |
| Drop `schema` from a canonical envelope | cross-domain distinctness test (item 13) |
| Treat declared session identity as authenticated | structural separation test |

The last mutant is weaker than the others and this is recorded rather than
glossed. It is a naming and structure defect, not a behavioral one, so its test
asserts the projection key set and the absence of any accessor presenting
declared context as authenticated identity. A determined rename could still
defeat it. Reviewers, not tests, are the real control there.

## Acceptance Contract

CR-OC-001A may be considered implemented only when:

- explicit human implementation approval has been granted;
- all Test Contract items pass;
- every mutant in the table is killed by its designated test, each shown to
  fail against the mutated version;
- all five canonical objects are implemented with closed field sets, required
  non-null fields, and a `schema` discriminator inside the digest input;
- `classify_request_replay` is pure and performs no lookup or persistence;
- the module performs no file, network, subprocess, IPC, or database access,
  demonstrated by test rather than asserted;
- the persistent privacy invariant passes over the projection;
- the full test suite passes with no new `xfail`;
- `git diff --check` passes;
- the implementation diff stays within the approved allowlist;
- `triage_core/authz.py`, `triage_core/capability_claims.py`, and
  `triage_core/task_ledger.py` are unmodified;
- no runtime module imports the new module.

Recording this proposal does not satisfy any acceptance item and does not claim
that implementation occurred.

## Candidate Future Implementation Allowlist

Subject to separate explicit human approval:

- `docs/change/requests/CR-OC-001A-mediated-single-file-effect-contract.md`
- `triage_core/mediated_effect.py`
- `tests/test_mediated_effect.py`
- `docs/current_backlog.md`
- `docs/change/change_log.md`

No modification to `triage_core/authz.py`,
`triage_core/capability_claims.py`, or `triage_core/task_ledger.py` should be
necessary. No CLI, router, worker, backend, FIDO2, or dependency-file change
should be necessary. This candidate list is not implementation authority.

## Downstream Sequence

```text
CR-OC-001A — pure effect contract
CR-OC-001B — atomic client-request reservation
CR-OC-001C — constrained single-file replacement executor
CR-OC-001D — privilege-separated broker and hardened named pipe
CR-OC-001E — exclusive OpenClaw tool and effective-schema evaluation
```

Each requires its own approval. None is authorized by this document.

## Limitations and Uncertainty

- This proposal has not implemented or exercised any of the contracts above.
- The module cannot verify that `broker_connection_id` was broker-generated,
  that the declared invocation context is truthful, or that `target_file_id`
  corresponds to a real allowlisted file. All three are validated
  syntactically and asserted substantively.
- Defining replay semantics prevents no replay. `classify_request_replay`
  compares two bindings it is handed; it cannot discover that a prior binding
  exists. Enforcement, durable state, and the `capability_id` ↔
  `client_request_id` one-to-one constraint all arrive with CR-OC-001B.
- Binding a content transition proves nothing about filesystem security
  metadata, which CR-OC-001C must handle separately.
- The scope-digest-per-connection consequence constrains capability issuance
  ordering in later slices and has not been validated against a real broker.
- Nothing here establishes that OpenClaw can be constrained to a single tool.
  That claim depends on CR-OC-001E and on evidence captured at the provider
  boundary, which no part of this slice provides.
