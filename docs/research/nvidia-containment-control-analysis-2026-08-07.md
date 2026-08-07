# NVIDIA Containment-Control Analysis — TriageCore @ `0dc5019`

## What this document is, and is not

**This is external architecture analysis. It is not governed-run evidence, not approved
architecture, and not an implementation authorization.**

It was produced by a model operating outside TriageCore's governed execution path. No
TriageCore route, capability, privacy, ledger, or authority surface participated in
producing it. It is offered as architecture-decision input whose every row is intended to be
verified against the repository independently.

Specifically, this document:

- is **not** evidence from the daily-use evidence window, and is not a trial or a day;
- is **not** the output of a `tc run` invocation. A governed `local_heavy` invocation
  attempting this analysis on 2026-08-07 did not complete within its read timeout; that
  session is recorded separately in
  [`local-heavy-diagnostic-2026-08-07.md`](../operations/local-heavy-diagnostic-2026-08-07.md);
- grants no implementation, execution-expansion, configuration, or merge authority;
- makes no claim that TriageCore is secure, contained, sandboxed, or production-ready, and
  no claim that adopting any item here would make it so.

Repository facts below were verified by direct source inspection at commit `0dc5019`.
Line references were accurate at that commit and should be re-verified before reuse.

## Source provenance

This analysis synthesizes **two related but distinct NVIDIA publications**, and the
distinction is preserved deliberately rather than attributing everything to one source:

- **Controls 1–9** map to NVIDIA AI Red Team guidance on sandboxing agentic workflows and
  managing execution risk, which treats network egress restriction, blocking writes outside
  the workspace, and blocking configuration-file writes as mandatory, and additionally
  recommends read confinement, sandboxing spawned functionality, VM/microVM isolation,
  per-instance approval for isolation-breaking actions, protected credential injection, and
  sandbox lifecycle management.
- **Control 10** derives primarily from NVIDIA's later Secure Agent Workspace architecture,
  which calls for centralized logging of workspace lifecycle, broker sessions, policy
  releases, network allow/deny activity, and runtime and tool events.

NVIDIA's separate guidance on agentic autonomy levels holds that control intensity should
scale with autonomy and tool exposure. That materially affects how controls 5, 6, 8, and 9
should be read here — see *Autonomy calibration* below.

## Autonomy calibration — read this before the matrix

At `0dc5019`, `tc run` is a **governed inference path**. The engine assembles messages, calls
the configured backend, optionally post-processes or validates returned text, and returns it.
No evidence was found of model-output execution or model-selected tool dispatch on that path:
a keyword sweep of `triage_core/*.py` for subprocess and process-isolation primitives returned
nothing on the worker path, and `extract_first_code_block` (`routers.py:99`) extracts text
rather than executing it.

Consequently, controls 5, 6, 8, and 9 describe a threat surface TriageCore **does not
currently expose**. Their classification below should not be read as "an autonomous
unsandboxed agent is running." It should be read as: the boundary does not yet exist, and it
is cheapest to install before the first agent-controlled effect rather than after.

## Two-axis control matrix

A single label per control obscures the most interesting fact about this codebase, so two
axes are used:

- **Mechanism maturity** — what exists in the repository:
  `enforced-component` (a mechanism that structurally denies the action within its own
  domain) · `partial-component` · `specification-only` · `none`
- **Live-path enforcement** — whether that mechanism constrains a `tc run` invocation today.

