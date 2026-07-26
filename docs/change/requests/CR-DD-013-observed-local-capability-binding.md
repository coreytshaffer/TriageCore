# CR-DD-013: Observed Local Capability Binding for Governed Routing

## Status

Proposed. Documentation only. No implementation authority is granted by this
document.

This CR is scoped against `main` at `ac851d5`. It is the first slice of M1 in
`docs/architecture/daily_driver_orchestrator_spec.md` and addresses gap G4.

CR-DD-013 is **not** part of the CR-DD-012 shared-decision lane. CR-DD-012B
remains reserved for shared preview/execution consumption and retains its
existing CR-YK-002 atomic-claiming gate. CR-DD-013 has no CR-YK dependency, no
CR-DD-012A dependency, and does not consume `GovernedDecision` or
`GovernedRunInputSnapshot`. The two lanes may proceed independently.

## Problem

Governed route selection currently treats local capability as available
without ever observing it.

`TriageClient._build_resilience_route_input` supplies:

- `lm_studio_ok=True`, `local_heavy_available=True`, `local_fast_available=True`
  as literals;
- no `memory_headroom_mb`, so the `ResilienceRouteInput` default of `4096`
  applies;
- no `recent_cloud_failures`, `recent_local_heavy_failures`, or
  `recent_local_fast_failures`, so each defaults to `0`;
- cloud flags derived from static configuration (`default_config.get_qwen_enabled()`),
  which is a configured intent, not an observation.

The router then evaluates `_local_heavy_ok` and `_local_fast_ok` against those
literals and returns a route that has never been checked against reality.

Four distinct states are currently collapsed into one:

- **configured** — an operator declared a backend in configuration;
- **observed available** — a metadata probe answered;
- **observed unavailable** — a probe ran and the endpoint did not answer;
- **unknown** — no probe ran, the probe was disabled, its record failed
  validation, or the observation is too old to rely on.

Today all four present to the router as `True`. The consequences are concrete:

- a selected `local_heavy` / `local_fast` route may be unable to execute,
  surfacing as a worker-stage failure rather than a routing decision;
- fallback depth and reason codes describe a route chosen on unverified
  assumptions, so route evidence overstates what was known at decision time;
- the posture is optimistic rather than fail-closed, which is inconsistent with
  the invariants the rest of the governed loop preserves.

The missing capability is **not** a probe. `triage_core/local_backend_probe.py`
(CR-114, hardened by CR-118 and gated by CR-119) already produces a validated,
metadata-only, privacy-safe observation and is surfaced read-only as
`tc probe`. Its module contract and
`docs/operations/local-backend-telemetry.md` both state that routing wiring and
route-input population remain future work. This CR is that future work.

Note on identifiers: "CR-114" is the internal telemetry change request for the
probe. It is unrelated to GitHub PR #114, which was a `tc run` evidence
correlation test.

## Objective

Consume an existing local capability observation before governed route
selection, map it into the existing `ResilienceRouteInput`, and record enough
provenance to explain the routing input.

Explicitly **not** in the objective: a second probe system, a second router, an
orchestration layer, new routing heuristics, or any change to
`choose_resilience_route`'s decision logic.

## Observation Source

CR-DD-013 consumes the existing `LocalBackendProbeRecord`
(`local_backend_probe_record.v1`) without modifying it. The record already
carries every field this CR needs:

| Record field | Use in CR-DD-013 |
|---|---|
| `reachable` | primary availability signal |
| `error_category` | distinguishes observed-unavailable from unknown |
| `evidence_tier` | provenance: `local_metadata_probe`, `operator_recorded`, or `synthetic_fixture` |
| `observed_at` | freshness evaluation |
| `source_type` | which local runtime was observed |
| `base_url` | already redacted to `scheme://host[:port]` |
| `model_count` / `observed_models` | model presence; never converted to a capability claim on its own |

No new probe, endpoint, schema version, or record field is proposed.

## Required Semantics

### Observation mapping

The binding must derive exactly one state per local route class. A class whose
evidence does not support a conclusion is `unknown`, never a default:

