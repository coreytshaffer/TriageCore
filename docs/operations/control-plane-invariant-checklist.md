# Control-Plane Invariant Checklist

## Purpose

One page listing the control invariants any future slice must preserve,
where each is enforced, and how a reviewer verifies it without trusting
this document. "Verified 2026-07-07" means the check was actually run or
the covering tests passed in the full-suite run recorded in
[reviewer-checkpoint-2026-07-07.md](reviewer-checkpoint-2026-07-07.md)
(803 passed / 2 skipped at `f8bf33c`).

This checklist restates existing invariants. It grants nothing, changes
nothing, and is not a certification.

## The Invariants

| # | Invariant | Enforced by | Reviewer verification | Status |
|---|---|---|---|---|
| 1 | Corrupt/unreadable identity registry fails closed: bounded `registry_load_failed` categories, exit 1, no traceback, no secret material, no ledger mutation, no partial verification output. | `triage_core/agent_identity.py` typed exceptions + CLI handler in `triage_core/tc_cli.py` (CR-097) | `python -m pytest tests/test_cr_097_identity_registry_load.py -q` | Verified 2026-07-07 (in full suite) |
| 2 | Persisted ledger records contain no prompts, completions, embeddings, credentials, or private paths. | Privacy scanner + persistent invariant audit (CR-002, CR-021) | `tc audit --privacy-invariants` | Verified 2026-07-07 (698 records passed) |
| 3 | Signatures prove provenance and tamper evidence only — never approval, safety, correctness, or execution authority. | Doc + CLI wording throughout; verification output is metadata-only | `tc audit --verify-signatures --kind route_decision`; confirm output claims verification counts only | Verified 2026-07-07 (valid_signed=2, invalid=0, unsigned=0, malformed=0) |
| 4 | A passing authority manifest grants nothing; validation is static and metadata-only; denied actions take precedence; omissions never waive review gates. | `triage_core/agent_authority.py` (CR-095, PR #80 hardening) | `tc authority check --manifest docs/security/examples/agent_authority_manifest_reviewer.json`; `pytest tests/test_agent_authority.py -q` | Verified 2026-07-07 (in full suite) |
| 5 | Local-only routing fails closed before the bounded external-safe Qwen path is considered. | CR-004B enforcement in routing; `triage_core/safe_task_packet.py` | `pytest tests/test_local_only_routing.py tests/test_qwen_cloud_routing.py -q` | Verified 2026-07-07 (in full suite) |
| 6 | TriageDesk GUI is read-only: zero direct LLM calls, file writes, or ledger mutations; all access via `triagedesk_adapter.py`. | Adapter-only architecture (baseline tag `triagedesk-daily-driver-baseline-2026-06-25`) | `pytest tests/test_cybernetic_validators.py -q` and adapter tests; code inspection of `triage_core/triagedesk_adapter.py` | Verified 2026-07-07 (in full suite) |
| 7 | Read-only by default; explicit mutation only; exports have no default write location, fail closed on existing files, and repeat byte-identically. | Runtime strategy export path (CR-109/CR-112); workspace write commands require explicit intent | `pytest tests/test_reports.py -q` plus runtime-strategy tests; attempt an export without `--output` | Verified 2026-07-07 (in full suite) |
| 8 | Deterministic fixture reports never ingest recorded or probe data; recorded/probe tiers are always labeled and validated via strict mapping (unknown fields rejected). | `triage_core/runtime_strategy_evidence.py` (CR-104 → CR-112); boundary for future telemetry defined in [local-backend-telemetry.md](local-backend-telemetry.md) | Runtime-strategy focused tests; confirm `recorded-report` requires explicit `--input` | Verified 2026-07-07 (in full suite) |
| 9 | Failure reporting uses closed vocabularies (reason codes), never raw error text; quality gates qualify cost interpretations but never rewrite or rank them. | CR-106/CR-108 vocabularies; CR-097 categories; CR-113 brief for future telemetry | Grep CLI output in tests for reason codes; confirm no "best strategy" output exists | Verified 2026-07-07 (in full suite) |
| 10 | Human review gates stay outside every automated loop; no evaluator, supervisor, or agent verdict becomes approval authority. | Workflow doctrine (README Safety Invariants, AGENTS.md §7); `tc doctor` runtime-safety postures | `tc doctor` → external execution `blocked`, human approval `human-review-required`, network/tool execution `unavailable` | Verified 2026-07-07 (doctor output) |

## Rules for Future Slices

- A slice that weakens any row above is out of scope by default and needs
  its own explicit, human-approved CR that names the row it changes.
- A slice that adds a new persisted record kind must route it through
  strict mapping validation and the privacy invariant (rows 2, 8, 9).
- A slice that adds a new CLI surface must default to read-only and fail
  closed (rows 1, 7, 9).
- No slice may make signing, manifest validation, or evaluation imply
  approval (rows 3, 4, 10).

## Related Docs

- [reviewer-checkpoint-2026-07-07.md](reviewer-checkpoint-2026-07-07.md)
- [fable-exit-audit-2026-07-07.md](fable-exit-audit-2026-07-07.md)
- [outer-loop-control-review-recipe.md](outer-loop-control-review-recipe.md)
- [future-agent-maintainer-handoff-2026-07-07.md](future-agent-maintainer-handoff-2026-07-07.md)
