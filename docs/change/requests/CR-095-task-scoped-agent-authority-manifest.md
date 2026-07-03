# CR-095: Task-Scoped Agent Authority Manifest

## Status
Implemented

## Scope

- Add a static agent authority manifest contract under `docs/security/`.
- Add valid and intentionally invalid JSON examples under
  `docs/security/examples/`.
- Add a metadata-only `tc authority check --manifest <path>` validator.
- Add focused tests for required fields, expiration, revocation state, action
  conflicts, wildcard scope, human approval gates, CLI output, and no-mutation
  behavior.
- Update backlog and change log wording to reflect the new authority-manifest
  slice.

## Non-Goals

- No route enforcement changes.
- No runtime execution changes.
- No ledger mutation.
- No identity registry mutation.
- No manifest signing.
- No automatic human approval.
- No network calls or backend probing.

## Description

Recent agent-RL and agent-identity signals point toward the same control-plane
need: agent behavior should be evaluated against explicit task, verifier,
identity, authority, and revocation boundaries. TriageCore already has signed
identity provenance for selected events, but signatures prove who emitted an
artifact, not what the agent was allowed to do.

This slice adds a small task-scoped authority manifest contract and validator
so TriageCore can describe allowed actions, denied actions, resource scope,
approval gates, expiration, and revocation state before any future runtime or
eval path treats an agent action as inside bounds.

## Acceptance Criteria

- [x] `docs/security/agent_authority_manifest.md` documents the authority
  manifest contract, validation rules, CLI usage, and non-goals.
- [x] A valid reviewer-style authority manifest example exists.
- [x] An intentionally invalid authority manifest example exists for failure
  coverage.
- [x] `tc authority check --manifest <path>` passes valid manifests.
- [x] The validator fails closed for missing fields, inactive status, expired
  manifests, contradictory actions, wildcard authority, and missing human
  approval gates for high-risk actions.
- [x] The CLI check remains metadata-only and does not mutate `.triagecore/`.

## Validation

- `python -m py_compile triage_core/agent_authority.py triage_core/tc_cli.py tests/test_agent_authority.py`
- `python -m pytest tests/test_agent_authority.py -q`
- `git diff --check`