```text
observed_available    reachable = true from a validated record within the freshness
                      bound, for a route class the record actually supports
observed_unavailable  reachable = false with error_category in
                      {endpoint_unreachable, timeout, malformed_response,
                       permission_or_policy_blocked}
configured            no usable observation, but an explicit operator configuration
                      declares the relevant route class available for consideration;
                      recorded as configured capability, never as observed health.
                      Ordinary backend configuration does not qualify
unknown               no record; error_category = probe_disabled; record failed
                      CR-119 validation; observed_at absent; observed_at older than
                      the explicit freshness bound; or a reachable record that
                      carries no evidence for this particular route class
```

`probe_disabled` is **unknown, not unavailable**. A disabled probe is an absence
of evidence about the backend, not evidence about the backend.

### Unknown is never promoted to availability

Missing, disabled, stale, or otherwise unknown probe evidence must not be
represented as observed availability. Specifically, the `tc run` route-input
construction path **must not synthesize `True` from unknown evidence**. The
current literals `lm_studio_ok=True`, `local_heavy_available=True`, and
`local_fast_available=True` are exactly that synthesis and are what this CR
removes.

Without either a usable observation or an explicit configured declaration,
local availability remains **unknown and must not be treated as healthy**.

### What qualifies as an explicit configured declaration

Generic backend configuration does not prove capability. An endpoint, a model
name, or an enabled backend entry means "this route may be configured," not
"this route is currently executable." Treating `default_config.get_backend_type()`
or a populated base URL as a capability declaration would reintroduce the
optimistic assumption this CR exists to remove, merely relabelled.

A configuration qualifies as a capability declaration **only when its semantics
explicitly declare the relevant route class available for consideration.**

CR-DD-013 does not invent that configuration surface. Defining it is separate
work. But this CR must not treat ordinary backend configuration as equivalent
to it: until such a surface exists, an operator with only ordinary backend
configuration and no observation resolves to `Unknown`, not `Configured`.

### Operator behavior when capability is unknown

Unknown is policy-sensitive rather than uniformly fatal:

- **Local-only task with unknown local capability** — fail closed with a clear
  governed-denial reason. There is no permitted route, and no worker executes.
- **Cloud-permitted task with unknown local capability** — routing may consider
  an explicitly configured and policy-permitted remote route. Both the route
  evidence and the operator-facing output must state that local capability was
  unknown, so an escalation is never silently attributed to a local failure
  that was never observed.
- **No acknowledgement prompt or interactive confirmation** is introduced by
  CR-DD-013.

This preserves the existing local-only invariant exactly: unknown local
capability never becomes a justification for external egress on a local-only
packet.

`error_category="probe_disabled"` remains unknown, not unavailable. A disabled
probe is an absence of evidence about the backend, not evidence about the
backend.

Configured capability must never be relabeled as observed. Evidence that says
"the operator declared this backend" and evidence that says "a metadata
endpoint answered" are different claims, and route evidence must keep them
distinguishable.

### Compatibility boundary for direct callers

This rule governs the `tc run` route-input construction path. Existing direct
callers that explicitly supply `ResilienceRouteInput` booleans retain current
behavior unchanged: an explicitly supplied `True` remains `True`, and no
observation is inferred on their behalf. `choose_resilience_route` itself is
not modified.

This is a deliberate behavioral change for `tc run` when no observation and no
explicit configured declaration exist. It is not backward compatible in that
narrow case, and the implementation CR must state so plainly rather than
describe the change as inert.

### Asymmetric observation semantics

Positive and negative observations do not carry equal weight, and the CR must
not treat them symmetrically.

- **An observed failure or unavailable result is conclusive for dependent
  routes.** If a runtime is observed unavailable, every route class that
  depends on that runtime may be ruled out. Nothing can execute on a runtime
  that is not answering.
- **An observed reachable runtime is not conclusive.** Reachability proves the
  metadata endpoint answered. It does not prove that both `local_fast` and
  `local_heavy` are executable, because those classes imply different model,
  memory, and context requirements that a metadata probe does not measure.

Therefore CR-DD-013 **must not set both route classes to available from a
single reachability observation** unless the probe record actually contains
model-specific evidence supporting both. Where the record does not, the
supported classes remain unknown rather than available.

