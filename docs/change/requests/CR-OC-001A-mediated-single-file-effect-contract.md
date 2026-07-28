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

1. A replacement is described by an allowlisted file identifier, not a
   caller-supplied path.
2. The intended transition is pinned to an exact pre-content digest and an
   exact post-content digest.
3. Client-declared invocation context is structurally separated from
   broker-authenticated connection binding.
4. Every bound field participates in a single canonical effect digest.
5. Replay semantics are defined in terms of a unique client request, not merely
   a capability.
6. The persistent projection carries metadata only and never file content.

## What This Slice Can and Cannot Establish

This distinction is binding and belongs in the module docstring, not only here.

A completed CR-OC-001A may support exactly this claim:

> TriageCore can deterministically represent a single-file content-replacement
> effect, bind it to exact pre- and post-content digests, a unique client
> request, a client-declared invocation context, and a broker-generated
> connection identifier, while producing a privacy-safe persistent projection.

It may not be used to support any of:

- that OpenClaw is contained;
- that the invocation context is authenticated;
- that replay is prevented in practice;
- that paths are safe;
- that a capability was claimed;
- that any file was actually changed;
- that OS privilege separation exists.

### The broker_connection_id honesty problem

`broker_connection_id` is **defined** as broker-generated and later bound to an
authenticated IPC connection. In this slice there is no broker, so the value is
supplied by the caller like every other field. **A pure module cannot tell a
broker-minted identifier from a forged one.**

CR-OC-001A therefore establishes only that `broker_connection_id` is a
*separate field with separate provenance* that participates in the effect
digest. Its trustworthiness is entirely a CR-OC-001D property. Any wording that
implies this slice authenticates the connection is false and must be rejected
in review.

The same applies to `declared_invocation_context`. Digesting a value prevents
later alteration; it does not make the value true when first supplied.

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
CR-OC-001A defines and validates only its canonical representation. It does not
enumerate, resolve, or verify that the described file exists.

`canonical_relpath` is carried for evidence legibility. It is **not** an input
channel: no validation, authorization, or later resolution may key off it in
place of `target_file_id`. A proposal presenting a path where a file ID belongs
fails closed as `invalid_target_file_id`.

## Replacement Proposal

```text
task_id
client_request_id
target_file_id
expected_pre_digest
proposed_bytes          # transient; never persisted, never digested directly
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

`proposed_bytes` is transient. It exists to be verified against
`expected_post_digest` and is then never carried into any digest input,
projection, or evidence structure. Because `expected_post_digest` is verified
against the bytes, every digest that includes the post-digest transitively
binds the content without ever handling it.

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

Broker-generated, later bound to an authenticated IPC connection. See the
honesty note above: in this slice its provenance is asserted, not proven.

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

## Existing Capability Mapping

The proposal maps onto the merged CR-YK-002 capability without changing
`AuthorizationRequest`, the capability schema, or any claim-store behavior.

```text
artifact_byte_digest = expected_post_digest
scope_digest         = sha256(canonical_json_bytes(authorized_effect))
plan_body_digest     = digest of the canonical proposal/decision linkage
task_id              = existing ledger-envelope binding
```

The existing canonical JSON and digest utilities are reused unchanged. No new
capability schema is introduced. Digests retain the `sha256:<64 lowercase hex>`
contract.

### A sequencing consequence worth recording now

`scope_digest` covers the whole authorized effect, which includes
`broker_connection_id`. CR-YK-002 binds `scope_digest` immutably at claim time
and rejects a mismatch as `scope_digest_mismatch`.

Therefore **a capability is bound to one broker connection.** It cannot be
claimed across a reconnect, and issuance must follow connection establishment
rather than precede it. That is the intended containment property, but it is a
real ordering constraint on CR-OC-001B and CR-OC-001D and should not be
discovered during their implementation.

## Request Replay Contract

Defined here, **persisted nowhere in this slice.**

```text
request_digest = hash(canonical proposal
                      excluding proposed_bytes,
                      including expected_post_digest and content_size_bytes)

reserved -> authorized -> claimed -> completed
                                  \-> failed
reserved -> denied
```

Required rules:

- The same `client_request_id` with the same `request_digest` may return the
  existing recorded outcome.
- The same `client_request_id` with a different digest is
  `request_id_reuse_mismatch`.
- An interrupted reservation is never silently treated as new.
- The claim is **at most once per client request**, not merely once per
  capability. A single capability must not be reachable through two distinct
  client requests, and one client request must not yield two claims.

CR-OC-001A provides the digest and the state vocabulary as pure values. The
atomic SQLite reservation store, and any enforcement whatsoever, belong to
CR-OC-001B. Nothing in this slice prevents replay in practice.

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

The named-pipe hardening redlines are recorded as **downstream requirements**
under CR-OC-001D. They are not features of this pure module and must not be
described as satisfied by it.

## Test Contract

A separately approved implementation must demonstrate:

1. Canonical representation and digest are deterministic across runs and
   independent of input field order.
2. Altering any bound field changes the scope digest.
3. Client-declared context and broker-generated binding remain distinct in the
   effect, the projection, and the API surface.
4. `proposed_bytes` must match `expected_post_digest` exactly; a mismatch fails
   closed.
5. Non-UTF-8 content fails closed.
6. Content exceeding `maximum_size_bytes` fails closed.
7. A path cannot substitute for a `target_file_id`.
8. Identical request replay and mismatched request-ID reuse are
   distinguishable.
9. The persistent projection contains no file content under any input,
   including content crafted to resemble metadata.
10. The projection passes the persistent privacy invariant.
11. A malformed object never produces a partially valid effect; construction is
    all-or-nothing.

### Mutant checks

Each mutant must be killed by a designated, named test. Per the CR-YK-002
precedent, a mutant check counts only when the test is shown to **fail** against
the mutated version.

| Mutant | Expected killer |
|---|---|
| Remove `broker_connection_id` from the digest | scope-digest sensitivity test |
| Remove `client_request_id` from the digest | scope-digest sensitivity test |
| Omit `expected_pre_digest` from the effect | effect-completeness test |
| Accept `proposed_bytes` that mismatch the post-digest | post-digest verification test |
| Persist `proposed_bytes` in the projection | projection privacy test |
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
  corresponds to a real allowlisted file.
- Defining replay semantics prevents no replay. Enforcement arrives with
  CR-OC-001B.
- Binding a content transition proves nothing about filesystem security
  metadata, which CR-OC-001C must handle separately.
- The scope-digest-per-connection consequence constrains capability issuance
  ordering in later slices and has not been validated against a real broker.
- Nothing here establishes that OpenClaw can be constrained to a single tool.
  That claim depends on CR-OC-001E and on evidence captured at the provider
  boundary, which no part of this slice provides.
