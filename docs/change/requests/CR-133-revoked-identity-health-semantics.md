# CR-133: Settle Revoked-Identity Health Semantics

## Status

- **Status:** Proposal only. This CR records an unsettled lifecycle-semantics question
  discovered during a read-only review. It proposes no change, prescribes no fix, and
  asserts no defect. It exists to get the semantic question answered before any code,
  test, or documentation is altered.
- **Type:** Design question / lifecycle semantics (agent identity). No runtime, routing,
  schema, or evidence-ledger component.
- **Priority:** Design review. Raised from a read-only comparison of the archived
  `wip/identity-doctor` branch against `main`; see Source Material below.
- **Implementation authority:** **None granted and none requested.** This CR does not
  authorize modifying `triage_core/agent_identity.py`, `triage_core/tc_cli.py`, any
  identity test, or any lifecycle behavior. It does not authorize adding regression
  tests for the behavior described below — see Deferred Work.
- **Proposal acceptance:** Not yet granted. Observations recorded against `main` at
  `770d9f25a6da6099f72913ef886a6781cd014ac2`.

## Scope

Exactly one file: this document.

This CR is a problem statement and a question. It deliberately stops short of a
controlling rule, because the evidence establishes that two surfaces differ — not that
either one is wrong.

## Human Approval Requirement

No subsequent slice may proceed on the strength of this document alone. Answering the
Open Design Question below is a human decision. Until it is answered and recorded, no
implementation, test, or documentation change in the identity lifecycle area is
authorized by this CR.

## Problem Statement

A cleanly revoked agent identity is accepted by `tc identity check` and simultaneously
classified as erroneous by `tc identity doctor`. No test establishes whether that
difference is intentional.

The word *bug* is deliberately not used. What is established is a divergence between two
surfaces and an absence of any recorded decision about it. Which behavior is correct — or
whether both are, under distinct definitions — is exactly what remains unsettled.

### Evidence anchor

All observations below were verified against `main` at
`770d9f25a6da6099f72913ef886a6781cd014ac2` (`main@770d9f2`). The durable anchors are the
**symbol names** — module, class, and function — together with that revision. Line numbers
are given only as a reading convenience for that exact revision and will drift with any
later refactor; where a line number and a symbol disagree in future, the symbol and the
pinned revision govern.

### Established facts

1. **`revoke_identity` itself can produce the disputed state.**
   `AgentIdentityRegistry.revoke_identity()` in `triage_core/agent_identity.py`
   (`main@770d9f2`; ~line 333 at that revision) sets `status=REVOKED_STATUS`, carries
   `rotated_at` forward unchanged — which is `None` for an identity that was never
   rotated — and does not archive the private key to
   `{agent_id}.{fingerprint}.key.rotated`. No abnormal input or corruption is required;
   the ordinary revocation path is sufficient.

2. **`check_consistency` accepts that state.**
   `AgentIdentityRegistry.check_consistency()` in `triage_core/agent_identity.py`
   (`main@770d9f2`; ~line 520) evaluates registry/key-file structural correspondence:
   identity count, key count, missing keys, orphaned keys, malformed registry, and
   private-key permission warnings, returning an `AgentIdentityCheckReport`. A revoked
   identity that retains its key file satisfies all of these. The test
   `test_identity_check_passes_for_revoked_identity_with_existing_key` in
   `tests/test_identity_cli.py` (`main@770d9f2`) pins this outcome.

3. **`check_health` reports `no_active_key` plus historical-artifact warnings.**
   `AgentIdentityRegistry.check_health()` in `triage_core/agent_identity.py`
   (`main@770d9f2`; ~line 547) derives `active_keys` by filtering records on
   `ACTIVE_STATUS`. For a fully revoked agent that list is empty, yielding the
   `IdentityDoctorIssue` with code `no_active_key`. The same method's historical-key loop
   over non-`ACTIVE_STATUS` records (`main@770d9f2`; ~lines 619-638) then treats the
   revoked record as a historical key and emits warnings `missing_rotated_at` and
   `missing_archived_key`, because revocation set neither.

4. **The archived passing-revocation test is historical design evidence, not authority.**
   The archived branch `wip/identity-doctor` (from stash `3910b11`, preserved and pushed)
   contains `test_identity_doctor_passes_for_revoked_identity_with_existing_key`, which
   asserted `Identity doctor passed` and `checked_agents=1` for a revoked identity. That
   test records a *previous* answer to the question this CR raises. It documents that the
   question was once decided one way. It does not settle it now, it is not current
   authority, and its implementation is superseded — `main@770d9f2` is ahead of the
   archived version by seven diagnostic codes, including `no_active_key`,
   `historical_fingerprint_mismatch`, `malformed_historical_key`, and
   `missing_requested_capability`.