| # | Control | Mechanism maturity | Live-path enforcement | Repository evidence |
| --- | --- | --- | --- | --- |
| 1 | Network egress restriction | `none` | no | `routers.py:6,44` — `is_internet_available()` opens `8.8.8.8:53` as the first statement of `SpecialistRouter.route_task`, reached on every governed run via `tc_cli.py:1229` → `client.py:117-118`. `client.py:488` — `internet_ok` is `get_qwen_enabled()`, a configuration value, not observed network state. `tc_cli.py:1092-94` gates `--allow-cloud` against `local_only`, which is route-selection policy |
| 2 | Write confinement to workspace | **`enforced-component`** | **no** | `mediated_executor.py` — frozen workspace anchor captured at construction (`:252,260`, via `win32.final_path`), resolution exclusively by `target_file_id` with **no path-based lookup** (`:264`), path-like IDs rejected (`:353`), duplicate-ID registry rejection (`:411-415`), platform gate and fail-closed containment outcomes. Not imported by `tc_cli.py`, `client.py`, `engine.py`, or `backends.py` |
| 3 | Protected configuration | `none` | no | `config.py:51-57` — `get_global()` reads a plain dict parsed from `triagecore.toml`, with an environment-variable override consulted first. No integrity check, content addressing, or permission enforcement found in the configuration layer |
| 4 | Read confinement | `none` | no | `tc_cli.py:1071-85` — for each `--files` argument: `os.path.exists()` then `open()`. No normalization, allowlist, or boundary admission precedes the open |
| 5 | Sandbox coverage of spawned functions | `none` | no (no spawned functionality exists today) | Keyword sweep for `chroot`/`namespace`/`cgroup`/`seccomp`/`appcontainer`/`jail`/`confine` across `triage_core/*.py` matches only inside `mediated_executor.py`. Worker executes inline in the CLI process |
| 6 | Kernel/VM isolation | `none` | no | Docker microVM execution-venue item is a research-only backlog candidate (`ff21b91`). No `Dockerfile` or Compose file is tracked |
| 7 | Fresh approval for boundary-crossing actions | **`enforced-component`** | **no** | `capability_claims.py` — SQLite structural enforcement in its own domain: state-enum and table-level `CHECK` constraints (`:130,136,142`), `UNIQUE INDEX` on execution attempt (`:171`), and five `RAISE(ABORT)` triggers covering binding immutability, legal state transitions, claim-ownership immutability, terminal-metadata immutability, and undeletable claimed rows (`:176-235`). `mediated_effect.py` and `request_reservation.py` add merged, tested contract surfaces. None of the three is imported by `tc_cli.py`, `client.py`, or `engine.py` |
| 8 | Scoped provisioning of protected runtime values | `none` | not applicable | `privacy_scanner.py` detects credential-shaped material in *submitted* content — inbound detection, a different control. No scoped, time-limited, or capability-bound issuance mechanism found |
| 9 | Sandbox lifecycle | `none` | no (vacuous) | No sandbox construct exists on the execution path per control 5, so there is no lifecycle to manage, reset, or verify |
| 10 | Centralized boundary-event evidence | `partial-component` | **yes**, with two qualifications | Five-event sequence `task_created` → `runner_selected` → `route_audit` → `route_decision` → `worker_result`, schema `0.2.0`; `privacy_invariants.py:76` `find_forbidden_persistent_fields()`. Qualification one: every event is written by the same process performing the action, and no independent out-of-process telemetry was found. Qualification two: fidelity is lossy — a 120-second read timeout and a fast HTTP 400 (Day-1 Trial 007) produce `worker_result` payloads identical in every recorded field, including `elapsed_seconds: 0.0`. Runtime evidence for the timeout case is recorded in [`local-heavy-diagnostic-2026-08-07.md`](../operations/local-heavy-diagnostic-2026-08-07.md) |

### Reframed tally

- **2 controls** (2, 7) have genuinely enforced components that the live path does not compose.
- **1 control** (10) has a partial component that *is* on the live path, but is self-attested
  and lossy — and it is an evidence control, not a containment control.
- **7 controls** (1, 3, 4, 5, 6, 8, 9) have no mechanism, four of which (5, 6, 8, 9) address a
  threat surface not currently exposed.
- **0 containment controls** are structurally enforced on the live `tc run` path.

## The structural finding

> TriageCore has built pieces of an enforcement plane; NVIDIA provides a reference
> architecture for composing them beneath any future agent/tool-execution layer rather than
> relying on model behavior to respect those boundaries.

Stated against the current codebase: TriageCore already possesses several unusually strong
enforcement components, but its governed inference path does not yet compose them into an
execution containment boundary.

The project's most rigorous engineering — the constrained replacement executor, atomic
capability claiming, request reservation, mediated effects, hardware authorization receipts —
produced mechanisms that structurally deny actions within their own domains. `mediated_executor`
refuses path-based target resolution outright. `capability_claims` enforces lifecycle legality
in the database rather than in Python. These are not paper contracts.

