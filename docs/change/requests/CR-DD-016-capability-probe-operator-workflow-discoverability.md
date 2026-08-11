# CR-DD-016: Capability Probe Operator Workflow Discoverability

## Status

- **Status:** Implementation candidate verified; completion is defined by merge of the
  implementation PR into `main`.
- **Type:** Documentation / Operator Workflow.
- **Priority:** Research backlog. Downstream of CR-DD-013; does not reopen or amend it.
- **Implementation authority:** Authorized for exactly the four-path Implementation
  Allowlist below, exercised only within it. No further changes are authorized. Merge of
  the implementation PR is the final human gate; once merged, that bounded authority is
  spent.
- **Human approval requirement:** Explicit human review and approval of this Change
  Request was required before implementation began, and was given separately. Merge of
  the implementation PR is the final acceptance gate.

This document records a requirements contract with a verified implementation candidate,
bounded to exactly the allowlist below. It grants no execution, integration, or standing
authority beyond that bounded implementation.

**Implementation evidence:** commit `01e8b14` on PR #157
(`claude/cr-dd-016-implementation` → `main`).
`docs/daily_driver_quickstart.md` gained a new "Understand
local-capability probing" section documenting the three-case contract below and the
300-second freshness consequence. `triage_core/tc_cli.py`'s `tc probe --output` argparse
help text now names `[capability].local_probe_record_path` as the required follow-up
config key. `tests/test_tc_cli.py` gained
`test_tc_probe_help_names_capability_probe_record_path`, asserting (against
whitespace-normalized output, so it does not depend on the ambient terminal width) that
the help text names `[capability].local_probe_record_path`, `triagecore.toml`, and
explains that persisted `--output` has no effect on `tc run` by itself. No other file was
touched; no schema, CLI flag, default value, command dispatch, probe execution,
capability resolution, or routing decision changed.

## Corrective Amendment — Capability Observation Semantics

Post-merge, read-only reconciliation against CR-DD-013's actual resolution code
(`resolve_capability`, `triage_core/capability_evidence.py`) and this repository's own
checked-in `triagecore.toml` found that the causal account below, as originally merged
in PR #155, conflated two evidentially different trials under one claim: that an
unobserved declaration leaves `local_only` failing closed. It does not. A valid
`[capability]` declaration with a resolved model binding resolves to `Configured` and
authorizes route consideration without any probe — the repository's own tracked
`triagecore.toml` is in exactly that state right now. Day-1 Trial 001 (no declaration
existed yet; pre-CR-DD-014) genuinely fails closed for that reason; the Aug-8 trial
cited alongside it (post-CR-DD-014, both routes declared and bound) does not, and its
actual block traces to an unrelated, sensitivity-driven routing selection, not to
capability evidence.

This amendment supersedes the affected statements in Problem Statement, Motivating
Evidence, Determination, Invariant 4, and Acceptance Criterion 1 below. It changes no
proposed scope, grants no implementation authority beyond what was already proposed,
and does not reopen CR-DD-013's own resolution precedence — CR-DD-013 remains the
governing runtime semantics; this amendment brings CR-DD-016's description of them
back into agreement.

## Scope

Documentation and CLI help text for the existing local-capability probe workflow
(CR-114, CR-DD-013). Nothing else.

## Problem Statement

CR-DD-013 established that a declared-but-unobserved local capability resolves to
`Configured`, not `ObservedAvailable` — the evidence tier stays an operator assertion,
never a fabricated health claim. A valid declaration with a resolved model binding still
authorizes route consideration in that state; only the absence of both a usable
observation and a usable declaration leaves `local_only` failing closed. This is
deliberate, documented, and tested behavior — not a defect.

What CR-DD-013 also required, but did not deliver, is the operator-facing half of its own
stated mitigation: *"the mitigation is the configured-capability path and explicit release
notes, not a silent optimistic default"* (CR-DD-013, Risks And Mitigations). No such release
notes or operator procedure exist. `docs/daily_driver_quickstart.md` — the primary operator
onboarding document — contains no mention of `tc probe`, the `[capability]` configuration
section, or what running a probe actually changes once a declaration already exists.

