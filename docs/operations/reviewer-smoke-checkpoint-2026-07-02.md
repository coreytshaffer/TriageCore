# Reviewer Smoke Checkpoint — 2026-07-02

## Purpose

This document preserves a point-in-time reviewer-readiness evidence record for TriageCore, taken on 2026-07-02 after the traceability, authority-manifest, and hygiene commits landed. It follows the command sequence in [reviewer-smoke-runbook.md](reviewer-smoke-runbook.md) plus the review-queue and signed route-decision verification checks.

This is an evidence record of one repository state and one local runtime state on one date. It is not a release certification, and it does not prove production readiness, safety, legal compliance, or correctness of model outputs.

## Commit Baseline

| Commit | Description |
| --- | --- |
| `60839d8` | docs: add reviewer traceability lifecycle path |
| `a7fb0e4` | feat: add task-scoped agent authority manifest check (CR-090) |
| `d84fd5e` | chore: remove tracked backup artifacts |

Branch: `main`. HEAD at time of checks: `d84fd5e`. Working tree: clean.

## Commands and Results

| # | Command | Result | Status |
| --- | --- | --- | --- |
| 1 | `git status --short` | Empty output — clean tree at `d84fd5e` | PASS |
| 2 | `python -m pytest -q` | `655 passed, 2 skipped` in ~67s | PASS |
| 3 | `tc doctor` | `Result - Overall: OK`, exit 0. Repo root and branch confirmed, git clean, ledger readable/writable. Runtime safety postures: external execution `blocked`, human approval `human-review-required`, network/tool execution `unavailable` | PASS |
| 4 | `tc review list` | Exit 0, `Status: available`, 100 pending items | PASS (caveat 1) |
| 5 | `tc audit --privacy-invariants` | `Privacy invariant audit passed: 697 record(s) checked` — no forbidden raw-content keys in the persistent ledger | PASS |
| 6 | `tc audit --verify-signatures --kind route_decision` | Exit 0: `valid_signed=1 invalid_signed=0 unsigned=0 malformed=0 skipped_non_target=696 strict=off`, with `PASS event_type=route_decision task_id=audit-signed-route-decision-smoke-test agent_id=router-tools` | PASS (caveats 2, 3) |

This is the first recorded checkpoint at which all six smoke commands pass.

## Caveats

1. **Stale review backlog.** The 100 pending review-queue items are residue from early-June 2026 routing, firewall, and backend experiments (router bypasses on destructive-operation keywords, local backend connection errors, quality-gate failures). They are deliberately undecided: nothing is marked reviewed without an explicit human decision. They are honest queue state, not current live work and not a hidden failure.
2. **Signed coverage is one opt-in smoke event.** The signature verification PASS covers exactly one metadata-only signed `route_decision` smoke-test event, written via the opt-in path in [signed-route-decision-verification.md](signed-route-decision-verification.md). It demonstrates that the verification path works end to end against the current local registry. It does not demonstrate signed coverage of real route decisions — the other 696 ledger events are non-target for this check, and signing remains opt-in. A valid signature proves provenance and tamper evidence of the record only; it does not prove correctness, safety, authorization, or approval.
3. **The baseline follows a same-day local identity repair.** Earlier on 2026-07-02, the local identity registry contained a corrupt synthetic record that caused this same verification command (and `tc identity list`) to crash with an unhandled traceback. That state was repaired in an explicitly approved local-maintenance step before this checkpoint. A corrupt registry would still crash these commands rather than degrade gracefully; see follow-up item 1 below.

## Local Runtime Identity Baseline

Observed read-only on 2026-07-02. This is local machine evidence, not committed source: the `.triagecore/` directory is gitignored, and this section describes one machine's runtime state on one date.

- Registry `.triagecore/identity/agents.json`: one active identity — `agent_id=router-tools`, role "Route decision signer", ed25519, capability `route_decision:sign`, not rotated. A public key and fingerprint are present (fingerprint prefix `d11abea9`); full key material is intentionally not reproduced here.
- `agents.json.backup-20260702`: preserved pre-repair backup containing the corrupt record, kept as a forensic artifact.
- Key files: `router-tools.key` (matches the active identity) and `project-steward.key` (2026-06-13), the latter **orphaned** — a private key file with no corresponding registry entry. `tc identity list` and the identity doctor do not currently flag orphaned key files; see follow-up item 2 below.

## Conclusion

TriageCore is reviewer-ready with disclosed runtime caveats as of this checkpoint: clean tree, full test suite green, environment doctor OK, privacy invariants holding across all 697 persisted ledger records, review queue inspectable, and the signed route-decision verification path demonstrably working against a healthy local registry.

Authority manifests validated by `tc authority check` (CR-090) are review evidence, not permission. A passing checkpoint is evidence of the recorded repository and runtime state on the recorded date, nothing more.

## Known Follow-Up Work (Not Started)

Each item should be its own narrow change request, in this order:

1. **Registry load robustness.** A malformed or corrupt `.triagecore/identity/agents.json` should produce a clear fail-closed `registry_load_failed` finding instead of an unhandled traceback. Affected paths: `verify_ledger_event_signatures_in_ledger` (`triage_core/task_ledger.py`) and `tc_identity_list` (`triage_core/tc_cli.py`).
2. **Identity doctor orphaned-key warning.** The identity doctor should detect private key files that have no corresponding registry entry and warn. Warn only; never delete key material.
3. **Review backlog classification.** The 100 pending items are documented here as early experiment residue. Any future grouping or reporting command should be read-only. Do not bulk-clear the backlog; clearing items requires explicit per-item (or explicitly approved per-cohort) human decisions recorded as `review_completed` events.

## Non-Claims

- This checkpoint is not a release certification and makes no production, compliance, legal, critical-infrastructure, or safety-certification claims.
- Signatures are provenance and tamper evidence only; they are not approval, authorization, or safety proof.
- Authority manifests describe scope for review; they do not grant permission or execution authority.
- No part of this checkpoint substitutes for a human approving one exact canonicalized action packet.