`model_count` and `observed_models` are the only model-adjacent fields the
record carries, and neither establishes that a given model fits a route class's
memory or context envelope. Absent such evidence, a reachable runtime yields
reachability only.

Separating route-to-backend and route-to-model bindings where current evidence
is insufficient remains **G3's responsibility**, not this CR's. CR-DD-013 must
not invent a model-class inference to fill the gap.

### Absent evidence is not zero

Absent memory, model-count, latency, or failure-count evidence must remain
unknown. In particular the binding must **not** write `memory_headroom_mb=0`,
`model_count=0`, or `recent_*_failures` derived from absent data. Zero is an
observation; absence is not.

For these non-availability numeric inputs, where no evidence exists the
existing `ResilienceRouteInput` default is retained and the capability
observation marks the field unknown. This is narrower than the availability
rule above and must not be read as licence to synthesize availability: a
retained numeric default is an acknowledged placeholder recorded as unknown,
whereas a synthesized `True` would be an unearned health claim. The
implementation CR should state which numeric defaults were retained and why.

Recent-failure counters remain out of scope entirely. They describe execution
history, not current capability, and belong to circuit-breaker work (G6).

### Local-only constraint is preserved, not rebuilt

A local-only task whose local routes are observed unavailable must fail closed
without remote execution. The existing mechanism already provides this:
`choose_resilience_route` will not offer cloud for `privacy_level="local_only"`,
and `TriageClient.run_task` raises `LocalRouteUnavailableError` when the
selected route is not in `{local_heavy, local_fast, deterministic}`.

CR-DD-013 must **prove this still holds** when observation marks local
capability unavailable. It must not add a second enforcement path.

### Probing must not execute a model task

The binding may only consume metadata-only observations. It must never trigger
a completion, chat, or embedding call, and must not turn route selection into a
network-dependent operation on a path that previously made no calls. Whether
the binding may probe on demand, or may only read an already-recorded
observation, is an open question below.

### Deterministic test injection

Tests must be able to inject a capability snapshot without contacting a real
runtime, opening a socket, or spawning a subprocess. The existing
`evidence_tier="synthetic_fixture"` value already exists for exactly this, so
no new test harness or fake-probe abstraction is required.

## Proposed Field Shape

Provisional. This shape is proposed, not authorized.

`ResilienceRouteInput` cannot currently express unknown. `lm_studio_ok`,
`local_heavy_available`, and `local_fast_available` are `bool`;
`memory_headroom_mb` is `int`. There is no third state, and no value of `bool`
or `int` can carry "not observed" without conflating it with `False` or `0` —
which the semantics above forbid.

The proposal is **exactly one** additive optional field on
`ResilienceRouteInput`: a capability-evidence value, defaulting to absent.
There is no second field and no parallel set of loose scalars.

Being a single field is not by itself sufficient. An ordinary object with
nullable members could still claim `configured` while carrying a probe
timestamp and an observed evidence tier — a combination that is semantically
impossible but structurally representable. Inconsistency is only excluded when
the value is **validated as a discriminated union** whose variants are mutually
exclusive and whose per-variant fields are separately required and forbidden.

The field is therefore specified as one validated capability-evidence object
with exactly four mutually exclusive variants:

```text
ObservedAvailable
ObservedUnavailable
Configured
Unknown
```

### Variant contracts

**ObservedAvailable** — required:

- probe source (`source_type`)
- evidence tier
- observation time (`observed_at`)
- freshness bound applied
- the route classes actually supported by the record

Forbidden: any route class the record does not support, and any configured-
capability marker.

**ObservedUnavailable** — required:

- probe source (`source_type`)
- evidence tier
- observation time (`observed_at`)
- freshness bound applied
- error category
- affected runtime and the route classes ruled out by it

Forbidden: any positive availability claim, and any configured-capability
marker.

**Configured** — required:

```text
source_type:      operator_config
config_reference: <profile or key path>
config_digest:    <optional redacted / non-secret digest>
```

plus the explicitly declared route classes.

Forbidden: any claim of observed health, any probe evidence tier, and any
`observed_at`. A configured variant must never fabricate probe provenance or an
observation timestamp it does not have.