The result is an operator-workflow gap, but not the one originally described here: a
declaration alone is enough for `local_only` work to proceed, so the risk is not that
work is blocked without a probe. The risk is that an operator has no discoverable way to
learn what a probe changes — that it can conclusively suppress a declared route on a
confirmed outage, that it can catch a declared model that isn't actually loaded, and that
its absence means routing decisions rest on an unverified assertion rather than a checked
one. None of that is stated anywhere in the standard onboarding material.

## Motivating Evidence

Not authoritative evidence-window data. The two trials below were originally cited as the
same root cause; reconciliation against the actual resolution code and the repository's
own tracked configuration found that only one of them supports that reading.

- **Day-1 Trial 001** (`daily-use-evidence-window-2026-08-01.md`): ran before CR-DD-014
  added the `[capability]` declarations to `triagecore.toml`, so no declaration and no
  probe existed. Capability genuinely resolved to `Unknown`, both routes genuinely
  unavailable, and the block (`recommended_route: human_handoff`,
  `reason_code: ambiguous_or_remote_route`) is a real instance of the no-declaration/
  no-probe fail-closed path this CR still documents.
- **A trial run during this CR's own investigation** (`task_id`
  `12fe348e-94fd-43da-8bb8-2aa61a3eb949`, isolated ledger
  `.triagecore/daily-use-window/2026-08-08/ledger.jsonl`): ran after CR-DD-014, with
  both `local_fast` and `local_heavy` declared and bound. `runner_selected` recorded
  `capability_state: "configured"` with resolved model bindings for both routes — under
  `resolve_capability`, that is `local_fast_available=True`, `local_heavy_available=True`,
  `lm_studio_ok=True`. Capability was not the limiting factor. The block traces to the
  separate, later `local_only` guard in `client.py` firing because `choose_resilience_route`
  itself selected a non-local route, which, given fully-available capability, is only
  reachable through the sensitivity gate (task classified `security_review` or
  `blocked_or_high_risk`), not through capability resolution. **This trial is withdrawn as
  evidence for a probe-absence-causes-blocking claim.** It remains true that no probe was
  configured at the time; it is not true that the absence of a probe caused this block.

The two trials are not the same root cause. Trial 001 demonstrates the genuine
no-declaration/no-probe fail-closed case. The Aug-8 trial demonstrates something else
entirely and should not have been cited alongside it.

## Determination

**Operator-workflow gap, but the gap is a misunderstanding of what probing does, not an
undiscoverable prerequisite for local execution.** Not an architectural gap: CR-DD-013
argued the fail-closed design explicitly and tested against the specific failure of
promoting `Configured` to healthy, and that design is intact. Not merely "missing
documentation" in a narrow sense either: an operator reading only `triagecore.toml` could
reasonably believe a declaration alone is a health check, because nothing in the standard
onboarding material explains that it is an unverified assertion, or what a probe adds when
one is run. That gap — the assurance role of probing being undocumented, not the ability to
run local work at all — is what makes discoverability and usability part of the control
surface here.

## Objective

Make the existing, intended workflow discoverable and usable as documented, without
changing what the workflow does, what it defaults to, or what it enforces.

## Invariants Preserved

This CR MUST NOT weaken, and its acceptance criteria must not be satisfiable in a way that
weakens, any of the following:

1. `Configured` MUST NOT imply `ObservedAvailable`.
2. `tc run` MUST NOT silently probe.
3. Stale or absent observations MUST remain non-authoritative.
4. `local_only` MUST fail closed when resolution and policy yield no eligible local route.
   An absent or stale observation alone MUST NOT erase a valid explicit declaration and
   model binding; a fresh observed-unavailable result MUST continue to suppress dependent
   declared routes.
5. Probe evidence MUST remain explicit, inspectable, and time-bounded.

