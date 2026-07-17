# CR-BW-001 — Evidence-Bound Build Review

## Status

Accepted for OpenAI Build Week on 2026-07-17.

## Purpose

Given a development request and a Git comparison, produce a structured review
packet showing intended scope, actual scope, validation evidence, findings, and
an explicit human decision.

This is a review boundary for Codex changes, local-model coding agents,
contributor pull requests, and security-sensitive modifications. It does not
autonomously remediate code or replace human approval.

## Declared scope

- `triage_core/build_review.py`
- `triage_core/build_review_integrity.py`
- `triage_core/build_review_report.py`
- `triage_core/build_review_cli.py`
- `triage_core/tc_cli.py`
- `tests/test_build_review_cli.py`
- `docs/build-review-contract.md`
- `examples/build-week/`
- `README.md`
- `BUILD_WEEK_SCOPE.md`

## Required validations

- `python -m pytest -q tests/test_build_review_cli.py`
- `python -m pytest -q`
- `python -m ruff check triage_core/build_review*.py tests/test_build_review_cli.py examples/build-week/generate_packets.py`
- `git diff --check`

## Command contract

```powershell
tc build-review create `
  --request-file docs/change/requests/CR-BW-001-evidence-bound-build-review.md `
  --base main `
  --head HEAD `
  --validate "python -m pytest -q"
```

The command writes:

```text
.triagecore/build-reviews/<review-id>/
├── review.json
├── review.md
├── review.html
├── diff-summary.json
└── validation-results.json
```

## Acceptance criteria

- Parse declared scope and required validations from the change request.
- Compare declared paths with the actual Git diff.
- Run bounded, reviewer-supplied validation commands.
- Flag scope drift, failed or missing validation, sensitive paths, binary
  artifacts, and source changes without test changes.
- Generate machine-readable JSON plus deterministic Markdown and HTML views.
- Keep the system recommendation separate from the human decision.
- Record one non-overwriting `approved`, `rejected`, or `needs_revision`
  decision in `decision.json`.
- Privacy-scan packet and decision content before persistence.

## Boundaries

Validation commands execute through the local shell and must be supplied only
by a trusted operator. Review packets are explicit local artifacts; they are
not automatically written to the task ledger or sent to a remote service.