**Unknown** — required:

- a reason code from a closed set: `missing`, `probe_disabled`, `stale`,
  `invalid_record`, `insufficient_model_evidence`

Forbidden: any positive availability claim.

### Projection, not embedding

A **validated projection** of `LocalBackendProbeRecord` is preferred over
embedding the complete probe record in routing input. Routing needs the state,
its provenance, and its age — not `observed_models`, response latency, or the
full record surface. A projection keeps the routing input narrow, prevents
unrelated probe fields from becoming de facto routing inputs, and lets the
projection step be the place where validation and freshness evaluation happen
once.

The projection is constructed and validated at the boundary; an invalid or
internally inconsistent projection fails to a `Unknown` variant with
`invalid_record`, never to an availability claim.

When the field is absent, direct callers behave exactly as today. The router
itself is not modified — `choose_resilience_route` continues to read the
existing booleans, and only the `tc run` construction path and the evidence
layer see the richer value.

### Evidence

This proposal requires **no new ledger schema and no schema-version bump**.

An existing extension point is available and must be used:
`build_route_decision_payload` produces an open dictionary written through
`TaskLedger.append_event`, which enforces the persistent privacy invariant but
does not restrict the field set. Observation state, evidence tier, source type,
observation time, and the applied freshness bound can be carried there
additively.

The closed `route_worker_ledger.py` contract (`route-worker-ledger.v1`), which
rejects unknown keys, is **not** modified and **not** used by this path.

If implementation review determines that this extension point is unsuitable,
the provenance requirement must be recorded as a narrowly scoped additive
evidence change requiring later approval. It must not be silently dropped:
omitting provenance while still binding capability would produce routing
decisions whose basis cannot be reconstructed.

## Plan / Execution Boundary

An observation describes the moment it was taken. Capability can change between
observation and worker execution: a runtime can be stopped, a model unloaded,
memory exhausted, or a port reclaimed.

CR-DD-013 therefore claims exactly this and no more:

- **In scope:** the route was selected using capability evidence that was valid
  and fresh at decision time, and the evidence is reconstructable afterward.
- **Not claimed:** that the selected route will still be executable when the
  worker runs.

A pre-route probe narrows the window between assumption and execution. It does
not eliminate runtime disappearance, and this CR must not be described as
preventing it.

Explicitly deferred to later, separately approved work:

- **stale-state handling** beyond rejecting an observation older than the
  freshness bound;
- **retry, re-probe, or re-route** after a worker-stage capability failure;
- **circuit breakers and degraded modes** (G6), including any use of
  `recent_*_failures`;
- **real per-route backend bindings** (G3), which remain collapsed onto one
  local backend and Qwen;
- **execution-time capability verification** immediately before the worker call.

## Recommended Design

These are recorded as the recommended design. They remain subject to the
supervisor approval gates repository convention requires; recording a
recommendation grants no implementation authority.

1. **Consume an already-recorded or injected capability snapshot.** Route
   selection reads an observation that already exists; it does not create one.
2. **No automatic network probe inside route selection.** Route selection must
   not acquire a network dependency or latency coupling it does not have today.
3. **Stale observations degrade to unknown, never silently to available.**
4. **The freshness threshold is explicit and configurable**, never an implicit
   constant, and the applied value is carried in evidence or configuration
   provenance so a reviewer can tell which threshold produced a given state.
   The numeric value is deliberately left unresolved here; the implementation
   CR must choose an explicit configurable threshold, test the fresh/stale
   boundary, record the threshold actually used, never silently apply an
   undocumented default, and degrade stale evidence to `Unknown`.
5. **Observed-unavailable may suppress every route dependent on that runtime.**
   A negative observation is conclusive for dependent routes.
6. **Observed-available confirms runtime reachability only.** It may not assert
   model-class availability the record does not support; unsupported classes
   remain unknown.

## Acceptance Criteria

1. `tc run` no longer hardcodes local availability as observed healthy. With no
   observation and no explicit configured declaration, the route-input
   construction path synthesizes no `True` for `lm_studio_ok`,
   `local_heavy_available`, or `local_fast_available`.
