# Reviewer Entrypoints

## Purpose

This index gives reviewers one place to start when inspecting the current TriageCore stabilization state. It points to the existing operational, signing, packaging, and submission documents without adding new runtime behavior.

Use this page when the goal is to understand what is implemented, what can be validated locally, and which claims remain out of scope.

## Recommended Reading Order

1. [stabilization-checkpoint.md](stabilization-checkpoint.md) - current project posture, implemented capabilities, and boundaries.
2. [reviewer-smoke-runbook.md](reviewer-smoke-runbook.md) - shortest repeatable local validation path.
3. [packaging-readiness.md](packaging-readiness.md) - local install and packaging-readiness expectations.
4. [issue-72-signed-route-decision-checkpoint.md](issue-72-signed-route-decision-checkpoint.md) - consolidated signed route-decision reviewer path.
5. [../submission/README.md](../submission/README.md) - judge-facing submission bundle and video-first materials.
6. [../current_backlog.md](../current_backlog.md) and [../change/change_log.md](../change/change_log.md) - current work lanes and applied change history.

## Validation Path

For a reviewer smoke check, start from the repository root:

```powershell
git status --short
tc --help
tc doctor
triagecore benchmark --list-only
tc audit --privacy-invariants
```

For a docs-only review, the minimum repository validation is:

```powershell
git diff --check
```

For a code-bearing branch, use the full project validation command documented in packaging readiness:

```powershell
python -m pytest -q
```

## Signed Route-Decision Docs

The signed route-decision lane is documented as an opt-in provenance path, not an approval system.

Start with:

- [issue-72-signed-route-decision-checkpoint.md](issue-72-signed-route-decision-checkpoint.md)
- [signed-route-decision-verification.md](signed-route-decision-verification.md)
- [signed-validation-result-verification.md](signed-validation-result-verification.md)
- [../security/agent_identity_provenance.md](../security/agent_identity_provenance.md)

Current claim boundary:

- signed `route_decision` events are explicit, not automatic
- signatures prove provenance and tamper evidence only
- a valid signature is not approval, safety certification, correctness proof, or permission to execute
- broader signed event coverage and runtime key rotation remain separate future work

## Packaging And Readiness Docs

Packaging readiness currently means the project can be installed locally for review, smoke commands are documented, and reviewers can inspect current evidence boundaries.

Use:

- [packaging-readiness.md](packaging-readiness.md)
- [stabilization-checkpoint.md](stabilization-checkpoint.md)
- [reviewer-smoke-runbook.md](reviewer-smoke-runbook.md)
- [../verification_guide.md](../verification_guide.md)

This does not mean PyPI publishing, release tagging, installer behavior, or package distribution behavior has changed.

## Submission And Video Docs

Use the submission bundle when preparing a judge-facing or reviewer-facing packet:

- [../submission/README.md](../submission/README.md)
- [../submission/judge_quickstart.md](../submission/judge_quickstart.md)
- [../submission/hackathon_submission_overview.md](../submission/hackathon_submission_overview.md)
- [../submission/claim_boundaries.md](../submission/claim_boundaries.md)
- [../submission/qwen_optional_reviewer_video_runbook.md](../submission/qwen_optional_reviewer_video_runbook.md)

Qwen optional reviewer artifacts are separate from this repo's core smoke path unless the named scripts, fixtures, outputs, or media files are actually present in the checkout or external submission workspace being packaged.

If those optional artifacts are absent, use the local reviewer smoke path instead of claiming Qwen optional reviewer execution evidence.

## Current Safety Posture

TriageCore is a local-first developer-agent control harness and research workbench. Its current reviewer posture is:

- local inspection and CLI smoke checks are the default path
- persistent evidence should remain metadata-first and privacy-safe
- approval, admission, execution, provenance, and review are separate concepts
- hosted model help is optional and bounded by documented external-safe rules
- signed records are provenance evidence only
- production, compliance, legal, critical-infrastructure, and safety-certification claims remain out of scope

## Non-Goals

This index does not add:

- runtime behavior
- signing surface
- identity lifecycle behavior
- execution pathways
- Qwen or cloud integration
- GUI behavior
- package publishing behavior
- release mechanics
- new reviewer evidence artifacts

## Next Safe Reviewer Actions

- Run the reviewer smoke path from [reviewer-smoke-runbook.md](reviewer-smoke-runbook.md).
- Confirm `git status --short` is clean before treating smoke output as final reviewer evidence.
- Inspect the signed route-decision docs without treating signatures as approval.
- Use the submission bundle for judge-facing packet assembly.
- Keep optional Qwen reviewer artifacts separate unless the files are present and validated.
- Keep future implementation slices narrow: runtime changes, signing expansion, identity lifecycle work, GUI work, and publishing behavior should each have separate CRs and focused validation.
