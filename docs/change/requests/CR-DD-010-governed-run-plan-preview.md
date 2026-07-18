# CR-DD-010: Governed Run Plan Preview

## Status

Implemented and merged through PR #104 on 2026-07-17 at merge commit
`1275819bd10a13dd572a74bac0a88f0d9d70b1d0`.

Human implementation approval was provided on 2026-07-17. The implementation
passed focused, full-suite, and persistent-privacy validation.

## Implementation Authority

Once approved, this CR authorizes only the non-executing `tc run --plan`
preview described below and its focused tests and documentation updates.

Previewing a plan does not approve that plan, authorize execution, satisfy a
human-review gate, or create evidence that execution occurred.

## Scope

Add a deterministic, non-executing planning mode to the existing governed run
surface:

```text
tc run "<prompt>" --plan --model <profile> [existing task-input and governance flags]
```

The preview reuses the current task assembly, packet preflight, privacy,
specialist-routing, resilience-routing, and context-budget logic without
invoking `TriageClient.run_task`.

Because `TaskClassifier.classify()` may contact a configured local model before
falling back to regex classification, planning must explicitly use a pure
deterministic classification path. The report must identify that classification
as a preview assumption and must not claim that a later execution route is
guaranteed to match it.

The preview reports:

- task-input presence and lengths without echoing prompt or inline-data content;
- context source paths in operator-supplied order and per-source sizes;
- the selected token-budget model profile, estimated input tokens, usable
  budget, and `fits` or `over_budget` status;
- the declared privacy class, privacy-preflight result, bounded finding codes,
  egress eligibility, and cloud-authorization posture;
- deterministic task classification, proposed logical route, route reason,
  fallback depth, human-review posture, and configured backend/model binding;
- deterministic specialist-risk assumptions and the existing ProjectSteward
  ethical-firewall posture, without exposing matched terms or raw reasons;
- which route inputs are declared or static and which live health inputs were
  not observed;
- bounded conditions under which policy could consider another local route, a
  governed handoff, or the existing Qwen cloud route;
- expected packet, privacy, route, output-validation, and human-review checks.

`--model` is required with `--plan`; the preview must not infer a context window
from a logical route.

`--plan` writes its bounded report to stdout only. It rejects `--output`,
`--print`, `--ledger-dir`, and `--no-ledger`, whose meanings would be ambiguous
in planning mode.

`--allow-cloud` is informational only for `external_safe` and `public`
previews. The existing `local_only` plus `--allow-cloud` combination remains an
input error.

## Output Contract

The default output is deterministic, bounded, ASCII-safe text with these
sections:

1. `Task`
2. `Context`
3. `Privacy and Egress`
4. `Logical Route`
5. `Escalation Conditions`
6. `Expected Verification`
7. `Preview Boundaries`

The report must not contain prompt or inline-data content, context-file
contents, matched sensitive values, environment secrets, backend responses,
timestamps, or generated random task IDs.

For identical inputs and configuration, repeated previews must be
byte-identical.

## Non-Goals

- No model, embedding, local-execution, or cloud-execution call.
- No `TriageClient.run_task` call.
- No backend construction, health check, metadata probe, HTTP request, or
  subprocess.
- No ledger creation, read, append, mutation, or signed event.
- No artifact write or default output location.
- No confirmation prompt, approval capture, execution-after-preview,
  approval-and-resume, persistence, retry, or checkpoint behavior.
- No result verification, evaluator invocation, artifact summary, or
  efficiency report.
- No TriageDesk changes.
- No new routing policy, backend, circuit breaker, provider, or live capability
  signal.
- No budget enforcement, truncation, compression, or context rewriting.
- No changes to privacy, external-safe, human-review, identity, signature,
  admission, or authority semantics.
- No claim that a previewed route will remain available or be selected later.
- No claims of energy, token, cost, latency, quality, or safety improvement.

## Description

CR-DD-009 exposed the governed execution loop through `tc run`, but planning
remains split across separate commands and runtime-only decisions. `tc context
plan` estimates one input against a model profile, while `tc run` assembles
inputs, preflights privacy, selects a route, and executes in one invocation.

CR-DD-010 adds the smallest missing integration seam: a side-effect-free
preview over the same operator inputs and existing pure policy components. It
lets the operator inspect context size, privacy and cloud posture, a proposed
logical route, route assumptions, escalation conditions, and expected checks
before any model call or evidence write.

The result is advisory. Runtime state may change between preview and later
execution. A plan is neither approval nor evidence that the planned action
occurred.

## Risks And Mitigations

- **Plan/execution drift:** Reuse shared pure helpers where practical, identify
  deterministic classification and unobserved runtime inputs, and make no
  execution guarantee.
- **False health claims:** Label route bindings as logical or
  configuration-derived and state that no live probe occurred.
- **Sensitive preview output:** Render only paths, lengths, classifications,
  and bounded reason codes; never render raw context or matched values.
- **Policy duplication:** Add parity tests around shared packet, privacy, and
  routing helpers.