2. An observed-unavailable runtime cannot be routed: every route class
   depending on it is suppressed, and the router's existing fallback ordering
   applies unchanged.
3. Unknown and stale observations are not labeled healthy. `probe_disabled`,
   missing records, failed CR-119 validation, absent `observed_at`, and
   observations older than the applied freshness bound all resolve to unknown —
   never to available, and never to unavailable.
4. Explicit caller-supplied route inputs remain behaviorally compatible: a
   caller that constructs `ResilienceRouteInput` directly and supplies booleans
   sees identical routing, ordering, reason codes, and fallback depth to
   current `main`.
5. An explicit configured route declaration is distinguishable in evidence from
   an observed capability result. Configured capability is never labeled
   observed, carries no probe evidence tier and no `observed_at`, and a
   reviewer can tell which one supported a route. Ordinary backend
   configuration alone resolves to `Unknown`, not `Configured`.
6. Local-only work with unknown local capability fails closed with a clear
   governed-denial reason: no cloud route, no worker execution, through the
   existing `LocalRouteUnavailableError` path.
6a. A cloud-permitted task with unknown local capability may consider an
   explicitly configured and policy-permitted remote route, and both the route
   evidence and the operator-facing output state that local capability was
   unknown. No acknowledgement prompt or interactive confirmation is added.
6b. The capability-evidence value is validated as a discriminated union:
   semantically impossible combinations — a `Configured` variant carrying an
   `observed_at` or a probe evidence tier, an `Unknown` variant carrying a
   positive availability claim, an `ObservedAvailable` variant naming a route
   class the record does not support — are rejected at construction rather than
   merely unused. An invalid projection resolves to `Unknown` with
   `invalid_record`, never to an availability claim.
7. A single reachability observation does not set both `local_fast` and
   `local_heavy` available unless the record carries model-specific evidence
   supporting both; otherwise unsupported classes remain unknown.
8. An existing validated `LocalBackendProbeRecord` populates the route input
   without a new probe system, endpoint, or record schema version.
9. Route evidence identifies observation state, source/evidence tier,
   observation time, and the applied freshness bound through the existing open
   `route_decision` payload extension point, with no new ledger schema. If that
   extension point proves unsuitable, provenance is recorded as a narrowly
   scoped additive evidence change requiring later approval, and is not
   silently omitted.
10. Every focused test injects capability deterministically with no network,
    socket, subprocess, model call, or real runtime, using the existing
    `synthetic_fixture` evidence tier.
11. Absent memory, model, token, or health evidence remains unknown; no absent
    value is written as `0`, and no advisory or configured value is relabeled
    as an observation.
12. The binding performs no model execution, and no metadata-only guarantee of
    the existing probe contract is weakened.
13. No provider, authorization, reviewer-burden, session, GUI, or
    circuit-breaker implementation is included; no readiness percentage is
    recalculated.

## Required Focused Tests

**Mapping**

- table tests covering `reachable=true`; each `error_category` in the
  unavailable set; `probe_disabled`; absent record; absent `observed_at`;
  `observed_at` at, just inside, and just outside the freshness bound; and a
  record that fails CR-119 validation;
- proof that `probe_disabled` and validation failure map to unknown, not to
  unavailable;
- proof that unknown never serializes as observed-available.

**Direct-caller compatibility**

- a caller constructing `ResilienceRouteInput` directly and supplying booleans
  produces identical route, reason code, and fallback depth to current `main`
  across the existing route matrix;
- the additive field absent means no observation is inferred on that caller's
  behalf.

**No synthesized availability**

- with no observation and no configured declaration, the `tc run` construction
  path emits no `True` availability value, and the resulting state is unknown;
- a test asserts the specific literals removed from
  `_build_resilience_route_input` are not reintroduced.

**Variant validation**

- construction rejects a `Configured` variant carrying `observed_at` or a probe
  evidence tier;
- construction rejects an `Unknown` variant carrying any positive availability
  claim;
- construction rejects an `ObservedAvailable` variant naming a route class the
  record does not support;
- an invalid or internally inconsistent projection resolves to `Unknown` with
  `invalid_record`, never to an availability claim;
- each `Unknown` reason code (`missing`, `probe_disabled`, `stale`,
  `invalid_record`, `insufficient_model_evidence`) is produced by its
  corresponding input condition.

