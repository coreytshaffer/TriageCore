# CR-135: Governed Backend Destination Policy and Transport Binding

## Status

- **Status:** Proposal and design accepted by the human operator on 2026-10-18, pinned
  to `a0bbd93fd4b82167c07e901dbdc7feac22847975`. Design amendment 1
  (`backend_protocol_unsupported`) approved separately on 2026-10-18. Slice 1 (contract
  module, not integrated) implemented and accepted at
  `149aa8e4d01e19f5c9e4f791822613f9402b978c`. Slice 2 not authorized. (First recorded as:
  Proposed. Proposal-only documentation. Then, at `e127d7e`: Proposal and design
  accepted; implementation not authorized.)
- **Type:** Governance kernel: privacy and provenance, capability and effect bounds.
  The invariant this CR strengthens: *a governed `tc run` attempt sends requests only to
  network endpoint identities that are bound to its governed decision and authorized by
  trusted destination policy. A route's name is never treated as evidence of where its
  traffic goes.*
- **Evidence baseline:** the Problem Statement's established facts, and the other
  repository facts from the original design investigation, were observed at `main` at
  `1dc9b88631748a4c71ebdf331c0536f33a714256`. Re-verify when the pin changes. The
  Post-Acceptance Record and the Slice 1 Review-Condition Checklist rest on later pins,
  identified separately:
  - `main@ed9e1651461188696ffdc704f4beeab3883994d9`: the merge record, the branch base,
    and `backends.py:422-439`;
  - `149aa8e`: the slice 1 files, test and function names, and the behaviour of
    `backend_protocol_unsupported`;
  - `a0bbd93`: the accepted design and its 17-code vocabulary;
  - the PR #186 and PR #187 descriptions as of 2026-10-18;
  - GitHub Actions run `39171753206`.

  (First recorded as: "`main` at `1dc9b88631748a4c71ebdf331c0536f33a714256`. Every
  repository fact below was observed at that commit. Re-verify when the pin changes."
  Narrowed in the PR #188 correction cycle, because that statement no longer covered the
  reconciliation sections.)
- **Proposal drafting authority:** Granted by the human operator on 2026-10-18 for this
  single document. Recorded verbatim under Authority Record.
- **Owner decisions:** Five recorded (D1–D5), plus two further approvals. See Owner
  Decisions.
