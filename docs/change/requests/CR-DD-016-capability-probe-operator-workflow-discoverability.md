# CR-DD-016: Capability Probe Operator Workflow Discoverability

## Status

- **Status:** Proposed.
- **Type:** Documentation / Operator Workflow.
- **Priority:** Research backlog. Downstream of CR-DD-013; does not reopen or amend it.
- **Implementation authority:** Not authorized. This proposal PR changes no
  source code. If separately approved, the bounded implementation described
  below may modify `triage_core/tc_cli.py` only for the specified argparse
  help text; this CR itself grants no authority to make that change.
- **Human approval requirement:** Explicit human review and approval of this Change
  Request is required before any implementation begins.

This document records a requirements contract only. It grants no execution, integration,
or standing authority.

## Scope

Documentation and CLI help text for the existing local-capability probe workflow
(CR-114, CR-DD-013). Nothing else.

## Problem Statement

CR-DD-013 established that a declared-but-unobserved local capability resolves to
`Configured`, not `ObservedAvailable`, and that `local_only` tasks fail closed rather than
treat an unobserved declaration as health. This is deliberate, documented, and tested
behavior — not a defect.

What CR-DD-013 also required, but did not deliver, is the operator-facing half of its own
stated mitigation: *"the mitigation is the configured-capability path and explicit release
notes, not a silent optimistic default"* (CR-DD-013, Risks And Mitigations). No such release
notes or operator procedure exist. `docs/daily_driver_quickstart.md` — the primary operator
onboarding document — contains no mention of `tc probe`, the `[capability]` configuration
section, or the two-step procedure required to move a declared capability from `configured`
to `observed`.

The result is an operator-workflow gap: the mechanism works exactly as designed, but the
path to using it correctly is not discoverable from the documentation an operator would
actually read. An operator who declares `local_fast`/`local_heavy` in `triagecore.toml` and
never separately runs `tc probe` will see every `local_only` task fail closed, with no
indication in the standard onboarding material that a probe step exists or why it matters.

## Motivating Evidence

Not authoritative evidence-window data; cited here only to establish that the gap is real
and recurring, not hypothetical:

- Day-1 Trial 001 (`daily-use-evidence-window-2026-08-01.md`): capability evidence missing
  or unknown; blocked with `recommended_route: human_handoff`,
  `reason_code: ambiguous_or_remote_route`.
- A trial run during this CR's own investigation (`task_id`
  `12fe348e-94fd-43da-8bb8-2aa61a3eb949`, isolated ledger
  `.triagecore/daily-use-window/2026-08-08/ledger.jsonl`): identical block signature.
  `runner_selected` recorded `capability_state: "configured"`; a read-only check confirmed
  the local backend was in fact reachable at the time. No probe record had ever been wired
  into `triagecore.toml`.

Both are the same root cause: no `[capability].local_probe_record_path` was ever configured,
so `resolve_from_config` has nothing to read and correctly reports `Configured`, never
`ObservedAvailable`, regardless of actual backend health.

## Determination

**Operator-workflow gap, with missing discoverability and documentation as the immediate
defect.** Not an architectural gap: CR-DD-013 argued the fail-closed design explicitly and
tested against the specific failure of promoting `Configured` to healthy. Not merely
"missing documentation" in a narrow sense either: the current operator path is brittle
enough — an undocumented two-step manual procedure with no CLI cross-reference and a short,
undocumented-in-onboarding freshness window — that discoverability and usability are
themselves part of the control surface here, not a cosmetic afterthought.

## Objective

Make the existing, intended workflow discoverable and usable as documented, without
changing what the workflow does, what it defaults to, or what it enforces.

## Invariants Preserved

This CR MUST NOT weaken, and its acceptance criteria must not be satisfiable in a way that
weakens, any of the following:

1. `Configured` MUST NOT imply `ObservedAvailable`.
2. `tc run` MUST NOT silently probe.
3. Stale or absent observations MUST remain non-authoritative.
4. `local_only` MUST continue to fail closed when the required local capability is not
   observed.
5. Probe evidence MUST remain explicit, inspectable, and time-bounded.

## In Scope

1. **Documentation.** Add the missing operator procedure to
   `docs/daily_driver_quickstart.md` (or a dedicated linked operations doc): run
   `tc probe --source-type <type> --base-url <url> --output <path>`, then set
   `[capability].local_probe_record_path = "<path>"` in `triagecore.toml`. State plainly
   that this is a manual, repeatable step — not a one-time setup — and document the
   300-second default freshness window and its consequence: a probe older than 300 seconds
   is treated identically to no probe at all.
2. **CLI discoverability.** Update `tc probe --help` text so it explicitly states that a
   persisted `--output` file has no effect on `tc run` until its path is also set as
   `[capability].local_probe_record_path` in `triagecore.toml`. Text only; no new flags, no
   new behavior.

## Provisional Implementation Allowlist

If this requirements contract is separately approved, the bounded implementation
is proposed to touch exactly these four paths — nothing else:

```text
docs/daily_driver_quickstart.md
triage_core/tc_cli.py
tests/test_tc_cli.py
docs/change/requests/CR-DD-016-capability-probe-operator-workflow-discoverability.md
```

Within `triage_core/tc_cli.py`, the permitted change is limited to `argparse`
help/description text for `tc probe`; no command dispatch, function body, flag
shape, default value, probe behavior, routing behavior, capability-resolution
behavior, or execution path change. The CR file itself would receive only
implementation/status/evidence updates.

Named exclusions — files a future implementer might be tempted to touch, and
explicitly must not, because this CR changes only how the existing workflow
explains itself, not how the workflow operates:

```text
triage_core/local_backend_probe.py
triage_core/capability_evidence.py
triage_core/config.py
triage_core/client.py
triage_core/routing/resilience_router.py
```