**Configured versus observed**

- an explicit configured declaration supports route consideration and is
  labeled configured in evidence, carrying `source_type=operator_config` and a
  `config_reference`;
- ordinary backend configuration alone yields `Unknown`, not `Configured`;
- configured capability never serializes as observed;
- a reviewer can determine from evidence alone which of the two supported a
  route.

**Unknown policy behavior**

- local-only plus unknown local capability fails closed with a governed-denial
  reason and no worker execution;
- cloud-permitted plus unknown local capability may consider a configured,
  policy-permitted remote route, and both evidence and operator output state
  that local capability was unknown;
- no test asserts an interactive prompt, because none is added.

**Asymmetry**

- an observed-unavailable runtime suppresses every dependent route class;
- a single reachability observation without model-specific evidence does not
  mark both `local_fast` and `local_heavy` available; unsupported classes
  remain unknown.

**Fail-closed**

- local-only with no usable local route from either observation or configured
  declaration raises `LocalRouteUnavailableError`, reaches no cloud route, and
  never invokes the backend;
- local-only plus observed-unavailable local routes does the same;
- the existing `tests/test_local_only_routing.py` expectations remain green
  unchanged.

**Isolation**

- traps proving the binding opens no socket, spawns no subprocess, and calls no
  generation endpoint;
- proof that absent evidence never materializes as `0`.

**Evidence**

- route-decision evidence carries posture, `evidence_tier`, `source_type`, and
  `observed_at`, and carries no raw base URL beyond the already-redacted form,
  no model output, and no secret;
- the closed `route-worker-ledger.v1` contract is unchanged.

## Risks And Mitigations

- **Unknown silently becomes available:** the state mapping is explicit,
  `probe_disabled` is pinned to unknown, the construction path is forbidden
  from synthesizing `True`, and tests assert the absence of promotion.
- **Absent evidence becomes zero:** absent non-availability numerics retain
  existing defaults and are marked unknown; a dedicated test asserts no `0` is
  written for absent memory or model evidence.
- **Routing changes for operators without a probe:** this is a real and
  intended consequence, not a risk to be argued away. Operators with no
  observation and no configured declaration will see local routes treated as
  unknown rather than healthy. The mitigation is the configured-capability path
  and explicit release notes, not a silent optimistic default. The
  implementation CR must state the change plainly.
- **Configured capability mistaken for observed health:** the two are separate
  variants of a validated discriminated union, `Configured` is forbidden from
  carrying probe provenance at construction, and evidence tests assert
  configured never serializes as observed.
- **Ordinary backend configuration relabelled as capability:** a configuration
  qualifies only when it explicitly declares the route class available for
  consideration; ordinary backend settings resolve to `Unknown`, which is
  tested directly.
- **Reachability overread as executability:** positive observations are
  explicitly non-conclusive for route classes, and a test pins that one
  reachability result does not mark both classes available.
- **Route selection acquires a network dependency:** the binding consumes
  observations only under the metadata-only contract; on-demand probing is an
  open question, not an assumption.
- **Pre-route probe oversold as a guarantee:** the plan/execution boundary
  states the claim precisely and disclaims runtime disappearance.
- **Scope creep into circuit breakers:** `recent_*_failures` are explicitly out
  of scope and remain at their defaults.
- **Tri-state leaks into the router:** the additive field is evidence-only;
  `choose_resilience_route` continues to read booleans and is not modified.

## Explicit Exclusions

- CR-YK changes of any kind; the Hardware-Bound Human Authorization lane remains
  complete and feature-frozen;
- any new probe implementation, endpoint, or record schema version;
- new routing heuristics or changes to `choose_resilience_route` logic;
- Claude, GPT, Gemini, or any other provider integration;
- token or context execution changes;
- circuit breakers, degraded modes, retry, or resume;
- interactive sessions;
- TriageDesk action support;
- reviewer-burden runtime fields, which remain planning-only and `null` when
  unmeasured;
- readiness-score recalculation;
- production-code edits under this proposal CR.

## Dependencies And Sequencing

