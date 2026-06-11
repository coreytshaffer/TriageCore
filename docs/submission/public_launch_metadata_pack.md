# TriageCore Public Launch Metadata Pack

This document is the public-launch metadata package for TriageCore.

It is intended to support the first proof-marker release and GitHub presentation work without changing runtime code or creating a release tag yet.

## GitHub About Description

Recommended:

> Privacy-first local/cloud AI orchestration control plane with auditable routing, scoped handoffs, and safety-first task governance.

Shorter alternative:

> Privacy-first AI orchestration control plane for local/cloud routing, scoped handoffs, and auditable task governance.

## GitHub Topics

Recommended topics:

- `ai-orchestration`
- `local-first`
- `privacy-first`
- `agent-framework`
- `llm-routing`
- `human-in-the-loop`
- `audit-logging`
- `task-routing`
- `safe-ai`
- `developer-tools`
- `python`
- `cli`
- `local-llm`
- `qwen`
- `workflow-automation`

Optional alternates if space or tone needs adjustment:

- `ai-safety`
- `governance`
- `edge-ai`
- `offline-first`
- `model-routing`
- `privacy-engineering`

## Recommended First Tag

`v0.1.0`

Reasoning:

- This is the first public proof-marker release.
- `v0.1.0` communicates that the project has a working validated foundation.
- It does not overclaim production maturity.

Do not use `v1.0.0` yet. TriageCore is credible, but the public contract is still forming.

## Release Title

`TriageCore v0.1.0 — Privacy-first orchestration foundation`

## Release Notes Draft

TriageCore v0.1.0 establishes the first public proof-marker release of the project: a privacy-first AI orchestration control plane focused on scoped task routing, local/cloud boundaries, explicit review gates, and auditable workflow evidence.

### Highlights

- GitHub Actions test workflow is present and active.
- README includes a live tests badge.
- CR-017 reviewer path and public evidence example are present and validated.
- Task routing and review workflows are structured around explicit approval boundaries.
- Privacy and security hardening work is underway, including mobile API boundary hardening.
- Current validation evidence includes a full passing test suite: `241 passed, 2 skipped`.

### Intended Audience

This release is intended for reviewers, collaborators, hackathon judges, and technically curious observers who want to understand the project’s architecture, safety posture, and development discipline.

### Known Limitations

- The project is still pre-production.
- Release tagging should occur only after unrelated in-progress web/mobile changes are committed, merged, or intentionally excluded.
- Browser visual verification for the mobile UI was blocked by the Windows browser runtime, though HTTP smoke checks and JavaScript syntax validation passed.

## Recommended Verification

Before creating the release tag, run:

```powershell
git status
python -m pytest -q
```

Confirm that the working tree contains only intentional release-ready changes.

## Release Checklist

Before creating `v0.1.0`:

1. Confirm working tree state:

   ```powershell
   git status
   ```

2. Confirm no unrelated in-progress files are included:

   ```powershell
   git diff --stat
   ```

3. Run full validation:

   ```powershell
   python -m pytest -q
   ```

4. Confirm README badge is visible.
5. Confirm `.github/workflows/tests.yml` exists.
6. Confirm CR-017 public reviewer and evidence path is present.
7. Commit or exclude current web/mobile hardening changes.
8. Create annotated tag:

   ```powershell
   git tag -a v0.1.0 -m "TriageCore v0.1.0 — Privacy-first orchestration foundation"
   ```

9. Push tag:

   ```powershell
   git push origin v0.1.0
   ```

10. Create the GitHub release using the release notes above.

## Do Not Do Yet

- Do not create the release tag while unrelated in-progress mobile/web files are still mixed into the working tree.
- Do not claim production readiness.
- Do not claim complete privacy/security hardening.
- Do not bury the browser visual verification limitation.

## Recommendation

Commit the mobile/API hardening separately first, then do the public-launch metadata and tag step.

Otherwise the release will blur “public proof marker” with “active hardening branch,” and that muddies the story.

## Preferred GitHub About Text

Use this one unless a shorter variant is required:

> Privacy-first local/cloud AI orchestration control plane with auditable routing, scoped handoffs, and safety-first task governance.

## Related Docs

- [README.md](C:/Users/corey/Documents/Science/AI/triagecore/README.md)
- [judge_quickstart.md](C:/Users/corey/Documents/Science/AI/triagecore/docs/submission/judge_quickstart.md)
- [public_evidence_example.md](C:/Users/corey/Documents/Science/AI/triagecore/docs/submission/public_evidence_example.md)
- [hackathon_demo.md](C:/Users/corey/Documents/Science/AI/triagecore/docs/workflows/hackathon_demo.md)
