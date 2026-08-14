# CR-133: Settle Revoked-Identity Health Semantics

## Status

- **Status:** Semantic question **settled**; see Accepted Semantic Decision below. This CR
  originally recorded an unsettled lifecycle-semantics question discovered during a
  read-only review. The design decision has now been made. The CR still proposes no code
  change, prescribes no fix, and asserts no defect, and it remains the stop point: no
  implementation has been scoped or authorized.
- **Type:** Design question / lifecycle semantics (agent identity). No runtime, routing,
  schema, or evidence-ledger component.
- **Priority:** Design review. Raised from a read-only comparison of the archived
  `wip/identity-doctor` branch against `main`; see Source Material below.
- **Proposal acceptance:** Granted by the human operator on 2026-08-14 for the problem
  statement, evidence, and framing recorded in this CR, observed against `main` at
  `770d9f25a6da6099f72913ef886a6781cd014ac2`.
- **Design decision:** Granted by the human operator on 2026-08-14, selecting **option
  (a)** from the Open Design Question below. The accepted semantics are recorded verbatim
  in Accepted Semantic Decision. This grant settles the *meaning* of a revoked identity's
  health. It grants no authority to change any code, test, or behavior to match that
  meaning.
- **Implementation-surface census:** Conducted read-only against `main@770d9f2` and
  recorded on 2026-08-14 at the operator's direction; see Implementation Surface below. The
  census enumerates a four-file allowlist, a defect that a naive fix would introduce, and
  binding acceptance constraints. **Recording it granted no authority to act on it**, and
  it is not an implementation design.
- **Implementation authority:** **Granted by the human operator on 2026-08-14**, for one
  bounded single-slice implementation against the four-file census allowlist. Recorded
  verbatim in Implementation Authority — Single Slice Granted below. The grant is
  single-use and stage-bound: it authorizes preparation of a reviewable implementation
  candidate, and is **exhausted** once that candidate exists. It does not carry
  implementation acceptance.
- **Merge / release / closeout authority:** Not granted.

## Scope

Exactly one file: this document.

This CR is a problem statement, a question, the accepted answer to that question, and — as
of 2026-08-14 — the durable record of the bounded implementation authority granted against
it. It settles what a revoked identity's health *means*. It does not itself implement that
meaning; the code change lives in PR #178 under the separately recorded grant.

## Human Approval Requirement

No subsequent slice may proceed on the strength of this document alone.

The Open Design Question below was a human decision, and it has been answered and recorded
(option (a), 2026-08-14). **Answering it did not confer implementation authority.**
Implementation authority was a separate, later human decision, granted on 2026-08-14 and
recorded verbatim in Implementation Authority — Single Slice Granted. It is bounded to four
paths, single-use, now exhausted, and does not extend to acceptance, merge, release, or
closeout. Any change beyond those four paths remains unauthorized by this CR.

## Problem Statement

*Stated as observed at proposal time; the question it raised has since been answered — see
Accepted Semantic Decision.*

A cleanly revoked agent identity is accepted by `tc identity check` and simultaneously
classified as erroneous by `tc identity doctor`. No test establishes whether that
difference is intentional.

The word *bug* is deliberately not used. What was established by the evidence is a
divergence between two surfaces and an absence of any recorded decision about it — not
that either behavior was wrong. Which behavior is correct, or whether both are under
distinct definitions, was exactly the open question; it is now settled by the accepted
decision recorded below, which the evidence in this section supports but did not by itself
determine.

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

## Open Design Question — Answered (a)

Retained as written for the record, so that the accepted answer is legible as a choice
*among* stated alternatives rather than as the only option considered.

Is revocation:

- **(a)** a valid terminal lifecycle state — an agent may end its life revoked, with no
  active key, and that condition is healthy; or
- **(b)** a valid state only when specified archival invariants hold — for example that
  revocation must set `rotated_at` and archive the prior key material, making the current
  warnings correct and `revoke_identity` incomplete; or
- **(c)** structurally consistent but intentionally operationally unhealthy — a defined
  state in which `check` passing and `doctor` failing is the designed, documented outcome?

Each answer implies a different subsequent change, and they are mutually exclusive.

**Answered on 2026-08-14: option (a).** See Accepted Semantic Decision.

## Accepted Semantic Decision

Granted by the human operator on 2026-08-14.

A correctly revoked identity is a **valid terminal lifecycle state**: healthy *as revoked*,
but intentionally **not operationally usable or capability-ready**.

Two consequences follow directly from that decision:

1. **Rotation-specific invariants do not automatically apply to revocation.** The
   `rotated_at` timestamp and the archived-key artifact are rotation concepts. Their
   absence on a revoked record is not, by itself, evidence of an unhealthy identity.