- **Accidental side effects:** Tests fail if planning opens a ledger, constructs
  or calls a backend, invokes `run_task`, writes a file, starts a subprocess, or
  performs network I/O.
- **Nondeterminism:** Do not generate timestamps, random IDs, or
  environment-dependent prose.

## Acceptance Criteria

- [x] `tc run "<prompt>" --plan --model <profile>` prints all seven required
  sections and exits `0` for a valid preview.
- [x] Planning accepts existing `--files`, `--data`, `--privacy`, and optional
  `--task-id` inputs without executing.
- [x] `--model` is required with `--plan`; unknown profiles fail with a bounded
  input error.
- [x] Context sources remain ordered, and token estimates and budgets match the
  existing context-plan calculation for the assembled input.
- [x] Privacy preflight uses the existing packet verification/scanner path and
  prints only bounded finding codes.
- [x] `local_only` plus `--allow-cloud` remains a bounded input error.
- [x] External-safe/public input distinguishes egress eligibility from explicit
  operator authorization.
- [x] Logical route, reason, fallback depth, human-review posture, and backend
  binding derive from deterministic classification plus current routing and
  configuration logic.
- [x] Sensitive-context prompts that trigger the existing ProjectSteward
  ethical firewall preview as `human_handoff`, require human review, bind no
  backend, and expose only bounded firewall status and escalation labels.
- [x] The report identifies deterministic/static assumptions and states that no
  backend probe occurred.
- [x] Expected verification reports current required checks and reports absent
  output validation as `not_configured`.
- [x] Planning rejects `--output`, `--print`, `--ledger-dir`, and
  `--no-ledger`.
- [x] Planning performs no model calls, backend construction/probes, network
  I/O, subprocesses, ledger access/mutation, or file writes.
- [x] Prompt, inline data, context contents, matched sensitive values, and
  secrets do not appear in output.
- [x] Repeated previews with identical inputs and configuration are
  byte-identical.
- [x] Existing `tc run` behavior and `tests/test_tc_run_cli.py` remain
  unchanged and green.
- [x] The daily-driver spec records CR-DD-009 as implemented and CR-DD-010 as
  the next bounded integration slice.

## Tests

Add focused offline tests covering:

- minimal valid local-only preview;
- ordered multiple-file context accounting plus inline data;
- fitting and over-budget profiles;
- unknown or missing `--model`;
- privacy-blocked sensitive input without raw-match disclosure;
- rejection of `local_only` plus `--allow-cloud`;
- external-safe/public planning with and without `--allow-cloud`;
- deterministic local, cloud-eligible, and human-handoff route renderings;
- configured/hardcoded ethical-firewall human-handoff behavior without matched
  term disclosure or ledger access;
- validator-not-configured disclosure;
- rejection of execution/output flags;
- byte-identical repeated output;
- no ledger creation and a byte-identical pre-existing ledger;
- no artifact writes; and
- traps proving no backend, model, network, subprocess, or `run_task` call.

## Allowed Files

Implementation is limited to:

- `docs/change/requests/CR-DD-010-governed-run-plan-preview.md`
- `triage_core/tc_cli.py`
- `triage_core/run_plan.py` — new pure planning/rendering module
- `triage_core/classifier.py` — deterministic helper extraction only
- `triage_core/client.py` — pure-helper extraction only if required to prevent
  routing-policy duplication
- `tests/test_tc_run_plan_cli.py`
- `tests/test_tc_run_cli.py` — regression/parity tests only
- `docs/architecture/daily_driver_orchestrator_spec.md`
- `docs/daily_driver_quickstart.md`
- `docs/current_backlog.md`
- `docs/change/change_log.md`

Changes outside this list require a separately approved scope amendment.

## Verification

Completed on 2026-07-17:

- Focused plan/run/classifier validation: `42 passed`.
- Full offline regression suite: `1022 passed, 3 skipped`.
- Persistent privacy audit: `698 record(s) checked`; passed.
- `git diff --check`: passed with line-ending conversion warnings only.

- `python -m pytest -q tests/test_tc_run_plan_cli.py tests/test_tc_run_cli.py`
- `python -m py_compile triage_core/run_plan.py triage_core/tc_cli.py triage_core/classifier.py triage_core/client.py`
- `python -m pytest`
- `python -m triage_core.tc_cli audit --privacy-invariants`
- `git diff --check`
- Manual offline smoke: run one local-only preview, confirm all sections appear,
  confirm no raw task/context content appears, confirm no ledger or artifact is
  created, and confirm repeated output is byte-identical.

## Dependencies / Sequencing

- Depends on the implemented CR-DD-009 governed `tc run` surface, CR-125
  terminal resilience-route behavior, and CR-126 privacy-before-persistence
  behavior, plus the existing token-budget/context-plan components.
- Must precede confirmation/execution coupling, approval-and-resume, durable
  plan records, combined artifact/evidence summaries, efficiency integration,
  and any TriageDesk action surface.
- Live capability probes, circuit breakers, budget enforcement, frontier
  providers, and actionable TriageDesk controls remain separate future CRs.
