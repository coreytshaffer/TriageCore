# Stabilization: Authority Manifest Boundary Wording and Negative Tests

## Status
Implemented

## Scope

- Add one boundary line to the successful `tc authority check` output so the
  most quotable success artifact carries its own claim boundary.
- Clarify `docs/security/agent_authority_manifest.md`:
  - absence of an action from `requires_human_approval_for` never waives
    TriageCore's existing human-review gates,
  - `denied_actions` always takes precedence over approval-gated language,
  - the purpose wording no longer implies an agent can become "safe to act."
- Add focused negative tests proving that a valid manifest does not clear or
  bypass a pending review, does not mutate an existing identity registry, and
  that the success output states the boundary.

## Non-Goals

- No validation behavior changes.
- No runtime authorization logic.
- No approval mechanisms.
- No manifest signing.
- No identity-registry binding.
- No routing or admission enforcement changes.
- No new cryptography.

## Description

An adversarial invariant audit of CR-090 confirmed the `tc authority check`
code path is side-effect-free and fail-closed, but found three semantic risks:
the success output was quotable without any boundary statement; the
`requires_human_approval_for` field could be misread as waiving review for
unlisted actions; and the precedence between `denied_actions` and approval
gates was undocumented. This slice closes those gaps with wording and tests
only.

The boundary meaning used across CLI output, docs, and tests is:

> A passing manifest is structural review evidence only. It is not approval,
> not permission, not authorization, not a capability grant, and not a
> substitute for human approval of one exact canonicalized action packet.

## Acceptance Criteria

- [x] Successful `tc authority check` output includes a `boundary=` line with
  the meaning above.
- [x] `docs/security/agent_authority_manifest.md` states the boundary, the
  no-waiver rule for `requires_human_approval_for`, and `denied_actions`
  precedence, and its expected-output example matches the CLI.
- [x] A negative test proves a passing manifest leaves a seeded pending review
  pending and the ledger byte-identical.
- [x] A negative test proves a passing manifest leaves a seeded identity
  registry byte-identical.
- [x] A test pins the boundary line in the success output.

## Validation

- `python -m pytest tests/test_agent_authority.py -q`
- `python -m pytest tests/test_tc_cli.py tests/test_reviewer_traceability.py tests/test_review_queue.py -q`
- `python -m pytest -q`
- `git diff --check`
