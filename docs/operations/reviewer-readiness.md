# Reviewer Readiness

## Purpose

This page gives reviewers one stable command path for checking the current TriageCore repo without expanding runtime scope.

It is a reviewer-orientation checkpoint, not a release certification, admission decision, or signing expansion plan.

## Canonical Reviewer Commands

Run these commands from the repository root:

```powershell
tc doctor
tc identity list
tc audit --verify-signatures --kind route_decision
python -m pytest
git diff --check
git status --short
```

## What Each Command Proves

### `tc doctor`

- Confirms the current repo root, branch, Python executable, CLI path, ledger visibility, and runtime safety posture.
- A reviewer-ready baseline should report `Overall: OK`.

### `tc identity list`

- Shows the locally registered public signer metadata.
- Supports operator discovery before signed smoke or verification steps.
- Should not print private key material.

### `tc audit --verify-signatures --kind route_decision`

- Verifies signed `route_decision` provenance when signed events are present.
- Keeps the output metadata-only.
- Does not treat a valid signature as approval, correctness, or safety.

### `python -m pytest`

- Runs the full project regression suite.
- This remains the broadest routine reviewer validation command.

### `git diff --check`

- Confirms there are no whitespace or patch-formatting errors in the current tracked diff.
- This is the minimum repository check for docs-only slices.

### `git status --short`

- Confirms whether the working tree is clean before treating results as final reviewer evidence.
- Empty output is the ideal reviewer-ready state.

## Signed Route-Decision Boundary

Use the signed route-decision docs as provenance guidance only:

- [issue-72-signed-route-decision-checkpoint.md](issue-72-signed-route-decision-checkpoint.md)
- [signed-route-decision-verification.md](signed-route-decision-verification.md)

Current boundary:

- signed `route_decision` events are explicit, not automatic
- signer choice remains intentional through `--agent-id`
- signatures prove provenance and tamper evidence only
- signatures do not grant approval, safety, or execution authority

## Reviewer Notes

- If `tc identity list` shows no identities, signed route-decision verification may still run but will only validate signed events that already exist in the ledger if the supporting registry is present.
- If the local registry is malformed or unreadable, the reviewer-facing CLI should fail closed with bounded output rather than a traceback.
- Local ledger counts can vary over time; a higher `valid_signed` count is expected if additional metadata-only smoke events were written locally.

## Related Docs

- [reviewer-entrypoints.md](reviewer-entrypoints.md)
- [reviewer-smoke-runbook.md](reviewer-smoke-runbook.md)
- [packaging-readiness.md](packaging-readiness.md)
- [reviewer-release-checkpoint-2026-07-02.md](reviewer-release-checkpoint-2026-07-02.md)