2. **Private-key disposition on revocation remains a separate, unresolved question.**
   Whether a revoked identity should retain, archive, or destroy its private key material
   is expressly *not* settled by this decision and must not be inferred from it.

### Controlling invariant

    LifecycleHealthy ≠ OperationallyUsable

These are distinct properties and must be represented distinctly. An identity may be
lifecycle-healthy (correctly revoked, terminal, well-formed) while being operationally
unusable (no active key, not capability-ready). Reporting the second as a failure of the
first conflates them.

*Refined for implementation purposes to a three-part form after the surface census — see
Refinement of the controlling invariant. The refinement does not alter this decision.*

### Implementation-facing consequence (not authorized here)

Any future change must make this distinction **explicit**. At `main@770d9f2` the current
behavior emerges incidentally: `no_active_key` falls out of an empty `ACTIVE_STATUS`
filter, and the two warnings fall out of a generic non-active-history loop that processes
`REVOKED_STATUS` records identically to `ROTATED_STATUS` ones. Under the accepted
semantics that outcome is an accident of those filters rather than an expression of a
stated rule — which is precisely what the Requirement section forbids.

This paragraph describes what a correct future change must satisfy. It does not authorize
making one.

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

## Implementation Surface — Read-Only Census

Conducted read-only against `main@770d9f2` on 2026-08-14. Recorded here so that a later,
separately authorized implementation slice inherits a bounded allowlist rather than
re-deriving one. **Recording this census grants no authority to act on it.**

### Already correct — outside the allowlist

The "not operationally usable" half of the accepted semantics is **already enforced** and
requires no change. `AgentIdentityRegistry.get_identity()` and
`.require_authorized_capability()` raise `RevokedAgentError` for a revoked identity;
`.verify_signed_payload()` returns `False`; `triage_core/task_ledger.py` already handles
`RevokedAgentError` at its two call sites.

Option (a) is therefore not a two-sided change. Only *health reporting* conflates the
properties. Also outside the allowlist, and not to be modified:

- `AgentIdentityRegistry.check_consistency()` — passing for a revoked identity is already
  correct under the accepted semantics
- `AgentIdentityRegistry.revoke_identity()` — unchanged; altering it would require settling
  private-key disposition, which remains open
- The `IdentityDoctorReport` and `IdentityDoctorIssue` dataclasses — the existing issue type
  is sufficient to express the distinction

### Minimum allowlist — exactly four files

| Path | Why it is necessary |
|---|---|
| `triage_core/agent_identity.py` | `check_health()` is the only place lifecycle health is computed |
| `triage_core/tc_cli.py` | without it, `--for-capability` reports success for a revoked identity — see Post-Change-State Trap |
| `tests/test_doctor_cli.py` | the doctor-behavior test surface; no existing test sits at the revoke/health intersection |
| `docs/security/identity_rotation_recovery_policy.md` | the normative policy authority for status semantics |

Test-surface note: revocation and doctor-health are currently tested in disjoint files —
`tests/test_doctor_cli.py` carries the health/doctor cases and no revocation cases, while
`tests/test_identity_cli.py` and `tests/test_agent_identity.py` carry revocation cases and
no health/doctor cases. No existing test pins the disputed behavior, so none breaks.

Documentation note: no normative CLI reference documents `tc identity doctor` output. Every
other file mentioning it is historical — past `CR-*.md` records, dated operations
checkpoints, and the append-only `docs/change/change_log.md`. None of those may be edited.

### Post-Change-State Trap

`tc_cli.py` is in the minimum surface because of a defect that would be **introduced** by a
correct-looking change confined to `check_health()` alone.

Verified by read-only probe against `main@770d9f2`, for a revoked agent invoked as
`tc identity doctor --agent-id <revoked> --for-capability <X>`:

```
ERROR no_active_key ...        <- the only error emitted
exit_code = 1
capability_ready line present: False
capability ERROR present:      False
```

Today's non-zero exit is produced **entirely** by the health error. In
`tc_identity_doctor()`, the `--for-capability` loop skips any agent without exactly one
`ACTIVE_STATUS` identity, and the process exits non-zero only when `report.has_errors` is
true. Remove `no_active_key` for revoked identities under the accepted semantics and that
invocation exits **0**, emitting neither a capability error nor a `capability_ready` line —
reporting success for an identity the accepted semantics state is not capability-ready.

Two consequences for any implementation:

1. The existing `missing_requested_capability` code **must not** be reused for this case.
   In the probe the requested capability was present in the identity's metadata; the
   identity is unusable because it is revoked, not because the capability is absent. That
   code would assert something false. A distinct code — for example
   `revoked_identity_not_capability_ready` — is required.
