# CR-130: Resolve `Approved`-Status Authority Semantics

## Status

- **Status:** Merged locally; pending closeout.
- **Proposal acceptance:** Granted by the human operator on 2026-08-11 for the controlling semantics and prospective-history rule in this record.
- **Implementation authority:** Explicitly granted by the human operator on 2026-08-11 for the exact two-path scope in this CR.
- **Implementation acceptance:** Granted by the human operator on 2026-08-11 after review of the bounded implementation.
- **Merge authority:** Granted and exercised by the human operator on 2026-08-11 for this reviewed two-path documentation change.
- **Release authority:** Not granted.
- **Closeout authority:** Not granted.
- **EGD adoption:** Not established.
- **Baseline:** Clean `main` at `7c7fb720aea546763fe062dd08438125d81bdd8c` immediately before the grant.

This CR is a prospective documentation-policy reconciliation. It does not adopt Evidence-Governed Development (EGD), create runtime authority, or rewrite historical records.

## Scope

The authorized implementation scope is exactly:

```text
docs/change/requests/CR-130-approved-status-authority-semantics.md
docs/change/change_management.md
```

The first path records the accepted governance decision and its boundaries. The second path becomes the canonical prospective policy. No other repository path is authorized.

## Human Approval Requirement

Proposal acceptance, bounded implementation authority, and implementation acceptance are satisfied as recorded above. Merge authority, release authority, and closeout remain separate human decisions.

## Problem Statement

`docs/change/change_management.md` previously required every CR to define status, scope, implementation authority, human approval requirement, and acceptance criteria, but also said that `Approved` status authorizes code changes. That made a status value independently authorization-bearing despite the separate implementation-authority field.

Newer TriageCore governance records use the more precise model this CR makes prospective policy: a proposal or architecture may be accepted while implementation authority is withheld; authority is separately scoped; later acceptance, merge, release, and closeout remain distinct; and a completed grant does not create standing authority.

## Accepted Controlling Rule

The canonical policy must state:

1. A CR defines status, scope, implementation authority, human approval requirement, and acceptance criteria.
2. `Status` records lifecycle or acceptance state. `Approved` may record acceptance of a proposal, design, or architecture for the purpose stated in the CR, but status alone does not authorize code changes.
3. Code changes require explicit human implementation authority recorded for the CR and scoped to the named change plus bounded files, systems, or actions.
4. Design or architecture acceptance, implementation authority, implementation acceptance, merge authority, release authority, and closeout are separate decisions unless an explicit human grant deliberately names and bundles particular stages.
5. A grant explicitly defined as single-slice, single-use, or stage-bound is exhausted when its authorized action or stage is completed. No grant creates standing authority beyond its recorded scope, conditions, and duration.

## Prospective Application and Historical Integrity

The new rule applies prospectively from the merge that makes it canonical.

- Completed or merged CRs remain historical records and must not be rewritten merely to resemble this policy.
- This CR does not manufacture missing historical authority, invalidate completed work solely because vocabulary evolved, or convert historical approval into future standing authority.
- After the rule is canonical, a future action may not rely on `Approved` status alone.
- An older active CR needs an applicable explicit scoped grant before new code changes begin.
- An existing explicit unspent grant remains bounded by its own recorded scope and conditions; a spent grant remains spent.

## Explicit Exclusions

This CR does not authorize:

- edits to historical CRs, ADRs, closure records, or the change log;
- `tc propose`, CR templates, pull-request templates, schemas, tests, CI, hooks, or enforcement automation;
- runtime authorization, WebAuthn, capabilities, manifests, routing, or review queues;
- risk-taxonomy changes;
- branch creation, commit, push, pull request, merge, release, or closeout;
- EGD adoption or either EGD pilot; or
- work on the independent #158 requirements-contract concern.

Deferred template and CLI consistency work must remain described as deferred, not complete.

## Acceptance Criteria

- [x] CR-130 records the proposal acceptance and bounded implementation grant.
- [x] `Approved` status no longer independently authorizes code changes.
- [x] Status and implementation authority remain distinct required facts.
- [x] Code changes require explicit human authority with bounded scope.
- [x] Design acceptance, implementation authority, implementation acceptance, merge authority, release authority, and closeout remain distinct unless explicitly bundled.
- [x] Only grants explicitly defined as single-slice, single-use, or stage-bound are exhausted by completion of their authorized action or stage.
- [x] No grant creates standing authority beyond its recorded scope, conditions, and duration.
- [x] The rule is prospective and historical CR text is preserved.
- [x] No excluded repository path was changed.
- [x] Implementation acceptance has been recorded.
- [x] Merge authority has been granted and exercised.
- [ ] Closeout has been recorded.

## Verification Plan

Before implementation acceptance, verify:

1. the final diff is limited to this CR and `docs/change/change_management.md`;
2. the prior `Approved`-authorizes sentence is absent from the policy;
3. the replacement preserves the required CR fields and separates the gates;
4. the rule is expressly prospective and does not rewrite history;
5. the repository has no unintended change; and
6. `git diff --check` passes.

No test-suite result is required for this documentation-only semantic change.

## Stop Point

Stop after the authorized merge. Closeout and EGD adoption require separate human decisions. Release authority remains not granted; no release action is in scope for this documentation-only change.