### Observed behavior

Reproduced read-only against `main@770d9f2`, exercising
`AgentIdentityRegistry.generate_identity()`, `.revoke_identity()`, `.check_health()`, and
`.check_consistency()` on a throwaway registry in a temporary directory. No repository
file was modified by the reproduction.

```
SAME registry, cleanly revoked agent:
  tc identity doctor -> has_errors=True
                        errors   = [no_active_key]
                        warnings = [missing_rotated_at, missing_archived_key]
  tc identity check  -> has_errors=False
                        missing_key=[] orphaned=[] malformed=False perm_warnings=0
```

`tests/test_doctor_cli.py` contains no revoked-identity case, so nothing in the suite
observes this divergence.

## Open Design Question

Is revocation:

- **(a)** a valid terminal lifecycle state — an agent may end its life revoked, with no
  active key, and that condition is healthy; or
- **(b)** a valid state only when specified archival invariants hold — for example that
  revocation must set `rotated_at` and archive the prior key material, making the current
  warnings correct and `revoke_identity` incomplete; or
- **(c)** structurally consistent but intentionally operationally unhealthy — a defined
  state in which `check` passing and `doctor` failing is the designed, documented outcome?

Each answer implies a different subsequent change, and they are mutually exclusive.
Selecting one is out of scope here.

## Non-Requirement

`tc identity check` and `tc identity doctor` are **not** required to return equivalent
judgments. It is legitimate for `check` to mean structural consistency while `doctor`
applies a stronger operational-health standard. Forcing the two surfaces to agree in all
output would erase a distinction that may be deliberate and useful.

## Requirement

Any difference between the two surfaces that presents as a contradiction must follow from
an explicit, documented lifecycle or semantic distinction — not emerge incidentally from
implementation mechanics.

The present divergence does not meet that bar. In
`AgentIdentityRegistry.check_health()` (`main@770d9f2`), `no_active_key` arises from an
empty `ACTIVE_STATUS` filter, and the two warnings arise from a historical-key loop that
processes `REVOKED_STATUS` records identically to `ROTATED_STATUS` ones. Whatever answer
is chosen, the outcome must be traceable to a stated rule about revocation rather than to
the incidental behavior of those filters.

## Explicit Exclusions

This CR does not change, and does not authorize changing:

- `triage_core/agent_identity.py` — including `revoke_identity`, `check_consistency`,
  `check_health`, and the `REVOKED_STATUS` / `ROTATED_STATUS` distinction
- `triage_core/tc_cli.py` — including `tc_identity_doctor` and its output contract
- `tests/test_identity_cli.py`, `tests/test_doctor_cli.py`, or any other identity test
- Any lifecycle behavior, status vocabulary, or diagnostic code
- `docs/current_backlog.md` and `docs/change/change_log.md`
- The archived `wip/identity-doctor` branch, which is preserved unmodified as evidence

## Deferred Work

The archived design also surfaced four scenarios whose behavior exists on `main@770d9f2`
but has no corresponding case in `tests/test_doctor_cli.py`: the `missing_rotated_at` and
`malformed_registry` codes emitted by `AgentIdentityRegistry.check_health()`, the positive
(matching) `agent_id` scoping path through that same method, and the `missing_audit_event`
code emitted by `tc_identity_doctor()` in `triage_core/tc_cli.py`. Adding those tests is
deliberately **not** proposed here.

A regression test written now would pin whichever behavior currently exists, which for
the revoked case is precisely the behavior in dispute. No regression behavior should be
pinned until the Open Design Question is settled.

## Source Material

Findings extracted from a read-only comparison of `wip/identity-doctor` against `main`.
That branch contains a superseded doctor implementation and is retained as archaeological
evidence only. This CR depends on findings extracted from it and deliberately does not
inherit its history; nothing in the archived branch is proposed as a patch.

Prior framing corrected during that review: the archived branch was initially read as an
unmerged doctor implementation. It is not. `main` already contains the doctor as
`check_health`, and twelve of the archived branch's thirteen scenarios are covered on
`main` — six directly, two via `check` rather than `doctor`, and four in behavior without
a doctor-level test. The revoked-identity case is the single genuine divergence.

## Stop Point

This CR stops at the question. The next governed step is a human decision selecting (a),
(b), or (c) — or rejecting the framing. Only after that decision is recorded should any
follow-on slice be scoped.