2. The revoked state should be **visible**, not merely non-erroring. Suppressing the three
   issues leaves `Identity doctor passed`, which reads as "this signer is ready". A
   positive statement of the lifecycle state and its operational consequence is preferred;
   exact vocabulary is an implementation-design question.

### Refinement of the controlling invariant

The accepted decision states `LifecycleHealthy ≠ OperationallyUsable`. Because the CLI
exposes capability readiness as a separately requestable check, the operative form is:

    LifecycleHealthy ≠ OperationallyUsable ≠ CapabilityReady

This refines the accepted two-part form for implementation purposes. It does not alter the
semantic decision granted on 2026-08-14.

### Acceptance Constraints

Binding on any future implementation slice, whenever one is authorized:

1. **CR-133 must not change `COMPROMISED_STATUS` health semantics.** CR-133 settled
   revocation, not compromise. Verified: nothing currently pins compromised doctor
   behavior — `COMPROMISED_STATUS` has one production consumer
   (`verify_signed_payload()`), no production code path sets it, and the single test
   touching it pins signature verification rather than health. There is no existing test
   to inherit protection from, so this constraint must be enforced deliberately.

   Two distinct vectors violate it, and an acceptance check must cover both:

   - rewriting the historical-key loop guard `status != ACTIVE_STATUS` to
     `status == ROTATED_STATUS`, which also exempts compromised records; and
   - suppressing `no_active_key` on the condition *"no active identity"* rather than
     specifically *"terminal revoked"* — a compromised identity also has no active key, so
     this changes compromised behavior without touching the historical loop at all.

   The criterion must therefore be written against the **condition used**, not merely the
   code region edited.

2. **Historical integrity checking must not be globally disabled.** Genuine
   `ROTATED_STATUS` history must remain subject to rotation archival expectations.

3. **`no_active_key` must remain intact** for an absent active identity arising from any
   cause other than accepted terminal revocation.

4. **Private-key disposition remains out of scope** and must not be resolved by inference
   from any of the above.

### Required Regression Set

Four behavioral cases, plus one constraint. Not authorized when first recorded; **authorized
and written under the single-slice grant** below, in `tests/test_doctor_cli.py`.

1. Generated → revoked: general doctor succeeds; no `no_active_key`; no revocation-caused
   `missing_rotated_at` or `missing_archived_key`; revoked/non-operational state visible.
2. Generated → revoked, with `--for-capability`: the readiness check fails explicitly with
   a not-capability-ready result; no `capability_ready` output.
3. Rotated history with the current identity revoked: the revoked record is healthy as
   revoked, while genuine `ROTATED_STATUS` history still receives archival checks — this is
   the case that proves constraint 2 held.
4. Absence of an active identity for a cause other than accepted terminal revocation:
   `no_active_key` behavior intact.

Plus: an explicit compromised-state case, **or** a recorded behavioral non-change proof for
`COMPROMISED_STATUS`. A compromised state must be constructed by direct registry mutation,
since no production path sets it.

## Implementation Authority — Single Slice Granted

Granted by the human operator on 2026-08-14. Recorded verbatim.

> Implementation authority is granted for one bounded CR-133 implementation slice
> implementing the accepted option (a) semantics:
>
>     LifecycleHealthy ≠ OperationallyUsable ≠ CapabilityReady
>
> The grant is limited to exactly these four paths:
>
> - `triage_core/agent_identity.py`
> - `triage_core/tc_cli.py`
> - `tests/test_doctor_cli.py`
> - `docs/security/identity_rotation_recovery_policy.md`
>
> Within `triage_core/agent_identity.py`, this grant includes authority to add one
> module-level helper that classifies the already-settled terminal revoked state for
> shared use by `AgentIdentityRegistry.check_health()` and `tc_identity_doctor()`. The
> helper must not introduce a new lifecycle state or modify `IdentityDoctorReport` or
> `IdentityDoctorIssue`.
>
> The terminal-revoked predicate must remain narrowly bounded:
>
> - zero `ACTIVE_STATUS` records;
> - exactly one `REVOKED_STATUS` record; and
> - every remaining historical record, if any, is `ROTATED_STATUS`.
>
> The implementation may:
>
> - prevent a correctly terminal-revoked identity from emitting revocation-caused
>   `no_active_key`, `missing_rotated_at`, or `missing_archived_key` health findings;
> - make the revoked/non-operational lifecycle state explicitly visible in
>   `tc identity doctor` output;
> - make `--for-capability` fail explicitly for a revoked identity using a distinct
>   diagnostic meaning that does not falsely claim the requested capability is absent; and
> - add the CR-133 regression coverage and the bounded normative-policy clarification
>   already specified in this CR.
>
> The implementation must preserve all recorded CR-133 constraints, including:
>
> - `ROTATED_STATUS` historical-integrity diagnostics remain intact;
> - `COMPROMISED_STATUS` health behavior remains unchanged, through both the zero-active
>   and historical-record paths;
> - `no_active_key` remains an error for zero-active states other than the accepted
>   terminal-revoked state;
> - revoked identities remain unusable for signing, verification, authorization, and
>   capability readiness;
> - `missing_requested_capability` is not reused to describe revocation when revocation is
>   the operative reason;
> - no private-key retention, archival, deletion, or other disposition policy is introduced
>   or inferred;
> - `revoke_identity()`, `check_consistency()`, `IdentityDoctorReport`, and
>   `IdentityDoctorIssue` remain unchanged; and
> - the separately deferred archived-design coverage gaps remain outside this slice.
>
> The implementation-authority grant is single-slice, single-use, and stage-bound. It
> authorizes preparation of a reviewable implementation candidate within the four-file
> allowlist, including the bounded edits, tests, verification, commit, push, and opening of
> an implementation PR. It does not grant implementation acceptance, merge authority,
> release authority, or closeout authority.
>
> This grant is exhausted when that reviewable implementation candidate is produced.

