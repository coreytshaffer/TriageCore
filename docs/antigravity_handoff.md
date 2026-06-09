# Antigravity Handoff

Last updated: 2026-06-05

## Paste-Ready Prompt

You are continuing TriageCore from the current `main` branch.

Treat the latest Codex checkpoint as the Phase 13 backlog baseline. Codex has imported SafeTask-derived learning artifacts into `docs/learning/`, added the validation-first `import-learning-seeds` command, added the static resilience router, added route-decision and worker-result ledger telemetry, and updated `docs/backlog.md` with Phase 13: Resilience Routing And Assignment Learning Store.

The imported artifacts define:

- assignment outcome telemetry
- assignment preflight records
- context pack templates
- task-class to local-combo routing
- waste controls and escalation rules
- improvement ranking and low-priority containers
- resilience/capability-aware routing for cloud, local heavy, local fast, deterministic, and human-handoff paths
- SafeTask-derived JSONL seed examples for preflights, context packs, and outcomes

Use the current Codex/Antigravity division of labor:

- Antigravity is the high-throughput implementation lane for IDE-native drafting, local pipeline coordination, and rapid backlog movement.
- Codex is the credibility and stabilization lane for repo reconciliation, methodology language, evidence boundaries, documentation quality, verification, and Git closeout.
- Antigravity output should be concrete and useful, but still treated as a reviewable draft until Codex/human review confirms the repo state, tests, and paper-facing claims.

Story 13.3 is complete enough for the current backlog: `python -m triage_core.cli import-learning-seeds --source-dir docs\learning\examples --ledger-dir .triagecore` validates the three SafeTask-derived seed files by default and requires `--write` before storing records under `.triagecore/learning_seeds/`.

Story 13.4 is complete enough for the current backlog: `triage_core/routing/resilience_router.py` exposes `choose_resilience_route()` with static decisions for cloud, local-heavy, local-fast, deterministic, and human-handoff paths.

Story 13.5 is complete enough for the current backlog: `route_decision` and `worker_result` events are built from the resilience router and emitted at the `TriageClient.run_task()` boundary for benchmark and stability-pass runs. Safety routes record `worker_result_status=not_attempted` and do not count as backend failures.

Your next high-throughput implementation target is **Phase 13 Story 13.6: Add Circuit Breakers And Degraded Mode States**.

Build a first working slice that cools down unstable routes and exposes degraded-mode state explicitly. Keep it deterministic and reviewable. Imported SafeTask records remain seed evidence until human-reviewed learning approvals promote rules.

Suggested outputs:

1. A circuit-breaker state module for cloud, local-heavy, and local-fast routes.
2. Explicit mode states such as `normal`, `degraded_cloud`, `offline_local`, `local_minimal`, `deterministic_only`, and `human_handoff`.
3. A small state-transition policy driven by recent route failures and recoveries.
4. Tests proving unstable routes cool down, successful recovery does not flap immediately, and degraded mode affects route choice deterministically.
5. Documentation that degraded mode and circuit-breaker state are execution guardrails, not automatic learning-rule approvals.

Important guardrails:

- Do not remove or bypass human review.
- Do not treat imported learning records as approved routing changes.
- Do not re-combine SafeTask AI and TriageCore; SafeTask-derived records are external examples only.
- Preserve the current context pack artifacts, `context_budgeted` ledger fields, and existing learning proposal/review files.
- Keep SafeTask AI and TriageCore separate: SafeTask records are external seed evidence only.
- Keep the implementation small enough for Codex to reconcile and stabilize afterward.

Verification to run before handing back:

```powershell
python -m pytest
git status --short --branch
```

Expected current baseline before your changes:

- Branch: `main`
- Repo is ahead of origin with existing local changes; inspect `git status --short --branch` before editing.
- Phase 13 backlog is defined in `docs/backlog.md`.
- Seed artifacts are in `docs/learning/`.

## Codex Stability Notes

Codex should be used after the Antigravity implementation to:

- inspect the diff for placeholders or accidental regressions
- reconcile any UI/CLI/doc drift
- run focused and full tests
- update methodology and backlog language
- commit and push only after the work is evidence-bound and reproducible
