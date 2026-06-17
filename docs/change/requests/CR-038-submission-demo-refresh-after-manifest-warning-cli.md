# CR-038: Submission Demo Refresh After Manifest Warning CLI

## Status

Implemented

## Scope

Refresh judge-facing and reviewer-facing docs after CR-036 and CR-037 so the
manifest warning path appears as an optional deeper verification step.

This change:

- updates `docs/submission/judge_quickstart.md`
- updates `docs/workflows/hackathon_demo.md`
- updates `docs/submission/hackathon_submission_overview.md`
- updates `docs/submission/public_evidence_example.md`
- updates the README reviewer path wording
- adds a changelog entry

## Non-Scope

- Do not change runtime routing behavior.
- Do not add backend probing.
- Do not turn manifest warnings into enforcement.
- Do not expand the demo into a live Qwen credential dependency.

## Acceptance Criteria

- [x] Judge-facing docs mention `tc model check` and `tc model warn`.
- [x] The manifest warning path is labeled optional, not part of the shortest
  path.
- [x] Docs say the warning command is non-blocking.
- [x] Docs avoid claims of runtime enforcement, backend probing, or production
  certification.
- [x] Changelog reflects the reviewer-path refresh.

## Validation

```powershell
git diff --check
git status --short
rg -n "model warn|non-blocking|optional deeper verification" README.md docs\submission docs\workflows
```