- Depends on the merged local backend probe lane (CR-114, CR-118, CR-119) and
  its `local_backend_probe_record.v1` contract.
- Independent of CR-DD-012A, CR-DD-012B, CR-YK-001, and CR-YK-002. It neither
  consumes nor blocks the shared-decision lane.
- Precedes real per-route backend bindings (G3) and circuit breakers (G6)
  within M1.
- Supports, but does not satisfy, the spec's evidence requirement that
  local-first behavior be demonstrated over a real usage window.

## Provisional Implementation File Allowlist

Provisional. Not authorized by this proposal; a separate implementation
approval must confirm or replace it.

- `triage_core/client.py` — map an observation into `ResilienceRouteInput`
- `triage_core/routing/resilience_router.py` — additive optional field only; no
  decision-logic change
- `triage_core/routing/route_events.py` — additive route-evidence provenance
  fields
- `triage_core/local_backend_probe.py` — read-only accessor if one is needed to
  obtain a record without the CLI
- `tests/test_capability_binding.py` (new)
- `tests/test_local_only_routing.py` — extend for observed-unavailable
- `docs/change/requests/CR-DD-013-observed-local-capability-binding.md`
- `docs/current_backlog.md`
- `docs/architecture/daily_driver_orchestrator_spec.md`

`triage_core/route_worker_ledger.py`, `triage_core/tc_cli.py`, every CR-YK
module, and `docs/change/change_log.md` are deliberately excluded.

## Resolved Since First Draft

- **On-demand probing versus recorded observation** — resolved: consume an
  already-recorded or injected snapshot; no automatic network probe inside
  route selection.
- **Stale-observation handling** — resolved: degrade to unknown, never to
  available.
- **Additive field shape** — resolved: exactly one validated capability-evidence
  field, specified as a discriminated union of `ObservedAvailable`,
  `ObservedUnavailable`, `Configured`, and `Unknown`, each with its own
  required and forbidden fields, built as a validated projection of
  `LocalBackendProbeRecord` rather than an embedding of it.
- **What qualifies as a configured declaration** — resolved: ordinary backend
  configuration does not qualify; only a configuration whose semantics
  explicitly declare the route class available for consideration. CR-DD-013
  does not invent that surface.
- **Operator behavior under unknown** — resolved: local-only fails closed with
  a governed-denial reason; cloud-permitted may consider an explicitly
  configured and policy-permitted remote route while stating that local
  capability was unknown; no acknowledgement prompt.
- **Configured provenance** — resolved: `source_type=operator_config`, a
  `config_reference`, and an optional non-secret `config_digest`; never a probe
  evidence tier and never an `observed_at`.
- **Evidence mechanism** — resolved: use the existing open `route_decision`
  payload extension point; no new ledger schema in this CR.
- **Route-class inference from one reachability result** — resolved: not
  permitted without model-specific evidence; unsupported classes remain
  unknown, and G3 owns binding separation.

## Deferred To The Implementation CR

These are settled in principle and require a concrete choice at implementation
time, recorded and tested there rather than assumed:

1. **Freshness threshold value and location.** Choose an explicit, configurable
   threshold; test the fresh/stale boundary; record the threshold used; never
   silently apply an undocumented default; degrade stale evidence to `Unknown`.
2. **Where the capability-evidence projection is constructed** relative to
   `_build_resilience_route_input`, and how a validation failure there is
   surfaced without leaking probe internals into routing.
3. **Operator-output wording** for the cloud-permitted unknown case, which must
   state that local capability was unknown without implying an observed local
   failure.

## Open Questions

1. **Where an explicit capability declaration surface would live**, if one is
   later introduced. CR-DD-013 deliberately does not invent it and resolves
   ordinary backend configuration to `Unknown` in its absence. Until that
   surface exists, operators without a probe will see local capability treated
   as unknown — this is the CR's main adoption consequence and is stated
   plainly rather than mitigated by an optimistic default.
2. **Whether `local_fast` and `local_heavy` can ever be distinguished from
   probe evidence alone**, or whether route-class availability necessarily
   waits on G3's backend/model binding separation. This CR assumes the latter
   and resolves unsupported classes to `Unknown` with
   `insufficient_model_evidence`.
