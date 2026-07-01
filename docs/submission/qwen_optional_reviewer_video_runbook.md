# Qwen Optional Reviewer Submission Video Runbook

## Purpose

This runbook prepares a short hackathon submission video and media package for the Qwen optional reviewer story.

The intended reviewer path is video-first: reviewers should be able to watch a 2.5 to 4 minute demo, then inspect a small set of supporting files without searching through the whole repository.

## Repo-State Note

This runbook is a submission packaging artifact. It does not add runtime behavior, signing behavior, identity behavior, execution pathways, Qwen/cloud integration, GUI behavior, or package publishing.

Before recording the optional reviewer demo, confirm the named demo artifacts exist in the working tree or in the external submission workspace being packaged. In this repo, do not claim optional reviewer scripts or outputs exist unless they are actually present.

If the optional reviewer artifacts are not present, use the existing reviewer smoke path instead:

```powershell
tc --help
tc doctor
triagecore benchmark --list-only
tc audit --privacy-invariants
```

## Recommended Video Host

Use YouTube Unlisted as the default video host. It gives reviewers stable playback, low login friction, and an easy link to paste into a hackathon form.

Google Drive is acceptable only if "Anyone with the link can view" is confirmed from an incognito or private browser window. Avoid GitHub file upload for video unless the submission platform specifically asks for it.

## Suggested Video Title

```text
Qwen Optional Reviewer Demo: Advisory Notes Without Approval Authority
```

## Target Length

```text
2.5-4 minutes
```

The goal is to show the boundary clearly without making reviewers watch a long architecture walkthrough.

## Video Script

### 0:00-0:20 - Problem

Say:

```text
Hosted models can help review actions, but they should not become the authority for approval or execution.
```

Show the project submission index, stabilization checkpoint, or claim-boundary note.

### 0:20-0:45 - Setup Boundary

Say:

```text
This demo treats Qwen as an untrusted hosted reviewer-note generator. It only receives a reduced synthetic fixture.
```

Show the boundary note or synthetic fixture. Make clear that no secrets, real civic data, personal data, or raw provider metadata are being shown.

### 0:45-1:15 - Synthetic Smoke Test

If the optional reviewer smoke script exists in the submission workspace, show:

```powershell
python scripts\qwen_smoke.py
```

Expected result:

```text
PASS: Qwen synthetic JSON smoke test succeeded
```

Interpretation:

```text
This proves the synthetic fixture can be validated and exercised without using real sensitive data.
```

### 1:15-2:00 - Advisory Reviewer Demo

If the optional reviewer demo script exists in the submission workspace, show:

```powershell
python scripts\qwen_optional_reviewer_demo.py
```

Expected result:

```text
PASS: Qwen optional reviewer demo produced advisory notes only
```

Say:

```text
Qwen can suggest notes, but the local deterministic code validates both input and output.
```

### 2:00-2:45 - Fail-Closed Tests

If the optional reviewer fail-closed tests exist in the submission workspace, show:

```powershell
python -m unittest tests.test_qwen_optional_reviewer_fail_closed
```

Expected result:

```text
Ran 8 tests
OK
```

Say:

```text
These tests reject missing synthetic flags, disallowed action types, extra keys like approved, wrong roles, execution language, and missing config.
```

### 2:45-3:20 - Why It Matters

Say:

```text
The useful pattern is not that Qwen can help. The useful pattern is that Qwen can help without approving, executing, mutating payloads, overriding policy, or changing gate state.
```

### 3:20-3:40 - Non-Claim

Say:

```text
This is a hackathon boundary proof, not production security certification.
```

End on the submission index or media bundle manifest.

## Existing Reviewer Smoke Fallback

If the optional reviewer artifact set is not available, record the existing local smoke path instead:

```powershell
git status --short
tc --help
tc doctor
triagecore benchmark --list-only
tc audit --privacy-invariants
```

Use [../operations/reviewer-smoke-runbook.md](../operations/reviewer-smoke-runbook.md) for expected output interpretation.

## Submission Summary

Use this text when the submission form asks for a description and the optional reviewer artifact set is present:

```text
This demo shows Qwen Cloud used as an untrusted hosted reviewer-note generator for a synthetic Secure Action / Human Approval Gate workflow. Qwen receives only a reduced synthetic fixture and may return advisory notes in an allowlisted JSON shape. Local deterministic code remains authoritative: it validates inputs before the model call, validates outputs after the model call, rejects unsafe or extra fields, and never allows model output to approve, execute, mutate payloads, override policy, make final decisions, or change gate state. The demo includes a live synthetic smoke test, an advisory-only reviewer run, and local fail-closed tests covering unsafe or invalid cases.
```

If using the current repo smoke fallback instead, use this shorter description:

```text
This demo shows TriageCore as a local-first reviewer workflow for AI-assisted work. The smoke path verifies the CLI entry point, local environment report, benchmark fixture discovery, and privacy-invariant ledger audit. The project keeps hosted model help, approval authority, execution authority, and persistent audit evidence separate, and it does not treat model output as approval, safety certification, or permission to execute.
```

## Media Bundle Checklist

Create a clean media folder only after confirming each artifact exists and is safe to share.

Preferred folder shape for the optional reviewer artifact set:

```text
submission-media/
  qwen-demo-index-2026-06-29.md
  qwen-optional-reviewer-boundary-note-2026-06-29.md
  qwen-smoke-result-2026-06-29.md
  qwen-optional-reviewer-demo-result-2026-06-29.md
  qwen-model-comparison-notes-v0.1.md
  synthetic_qwen_reviewer_action.json
  test_qwen_optional_reviewer_fail_closed.py
  qwen_smoke.py
  qwen_optional_reviewer_demo.py
```

Zip command:

```powershell
Compress-Archive -Path submission-media\* -DestinationPath qwen-optional-reviewer-media-2026-06-29.zip -Force
```

## Do Not Include

Do not include:

- `.env`
- password manager exports
- screenshots of cloud console or API key pages
- raw provider responses with IDs or metadata
- terminal logs containing tokens
- private repo paths if they reveal sensitive context
- real civic, environmental, or personal data
- anything that implies model output grants approval or execution authority

## Final Pre-Submission Check

Before submitting:

```powershell
git status --short
```

Confirm:

- video link opens in an incognito or private browser
- media bundle contains only intentional files
- no secrets or raw provider metadata are included
- submission text matches the artifacts actually shown
- non-claims are explicit
