# CR-088: Submission Video Runbook

## Status
Implemented

## Scope

- Add a video-first submission runbook for the Qwen optional reviewer story.
- Document the recommended host, title, target length, timed script, media bundle checklist, do-not-include list, and final pre-submission checks.
- Include a repo-state note so reviewers do not treat absent optional reviewer artifacts as implemented in this checkout.
- Link the runbook from the submission bundle reading order.
- Update backlog and change log wording for this docs-only submission packaging slice.

## Non-Goals

- No runtime behavior changes.
- No signing surface changes.
- No identity lifecycle changes.
- No new execution pathways.
- No Qwen/cloud integration changes.
- No GUI changes.
- No package publishing behavior.
- No generated media archive in the repo.
- No claim that optional reviewer scripts or outputs exist unless the files are present in the submission workspace.

## Acceptance Criteria

- [x] `docs/submission/qwen_optional_reviewer_video_runbook.md` gives a short recording script and reviewer-first media packaging checklist.
- [x] The runbook distinguishes optional reviewer artifacts from the current repo smoke fallback.
- [x] The runbook includes clear non-claims and no-secret media exclusions.
- [x] `docs/submission/README.md` links the runbook in the submission reading order.
- [x] `docs/current_backlog.md` reflects the submission packaging slice.
- [x] `docs/change/change_log.md` records CR-088.

## Validation

- `git diff --check`
- `git status --short`
