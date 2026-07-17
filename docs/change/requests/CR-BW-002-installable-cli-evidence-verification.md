# CR-BW-002 — Installed CLI and Evidence Verification

## Status

Accepted as the final Build Week hardening slice on 2026-07-17.

CR-BW-001 is feature-complete. This request integrates it into the public
TriageCore package and adds independent packet verification.

## Purpose

Extend the existing installed `tc` command with:

```text
tc build-review create ...
tc build-review decide ...
tc build-review verify <packet-path>
```

The release claim is:

> TriageCore does not merely generate review evidence—it can verify that its
> evidence artifacts remain internally consistent and that a decision is bound
> to the exact evidence hash.

This is an integrity check, not a digital signature or proof against an actor
who can replace every artifact and recompute every digest.

## Declared scope

- `triage_core/build_review.py`
- `triage_core/build_review_cli.py`
- `triage_core/build_review_integrity.py`
- `triage_core/build_review_report.py`
- `triage_core/build_review_verify.py`
- `triage_core/tc_cli.py`
- `tests/test_build_review_cli.py`
- `examples/build-week/`
- `docs/build-review-contract.md`
- `docs/change/requests/CR-BW-001-evidence-bound-build-review.md`
- `docs/change/requests/CR-BW-002-installable-cli-evidence-verification.md`
- `README.md`
- `BUILD_WEEK_SCOPE.md`

## Required validations

- `python -m pytest -q`
- `python -m build`
- `python -m pip install --force-reinstall dist/triagecore-0.1.0-py3-none-any.whl`
- `tc build-review --help`
- `tc build-review verify examples/build-week/clean-self-review`
- `tc build-review verify examples/build-week/adversarial-scope-drift`
- `python -m ruff check triage_core/build_review*.py tests/test_build_review_cli.py examples/build-week/generate_packets.py`
- `git diff --check`
- `git status --short`

## Verification contract

`verify` independently:

1. Resolves a review directory or `review.json` path.
2. Confirms all required packet files exist and rejects symlinked artifacts.
3. Parses JSON strictly, rejecting duplicate keys and non-standard constants.
4. Recomputes the canonical evidence hash.
5. Reconstructs and compares `diff-summary.json`.
6. Reconstructs and compares `validation-results.json`.
7. Reconstructs and compares the Markdown and HTML views.
8. Validates an optional decision enum, packet ID, evidence reference, and
   deterministic decision ID.
9. Confirms immutable `review.json` still carries a pending decision.
10. Performs no writes.

Exit codes:

```text
0  verified
1  verification, integrity, or operation failure
2  malformed CLI invocation
```

## Canonicalization contract

Canonical JSON is UTF-8 encoded with recursively sorted keys, compact
separators, and preserved Unicode. The evidence digest excludes only
`decision` and `evidence_sha256`. The decision ID covers every decision field
except `decision_id`, including the reviewer note.

## Required installed-command tests

```text
test_cli_creates_complete_review_packet
test_cli_records_approved_decision
test_cli_records_rejected_decision
test_cli_records_needs_revision_decision
test_cli_refuses_decision_overwrite
test_cli_verifies_intact_packet
test_cli_detects_modified_evidence
test_cli_detects_modified_decision_reference
test_cli_detects_missing_artifact
```

The suite also covers deterministic canonicalization, malformed invocation,
duplicate JSON keys, useful stderr, exact exit codes, no verifier mutation, and
no writes to the reviewed repository.

Repository-wide Ruff cleanup is outside this CR. The baseline contains
unrelated lint debt, so the release gate lints the new Build Review surface
while the complete repository is covered by the full pytest suite.

## Freeze rule

After CR-BW-002, accept only installation defects, verification defects, broken
tests or documentation, demo failures, and submission-critical accessibility
fixes. All new features move to the post-hackathon backlog.