- **Publication and review:** Published as draft
  [PR #186](https://github.com/coreytshaffer/TriageCore/pull/186). The operator's
  full-document review at `b057945` requested five corrections, made in `55a3f32`. The
  design review at `55a3f32` requested three further corrections and two editorial
  changes, made in `44faec2`. The design-acceptance review at `44faec2` requested two
  final S3 corrections, made in `a0bbd93`. The final design review at `a0bbd93`
  recommended acceptance with no further corrections (see Review Corrections).
- **Proposal acceptance:** Granted by the human operator on 2026-10-18, pinned to
  `a0bbd93`. Recorded verbatim under Acceptance record. (First recorded as: Not
  granted.)
- **Design acceptance:** Granted by the human operator on 2026-10-18 for the design as
  recorded in this document at `a0bbd93`. Recorded verbatim under Acceptance record.
  (First recorded as: Not granted.)
- **Documentation merge:** PR #186 squash-merged into `main` by the operator as
  `ed9e1651461188696ffdc704f4beeab3883994d9`. See Post-Acceptance Record.
- **Implementation authority:** Slice 1 only: one implementation grant and four
  corrective grants, all exercised and exhausted. Slice 2 and slice 3: not granted.
  (First recorded as: Not granted.)
- **Implementation acceptance:** Slice 1 only, pinned to `149aa8e`, recorded in
  [PR #187](https://github.com/coreytshaffer/TriageCore/pull/187). (First recorded as: Not
  granted.)
- **Slice 1 merge / release / closeout:** Not granted.

### Lifecycle state

| Stage | State |
|---|---|
| identifier allocation | CR-135, allocated by the operator after confirming that `main` at `1dc9b88` has no CR-135 (highest numeric CR there: CR-134) |
| proposal drafting | granted, single document |
| owner decisions | D1–D5 approved with binding qualifications; HTTPS-only remote transport and separate destination kinds approved |
| publication | fresh branch from `main@1dc9b88`; draft [PR #186](https://github.com/coreytshaffer/TriageCore/pull/186) |
| full-document review | revisions requested 2026-10-18 at `b057945`; one documentation-only correction cycle confined to this file on the PR #186 branch, made in `55a3f32` (see Review Corrections) |
| design review at `55a3f32` | minor design revisions requested; proposal judged ready for owner acceptance on technical grounds; made in `44faec2` (see Review Corrections) |
| design-acceptance review at `44faec2` | proposal technically acceptable; design acceptance not recommended at `44faec2`; two S3 corrections requested; made in `a0bbd93` (see Review Corrections) |
| final design review at `a0bbd93` | proposal and design acceptance recommended; no further document corrections required |
| proposal acceptance | **granted** 2026-10-18, pinned to `a0bbd93` (see Acceptance record) |
| design acceptance | **granted** 2026-10-18 for the design as recorded at `a0bbd93` (see Acceptance record) |
| documentation merge | PR #186 squash-merged by the operator as `ed9e165`; file content identical to `e127d7e` (see Post-Acceptance Record) |
| slice 1 implementation authority | granted 2026-10-18 (P1(a), two-file allowlist); exercised at `5d72645`; exhausted |
| slice 1 corrective grants | four, same two files; exercised at `c228157`, `412dbf7`, `fc02328`, `149aa8e`; exhausted |
| slice 1 implementation acceptance | **granted** 2026-10-18, pinned to `149aa8e`, recorded in PR #187 |
| design amendment 1 (`backend_protocol_unsupported`) | **approved** 2026-10-18, separately from the `a0bbd93` design acceptance |
| slice 1 review-condition reconciliation | checklist recorded; U-1 and U-2 resolved 2026-10-18; U-3 open (see Slice 1 Review-Condition Checklist) |
| accepted-design preservation | annotated tag `cr-135-design-accepted-a0bbd93` authorized (see Post-Acceptance Record) |
| slice 1 merge / release / closeout | not granted |
| slice 2 and slice 3 implementation authority | not granted |
| CR-135 closeout | not granted |

Rows above "documentation merge" are as recorded at `e127d7e`, except that the last five
rows recorded there (implementation authority, implementation acceptance, merge
authority, release authority, closeout: all "not granted") are replaced by the rows
from "documentation merge" down.

## Scope

Exactly one file: this document.

No code, test, schema, configuration, CLI, credential, evidence-ledger, backlog,
change-log, architecture, or README change is made or authorized. This grant does not
authorize branch publication, push, pull request, merge, release, or deployment.

This section records the drafting grant's scope, as first recorded. Later grants, each
with its own scope, are recorded under Post-Acceptance Record.

## Human Approval Requirement

Each later stage needs its own explicit human decision: proposal acceptance, design
acceptance, implementation authority (which must name a bounded file allowlist),
implementation acceptance, merge, release, and closeout. None of these is implied by
this document, by a passing test, or by a reviewer's verdict. Under change management, a
grant that names no bounded allowlist is incomplete. CR-DD-012B preserves the defect that
results when such an allowlist is inferred instead of granted.

## Implementation Authority

**Not granted.** The Proposed Implementation Slices section is a proposal for review, not
an allowlist anyone may act on. (As first recorded.)

**Slice 1 only, now exhausted.** The operator later granted one slice 1 implementation
grant and four corrective grants, each naming the same two-file allowlist. All five were
exercised and are exhausted (see Post-Acceptance Record). No implementation authority is
currently open for this CR. Slice 2 and slice 3 each need their own grant naming an exact
file allowlist.

## Authority Record

Context: the operator ran an M04 design review, a remediation work-package label from the
NIST/ISO assessment and not a CR identifier, over a read-only planning return. The
operator independently checked `main@1dc9b88`, including CR-134 and the governed-run
implementation, and recorded this disposition on 2026-10-18 (2026-10-17 PDT).

The owner-decision table, recorded verbatim:

> | Decision                       | Disposition | Binding qualification |
> | ------------------------------ | ----------- | --------------------- |
> | D1 — Reject localhost          | Approved    | Literal 127.0.0.1 and [::1] only; migrate defaults and provide an explicit compatibility refusal. |
> | D2 — Require loopback          | Approved    | Applies to every network-capable local_* route in governed tc run. Legacy/direct paths remain explicitly outside the first assurance claim. |
> | D3 — Defer trusted LAN         | Approved    | LAN requires a separately authorized expansion of trusted destinations, not merely a new configuration entry. |
> | D4 — Fail whole attempt        | Approved    | Configuration-integrity violation, exit 2, zero network requests. Never silently fall back to cloud. |
> | D5 — Bind configuration digest | Approved    | Bump CONFIGURATION_VERSION; bind canonical, route-indexed endpoint identities and transport policy, with independently testable revalidation. |
>
> I also approve HTTPS-only remote cloud transport and the separation of endpoint,
> recipient and staging destination policy kinds.

The allocation and drafting grant, recorded verbatim:

> Allocate `CR-135`: Governed Backend Destination Policy and Transport Binding.
>
> Recommended path:
>
> `docs/change/requests/CR-135-governed-backend-destination-policy.md`
>
> The authorization is limited to creating that single proposal document, recording the
> five decisions above, the required refinements, design assumptions, acceptance fixtures
> and explicit non-claims.
>
> No code, test, schema, configuration, CLI, credential or evidence-ledger changes are
> authorized. No branch publication, push, PR, merge, release or deployment is authorized
> by this decision. Design acceptance and implementation authority remain separate future
> gates.
>
> The new CR should preserve CR-134's accepted recipient/export contract rather than
> reopening it. M03 and M09a remain on their existing branch and are not pulled into this
> scope.

> Disposition: CR-135 proposal drafting authorized; implementation not authorized.

The operator also required five design refinements (A–E). They are recorded under
Required Refinements and carried into the design below. The operator stated the reasoning
for refinement A, recorded verbatim:

> Cloud intent permits consideration of an already-authorized cloud destination; it does
> not authorize an arbitrary URL.

### Acceptance record

On 2026-10-18 (2026-10-17 PDT), after the final design review at `a0bbd93`, the operator
granted, recorded verbatim:

> Grant proposal and design acceptance at a0bbd93 and record both

Proposal acceptance and design acceptance are separate decisions in this repository.
This instruction grants both and names both, and they are recorded as two decisions:

- **Proposal acceptance** accepts the problem statement, objective, scope, and
  boundaries, as recorded at `a0bbd93fd4b82167c07e901dbdc7feac22847975`.
- **Design acceptance** attaches to the design as recorded in this document at
  `a0bbd93fd4b82167c07e901dbdc7feac22847975`. That covers:
  - D1–D5 and the two further approvals;
  - refinements A–E;
  - review corrections 1–10;
  - the S1, S2, pre-invocation and S3 enforcement sequence;
  - the refusal classes and propagation requirement;
  - the F1–F14 fixture specification;
  - the non-claims.

  `cloud_model_unbound` was recorded at `a0bbd93` as a proposed reason code subject to
  design acceptance, and is accepted with this design.

Scope and limits of both decisions:

- **Pinned to `a0bbd93`.** This record is added in a later commit, which changes only
  the Status, Lifecycle state, Acceptance record, and Stop Point text. Any later change
  to design content needs its own review and acceptance. Acceptance does not follow the
  branch tip.
- **No downstream authority.** Neither decision carries implementation authority,
  implementation acceptance, merge, release, or closeout.
- **Bounded allowlist still required.** Any implementation grant must name a bounded
  file allowlist, as [change management](../change_management.md) requires.
- **Planned tests, not evidence.** F1–F14 remain planned tests. Green CI on this
  document is not evidence of endpoint containment.
- **Recommended starting point.** The final review recommended that any implementation,
  if separately authorized, begin with slice 1, the contract module that is not wired
  into runtime.
- **Unchanged.** CR-134's accepted design, the NIST/ISO assessment scores, and the
  separate M03/M09a records are unchanged.

## Post-Acceptance Record (reconciliation, 2026-10-18)

This section was added on `claude/cr-135-slice1-reconciliation`, branched from
`main@ed9e1651461188696ffdc704f4beeab3883994d9`. It records decisions made after the
acceptance record at `e127d7e`. The rest of the document is kept as recorded. The only
changes elsewhere are later-status notes in these sections, each of which keeps its
earlier text:

- Status;
- Lifecycle state;
- Scope;
- Implementation Authority;
- Proposed Implementation Slices;
- Deferred Work;
- Explicit Exclusions;
- Stop Point.

The design as accepted at `a0bbd93` is unchanged. The one addition to it is the
Reason-code vocabulary subsection, which lists the 17 accepted codes and design
amendment 1, recorded separately below.

Quotations are verbatim from the operator's messages in the session that carried out
this work, or from the PR descriptions cited. Where only a short instruction exists, the
scope it approved is described and attributed, and is not presented as a quotation.

### Documentation merge (PR #186)

- **Merged by:** the operator (GitHub `merged_by`: `coreytshaffer`), on 2026-10-18 at
  06:59:47 UTC (2026-10-17 23:59:47 PDT). No merge authority was issued to the agent; the
  operator performed the merge.
- **Squash commit:** `ed9e1651461188696ffdc704f4beeab3883994d9`, parent `main@1dc9b88`,
  one file.
- **Content:** the merged file's git blob (`5301b317feaef4e3bfd09971c0dcd261878e981e`) is
  identical to the file at the PR head `e127d7e`: 887 lines, SHA-256
  `c21a336b26acd40d5581e6ac985965ae1b0e54b0b39ff4115e814ad356505fe4`.
- **Accepted-design commit:** `a0bbd93` is reachable from `e127d7e` but not from `main`,
  because the merge was a squash. See Accepted-design preservation.

The operator's disposition after the merge, recorded verbatim:

> Disposition: CR-135's accepted design is now recorded on `main`. M04 remains
> design-complete, not implementation-complete. No NIST/ISO assessment scores or security
> assurance claims change as a result of this merge.

### Slice 1 implementation grant (exercised; exhausted)

Granted on 2026-10-18 at 07:12 UTC (00:12 PDT), after a read-only slice 1 plan. Recorded
verbatim:

> CR-135 Slice 1 — Implementation authorization
>
> I authorize one bounded implementation candidate for CR-135 Slice 1, selecting P1(a).
>
> Baseline: "main@ed9e1651461188696ffdc704f4beeab3883994d9"
>
> Branch: "claude/cr-135-slice1-destination-policy", created separately from the M03/M09a and CR-135 documentation branches.
>
> Exact writable allowlist:
>
> - "triage_core/destination_policy.py" — new file
> - "tests/test_destination_policy.py" — new file
>
> Implement the accepted destination-policy contract, strict endpoint normalization, pure configuration resolution, deterministic policy digests, route bindings, and "GuardedTransport" with its offline recording-adapter tests.
>
> Follow the additional parsing, method-and-URL binding, error-provenance, runtime-seal and test-evidence conditions established in the Slice 1 review.
>
> Publication authority: After focused tests, the full test suite, diff checks and import-isolation checks pass, you may create a local commit, push the candidate to the named feature branch, and open one draft PR against "main" for review exposure.
>
> Restrictions: No modifications outside the two-file allowlist. No integration with existing runtime modules, no live backend or provider calls, no external network requests in tests, and no changes to "CONFIGURATION_VERSION", existing schemas, configuration files or workflows. Do not mark the PR ready, enable auto-merge, merge, release or close out the work.
>
> Preserve the test results, revision identifiers, environment details, and exact assurance limitations. If scope expands, the baseline changes materially, or verification reveals a blocking failure, stop and report rather than extending authority.
>
> This grant is single-use and expires when the initial reviewable Slice 1 candidate is published. Implementation acceptance and all later stages require separate approval.

P1(a) is the read-only plan's option to include `GuardedTransport` and its adapter-level
tests in slice 1. Exercised in
`5d7264547e9e5839a2faff0f9ca3dce403d9d916`, published as draft
[PR #187](https://github.com/coreytshaffer/TriageCore/pull/187). Under its own terms the
grant expired at that publication.

### Slice 1 corrective grants (four; each exercised; all exhausted)

Each corrective grant named the same two files, one commit pushed to
`claude/cr-135-slice1-destination-policy`, a PR #187 description update, and the PR kept
as a draft.

| # | Review it answered | Grant | Exercised in |
|---|---|---|---|
| 1 | Implementation review at `5d72645`: configuration precedence; transport-policy floor and enforcement | "Grant the corrective fix for the same two files", approving the scope proposed in the preceding session message (the two fixes, their regression tests and parity grid, and the PR description correction) | `c2281573bb7402dbb467a8ea9485b8e49149c988` |
| 2 | Corrective review at `c228157`: transport-policy immutability | "Grant the corrective fix for the same two files", approving the proposed freeze-on-construction fix, policy-digest recheck and regressions | `412dbf7d8bdac7e01cca4a9676fcb8b08b9dc6dc` |
| 3 | Review at `412dbf7`: binding allowlist; session headers and cookies; latched `verify_integrity` | "Grant the corrective fix for the same two files", approving the proposed binding/policy intersection, standalone request preparation, seal extension and latched integrity check | `fc02328a0eda407a4afbee7850adcf5ff05b8b5a` |
| 4 | Changes requested at `fc02328`: inspection failures did not latch a refusal | Recorded verbatim below | `149aa8e4d01e19f5c9e4f791822613f9402b978c` |

The quoted text in rows 1–3 is the operator's whole instruction. The scope descriptions
are this record's summary of the proposal each instruction answered, not quotations.

Corrective grant 4, recorded verbatim:

> For CR-135 Slice 1, authorize one corrective implementation cycle based on "fc02328" on "claude/cr-135-slice1-destination-policy".
>
> Writable file allowlist:
>
> - "triage_core/destination_policy.py"
> - "tests/test_destination_policy.py"
>
> Implement the proposed inspection-failure repair:
>
> 1. Cover session-policy conformance, fingerprinting, and policy-digest inspection. Inspection failures must latch "transport_settings_changed".
> 2. Cover owner-identity inspection, including reading and normalizing "base_url". Inspection failures must latch "destination_binding_mismatch".
> 3. Preserve refusals already raised and latched by the guard. Catch "Exception" at these inspection boundaries; do not catch "BaseException" or extend this handling around adapter I/O.
> 4. Preserve safe error provenance: refusal messages must not include raw inspected values or underlying exception messages.
>
> Add regressions for the six reported session-state replacements and the raising owner property, each at S2, before the first send, and between discovery and generation. Assert the expected reason code, latched state, zero additional sends, and continued refusal after restoring valid state.
>
> Keep the existing binding intersection, request isolation, policy immutability, digest behavior, and refusal semantics intact. Do not add reason codes or integrate the module into runtime.
>
> Run the focused suite and appropriate regression checks. Report any full-suite failures with their baseline comparison.
>
> Publication authority is limited to:
>
> - One corrective commit containing only the two allowlisted files.
> - Pushing that commit to the existing branch.
> - Updating PR #187’s description with the correction and evidence.
> - Keeping the PR in draft.
>
> Stop afterward and report the commit SHA, both file hashes, and verification results. If the branch head differs from "fc02328", establish and report the difference before making changes.
>
> This grant does not resolve the "backend_protocol_unsupported" amendment, the earlier review-condition reconciliation, or the parser deviation. It grants no implementation acceptance, ready-for-review transition, merge, release, closeout, or Slice 2 work.

### Slice 1 implementation acceptance (pinned to `149aa8e`)

On 2026-10-18 at 22:25 UTC (15:25 PDT), after reviewing both files at `149aa8e`, the
operator wrote, recorded verbatim:

> Implementation granted

Asked to confirm what this recorded, the operator selected these answers:

- **Decision:** "Accept Slice 1 at 149aa8e".
- **Open review items:** "Accept code, keep items open".
- **Where recorded:** "Update PR #187 description".

The acceptance is recorded in the PR #187 description, and here by reference.

- **Pinned to `149aa8e4d01e19f5c9e4f791822613f9402b978c`.** It covers exactly
  `triage_core/destination_policy.py` (1053 lines, SHA-256
  `dda7ebf75556163717b9aa852e653a59947f0d9dc14a17522cfc6cdb1ced9275`) and
  `tests/test_destination_policy.py` (1493 lines, SHA-256
  `2af4c049bad6413c64fb4ef066927e6b185462746431af01d348e0cfff60f6fa`).
- **Verification evidence cited by PR #187 at that commit:**
  - 465 focused tests passed on Python 3.12.3 and 3.11.17 (`requests` 2.34.2);
  - full suite 24 failed / 2172 passed / 77 skipped, with the failure set identical to the
    `ed9e165` baseline (environmental: 11 `tkinter`, 13 `test_build_review_cli`);
  - GitHub Actions run `39171753206`: `pytest` 3.10, 3.11 and 3.12 and `windows_executor`
    passed.
- **Items kept open at acceptance:** the reason-code amendment, now approved as design
  amendment 1, and the review-condition reconciliation, now carried by the checklist
  below.
- **No downstream authority.** It granted no ready-for-review transition, merge, release,
  closeout or slice 2 work.

The operator later confirmed, recorded verbatim:

> Your implementation acceptance stands. The next decisions concern the remaining
> design/review reconciliation and eventual merge authority. No additional repair is
> required for the inspection-failure finding.

### Design amendment 1: `backend_protocol_unsupported` (approved 2026-10-18)

This is a separate design decision. It is **not** part of the design acceptance at
`a0bbd93`, which remains pinned and unchanged. The operator approved, recorded verbatim:

> Approve adding "backend_protocol_unsupported" to CR-135’s closed reason-code vocabulary, matching its existing behavior at "149aa8e": refuse unsupported backend protocols before network contact. This authorizes no additional protocol, endpoint, route, or fallback.

Background: the PR #187 implementation review at `5d72645` recommended keeping the code,
recorded verbatim:

> `backend_protocol_unsupported`: I recommend retaining this new reason code. It is more
> informative than treating an unknown protocol as a malformed endpoint. However, it
> extends CR-135's accepted closed vocabulary and should receive an explicit owner design
> amendment before implementation acceptance.

The behaviour approved is the behaviour at `149aa8e`:

- **Local routes.** `bind_route_endpoints` refuses a `local_fast` or `local_heavy` member
  whose backend type does not map to a supported local protocol. The supported types are
  the ones `create_backend` already recognizes (`backends.py:422-439`), mapped to the two
  protocols in the protocol table:
  - Ollama: `ollama`, or an empty type, which `create_backend` treats as `ollama`;
  - OpenAI-compatible: `lmstudio`, `lm_studio`, `vllm`, `llama.cpp`, `llamacpp`,
    `custom`.

  The member's endpoint is normalized first, so an invalid endpoint reports its endpoint
  code instead.
- **Request URLs.** `allowed_request_urls` refuses a protocol absent from the protocol
  table.
- **Refusal class.** A binding-time (S1) pre-contact refusal: zero requests, and once
  integrated, exit 2 for the whole attempt under D4, with no fallback.

The amendment adds no protocol, backend type, endpoint, profile, route or fallback, and
changes no other reason code. The closed vocabulary with this amendment is listed under
Design, Reason-code vocabulary.

### Reconciliation grant (this commit)

On 2026-10-18 at 22:32 UTC (15:32 PDT) the operator wrote "Authorize one bounded CR-135
reconciliation pass." The grant's scope, as granted:

- this document as the sole writable repository file, in one documentation-only commit on
  `claude/cr-135-slice1-reconciliation`, branched from verified `main@ed9e165`, without the
  slice 1 implementation commits;
- one draft PR for that branch;
- a title-only update to PR #187, which stays a draft;
- an annotated preservation tag for `a0bbd93`.

It granted no code change, ready-for-review transition, merge, release, closeout or slice
2 work.

### Accepted-design preservation

- **Tag:** `cr-135-design-accepted-a0bbd93`, annotated, authorized by the reconciliation
  grant.
- **Target:** exactly `a0bbd93fd4b82167c07e901dbdc7feac22847975`.
- **Annotation:** identifies proposal and design acceptance only. It is not a release
  tag, and it carries no implementation, merge, release, deployment or closeout
  authority.
- **Why:** after the squash merge, `a0bbd93` is reachable only from
  `claude/cr-135-governed-backend-destination-policy`. The tag keeps it reachable if that
  branch is ever deleted.
- **Branches:** neither existing CR-135 branch is deleted by this grant.
- **Publication:** the tag's publication state is reported in the reconciliation PR, not
  in this record.

### Follow-up: owner-type regression coverage (open)

At `149aa8e`, 21 mutation probes were run against the guard, and PR #187 records one
survivor:

- **The survivor:** removing the owner-type comparison (`type(owner) is
  self._state.owner_type`) in `GuardedTransport._check_owner_identity` is not detected by
  any test.
- **The check works.** It is present and enforced. The gap is in test coverage, not
  behaviour.
- **Reachability:** reaching it needs a write to the private `_state.owner`.
- **No finding reopened.** It does not reopen the repaired inspection-failure finding.

A regression test for it needs a future grant naming `tests/test_destination_policy.py`.
No test is added, and the backlog is not edited, in this reconciliation.

## Slice 1 Review-Condition Checklist (reconciliation, 2026-10-18)

### Sources

| ID | Source | Availability |
|---|---|---|
| R-D | This design at `a0bbd93`: slice 1 description, normalization and base-path tables, guarded transport, refusal classes, propagation, F-series | In this document |
| R-G | Slice 1 implementation grant (verbatim above): allowlist, restrictions, pre-commit checks, and five named condition categories | In this document |
| R-P | The read-only slice 1 plan, sections 2 to 6, which the grant's P1(a) refers to | In the session that carried out this work. Not in the repository |
| R-V | The operator's slice 1 review, which established "the additional parsing, method-and-URL binding, error-provenance, runtime-seal and test-evidence conditions" | **Unavailable** (gap E-1) |
| R-C | Operator reviews at `5d72645`, `c228157`, `412dbf7`, `fc02328`, and corrective grant 4 | Findings in the PR #187 description; grant 4 verbatim above |

### Checklist

Test names refer to `tests/test_destination_policy.py` at `149aa8e`.

| # | Requirement | Source | Implementation at `149aa8e` | Verification evidence | Status |
|---|---|---|---|---|---|
| C1 | Only the two allowlisted files change | R-G | — | `git diff --name-only ed9e165 149aa8e` lists exactly the two files; PR #187 file list | Met |
| C2 | Not integrated; imports only the standard library and `requests` | R-D (slice 1), R-G | No `triage_core` module imports it | `test_module_imports_only_stdlib_and_requests` (AST); `git grep destination_policy -- triage_core` | Met |
| C3 | `CONFIGURATION_VERSION`, existing schemas, configuration files and workflows unchanged | R-G | — | C1 scope | Met |
| C4 | No external network in tests | R-G | Recording adapter on the guard's own session | Autouse socket-blocking fixture | Met |
| C5 | **Parsing:** strict normalization, validated never repaired, per the endpoint-normalization and base-path tables | R-D, R-G category "parsing" | `normalize_endpoint`, `_split_endpoint`, `_parse_host`, `canonicalize_base_path` | `test_rejected_endpoint_forms_have_named_codes`, `test_noncanonical_base_paths_are_rejected`, `test_canonical_base_paths`, `test_trailing_slash_is_the_only_normalization_and_is_equivalent`, LAN, remote and cloud tests | Met for the design tables |
| C6 | **Parsing:** preference for standard-library URL tokenization followed by strict validation | R-V, as reported in the PR #187 implementation review | Purpose-written tokenizer (`_split_endpoint`), not `urllib.parse.urlsplit` | — | **Deviation, recorded below; accepted by the operator as a recorded deviation at `149aa8e` (U-1)** |
| C7 | **Method-and-URL binding:** closed per-protocol request set; exact prepared method and URL match; no prefix matching; binding allowlist and policy both enforced | R-D (S3, protocol table), R-G, R-C (`412dbf7` finding 1) | `allowed_request_urls`; guard permits the intersection of `binding.allowed_requests` and `policy.permitted_calls` | `test_allowed_request_urls_are_exact_and_closed`, `test_guard_refuses_collisions_and_off_set_urls_before_send`, `test_guard_compares_the_url_actually_sent`, `test_guard_enforces_the_binding_allowlist_as_well_as_the_policy`, `test_guard_enforces_a_policy_that_removes_post`, `test_guard_cloud_route_permits_only_generation_on_the_canonical_url` | Met at unit level |
| C8 | **Error provenance:** refusal type neither `RequestException` nor `ValueError`; messages carry the reason code and safe label only; inspection refusals carry no chained exception or inspected value | R-D (Propagation), R-G, grant 4 item 4 | `DestinationPolicyError`; refusals raised after the inspection `try` | `test_destination_error_is_not_a_swallowable_type`, `test_refusal_messages_never_carry_raw_input`, `test_inspection_failure_latches_and_stays_refused_after_restore` | Met. The engine re-raise is slice 2 |
| C9 | **Runtime seal:** deterministic policy digest kept separate from the per-instance runtime seal; session checked against both before every send | R-D (correction 10, F12), R-G | `TransportPolicy.sha256`; `_session_fingerprint` and `_seal`; `_check_session` | `test_policy_digest_is_independent_of_runtime_objects`, `test_digests_are_identical_across_processes`, session-mutation tests at three stages | Met at unit level |
| C10 | Owner-identity check before every send, independent of URL equality (F7(g)) | R-D (correction 9) | `_check_owner_identity` | `test_guard_owner_identity_mismatch_refuses_even_with_allowed_url`, `test_guard_owner_mutation_before_first_send_is_refused` | Met; coverage gap on the owner-type comparison (Follow-up) |
| C11 | Sealed surface: forbidden per-call arguments refused; redirects never followed; 3xx is a late refusal; environment proxy, `.netrc` and CA variables ignored | R-D (S3, F8, F9 at unit level) | Keyword allowlist; `adapter.send(..., proxies={}, cert=None)` | `test_guard_refuses_behaviour_changing_call_arguments`, `test_guard_redirects_on_generation_are_late_refusals`, `test_guard_redirects_on_discovery_are_late_refusals`, `test_guard_ignores_environment_proxies_netrc_and_ca_bundle` | Met at recording-adapter level only. Real-Requests proof is F8/F9 in slice 2 |
| C12 | Send path | R-P (planned `session.send(prepared, allow_redirects=False)`) | Direct `adapter.send`: `Session.send` runs redirect resolution even with redirects disabled, and with `max_redirects=0` that raises `TooManyRedirects` instead of the guard's late refusal | Redirect tests above | Deviation from the plan. The PR #187 implementation review judged it "Acceptable as a proposed Slice 1 implementation strategy", with real Requests behaviour still requiring F8/F9 in slice 2 |
| C13 | Effective-configuration precedence matches the runtime | R-D (refinement C), R-C (`5d72645` finding 1) | `resolve_effective_configuration`, `_env_then_toml`, `_backend_fallthrough` | `test_empty_base_url_variable_beats_toml_and_falls_through_to_backend_env`; parity grid `test_*_resolution_matches_config_and_create_backend` | Met |
| C14 | Policy may only tighten the v1 floor, and is deeply immutable | R-C (`5d72645` finding 2, `c228157`) | `TransportPolicy.__post_init__`, `_freeze_calls`; policy digest rechecked by the guard | `test_transport_policy_cannot_weaken_the_v1_floor`, `test_policy_ignores_caller_mutation_after_the_guard_is_built`, `test_policy_mutation_before_the_guard_cannot_widen_the_floor`, `test_policy_inner_list_mutation_cannot_widen_the_floor`, `test_guard_refuses_every_send_after_policy_tampering` | Met |
| C15 | No session headers, cookies, auth or params reach a request | R-C (`412dbf7` finding 2) | Standalone `Request(...).prepare()` with default headers captured once; headers and cookies in the seal | `test_guard_never_inherits_session_state_even_if_the_seal_were_bypassed`, `test_guard_headers_match_an_ordinary_session_and_keep_call_headers` | Met |
| C16 | Refusals latch; `verify_integrity` reports a latched refusal; uninspectable state latches and stays refused after restore | R-C (`412dbf7` finding 3, `fc02328` P2), grant 4 items 1–3 | `_refuse`; inspection boundaries catch `Exception` only; adapter I/O not wrapped | `test_verify_integrity_reports_a_latched_refusal`, `test_inspection_failure_latches_and_stays_refused_after_restore` (21 cases, all failing against the `fc02328` module) | Met |
| C17 | Closed reason-code vocabulary | R-D, design amendment 1 | `REASON_CODES`: the 17 codes at `a0bbd93` plus `backend_protocol_unsupported` | `test_reason_code_vocabulary_is_closed_and_complete` | Met with amendment 1 |
| C18 | **Test evidence:** focused tests, full suite, diff check and import isolation before commit; results, revisions, environment and assurance limits preserved | R-G, R-P (section 6) | — | PR #187 Verification and Assurance limits sections | Met |
| C19 | Fixture coverage for slice 1: F3, F4 and F12 at unit level, plus normalization positive controls | R-D (slice 1) | — | C5, C9 tests; additional unit- and adapter-level cases for F1, F2, F5, F6, F7(e)/(g), F8, F9, F10, F11 | Met at unit level. These are not the F-series integration results that implementation acceptance of the governed path requires |

### Parser deviation (C6)

The source for C6 is the PR #187 implementation review at `5d72645`, recorded verbatim:

> My preceding Slice 1 review did establish additional implementation conditions,
> including a preference for standard-library URL tokenization followed by strict
> validation. The custom parser is a deviation from that preference, not automatically a
> blocker; record its rationale rather than stating that no separate review conditions
> existed.

The read-only plan had already proposed a purpose-written parser. The implementation
kept it as an implementation choice. Standard-library tokenization followed by strict
validation of the raw substrings could also meet the design tables, because
`urlsplit(...).netloc` preserves the host as written (only `.hostname` lowercases it). The
purpose-written parser was chosen because:

- validation runs on the raw string with no normalizing step, so nothing has to avoid
  accessors such as `.hostname`;
- `urlsplit` defers port errors: an out-of-range or non-decimal port raises only when
  `.port` is read;
- `urlsplit` and `requests` can disagree about the host. For
  `http://127.0.0.1\@evil.example/v1`:
  - `urlsplit` reports `evil.example`;
  - urllib3, used by `requests`, reports `127.0.0.1`;
  - `requests` prepares `http://127.0.0.1/%5C@evil.example/v1`;
  - the purpose-written parser refuses it as `endpoint_credentials_embedded`.

  Observed on Python 3.12.3 with `requests` 2.34.2.

Neither approach is claimed to lose information the other keeps. (Corrected on
2026-10-18 in the PR #188 correction cycle. The rationale first recorded at `4601191`
stated that `urlsplit` lowercases the host. That holds only for `.hostname`, as the
operator reproduced on Python 3.12.14.)

The deviation stays a deviation. Neither this record nor implementation acceptance turns
it into compliance. The operator accepted it as a recorded deviation under U-1.

### Evidence gap E-1: the operator's slice 1 review

- **What is missing:** the text of the operator's slice 1 review. It was written between
  the read-only slice 1 plan and the slice 1 implementation grant on 2026-10-18.
- **Where it was looked for:** this repository at `ed9e165`, the PR #186 and PR #187
  descriptions and comments, and the session that carried out the work. It is in none of
  them.
- **What is known of it:** the five condition categories the grant names (parsing,
  method-and-URL binding, error-provenance, runtime-seal and test-evidence), and the
  tokenization preference quoted under Parser deviation.
- **What C5–C19 show:** they map the requirements that can be identified to evidence.
  They do **not** establish that the review's other, unseen conditions are satisfied.
- **Nothing is waived.** This record does not waive those conditions.
- **Retrieval:** the operator's later retrieval recovered summaries of the review, not
  its original full text.
- **Disposition (U-2):** E-1 is kept as a historical evidence gap. C1–C19 and the
  recorded deviations (C6, C12) are adopted as the prospective review baseline for the
  slice 1 implementation. The unseen conditions are not claimed to have been satisfied.

### Decisions returned for review

At `4601191` this subsection was headed "Unresolved decisions (returned for review)".
It listed U-1 to U-3 as open, and stated for U-2 that "This record makes neither choice".

| ID | Decision | Options as returned at `4601191` | Status |
|---|---|---|---|
| U-1 | Parser deviation (C6) | Accept the purpose-written parser as a recorded deviation; or require standard-library tokenization with strict validation, under a new grant naming the two slice 1 files | **Resolved 2026-10-18:** custom parser accepted at `149aa8e` as a recorded deviation, with its rationale corrected; no parser rewrite |
| U-2 | Evidence gap E-1 | Supply the review text for reconciliation against C1–C19; or decide explicitly how its unseen conditions are to be treated | **Resolved 2026-10-18:** E-1 kept as a historical gap; C1–C19 and the recorded deviations adopted as the prospective review baseline; unseen conditions not claimed satisfied |
| U-3 | Owner-type regression coverage | Schedule the test under a future grant naming `tests/test_destination_policy.py`, or carry it into slice 2 | **Open.** The operator recommended a separate test-only cycle before merging PR #187, then review of the resulting head. Not yet granted |

**Decision record for U-1 and U-2.** On 2026-10-18 at 22:56 UTC (15:56 PDT) the
operator wrote, recorded verbatim:

> Grant the PR #188 correction cycle and record U-1 and U-2

That instruction adopted the dispositions the operator had recommended in their
documentation review of PR #188 at `4601191`, recorded verbatim:

> U-1: parser deviation	Accept the custom parser at 149aa8e as a recorded deviation after correcting its rationale. No parser rewrite needed.

> U-2: missing review	Retain E-1 as a historical evidence gap. Explicitly adopt C1–C19 and the recorded deviations as the prospective review baseline, without claiming unseen conditions were satisfied. Retrieval recovered summaries, not the original full text.

The same review recommended, recorded verbatim, and this record does not adopt as a
decision:

> U-3: owner-type test	Add the regression in a separate test-only cycle before merging PR #187, then review the resulting head. It does not reopen the resolved inspection-failure finding.

Neither decision grants anything downstream. Neither grants a parser change, a test
change, merge, release, closeout or slice 2 work. A test-only commit for U-3 would move
PR #187's head past `149aa8e`, and that head would need its own review and acceptance.

The test file at `149aa8e` still describes `backend_protocol_unsupported` in a comment as
"flagged for implementation-acceptance review". The comment is now out of date. It is
code-adjacent and outside this grant, so it is left for the next grant that names that
file.

## Owner Decisions

| # | Decision | Effect in this design |
|---|---|---|
| D1 | Reject `localhost` | The device-local profile accepts only the literal addresses `127.0.0.1` and `[::1]`. Defaults move to those literals. Any hostname, `localhost` included, gets the named compatibility refusal `hostname_not_literal_loopback`, with a fix hint. |
| D2 | Require loopback | Every network-capable `local_*` route in governed `tc run` (`local_fast`, `local_heavy`) must bind to a `device_loopback` endpoint, whatever the privacy class. `human_handoff` and `deterministic` contact no network and are unaffected. Legacy and direct paths stay outside the first assurance claim (see Paths Outside the First Assurance Claim). |
| D3 | Defer trusted LAN | There is no LAN profile in v1. A LAN destination would widen the built-in profile. It needs its own authorized expansion and cannot be added as a configuration entry. |
| D4 | Fail the whole attempt | Any destination-policy or configuration-integrity violation ends the attempt with exit 2. It is never treated as an unavailable route and never falls back to another envelope member, cloud included. A violation detected before the attempt's first request (S1, S2, the pre-invocation check, or an S3 pre-send check) is a **pre-contact refusal**: zero requests. A violation detected after one or more permitted requests (a mutation caught between model discovery and generation, or a redirect answer from the bound endpoint) ends the attempt with zero *additional* requests after detection, and the complete count and identities of the requests already permitted are recorded (see Refusal Classes). |
| D5 | Bind into the configuration digest | `CONFIGURATION_VERSION` is bumped. The decision's configuration digest binds canonical, route-indexed endpoint identities and the transport policy. Revalidation is a separate step that can be tested on its own. |
| — | HTTPS-only remote transport | Every `remote_cloud` identity requires `https` with TLS verification. |
| — | Separate destination kinds | `backend_endpoint`, `external_recipient` (CR-134), and `local_staging` (CR-134) are distinct kinds. They share policy versioning and provenance; claims are specific to each kind. |

## Problem Statement

A governed route can be labelled local without its actual network destination being
bound to the decision. The operator independently confirmed this finding. It is a
static design gap. It is not evidence that protected content was transmitted anywhere,
and this CR claims no such incident.

### Established facts (at `1dc9b88`)

1. **No endpoint in any binding.** `run_plan.configuration_digest`
   (`run_plan.py:185-203`) digests the cloud enabled/model settings, the local backend
   *type*, and policy versions. It includes no endpoint URL. The decision seam
   (`tc_cli.py:1143`, which reads config at `run_plan.py:369,373`) never reads the local
   base URL.
2. **The URL is read after the decision, by a separate read.** The client is built at
   `tc_cli.py:1284-1291` from a second read of `default_config`. Effective precedence
   for the local URL: `TRIAGE_BASE_URL` env > `triagecore.toml [backend].base_url` >
   backend-specific env (`TRIAGE_OLLAMA_BASE_URL`, `TRIAGE_SUPERVISOR_BASE_URL`) >
   hard-coded `http://localhost:<port>` preset (`config.py:24-33,51-81`;
   `backends.py:393-461`). `Config.get_*` reads the environment live on every call.
3. **Locality is a label.** The local-only guard (`client.py:283`) checks the route name.
   `_member_binding` (`runtime_observation.py:175-210`) receives `local_backend_type` as
   a name only.
4. **The revalidation checks no endpoint.** `_verify_governed_inputs`
   (`client.py:533-656`, digest recheck at `:614-624`) recomputes the same
   endpoint-free digest from a third config read.
5. **The cloud backend is built late.** It is constructed only inside
   `_execute_cloud_task` (`client.py:739-744`), from a live read of
   `get_qwen_base_url()`: `TRIAGE_QWEN_BASE_URL` env > TOML >
   `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`. Any URL is accepted.
6. **Requests go straight to the network.** Backends call module-level `requests.get`
   and `requests.post` directly (`backends.py:76,114,147,193,229,266,305,336,367`). The
   first contact on the local governed path is `resolve_model`'s GET (`/models` or
   `/api/tags`) when the model is an auto sentinel (`backends.py:10`), followed by the
   generation POST, streaming or not. `base_url` and `model` are mutable dataclass
   fields; `model` is mutated at `client.py:490` and restored afterwards.
7. **A second endpoint hides in `ping`.** `OllamaBackend.ping` contacts
   `TRIAGE_SUPERVISOR_BASE_URL` (LM Studio) before its own URL (`backends.py:359-367`,
   `:69-80`). `ping` is not invoked on the governed `run_task` path.
8. **Bad config fails open.** A TOML parse failure prints a warning and returns `{}`
   (`config.py:13-21`), so execution silently uses defaults. The config root is the
   current directory. Separately, importing `sustainability.py` calls `load_dotenv()`,
   which loads a `.env` file into the process environment. That import was not observed
   among the direct imports of the governed path.
9. **Capability evidence names no endpoint.** CR-DD-013 probe records carry a redacted
   `base_url` (`local_backend_probe.py:89`), but `capability_evidence` never compares it
   with the executing endpoint (`capability_evidence.py:361-405`).
10. **`requests` defaults are unconstrained.** With default `trust_env`, the installed
    `requests` (2.34.2 observed; requirement `>=2.28.0`) can honour proxy environment
    variables, `.netrc`, and CA-bundle variables, and follows redirects for POST. A 307
    or 308 re-sends the body to the new location. These are library defaults and must be
    confirmed by fixture (see Acceptance Criteria), not assumed.
11. **Nothing persists the configuration version.** At `1dc9b88`,
    `configuration_version` and `configuration_sha256` appear in `governed_decision.py`,
    `run_plan.py` and `client.py`, and in three test files. No artifact module or schema
    in `triage_core/` or `schemas/` references them.
12. **The engine converts every backend exception into a handoff.**
    `TriageEngine.execute_task` catches `requests.exceptions.Timeout`, `ValueError`, and
    any other `Exception` around `backend.generate` and returns a `handoff_required`
    result carrying the exception text (`engine.py:98-121`). Backends wrap
    `RequestException` as `BackendUnavailableError` with the request URL in its message
    (for example `backends.py:155-156`).

## Objective

Make governed `tc run` bind the actual network endpoint identities of every
network-capable member of the decision's envelope, together with the transport policy,
into the decision. Then enforce, at the real network sink, that the attempt sends
requests only to those identities, with a refusal before any request whenever policy or
binding fails.

## Required Refinements (owner, 2026-10-18)

- **A. Constrain cloud endpoints.** An allowlist *restricts* the authority a configurable
  remote URL currently provides. The first governed profile binds the approved Qwen
  provider origin and API path. Any other remote destination needs explicit operator
  policy; `--allow-cloud` does not supply it.
- **B. Guard the actual network sink.** All governed model-discovery and generation
  calls, including streaming and any applicable `ping`, pass through an injected guarded
  transport. Allowed HTTP methods and paths are bound per backend protocol. Governed
  tests must exercise that transport; a module-level `requests` mock is not evidence for
  the governed path.
- **C. Freeze effective configuration once.** Governed execution refuses malformed
  configuration instead of falling back to defaults. One immutable effective-config
  snapshot is built at S1, with the winning source of each value identified. S2
  validates the actual backend instances, including the cloud backend, before its first
  request and without a second policy decision.
- **D. Trusted LAN is an authority expansion.** Keep it out of v1. A future LAN profile
  needs explicit owner approval, a separately versioned policy, and a local-network
  threat model.
- **E. Narrow the assurance claim.** See Non-Claims.

## Review Corrections (operator full-document review, 2026-10-18)

The operator read the complete document at `b057945` on PR #186 and requested revisions.
The review found the proposal sound at the problem-and-scope level and D1–D5 correctly
represented, and asked for five corrections to design and test expectations before
design acceptance. The disposition for this cycle, recorded verbatim:

> I support a single documentation-only correction cycle, confined to
> `docs/change/requests/CR-135-governed-backend-destination-policy.md` on the existing
> PR #186 branch. No other files should change, and the M03/M09a checkout should remain
> untouched.

> These are corrections to the documented design and test expectations, not permission
> to implement it.

| # | Requested correction | Where it is addressed |
|---|---|---|
| 1 | F7(a): an environment change after S1 must not change the bound backend; prove the frozen destination stays authoritative | Effective configuration snapshot; F7(a) |
| 2 | F7(c): a backend swapped after S2 could bypass the guard; ensure execution uses only the verified instance, and test mutation between model discovery and generation | Verified execution set; pre-invocation check; F7(c), F7(g) |
| 3 | F8–F10: the tripwire must not reject the approved session; F8 and F9 must exercise real Requests session behaviour | Fixture harness; F8, F9, F10 |
| 4 | D4 zero-call wording: distinguish pre-contact refusals from late refusals | D4; Refusal Classes; fixture assertions; supported claim |
| 5 | Endpoint path canonicalization | Base-path canonicalization; exact-URL request check; F3, F10 |

One further item was found while making correction 4 and is recorded rather than left
implicit: the engine converts every backend exception into a handoff (fact 12), so a
guard refusal would today surface as exit 3. The Propagation requirement under Refusal
Classes, and `triage_core/engine.py` in the proposed slice 2 file list, address it.

### Second review, at `55a3f32`

The operator's design review at `55a3f32` found the earlier corrections substantially
resolved and confirmed the engine exception-propagation finding. It requested three
further corrections before design acceptance, plus two editorial changes:

| # | Requested correction | Where it is addressed |
|---|---|---|
| 6 | Transport mutation after S2: identity of the transport object is not enough, because the same session's `trust_env`, proxies, TLS settings or adapters could change. Make effective settings immutable, or revalidate before every send, with `transport_settings_changed` and zero additional sends. | Guarded transport: sealed wrapper and per-send settings revalidation; F7(e) |
| 7 | Verified execution set → engine: the engine calls `self.backend.generate`; specify how it receives the verified instance, and confirm the object actually executing generation is the verified one | Per-invocation engine; F7(c), F7(d) |
| 8 | Windows coverage: the mandatory Windows group runs a fixed set of three test files, so a new test file would not run there | Windows F9 placement; Design Assumptions; slice 2 file list |
| E1 | Say explicitly that `/v1` and `/v1/` are equivalent after the permitted trailing-slash removal | Base-path canonicalization |
| E2 | F8's one-request POST cases need a fixed model, so model discovery does not change the expected count | F8 |

One consequence of correction 7 is recorded rather than left implicit: model discovery
and generation both happen inside a single `generate` call (`backends.py:136-138`,
`:294-296`), so no pre-invocation check sits between them. F7(g), a mutation between
discovery and generation, is therefore caught by S3's per-send check, not by the
pre-invocation check as `55a3f32` stated. F7(g) is corrected accordingly.

### Third review, at `44faec2`

The operator's design-acceptance review at `44faec2` found corrections 6–8 addressed in
substance, and judged the proposal technically acceptable. It did not recommend design
acceptance at `44faec2`, because two items bear directly on the S3 enforcement
invariant:

| # | Requested correction | Where it is addressed |
|---|---|---|
| 9 | F7(g) and URL capture: at `1dc9b88`, both `generate` implementations build the generation POST URL **before** calling `resolve_model` (`backends.py:136-138`, `:294-296`). A `base_url` mutated after the discovery GET therefore does not change the already-built POST URL, so S3's exact URL check alone would pass. S3 must also revalidate the backend's current endpoint identity before each send, and the test must show this independently of URL equality. | Guarded transport: owner-identity check before every send; Pre-invocation check paragraph; F7(g) |
| 10 | Policy digest versus runtime seal: adapter object identities are process-specific and do not exist when S1 forms the decision, so they cannot enter the deterministic `transport_policy_sha256`. Verify the live session against both the canonical policy and a construction-time runtime seal. | Guarded transport: policy digest and runtime seal; F12 |

This also corrects the statement recorded above for correction 7. S3's exact URL check
does **not** catch an in-flight F7(g) mutation, because the POST URL was built before
the mutation. The owner-identity check (correction 9) does.

## Design

### Destination kinds

One policy family, `triagecore.destination_policy`, with closed, separately versioned
kinds:

| Kind | Owner | Defined by | Claim it supports |
|---|---|---|---|
| `backend_endpoint` | This CR | Built-in profiles below | The governed transport attempted requests only to bound endpoint identities |
| `external_recipient` | CR-134, unchanged | CR-134 policy: provider/surface allowlist, data-class ceiling, TTLs, size cap, operation vocabulary | Eligibility bound to an *intended* recipient. Not proof of where the operator pasted anything. |
| `local_staging` | CR-134, unchanged | CR-134 Staging and Destination Security | Bytes staged locally. Not delivery, not egress. |

Rules that hold across kinds:
- No URL locality check is ever applied to a chat recipient.
- An approved recipient is never authority for a backend URL.
- An endpoint allowlist never satisfies a recipient binding.

### Built-in endpoint profiles (v1)

Profiles are in-code constants, each with a version and a digest of its canonical
serialization. **No operator file can add an endpoint in v1.** A request (CLI flag or
proposal) may tighten a profile and can never enlarge one.

| Profile | Locality class | Identity | Allowed for |
|---|---|---|---|
| `device_local_loopback.v1` | `device_loopback` | Scheme `http` or `https`; host exactly `127.0.0.1` or `::1` (written `[::1]`); explicit or scheme-default port; normalized base path | `local_fast`, `local_heavy` |
| `qwen_dashscope_intl.v1` | `remote_cloud` | `https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1` exactly | `cloud_primary`, `cloud_secondary`, only when the decision's envelope already contains that route and cloud execution is enabled |

`trusted_lan` is a reserved, unsupported class in v1. A LAN address gets
`trusted_lan_not_in_profile`.

A configured cloud URL that does not equal the approved identity gets
`cloud_endpoint_not_approved`. This check runs only when the envelope contains a cloud
route. Otherwise the cloud URL is recorded as `not_bound` and has no effect.

### Endpoint normalization (closed)

| Input | Outcome |
|---|---|
| Missing scheme or host; unparsable URL | `endpoint_malformed` |
| Scheme other than `http`/`https`; `http` on a `remote_cloud` identity | `endpoint_scheme_not_permitted` |
| Userinfo (`user:pass@`) | `endpoint_credentials_embedded` |
| Query string or fragment | `endpoint_query_or_fragment` |
| Any hostname on a local route, including `localhost` (D1) | `hostname_not_literal_loopback` |
| Non-canonical IPv4 (`127.1`, `0x7f.0.0.1`, `2130706433`, `0177.0.0.1`), `0.0.0.0`, other `127.0.0.0/8` addresses, IPv4-mapped IPv6 (`::ffff:127.0.0.1`), zone IDs, percent-encoded or IDNA hosts, trailing dots | `endpoint_deceptive_identity` |
| A host that strict parsing of the literal string accepts as a non-loopback address | `endpoint_not_device_local` (or `trusted_lan_not_in_profile` for private ranges) |
| Remote host not exactly equal to an approved remote identity (lowercase ASCII, no trailing dot) | `cloud_endpoint_not_approved` |

The host is parsed from the literal string with strict address parsing, so the OS's
lenient IPv4 parsing never gets a say. The device-local profile involves no DNS lookup.
For `remote_cloud`, the identity is the origin name plus TLS certificate verification
against that name, using the library's bundled trust store, since environment CA
variables are ignored (see transport). DNS resolution of the remote name is not pinned.

The canonical identity is `scheme://host:port/base-path`. The port is always explicit.

### Base-path canonicalization (correction 5)

The configured base path is **validated, never repaired**. Ambiguous forms are rejected
rather than rewritten into an equivalent, so no two accepted configurations can denote
the same request path.

| Base-path input | Outcome |
|---|---|
| Empty, or a single `/` | Canonical empty base path |
| One trailing `/` (e.g. `/v1/`) | Removed; this is the only normalization applied. `/v1` and `/v1/` are therefore intentionally equivalent and produce the same canonical identity and digest |
| Segments of RFC 3986 unreserved characters only (`A–Z a–z 0–9 - . _ ~`) | Accepted as written; case is preserved and compared exactly |
| Dot segments (`.` or `..`), anywhere | `endpoint_path_noncanonical` |
| Any percent-encoding (`%2F`, `%5C`, `%2E`, or any other `%XX`) | `endpoint_path_noncanonical` |
| Backslash, repeated separators (`//`), empty interior segments, more than one trailing `/` | `endpoint_path_noncanonical` |
| Any other character (including `;`, `:`, `@`, whitespace, non-ASCII) | `endpoint_path_noncanonical` |

The approved Qwen identity's base path, `/compatible-mode/v1`, satisfies these rules.

At binding, each route's **closed set of allowed request URLs** is computed: canonical
identity followed by `/` and an exact suffix from the protocol table (for example
`http://127.0.0.1:11434/api/chat`). At S3, the guard compares the **prepared request URL**
(the URL the session would put on the wire, after Requests' own preparation) by exact
string equality against that set. No prefix or `startswith` matching is used anywhere,
so `/v1evil/...`, `/v1/../x`, `/v1//chat/completions` and `/V1/...` never match `/v1`.
A prepared URL carrying a query string, fragment, userinfo, or a different authority is
refused with `transport_request_not_permitted` before it is sent.

### Effective configuration snapshot (refinement C)

At S1, governed `tc run` builds one immutable `EffectiveBackendConfiguration`:

- **Values recorded:** local backend type, model, local URL, timeout, cloud enabled,
  cloud model, cloud URL, and whether a cloud API key is *present*. The key's value and
  any digest of it are never recorded.
- **Sources recorded:** the winning source of each value, by name only:
  `env:<NAME>`, `toml:triagecore.toml`, `backend_env:<NAME>`, `preset`, or `absent`.
- **Environment:** read once, at S1. Values that a `.env` file loaded into the
  environment earlier are indistinguishable from other environment values, and are
  recorded as `env:<NAME>`.

Failure handling:
- A configuration file that exists but cannot be parsed, or cannot be read, or that
  needs a TOML parser the runtime lacks, gives `configuration_unreadable`, exit 2. It
  never falls back to defaults.
- An absent file is not an error; its values come from `preset` and are recorded that
  way.

Every later step reads from this snapshot. The client, the local backend, and the cloud
backend are all built from it, never from a fresh `default_config` read.

**Snapshot isolation (correction 1).** Because nothing after S1 reads configuration, a
change to the environment or to `triagecore.toml` after S1 has **no effect** on the
attempt: the frozen destination stays authoritative, the changed value is never read,
and it is never contacted. This is not a mismatch and is not refused. What S2 does
detect is a *different snapshot* or a backend built from anything other than the
snapshot: a backend instance whose fields do not match the bound identity gets
`destination_binding_mismatch`.

### Binding (S1) and the configuration digest (D5)

For each network-capable member of the envelope (`preferred_logical_route` followed by
`permitted_fallback_envelope`, in order), S1:

1. normalizes and classifies that member's endpoint against its profile;
2. on any failure, ends the attempt with exit 2 and the reason code (D4); and
3. on success, records a route-indexed entry:
   `route=<name>, profile=<id>@<version>, class=<locality>, protocol=<backend protocol>,
   identity_sha256=<digest of canonical identity>`.

`configuration_digest` gains:
- one line per route-indexed entry, in envelope order;
- a `transport_policy_sha256` line; and
- a `destination_profiles_sha256` line.

`CONFIGURATION_VERSION` moves from `governed_decision_configuration.v1` to
`governed_decision_configuration.v2`. Decision identifiers and the plan digests derived
from them change value once. Because nothing persists the configuration version (fact
11), no stored artifact needs migration.

Evidence records carry a **safe label**, such as `loopback-ipv4:11434`, `loopback-ipv6:1234`
or `qwen_dashscope_intl`, plus the identity digest. They never carry a raw URL, a
credential, or a key digest.

### Backend construction and S2 revalidation

Both the local backend and, when the envelope contains a cloud route and cloud execution
is enabled, the cloud backend are **built once from the snapshot, before any request**.
`_execute_cloud_task` uses that pre-built instance and no longer calls `create_backend`
from live configuration. Building it earlier is a projection of the snapshot, not a
second policy decision: it adds no route and evaluates no policy.

S2 runs inside `_verify_governed_inputs`, before any backend call. It is a separately
testable function, `verify_destination_binding(decision, backends)`, that:

1. recomputes each bound route's canonical identity from the **actual backend
   instance's** fields (`base_url`, protocol, transport settings);
2. checks that each instance carries a guarded transport whose owner is that same
   instance, that the transport's bound identity matches, and that its session conforms
   to the canonical policy and its runtime seal; and
3. on any mismatch, raises `GovernedBindingError` with `destination_binding_mismatch`,
   `transport_not_guarded`, or `transport_settings_changed`. Exit 2, zero requests.

On success, S2 returns an immutable **verified execution set**: a mapping from each bound
route to the exact backend instance it verified and that instance's guarded transport.

**Execution uses only the verified set (correction 2).** Governed execution invokes a
backend only through the verified set. It never re-reads `self.engine.backend`, never
calls `create_backend`, and never resolves a backend by name after S2. Immediately before
each backend call (model discovery and generation alike), a **pre-invocation check**
confirms that:

- the instance about to be called is the same object (`is`) that S2 verified;
- that instance's transport is the same guarded transport object S2 verified; and
- the instance's `base_url` and protocol still produce the bound canonical identity.

Any failure gives `destination_binding_mismatch` (instance or fields changed) or
`transport_not_guarded` (transport replaced). The `model` field remains mutable by
design (`client.py:490`), because the model is not part of endpoint identity.

**How the engine receives the verified instance (correction 7).** At `1dc9b88`,
`TriageEngine.execute_task` calls `self.backend.generate` (`engine.py:32`), and the
client's engine is a long-lived attribute (`client.py:83`). Governed execution therefore
does not use `self.engine`. After S2 it constructs a **per-invocation engine**,
`TriageEngine(backend=<verified instance>, timeout_seconds=...)`, held only in a local
variable for that call. This mirrors how the cloud path already builds a call-local
engine (`client.py:756`), which now receives the pre-built, verified cloud instance. The
pre-invocation check runs immediately before that engine's `execute_task`. Because the
per-invocation engine is never stored on the client, replacing `self.engine.backend`,
or `self.engine` itself, after S2 has no path to execution: the swapped-in object is
never called.

Discovery and generation both happen inside one `generate` call
(`backends.py:136-138`, `:294-296`), so the pre-invocation check runs once per
`generate`. Both implementations also build the generation POST URL **before** the
discovery request, so a field changed between those two requests does not alter the
POST URL. Changes inside a `generate` call are caught by S3's owner-identity check
below (correction 9), not by URL comparison.

The pre-invocation check is defence in depth. S3 does not depend on it, because before
every send S3 independently checks both the owning backend's current endpoint identity
and the prepared request URL.

### Guarded transport (S3, refinement B)

Every governed backend instance receives an injected transport. Its HTTP calls go only
through that transport; no governed request may reach module-level `requests`. The
transport's settings are:

- environment trust disabled: no environment proxies, no `.netrc`, no CA-bundle
  variables;
- an explicitly empty proxy map;
- redirects disabled on every call; and
- before every send, an **owner-identity check** and an **exact prepared-URL check**
  (below) against the bound identity and the protocol table.

**Owner-identity check before every send (correction 9).** Each `GuardedTransport` is
bound, at construction and irrevocably, to exactly one backend instance (its *owner*)
and to that route's frozen canonical identity. Immediately before every send, the
transport recomputes the owner's **current** canonical identity from its live fields
(`base_url` and protocol) and compares it with the frozen identity. A mismatch is
refused with `destination_binding_mismatch`, with zero additional sends. This check is
independent of the prepared URL: it refuses even when the prepared URL is still one of
the allowed URLs, as with a POST URL built before the owner's field changed. Only after
it passes does the exact prepared-URL check run.

**Sealed wrapper with per-send revalidation (correction 6).** Checking that the
transport is the same object is not enough, because the settings of one `requests.Session`
can be changed in place. The design uses both protections:

1. **Sealed surface.** The backend receives a `GuardedTransport` wrapper, never the
   session. The wrapper owns a private session, is built from a frozen `TransportPolicy`,
   and exposes only the send operations the protocol table needs. Per-call keyword
   arguments that would change transport behaviour (`proxies`, `verify`, `cert`,
   `allow_redirects=True`, `auth`, `hooks`) are refused with
   `transport_settings_changed`. The wrapper forces `allow_redirects=False` itself.
2. **Revalidation before every send, against two references (correction 10).**
   - **Policy digest (deterministic).** `transport_policy_sha256` is computed at S1 from
     the canonical `TransportPolicy` alone: environment trust off, empty proxy map,
     redirects refused, TLS verification mode, redirect limit, and the allowed
     method/suffix table per protocol. It contains nothing process-specific, so it is
     identical across processes and runs, and it is the only transport value that enters
     the configuration digest and the decision identifier.
   - **Runtime seal (per instance).** When the wrapper constructs its session and mounts
     its adapters, it records a seal: the session's effective settings (`trust_env`,
     `proxies`, `verify`, `cert`, `max_redirects`, `auth`, `hooks`) together with the
     ordered mounted-adapter prefixes and the identity of each mounted adapter object.
     The seal exists only in memory for that attempt. It is never persisted, digested
     into the decision, or recorded as evidence beyond a "seal intact" result.

   S2, and then the wrapper immediately before every send, check that (a) the live
   session's effective settings conform to the canonical policy behind
   `transport_policy_sha256`, and (b) the live session still equals its runtime seal. A
   failure of either check is refused with `transport_settings_changed`, with zero
   additional sends.

Test adapters, such as the recording adapter in the fixture harness, are supplied when
the wrapper is constructed, so they are captured in the runtime seal. They never affect
the policy digest. Mounting one later breaks the seal and is a settings change.

| Backend protocol | Allowed calls, relative to the bound base path |
|---|---|
| OpenAI-compatible, local (`lmstudio`, `vllm`, `llama.cpp`, `custom`) | `GET models` (model discovery or `ping`); `POST chat/completions` (streaming or not) |
| Ollama, local | `GET api/tags` (model discovery or `ping`); `POST api/chat` (streaming or not) |
| Qwen, `remote_cloud` | `POST chat/completions` only. `create_backend` replaces an auto-sentinel cloud model with `TRIAGE_QWEN_MODEL` or `qwen-max` (`backends.py:413`), so discovery is unnecessary by default. Discovery is refused. **Proposed (not owner-approved; subject to design acceptance):** a cloud model that still resolves to an auto sentinel when a cloud binding is required is refused at S1 with `cloud_model_unbound`. This is a missing-model-identity failure, distinct from endpoint-policy violations. It refuses before any network contact, and no fallback may mask it. |

Refusals:
- A call outside the table → `transport_request_not_permitted`. A **pre-send** refusal:
  no request is sent.
- Any 3xx response (301, 302, 303, 307, 308) → `endpoint_redirect_refused`. A **late**
  refusal: the request that drew the redirect was already sent to the permitted
  endpoint; the redirect is not followed, and no additional request of any kind is made
  in that attempt.
- `OllamaBackend.ping`'s LM Studio side-contact is a different identity and is refused
  if any governed path ever invokes `ping`.

The transport also counts and records every call, so tests can assert exact counts.

Compatibility, narrowed per refinement B:
- Legacy and direct callers keep the module-level default transport, so existing tests
  that patch `triage_core.backends.requests.*` stay valid **for legacy paths only**.
- Those tests are not evidence for the governed path. Governed tests must go through the
  guarded transport and assert that module-level `requests` is never called.

### Refusal classes (correction 4)

| Class | Where | Requests already sent | Requests after detection | Evidence |
|---|---|---|---|---|
| Pre-contact refusal | S1, S2, pre-invocation check, S3 pre-send check before the attempt's first request | 0 | 0 | Reason code; send count 0 |
| Pre-send refusal after earlier permitted requests | Pre-invocation or S3 pre-send check later in the attempt (e.g. a mutation between discovery and generation) | n ≥ 1, all permitted | 0 | Reason code; the complete list of the n permitted requests (route, safe label, method, suffix) |
| Late refusal | S3, on a response from a permitted endpoint (a 3xx) | n ≥ 1, all permitted | 0 | Reason code; the complete list of permitted requests, including the one that drew the response |

Every class ends the attempt with exit 2 (D4) and never falls back. "Zero requests" is
claimed only for pre-contact refusals. For the other classes the claim is *zero
additional requests after detection*, together with the full record of the requests
that were permitted and sent.

**Propagation.** Because the engine currently turns any backend exception into a
handoff (fact 12), a guard refusal raised inside `generate` would today surface as exit 3
with the exception text in the result. The design therefore requires that destination
refusals use a dedicated exception type that is neither a `RequestException` nor a
`ValueError`, that backends do not wrap it, and that the engine re-raises it unchanged,
so `tc run` reports it as exit 2 with its reason code. Refusal messages carry the
reason code and safe label only, never a raw URL.

### Reason-code vocabulary (closed)

Added by the reconciliation on 2026-10-18. The first 17 codes are the codes defined in
the sections above, accepted with the design at `a0bbd93`; this list adds no meaning to
them. The 18th is added by design amendment 1 (see Post-Acceptance Record) and is not
part of the `a0bbd93` acceptance.

| Source | Codes |
|---|---|
| Design at `a0bbd93` (17) | `endpoint_malformed`, `endpoint_scheme_not_permitted`, `endpoint_credentials_embedded`, `endpoint_query_or_fragment`, `hostname_not_literal_loopback`, `endpoint_deceptive_identity`, `endpoint_not_device_local`, `trusted_lan_not_in_profile`, `cloud_endpoint_not_approved`, `endpoint_path_noncanonical`, `cloud_model_unbound`, `configuration_unreadable`, `destination_binding_mismatch`, `transport_not_guarded`, `transport_settings_changed`, `transport_request_not_permitted`, `endpoint_redirect_refused` |
| Design amendment 1, 2026-10-18 (1) | `backend_protocol_unsupported`: a local route's backend type maps to no supported local protocol, or a protocol is absent from the protocol table. Refused at binding (S1) before network contact; a pre-contact refusal. Adds no protocol, endpoint, route or fallback |

No other code may be added without a further design amendment.

### Ordering

```text
S1 (tc_run seam): effective-config snapshot -> endpoint binding -> decision (digest v2)
     | refusal: exit 2, zero requests
build client + backends from the snapshot (no network)
S2 (_verify_governed_inputs): instance identity == bound identity; transport guarded
     | refusal: exit 2, zero requests
route binding (unchanged envelope filter; capability is availability only)
pre-invocation check (before each backend call): verified instance and transport
     | refusal: exit 2, zero additional requests
S3 (every request): exact prepared-URL match, method, no redirect
     | pre-send refusal: zero additional requests; late refusal (3xx): zero additional
```

Route binding (`runtime_observation`) is unchanged. The endpoint check never adds,
removes, or reorders an envelope member.

## Relationship to Existing Contracts

| Contract | Treatment |
|---|---|
| CR-134 `public_export_v0` | **Preserved as accepted.** Its recipient and staging rules, Parent Normalization, approval-gate interpretation, and non-claims are not reopened. CR-135 defines only the `backend_endpoint` kind. When CR-134 is implemented, its policy file carries CR-134's sections, and its whole-file digest binds as CR-134 specifies. |
| CR-DD-012B snapshot/decision pattern | **Extended.** Configuration digest v2. Seam, projection, and envelope-filter semantics unchanged. |
| CR-DD-013 capability evidence | **Unchanged.** Availability evidence only. A probe of one endpoint never authorizes another. |
| CR-114/118/119 local probe | Outside the governed path. `redact_base_url` is prior art for normalization; its rules are looser than this CR's local profile. |
| CR-095 parent manifests | Not consulted for endpoints. A parent field claiming an endpoint dimension is `unsupported_constraint` under CR-134's closure. |

## Paths Outside the First Assurance Claim

These paths keep their current behaviour, and the assurance claim says nothing about
them:

- non-governed `TriageClient.run_task`, including `TaskClassifier.classify`, which sends
  the prompt to an Ollama backend at a configured URL (`classifier.py:12-20`);
- `triagecore` CLI (`cli.py:496,947,1074`);
- `worker_registry.py:16-27`;
- TriageDesk (`ui/app.py:3494-3528`);
- `tc probe`, `tc status`, `tc doctor`;
- `apply_triagecore_local_backend_repair.py`; and
- library callers that inject their own backend.

## Acceptance Criteria

### Acceptance standards by stage (owner, 2026-10-18)

| Stage | Required evidence |
|---|---|
| Proposal acceptance | Problem statement, scope and boundaries are sound |
| Design acceptance | Contract, enforcement seams, F1–F14 fixture specifications and expected outcomes are reviewable |
| Implementation authorization | Explicit bounded file allowlist and permitted actions |
| Implementation acceptance | Executed F1–F14 results, regression tests, and evidence demonstrating enforced transport behavior |

F1–F14 do not need to pass before design acceptance. Until implementation is
independently authorized, they are planned verification, not evidence. If an
architectural assumption cannot be evaluated without experimentation, a synthetic,
offline feasibility test may be proposed. It needs its own grant and authorizes no
runtime change.

For design acceptance, the fixture **specification** must cover each of the following:

1. zero-call refusals;
2. mutable endpoint substitution after decision formation;
3. redirect handling, including 307 and 308;
4. proxy and `.netrc` isolation;
5. every actual governed request path;
6. cloud-host substitution;
7. TOML parse failure; and
8. the changed decision/configuration digest.

A successful configuration check is not evidence of controlled egress unless every
relevant request goes through the enforced transport.

### Fixture specification: planned tests, not evidence; nothing is created or executed by this CR

**Common setup.**
- Synthetic protected marker bytes, `M04-PROTECTED-<uuid>`.
- **Two harness levels** (correction 3):
  - *Recording adapter*, for unit-level cases: a recording `HTTPAdapter` mounted on the
    guarded session itself, so requests pass through the real session's preparation and
    the guard's checks before reaching the adapter, which logs `(method, prepared URL,
    headers, body)` and returns canned responses.
  - *Loopback server harness*, for F8 and F9 and wherever library behaviour is the thing
    under test: in-process HTTP servers bound to `127.0.0.1` on ephemeral ports, playing
    the bound endpoint, a redirect target, and a proxy. Each logs every connection and
    request it receives. The real guarded session sends real requests to them. No
    external network and no inference endpoint is contacted.
- **Tripwire that distinguishes the approved session** (correction 3): module-level
  `requests.get`, `requests.post` and `requests.request` fail the test on any governed
  path; `requests.Session.request` is wrapped so that calls whose session is one of the
  guarded sessions registered in the verified execution set pass through, and calls from
  any other session fail the test.

**Assertions** (correction 4).
- **Pre-contact refusals:** zero requests recorded by any adapter or server, and zero
  tripwire hits.
- **Pre-send refusals after permitted requests, and late refusals:** zero requests after
  the point of detection; the permitted requests before it are asserted exactly (count,
  route, method, prepared URL) and must appear in the attempt's evidence.
- **Permitted runs:** the exact call list, with markers seen only at bound identities.

| # | Scenario | Expected | Refused at | Sends |
|---|---|---|---|---|
| F1 | `http://127.0.0.1:11434` (Ollama) and `http://[::1]:1234/v1` (OpenAI-compatible), benign local-only task, auto model | Success; calls are discovery GET then generation POST, both to the bound identity; tripwire unhit | — | 2 |
| F2 | `TRIAGE_BASE_URL=http://203.0.113.5:11434` with type `ollama` | Exit 2, `endpoint_not_device_local` | S1 | 0 |
| F3 | `localhost`, an `.attacker.example` suffix, `127.1`, `0x7f.0.0.1`, `2130706433`, `0177.0.0.1`, `0.0.0.0`, `::ffff:127.0.0.1`, `fe80::1%eth0`, IDNA host, trailing dot, userinfo, query, fragment, `ftp:`/`file:`; base paths `/v1/../v2`, `/./v1`, `/v1/%2E%2E`, `/v1%2Fchat`, `/v1%5C`, `/v1\x`, `//v1`, `/v1//`, `/v 1`. Positive controls: `/v1`, `/v1/`, `/compatible-mode/v1`, empty | One named code per case (Endpoint normalization and Base-path canonicalization tables); positive controls canonicalize as specified | S1 | 0 |
| F4 | `192.168.1.10`, `10.0.0.2`, `fe80::1` on a local route | `trusted_lan_not_in_profile` | S1 | 0 |
| F5 | Public task, `--allow-cloud`, cloud enabled, approved Qwen identity | `remote_cloud` binding; one POST to the approved origin; never labelled device-local | — | 1 |
| F6 | **Cloud-host substitution:** `TRIAGE_QWEN_BASE_URL` set to another `https` host, to an `http` URL, or to the approved host with a different path or port | `cloud_endpoint_not_approved` / `endpoint_scheme_not_permitted`; the local route does **not** proceed (D4) | S1 | 0 |
| F7 | **Mutation after decision:** (a) `TRIAGE_BASE_URL` and `triagecore.toml` changed to a different loopback port, and separately to a remote URL, after S1 and before construction; (b) `backend.base_url` mutated after S2, before the first call; (c) engine backend, and separately the client's engine, replaced by a different object after S2; (d) cloud instance replaced after S2; (e) transport settings changed in place on the same session: `trust_env=True`, a proxy entry, `verify=False`, a newly mounted adapter, an added hook, `auth` set, and a per-call `proxies=` or `allow_redirects=True` argument, each applied (e1) before S2, (e2) after S2 and before the first request, and (e3) between model discovery and generation; (f) a backend built from a different snapshot handed to S2; (g) `backend.base_url` mutated **between** model discovery and generation, inside one `generate` call | (a) **No refusal**: the attempt contacts only the frozen S1 destination; the changed values are never contacted (the server on the new port records zero connections). (b) `destination_binding_mismatch` at the pre-invocation check. (c) The replacement is never called. The test confirms that the object whose `generate` actually executed is the verified instance (per-instance call counter, and the recording adapter's log attributes every request to that instance's transport), and that an instrumented replacement recorded zero `generate` calls and zero requests. (d) Same as (c) for the cloud route and the call-local cloud engine. (e1) `transport_settings_changed` at S2. (e2) `transport_settings_changed` at S3 pre-send. (e3) `transport_settings_changed` at S3 pre-send, before generation. (f) `destination_binding_mismatch` at S2. (g) `destination_binding_mismatch` at S3 pre-send, from the **owner-identity check**, before the POST is sent. The test asserts that the POST's prepared URL was still in the allowed set at refusal (it was built before the mutation), proving the refusal did not come from URL comparison. A companion case, where the mutation happens before `generate` builds its URL, is refused by the pre-invocation check. The pre-invocation check does not run between the two requests inside one `generate` | (a, c, d) —; (b) pre-invocation; (e1, f) S2; (e2, e3, g) S3 pre-send | (a) as F1, frozen destination only; (b, e1, e2, f) 0; (c, d) as F1, verified instance only; (e3, g) 1 permitted (discovery), 0 additional |
| F8 | **Redirects (loopback server harness):** the bound endpoint server answers 301, 302, 303, 307 and 308, each with `Location` pointing at a second loopback server standing in for a remote host, on both the discovery GET (auto model) and the generation POST (streaming and not). The POST cases use a **fixed, non-sentinel model**, so no discovery request precedes the POST | Late refusal `endpoint_redirect_refused`, exit 2; the redirect-target server records **zero** connections; the marker body is never re-sent; no fallback | S3 (late) | 1 permitted (the request that drew the 3xx), 0 additional |
| F9 | **Proxy and `.netrc` isolation (loopback server harness):** `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY` point at a recording proxy server, with no `NO_PROXY`; a temporary `HOME` with a `.netrc` entry for `127.0.0.1`; `REQUESTS_CA_BUNDLE` set to a nonexistent path | The bound endpoint server receives the request directly; the proxy server records zero connections; the endpoint server sees no `Authorization` header; the CA variable has no effect (no error, and the session's merged settings show no `verify` override) | — | 1 per call, bound endpoint only |
| F10 | **Every governed request path (recording adapter):** discovery GET for both protocols; streaming and non-streaming POST for both protocols; cloud POST; `ping` reached through a governed instance, including the Ollama LM Studio side-contact; prefix-collision and equivalent-representation URLs (`/v1evil/chat/completions`, `/v1/../chat/completions`, `/v1//chat/completions`, `/V1/chat/completions`) issued directly through the guarded session, bypassing the pre-invocation check so that S3 is tested on its own | Every permitted call passes through the guarded session and is recorded by its adapter; the side-contact and every collision URL give pre-send `transport_request_not_permitted`; the module-level tripwire is never hit, and the session tripwire is hit only by registered guarded sessions | S3 (pre-send) | permitted calls only; 0 for each refused URL |
| F11 | **TOML failure:** unparsable `triagecore.toml`; unreadable file; parser unavailable | `configuration_unreadable`, exit 2; legacy behaviour unchanged for non-governed commands | S1 | 0 |
| F12 | **Digest change and determinism:** (a) same inputs with a different loopback port, a different envelope order, or a different canonical transport policy; (b) identical inputs in two separate client constructions, and in two processes, with different session and adapter objects, including a mounted recording adapter in one and not the other | (a) Different `configuration_sha256` and `decision_id`; `CONFIGURATION_VERSION` is `…v2`; a v1-digest decision is rejected at S2. (b) **Identical** `transport_policy_sha256`, `configuration_sha256` and `decision_id`: runtime objects never enter the decision. Each instance's runtime seal differs, and each is checked only against its own session | S2 | 0 |
| F13 | Capability probe record for `127.0.0.1:1234` while executing against `127.0.0.1:11434` | Binding uses the configured identity; capability changes availability only; no destination authority derived from the probe | — | per F1 |
| F14 | **Usefulness controls:** existing suite; default `triagecore.toml` migrated to `127.0.0.1` | Unchanged pass; benign tasks complete | — | — |

**Retained results (future run):**
- machine-readable test output;
- fixture-corpus digest and destination-profile digests;
- commit;
- Python, `requests` and OS versions;
- an explicit coverage boundary: recording-adapter and in-process loopback-server level,
  with no external network.

These fixtures do not earn a G1 pass (see Non-Claims).

## Non-Claims

This CR, and any implementation of it, does not claim that:

- a loopback listener is a trustworthy process, or that it cannot forward or proxy
  requests elsewhere. A service on `127.0.0.1` may be an SSH tunnel, a proxy, or a
  runtime that uses remote models;
- the device made no other network connections, through other processes, other
  TriageCore paths, or the OS;
- DNS answers for the remote origin were authentic beyond what TLS verification
  establishes;
- protected content was ever transmitted anywhere. The motivating finding is a static
  design gap;
- capability or probe evidence is destination authorization;
- legacy or direct paths (Paths Outside the First Assurance Claim) are covered;
- an intended external recipient received anything, or that staging is delivery (CR-134
  non-claims stand); or
- assessment scores or gate G1 are changed. Local-only remains a routing policy under
  trusted configuration until endpoint enforcement is verified by integration evidence.

The supported claim, once implemented and accepted: *for a governed `tc run` attempt, the
guarded transport attempted requests only to the network endpoint identities bound to
that attempt's governed decision, using the bound methods, exact request URLs and
transport settings; every pre-contact refusal sent zero requests, and every later
refusal sent zero additional requests after detection, with the requests permitted
before it recorded.*

A stronger no-egress claim needs separate evidence: an integration run against a real
loopback service under an OS-level control, such as a network namespace containing only
loopback or a per-process outbound-deny rule, with a capture showing the markers never
left loopback, plus evidence of the local service's own forwarding configuration.

## Design Assumptions

- The operator's environment variables and `triagecore.toml` are trusted inputs. Anyone
  who can write to them can choose a destination *within* the profiles, never outside
  them.
- The installed `requests` honours session-level `trust_env=False`, explicit empty
  proxies, and per-call `allow_redirects=False`. F8 and F9 must confirm this.
- The governed path does not import a module that calls `load_dotenv()` *after* S1. If
  one did, the environment change would have no effect on the attempt (snapshot
  isolation); fixture F7(a) covers changes after S1, whatever their source.
- Requests' prepared URL is the URL put on the wire. F10's collision cases and F8's
  loopback-server harness must confirm this for the installed version.
- Windows proxy-bypass behaviour (registry and system settings) is not separately
  examined, so F9 must also run in the `windows_executor` job (correction 8). At
  `1dc9b88` that job's mandatory group runs exactly three files:
  `tests/test_mediated_executor.py`, `tests/test_privacy_invariants.py` and
  `tests/test_governed_consumption_parity.py` (`.github/workflows/tests.yml`). Its gate
  fails on **any skip** and runs with `-m "not windows_optional"`. The design therefore
  places the Windows-required F9 cases (the proxy-variable and `.netrc` cases, using the
  loopback server harness) in `tests/test_governed_consumption_parity.py`. They must run
  without skipping on both Windows and Linux and must not carry the `windows_optional`
  marker. The remaining F7–F10 cases may live in the new
  `tests/test_endpoint_transport_guard.py`, which runs only in the Ubuntu jobs. No
  workflow change is proposed. If the owner prefers to run the new file on Windows
  instead, `.github/workflows/tests.yml` must be named in a separate implementation
  grant.

## Proposed Implementation Slices (not authorized)

For review only. Each slice needs its own grant naming its exact file allowlist.

Later status (reconciliation, 2026-10-18): slice 1 was granted, implemented and accepted
at `149aa8e` (see Post-Acceptance Record). Slices 2 and 3 remain not authorized. The
slice descriptions below are kept as accepted at `a0bbd93`.

1. **Contract module** (about 2–3 hours).
   - Files: new `triage_core/destination_policy.py` (profiles, normalization, effective-config
     snapshot type, binding digest, guarded transport, reason codes) and new
     `tests/test_destination_policy.py` (F3, F4, F12 at unit level, plus normalization
     positive controls).
   - Not wired into runtime.
   - Stop point: module and unit tests pass, the full suite is unchanged.
2. **Governed integration** (about 3–4 hours).
   - Files: `triage_core/backends.py` (injected transport for all nine call sites;
     literal-loopback presets), `triage_core/config.py` (a strict snapshot reader for
     governed use; legacy reader unchanged), `triage_core/run_plan.py` (S1, digest v2),
     `triage_core/governed_decision.py` (`CONFIGURATION_VERSION`),
     `triage_core/client.py` (S2, verified execution set, pre-invocation check,
     pre-built cloud instance, guarded transports), `triage_core/engine.py` (re-raise
     destination refusals instead of converting them to a handoff),
     `triage_core/tc_cli.py` (exit-2 mapping, snapshot hand-off), `triagecore.toml`
     (literal default; a configuration change the grant must name), new
     `tests/test_endpoint_transport_guard.py` (F7, F8, F10, and the F9 cases not
     required on Windows), and updates to `tests/test_governed_consumption_parity.py`
     (F1, F2, F5, F6, F11, F13, and the Windows-required F9 cases, which must not skip)
     and
     `tests/test_backends.py` (preset assertions).
   - Stop point: governed `tc run` enforces S1–S3, with legacy paths untouched and
     documented.
3. **CR-134 consumer.** Separate, under a CR-134 implementation grant.

## Deferred Work and Open Questions

- **Trusted LAN profile.** A future authority expansion (D3, refinement D) needing owner
  approval, a separately versioned policy, and a local-network threat model.
- **Additional remote origins.** Need explicit operator policy (refinement A). The trust
  location of an operator policy file, outside any working tree and not agent-writable,
  is to be settled with CR-134's policy file.
- **`cloud_model_unbound` (proposed).** Consistent with D4's fail-closed policy, but not
  independently approved as new runtime behavior. It stays a proposed reason code until
  design acceptance. Proposed semantics: a missing cloud model identity is distinct from
  an endpoint-policy violation; it refuses before network contact whenever a cloud
  binding is required; and no fallback may conceal it. (Later status: accepted with the
  design at `a0bbd93`; see Acceptance record.)
- **Legacy paths.** Bringing any of them under the guard is separate work.
- **Integration evidence for G1.** See Non-Claims.

## Explicit Exclusions

These are the drafting grant's exclusions, as first recorded. Each later grant's own
limits are recorded with it under Post-Acceptance Record.

- Any code, test, fixture file, schema, configuration, CLI, credential, or ledger change.
- Any network or provider call, or any probe.
- Any change to CR-134's accepted contract.
- Branch publication, push, pull request, merge, release, deployment, and closeout.
- M03 and M09a records.
- Backlog, change-log, architecture, and README updates.

## Stop Point

This document is the stop point. It records:

- CR-135's allocation, five owner decisions, the required refinements, the design, the
  acceptance fixtures, and the non-claims;
- the operator's proposal and design acceptance at `a0bbd93` (Acceptance record);
- the PR #186 merge, the exhausted slice 1 grants, slice 1 implementation acceptance at
  `149aa8e`, design amendment 1, the preservation tag, and the slice 1 review-condition
  checklist (Post-Acceptance Record and checklist).

It grants no slice 1 merge, release or closeout authority, no slice 2 or slice 3
implementation authority, and no CR-135 closeout. (First recorded as: "It grants no
acceptance and no implementation, publication, merge, release, or closeout authority."
Then, at `e127d7e`: "It grants no implementation, implementation-acceptance, merge,
release, or closeout authority.")