They are also not reachable from `tc run`. Each closeout records that its implementation
authority was deliberately spent within a narrow allowlist, which is why the modules exist as
unconsumed library surfaces. The gap is therefore **consumption at an effect boundary**, not
implementation quality.

That reframing matters for sequencing: the next architectural step is not primarily to build
new enforcement, but to create the seam at which existing enforcement can be composed
underneath the agent rather than trusted to be respected by it.

### One control with active counter-evidence

Control 1 is the only row where the system takes an affirmative outbound action rather than
merely failing to prevent one: `is_internet_available()` opens a socket on every governed run,
including runs declared `--privacy local_only`.

**This is not a violation of TriageCore's existing contract.** `privacy_metadata_for_run`
(`run_plan.py:31-33`) defines `local_only` as `PrivacyMetadata(external_model_allowed=False)` —
an external-*model* prohibition, not a no-sockets guarantee. The probe is correctly described
as **ambient external network activity inconsistent with the NVIDIA default-deny target
architecture**, not as a broken promise.

It remains the sharpest gap in the matrix, and the one most likely to be raised first by an
external reviewer.

## Nominated next slice — exactly one

**Context-Source Venue Admission.**

Every `tc run --files` source must be proven to resolve inside an explicitly declared
workspace boundary **before that source is opened or read**. If containment cannot be
established, execution fails closed before file I/O, before ledger creation, and before
backend invocation.

**Mechanically verifiable invariant:**

> For every path supplied via `--files`, containment within the declared workspace boundary is
> established before the path is opened. Where containment cannot be established, no file is
> opened, no ledger is created, and no backend request is issued.

**Acceptance must prove three distinct negatives** for an outside-workspace source:

1. the source file is never opened;
2. no ledger is created;
3. the backend is never invoked.

The three are separable and must be asserted separately. Ordering at `0dc5019` makes this
concrete: `--files` is opened at `tc_cli.py:1076`, the ledger is constructed at
`tc_cli.py:1184`, and the backend is invoked at `tc_cli.py:1229`. An admission check placed
before the backend request — or even before ledger creation — would leave the read already
performed and would not constitute read confinement.

**Explicit exclusions.** No new mutation authority of any kind. No change to routing,
classification, privacy scanning, capability semantics, model selection, or executor behavior.
Does not address writes, egress, configuration protection, or credential provisioning. Does
not wire `mediated_executor`, `mediated_effect`, `request_reservation`, or `capability_claims`
into the execution path. Does not build a sandbox and must not be described as one.

**Honest limits of this nomination.** `--files` sources are operator-supplied, not
agent-selected, so this slice does not by itself contain an agent; at current autonomy there is
no agent-controlled read to contain. Its value is that it creates the **first live
venue-bound structural seam** on the governed path, at the only point where external content
currently enters, and establishes the declared-boundary-plus-fail-closed-admission pattern
that controls 2, 5, and 9 would later reuse.

**Alternative considered and not nominated.** Wiring `mediated_executor` behind a venue check
would convert control 2 from component-enforced to live-path enforced, which is higher value.
It requires an execution-venue abstraction and is materially larger than a smallest next
slice. It is recorded here as the natural successor, not as this nomination.

## Relationship to existing backlog

This analysis is distinct from, and does not supersede, the Docker microVM execution-venue
research candidate, which evaluates containment topology and host exposure. The venue seam
described above would be the natural anchor that later venue work — including microVM
evaluation — attaches to. Neither item substitutes for the other, and neither is authorized by
this document.

## Verification status and limits

Every repository claim above was verified by direct source inspection at `0dc5019`. The
following were **not** established and are explicitly open:

- No network capture was taken; the unconditional reachability probe is **source-confirmed on
  the live path, not runtime-observed**. That distinction should not be collapsed downstream.
- No claim is made about the completeness of the keyword sweeps used for controls 5 and 8. A
  negative grep is weak evidence of absence.
- NVIDIA's published guidance is summarized from the cited articles as understood at the time
  of writing; it is not quoted, and the mapping from that guidance to these ten rows is an
  interpretation, not a vendor-endorsed conformance profile.
- No claim is made that this ten-control set is complete, that the classifications would
  survive an adversarial review, or that any classification implies a security property.