This allowlist is provisional and proposed only. Listing it here grants no
implementation authority; a separate, explicit approval is still required
before any file on it may be modified.

## Explicitly Out of Scope

- **No default `--output` path for `tc probe`.** A predictable default location (something
  like `.triagecore/local-backend-probe.json`) looks harmless but reopens exactly the class
  of problem recorded in the worktree ledger-census-gap finding
  (`docs/operations/evidence-ledger-worktree-limitation-2026-08-07.md`): which checkout owns
  the file in a multi-worktree environment, whether a probe made in one worktree could be
  read as authorizing routing in another, whether the path should be canonical-checkout- or
  config-file-relative, atomic replacement under concurrent probes, and whether stale
  evidence lingering at a predictable path creates confusing state. This CR leaves
  `--output` explicit and defers a default path to a separate, later design question
  informed by that same lesson.
- **No implicit persistence** of any kind beyond what `--output` already does explicitly.
- **No multi-worktree semantics** introduced, implied, or assumed.
- **No change to `freshness_seconds`, its default, or its semantics.** The 300-second
  window is documented as-is. Whether the intended operational unit is a probe-per-run,
  probe-per-session, or a bounded-refresh-window is recorded here as an open design
  question for a later CR, not answered by this one. Changing freshness semantics would
  reopen CR-DD-013 policy; this CR does not.
- **No change to `capability_evidence.py`, `resolve_from_config`, `resolve_capability`,
  `choose_resilience_route`, or any routing decision.**
- **No implementation authority of any kind.** Acceptance of this CR authorizes writing the
  docs/help-text slice only once separately approved; it authorizes nothing else.

## Related, Explicitly Out of Scope of This CR

Two adjacent, independently-verified observations surfaced while tracing the routing
consequence of this gap. Both are real and code-confirmed; neither is connected here to
this CR's finding, and neither is in scope for it:

- **Classifier terminal fallback.** `TaskClassifier.classify` (`classifier.py`) attempts a
  live Ollama call with a 1.5-second timeout before falling back to a regex classifier
  whose terminal, no-match fallback is `"refactor"` — a specific, semantically wrong
  category rather than an `"unknown"` or neutral result. **The sunscreen run did not
  establish that the classifier reached the `"refactor"` fallback. The fallback was
  discovered during adjacent code tracing and remains an unconnected observation until a
  separate investigation establishes the actual execution path.** That investigation is
  planned as its own read-only thread, independent of this CR.
- **`privacy_level` normalization.** `TriageClient._build_resilience_route_input`
  (`client.py`) hardcodes `privacy_level="local_ok"` regardless of the packet's actual
  requested privacy class, and `"local_ok"` is not a member of the resilience router's own
  `LOCAL_ONLY_VALUES`. Local-only enforcement for `tc run` appears to happen entirely in a
  separate, later guard (`client.py`, post-route-decision). Whether this is intentional
  normalization, dead/legacy behavior, or a genuine propagation defect is unestablished and
  is planned as a separate read-only investigation, independent of both this CR and the
  classifier thread above.

These two threads concern different assurance properties (semantic classification
integrity versus privacy-authority propagation) and are not to be combined into one
investigation or CR even if both eventually warrant changes.

## Acceptance Criteria

- [ ] `docs/daily_driver_quickstart.md` (or a linked operations document) documents the
      full `tc probe` → `[capability].local_probe_record_path` procedure, including the
      300-second freshness consequence, in language an operator encountering a
      `Configured`-not-`Observed` block could act on without reading source code.
- [ ] `tc probe --help` text references `[capability].local_probe_record_path` by name as
      the required follow-up step for persisted output to take effect.
- [ ] `triage_core/tc_cli.py` is the only permitted file under `triage_core/`,
      and changes to it are limited to `argparse` help/description text for
      `tc probe`; no command dispatch, function body, flag shape, default value,
      probe behavior, routing behavior, capability-resolution behavior, or
      execution path changes.
- [ ] No schema, CLI command or flag shape, default value, command dispatch,
      probe execution, capability resolution, routing decision, persistence
      behavior, or runtime semantics change.
- [ ] A focused CLI regression test proves that `tc probe --help` names
      `[capability].local_probe_record_path` and explains that persisted
      `--output` does not affect `tc run` until that configuration path is set.
- [ ] All five invariants listed above remain true and unmodified by this slice.
- [ ] The two adjacent findings (classifier fallback, `privacy_level` normalization) are
      not addressed, referenced as resolved, or folded into this CR's acceptance.

## Non-Goals

- Redesigning or reopening any part of CR-DD-013's resolution precedence.
- Adding a default probe-output location or any repository-relative persistence
  convention.
- Changing freshness semantics or the operational cadence of probing.
- Investigating or resolving the classifier fallback or privacy-normalization findings.
- Any runtime, schema, or routing change.

## Sequencing

This is Track A of a three-track sequence, tracks B and C being separate, independent,
read-only investigations that must not be combined with each other or with this CR:

- **A — this CR.** Capability probe operator-workflow discoverability. Docs + help text
  only.
- **B — Classifier fallback investigation.** Determine whether `"refactor"` is genuinely
  the universal terminal fallback, what downstream routing decisions depend on it, and
  whether any specific trial (including the one motivating this CR) actually traversed
  that path. Read-only until its own findings warrant a separately scoped CR.
- **C — Privacy propagation investigation.** Trace `--privacy` from CLI parsing through
  `TaskPacket` construction, `_build_resilience_route_input`, `choose_resilience_route`,
  and the post-decision guard in `client.py`. Establish whether `privacy_level="local_ok"`
  is intentional normalization, legacy dead code, or a genuine propagation gap. Read-only
  until its own findings warrant a separately scoped CR.