### Grant exercised and exhausted

The candidate was produced on 2026-08-14 as
[PR #178](https://github.com/coreytshaffer/TriageCore/pull/178), branch
`claude/cr-133-revoked-identity-health-implementation`, based `origin/main@770d9f2`,
touching exactly the four allowlisted paths. **The grant is therefore exhausted.**

Implementation acceptance was reviewed on 2026-08-14 and **withheld** pending two evidence
repairs: this authority record, and regression-pinning of the `tc identity doctor` exit-code
contract (the stdout assertions alone did not pin exit 0 versus exit 1, which is precisely
what the Post-Change-State Trap turns on). Implementation design and code review both
passed. Merge, release, and closeout remain ungranted.

## Explicit Exclusions

These exclusions describe this CR document's own scope. They are superseded, for the four
allowlisted paths only, by the single-slice grant recorded above; everything not named in
that grant remains excluded.

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

The single-slice grant of 2026-08-14 does **not** disturb this deferral: it authorizes the
Required Regression Set only, and the four archived-design coverage gaps remain outside it.

The original reason was that a regression test written before the decision would pin
whichever behavior currently exists, which for the revoked case was precisely the behavior
in dispute.

That reason has now sharpened rather than lapsed. With option (a) accepted, the current
revoked-case behavior at `main@770d9f2` is known to *contradict* the accepted semantics —
so pinning it would encode the wrong rule, not merely a premature one. The other three
scenarios remain unpinned because the test-authoring authority later granted covers only the
Required Regression Set. Their scoping belongs to a further, separately authorized slice.

**These are two distinct sets; do not conflate them.** The four scenarios above are
*archived-design coverage gaps* (`missing_rotated_at`, `malformed_registry`, positive
agent-scoping, `missing_audit_event`) inherited from the `wip/identity-doctor` comparison.
The four cases in the Required Regression Set are *revocation-semantics cases* derived from
the accepted decision. They overlap only incidentally — `missing_rotated_at` appears in both
lists for different reasons, as an untested code in the first and as an assertion about
revoked identities in the second. Neither set is authorized by this CR.

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

This CR has stopped three times, and stops a fourth time here.

1. It stopped at the open question. Answered: option (a), 2026-08-14.
2. It stopped before implementation scoping. A read-only census was then authorized and
   recorded — see Implementation Surface.
3. It stopped before implementation. A bounded single-slice implementation authority was
   then granted on 2026-08-14 and exercised as PR #178 — see Implementation Authority. That
   grant is now exhausted.
4. **It now stops before implementation acceptance.** Acceptance was reviewed on
   2026-08-14 and withheld pending two evidence repairs. Nothing in this document
   authorizes merging PR #178, nor any change outside the four allowlisted paths.

The surface question posed at the second stop — which surface should carry the distinction —
is answered by the recorded census: both `AgentIdentityRegistry.check_health()` and
`tc_identity_doctor()`, because a change confined to the first introduces a false success in
the second. `check_consistency()` is not involved; its current behavior is already correct.

**Private-key disposition on revocation remains open** and must not be resolved by inference
from the accepted semantics or from the census.

The next governed step is a separate human decision on implementation acceptance for
PR #178, re-reviewing the two repair deltas rather than reopening the whole implementation.
That decision has not been made.
