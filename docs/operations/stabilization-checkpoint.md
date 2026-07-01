# TriageCore Stabilization Checkpoint

## Purpose

This checkpoint gives reviewers a single entry point for understanding the current TriageCore state after the signed route-decision lane.

TriageCore is a local-first developer-agent control harness. It helps operators package tasks, inspect routing and audit evidence, validate review artifacts, and keep local/cloud boundaries visible. It is still a prototype and research workbench, not a production safety system.

## Current Capabilities

- Local environment and repo checks through `tc doctor`.
- Offline demo and reviewer paths through `tc demo --dry-run`, `tc preflight`, and `tc handoff`.
- Privacy-safe ledger inspection through `tc audit`.
- Task Envelope and Admission Evidence validation/rendering through `tc task-envelope` and `tc admission`.
- Local benchmark fixture listing and benchmark-report scaffolding.
- Optional, bounded Qwen Cloud support only for packets classified as external-safe.
- Signed provenance checks for selected ledger evidence, including `validation_result` and opt-in signed `route_decision` events.

## Current Safety Posture

TriageCore favors local-first, file-based, inspectable workflows. Persistent records are intended to stay metadata-first and privacy-safe. Approval, admission, execution, provenance, and review are treated as separate concepts.

The current posture is:

- local execution remains the default orientation
- mutation is explicit and command-scoped
- signed events prove provenance and tamper evidence only
- review artifacts do not grant execution authority
- external runtime work remains gated by documented admission boundaries
- broader production, compliance, or critical-infrastructure claims remain out of scope

## Signed Route-Decision Checkpoint Status

The signed route-decision lane is checkpointed, not expanded.

Current proven behavior:

- `route_decision` has an explicit opt-in signed ledger path.
- `tc identity doctor <agent-id> --for-capability route_decision:sign` checks signer readiness.
- `tc audit --signed-route-decision-smoke-test --agent-id <agent-id>` can create one metadata-only signed smoke event.
- `tc audit --verify-signatures --kind route_decision` can verify signed route-decision evidence after the fact.
- Missing signer identity, missing capability, malformed key material, and tampered signed payloads fail closed.

Current non-claims:

- route-decision signing is not automatic
- a valid signature is not approval
- a valid signature is not safety certification
- a valid signature is not correctness proof
- this checkpoint does not add new signed event types

See [issue-72-signed-route-decision-checkpoint.md](issue-72-signed-route-decision-checkpoint.md) for the full operator path.

## Reviewer Validation Path

Install locally from the repo root:

```powershell
python -m pip install -e .
```

Run the core smoke path:

```powershell
tc --help
tc doctor
tc demo --dry-run
tc audit --self-test
tc audit --kind route_audit --last 10
tc audit --privacy-invariants
triagecore benchmark --list-only
```

Run the test suite when validating a code-bearing branch:

```powershell
python -m pytest -q
```

For this docs-only stabilization checkpoint, the minimum repository validation is:

```powershell
git diff --check
```

## Packaging Readiness Meaning

Packaging readiness currently means reviewers can install TriageCore locally, run documented CLI checks, inspect the current proof markers, and understand known boundaries without reconstructing the project from scattered notes.

It does not mean:

- a PyPI release is ready
- installer behavior has changed
- release tags have been cut
- a production deployment path is approved
- new cryptographic behavior has been added

See [packaging-readiness.md](packaging-readiness.md) for the focused reviewer checklist.

## Out Of Scope For This Checkpoint

- package publishing
- PyPI setup
- installer changes
- new signing features
- new identity lifecycle behavior
- new agent execution hooks
- Qwen integration changes
- GUI expansion
- live backend integration

## Next Safe Stabilization Steps

- Keep reviewer documentation aligned with current commands.
- Preserve packaging/readiness as a documentation and verification lane before release mechanics.
- Defer deeper signing, key lifecycle, and identity work to separate CRs.
- Keep future runtime changes paired with focused tests and explicit safety boundaries.