## In Scope

1. **Documentation.** Add the missing operator explanation to
   `docs/daily_driver_quickstart.md` (or a dedicated linked operations doc), covering what
   probing actually changes, not only how to run it:
   - A `[capability]` declaration with a resolved model binding authorizes route
     consideration by itself; no probe is required for `local_only` work to proceed.
   - Running `tc probe --source-type <type> --base-url <url> --output <path>`, then setting
     `[capability].local_probe_record_path = "<path>"` in `triagecore.toml`, upgrades that
     unverified declaration to a checked observation: a fresh negative result conclusively
     suppresses the declared route even though the declaration alone would have permitted
     it, and a fresh positive result with model names can catch a declared model that isn't
     actually loaded.
   - With neither a usable declaration nor a usable observation, local capability is
     `Unknown` and `local_only` work fails closed.
   - State plainly that probing is a manual, repeatable step, and document the 300-second
     default freshness window and its consequence: a probe older than 300 seconds is
     treated identically to no probe at all.
2. **CLI discoverability.** Update `tc probe --help` text so it explicitly states that a
   persisted `--output` file has no effect on `tc run` until its path is also set as
   `[capability].local_probe_record_path` in `triagecore.toml`. Text only; no new flags, no
   new behavior.

## Authorized Implementation Allowlist

The bounded implementation, separately approved, touches exactly these four paths —
nothing else:

```text
docs/daily_driver_quickstart.md
triage_core/tc_cli.py
tests/test_tc_cli.py
docs/change/requests/CR-DD-016-capability-probe-operator-workflow-discoverability.md
```

Within `triage_core/tc_cli.py`, the change is limited to `argparse` help/description
text for `tc probe`; no command dispatch, function body, flag shape, default value,
probe behavior, routing behavior, capability-resolution behavior, or execution path
changed. The CR file itself received only implementation/status/evidence updates.

Named exclusions — files a future implementer might be tempted to touch, and which were
not touched, because this CR changes only how the existing workflow explains itself, not
how the workflow operates:

```text
triage_core/local_backend_probe.py
triage_core/capability_evidence.py
triage_core/config.py
triage_core/client.py
triage_core/routing/resilience_router.py
```

Implementation authority for this allowlist has been exercised strictly within these
four paths. Merge of the implementation PR is the final human gate; once merged, that
bounded authority is spent. No further file on this list — or any other file — may be
touched under this authorization, before or after merge, without a separate, explicit
approval.

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

- [x] `docs/daily_driver_quickstart.md` (or a linked operations document) documents the
      full `tc probe` → `[capability].local_probe_record_path` procedure and the
      three-case contract above (declaration-only permits route consideration; a fresh
      probe upgrades or conclusively overrides it; neither usable fails `local_only`
      closed), including the 300-second freshness consequence, in language an operator
      could act on without reading source code.
- [x] `tc probe --help` text references `[capability].local_probe_record_path` by name as
      the required follow-up step for persisted output to take effect.
- [x] `triage_core/tc_cli.py` is the only permitted file under `triage_core/`,
      and changes to it are limited to `argparse` help/description text for
      `tc probe`; no command dispatch, function body, flag shape, default value,
      probe behavior, routing behavior, capability-resolution behavior, or
      execution path changes.
- [x] No schema, CLI command or flag shape, default value, command dispatch,
      probe execution, capability resolution, routing decision, persistence
      behavior, or runtime semantics change.
- [x] A focused CLI regression test proves that `tc probe --help` names
      `[capability].local_probe_record_path` and explains that persisted
      `--output` does not affect `tc run` until that configuration path is set.
      (`tests/test_tc_cli.py::test_tc_probe_help_names_capability_probe_record_path`,
      whitespace-normalized to be independent of ambient terminal width.)
- [x] All five invariants listed above remain true and unmodified by this slice.
- [x] The two adjacent findings (classifier fallback, `privacy_level` normalization) are
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
