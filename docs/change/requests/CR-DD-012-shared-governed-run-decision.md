# CR-DD-012: Shared Governed Run Decision

## Status

Architecture approved; monolithic implementation authority withheld.

This is a documentation-only architectural milestone. Implementation is
decomposed into CR-DD-012A and CR-DD-012B below. CR-DD-012A has received
separate bounded implementation approval and is complete and validated on its
branch as an internal, non-integrated foundation; merge is pending.
CR-DD-012B still requires its own explicit human implementation approval and
bounded file allowlist. Current CR-DD-009 through CR-DD-011 behavior remains
unchanged.

The CR-DD-012A foundation is specified in
`CR-DD-012A-governed-decision-foundation.md`. It resolves “exact bytes” as the
established normalized worker-facing execution representation, not raw
filesystem or backend transport bytes. CR-DD-012A implementation authority
is limited to its exact internal module, focused test, and documentation
allowlist. CR-DD-012B remains blocked until 012A lands and 012B receives its
own separate approval.

## Decision

Introduce one immutable `GovernedRunInputSnapshot` and one immutable
`GovernedDecision` contract. One shared deterministic path constructs the
snapshot and decision, and both are consumed by:

1. CR-DD-010 preview generation, including the CR-DD-011 plan-artifact
   renderer; and
2. ordinary `tc run` execution.

The snapshot contains the exact instruction, inline-input, ordered
context-source, and assembled execution bytes governed for the attempt.
Normalization, decision construction, preview, and execution consume that same
immutable snapshot. Execution never reopens a context file, reconstructs
assembled content, or silently substitutes different bytes.

For the same snapshot and identical decision-relevant policy facts, preview
and execution must receive the same canonical decision body and `decision_id`.
Neither path may independently classify, calculate privacy or context-budget
posture, choose a logical route, expand a fallback envelope, or derive
verification requirements after the shared decision is built.

Volatile backend health is not part of the governed policy decision. Runtime
availability and the physical backend selected within the decision's permitted
fallback envelope are represented initially by a validated internal
`RuntimeObservation` value. CR-DD-012B adds only bounded `decision_id` linkage
to existing route and worker evidence while preserving existing ledger event
shapes where possible. Durable `RuntimeObservation` and `ExecutionRecord`
contracts are deferred.

This CR deliberately does not make a CR-DD-011 plan artifact executable.

## Problem

CR-DD-010 and CR-DD-011 provide deterministic preview, artifact, and exact
review-confirmation foundations. Ordinary `tc run` still has decision seams
that can diverge from that preview:

- preview uses deterministic classification while execution may use the
  model-assisted classifier;
- specialist routing currently mixes policy-sensitive handling with a live
  socket-dependent branch;
- preview and execution can call policy components independently;
- preview and execution do not yet share one immutable byte snapshot, so a
  later file reopen or content reconstruction could create a TOCTOU gap; and
- volatile runtime health can affect a physical route without an explicit
  distinction between reviewed policy and observed availability.

Adding `--confirmed-plan` before these seams are removed would imply that
execution honors the reviewed decision when the system cannot yet prove that
claim.

## Scope

CR-DD-012 is an architectural milestone divided into two bounded,
separately-approved implementation slices.

### CR-DD-012A — Governed Decision Foundation

Under its separate bounded implementation approval, CR-DD-012A is limited to:

- an immutable `GovernedRunInputSnapshot` containing exact execution bytes,
  privacy-safe bindings, and normalized operator declarations;
- a closed, versioned, canonical `GovernedDecision` schema;
- a deterministic, content-addressed `decision_id`;
- one versioned deterministic snapshot/normalization path;
- one shared pure decision builder;
- shared privacy, egress, context-budget, classification, logical-route,
  fallback-envelope, escalation, human-review, and verification fields; and
- focused contract, canonicalization, privacy, mutation, and determinism tests.

CR-DD-012A changes no CLI behavior, ledger event, plan renderer or artifact
contract, route execution, runtime-observation persistence, or cloud authority.

### CR-DD-012B — Shared Preview/Execution Consumption

Only after CR-DD-012A lands and CR-DD-012B receives a separate human
implementation approval, CR-DD-012B is limited to:

- making `tc run --plan` consume the completed decision and immutable snapshot;
- making ordinary `tc run` consume that same completed decision and snapshot;
- preventing downstream reclassification, privacy recalculation, context
  replanning, specialist-policy selection, or logical rerouting;
- representing volatile execution facts as a validated internal
  `RuntimeObservation` value;
- enforcing actual runtime binding within the permitted fallback envelope;
- adding bounded `decision_id` linkage to existing route and worker evidence
  while preserving existing ledger event shapes where possible; and
- focused parity, fail-closed, privacy, and regression tests.

Both slices must preserve the existing public `tc run` and `tc run --plan`
command meanings. Neither slice adds a plan-artifact version, a durable runtime
observation/execution-record schema, saved-plan execution, or new authority.
Each implementation file allowlist requires its slice-specific human approval.

## Contract Model

```text
GovernedRunInputSnapshot
├── raw instruction bytes
├── raw inline-input bytes
├── ordered context-source byte snapshots
├── exact assembled execution bytes
├── privacy-safe digests and lengths
└── normalized operator declarations

GovernedDecision
├── governed input-snapshot binding
├── privacy and egress posture
├── context-budget result
├── deterministic classification
├── logical route policy
├── permitted fallback envelope
├── escalation posture
└── required verification and review

RuntimeObservation
├── governed decision ID
├── backend availability
├── latency or circuit state
├── actual backend binding
└── observed fallback

Existing route and worker evidence
├── bounded governed decision ID linkage
├── resulting logical and physical route
└── existing artifact and route evidence linkage
```

### GovernedRunInputSnapshot

`GovernedRunInputSnapshot` is an immutable, attempt-local value object created
before decision construction. It contains:

- the exact raw instruction bytes;
- the exact raw inline-input bytes;
- an ordered sequence of context-source snapshots, each holding the exact
  source bytes plus privacy-safe locator/content digests and byte lengths;
- the exact assembled execution bytes produced from those components;
- privacy-safe component and assembled digests and lengths; and
- versioned normalized operator declarations, including declared privacy,
  declared cloud intent, task-identity posture, and the resolved
  context/model profile.

The snapshot construction contract defines byte encoding, newline treatment,
source ordering, assembly separators, absent-input representation, and
normalization rules. Once validated, neither its bytes nor declarations may be
mutated or replaced. Raw snapshot bytes remain ephemeral execution material;
they are not serialized into the governed decision, plan artifact, ledger, or
other persistent metadata.

The normalizer, decision builder, preview consumer, and executor receive the
same snapshot instance/value. The builder derives privacy-safe decision
bindings from that snapshot. Preview renders from the completed decision and
the matching snapshot without rebuilding either. Execution passes the
snapshot's exact assembled bytes to the selected worker and never reopens
source files, rereads inline input, reconstructs assembled content, or silently
replaces snapshot bytes.

A source may change after the snapshot is created. Such drift may be captured
as a bounded runtime observation only when already available without adding a
new probe or reopen requirement. It does not replace or invalidate the
snapshot, and execution still consumes exactly the governed snapshot bytes.
If a caller requires current source bytes, it must begin a new attempt and
construct a new snapshot and decision.

### GovernedDecision

`GovernedDecision` is an immutable value object with a closed
`governed_decision.v1` schema. Its top-level form is:

```text
identity_domain
contract_version
canonicalization_version
decision_id
decision_body
```

`decision_body` contains only decision-relevant, deterministic fields:

- normalization and policy-contract versions;
- privacy-safe governed-snapshot and normalized operator-intent bindings;
- decision-relevant non-secret configuration bindings;
- declared privacy class and derived privacy-preflight posture;
- egress eligibility and declared cloud intent, kept distinct;
- model/context profile, estimated input tokens, usable budget, and budget
  posture;
- deterministic task classification and bounded specialist-risk posture;
- ethical-firewall and human-review posture;
- preferred logical route and bounded reason code;
- ordered permitted fallback envelope;
- escalation conditions;
- required verification and review checks; and
- explicit authority-boundary fields.

It must not contain:

- timestamps, random IDs, mutable counters, or process-local object IDs;
- backend availability, latency, socket state, circuit state, recent failures,
  or actual backend selection;
- prompt, inline-data, or context-file content;
- raw context paths, matched privacy/firewall values, raw reasons, secrets, or
  credentials;
- backend or model output;
- approval, admission, acceptance, or execution evidence; or
- a claim that cloud execution is authorized.

The object must be immutable after validation. A consumer cannot replace a
route, widen a fallback envelope, change privacy posture, or add a verification
exception. A changed decision-relevant input produces a new decision rather
than mutating the existing one.

### Canonicalization And Decision ID

The schema and canonicalization profile are independently versioned. The
canonical profile must be deterministic UTF-8 JSON with a closed field set,
duplicate-key rejection, recursively sorted object keys, no floats, no BOM,
and a specified newline policy. Arrays preserve contract-defined semantic
order. Only collections explicitly declared set-like by the schema may be
sorted, and each such field must specify its deterministic sort key and
duplicate policy. Ordered context sources and ordered fallback routes are
semantic arrays and must never be sorted or deduplicated.

Decision identity uses this closed, domain-separated hash envelope:

```text
identity_domain = "triagecore.governed_decision.identity.v1"
contract_version
canonicalization_version
decision_body
```

`identity_domain` is the exact fixed ASCII tag shown above; aliases, case
changes, and unknown tags fail closed. `decision_id` is a lower-case
`sha256:[0-9a-f]{64}` digest over the canonical bytes of the complete identity
envelope. The envelope binds the fixed domain tag, contract version,
canonicalization version, and decision body. It excludes only `decision_id`,
avoiding self-reference while preventing the same ID from ambiguously naming
different contract or canonicalization domains.

The serialized `GovernedDecision` carries the same four envelope values plus
`decision_id`. Parsing and validation must reconstruct the closed identity
envelope, verify the fixed domain tag, recompute the ID, and reject any
mismatch. Changing the domain tag, contract version, canonicalization version,
or decision body necessarily changes the decision ID.

The `decision_id` is content linkage, not authenticity, identity, approval,
authorization, safety, or correctness. It is distinct from CR-DD-011's
`plan_body_digest` and `artifact_byte_digest`; none may be substituted for
another.

### Plan Artifact Boundary

In CR-DD-012B, the preview path consumes the completed `GovernedDecision` and
matching snapshot. The existing CR-DD-011 plan renderer may consume that
completed decision without calling the decision builder again. The renderer
continues to publish `governed_run_plan.v1` under its existing closed schema
and semantics.

`governed_run_plan.v1` must not be changed to add `decision_id` or any other
field. Its `plan_body_digest` and `artifact_byte_digest` retain their current
meanings. Existing and newly rendered v1 artifacts remain confirmable and
inspectable under CR-DD-011, and they remain non-executable.

A decision-ID-bearing plan contract, including any
`governed_run_plan.v2`, is deferred to a separately proposed and approved later
CR. Neither CR-DD-012A nor CR-DD-012B authorizes an artifact migration or saved
plan execution.

### Snapshot And Normalized Operator Intent Binding

Snapshot construction uses one versioned input normalizer before building a
decision. The immutable snapshot holds exact task bytes and normalized
declarations. Its privacy-safe decision binding includes, at minimum:

- explicit task ID when supplied, or a fixed deterministic
  `implicit_unassigned` identity posture when it is not;
- instruction digest and byte length;
- inline-input digest and byte length;
- assembled-input digest and byte length;
- ordered context-source bindings using locator digests, content digests, and
  byte lengths rather than raw paths;
- declared privacy class;
- declared cloud intent;
- one canonically resolved context/model profile; and
- decision-relevant validation configuration.

An execution correlation task ID generated when the operator did not supply one
must not enter `decision_body` or `decision_id`. It belongs only in execution
and ledger evidence, where it links the attempt to the governed decision ID.
Random execution correlation therefore cannot cause preview/execution decision
drift.

One pure deterministic profile resolver must serve both paths. It resolves an
explicit `--model` value or the existing stable ordinary-run default to one
canonical context/model profile ID. CR-DD-010's requirement that preview
receive `--model` remains compatible: an explicitly selected preview profile
and an ordinary-run default resolve identically only when they name the same
canonical profile. No path may infer a context window or model profile from a
logical route, backend availability, or actual backend binding. If the current
CLI inputs cannot resolve one supported canonical profile, decision
construction fails closed rather than choosing a route-specific profile.

Raw task material remains only in the immutable snapshot. The
`GovernedDecision` carries the privacy-safe binding needed to prove that the
snapshot supplied to execution is the snapshot that was governed.

Low-entropy values can be guessable from unsalted digests. Decision metadata
therefore remains operator-controlled and is not a public redaction artifact.

Normalization must be identical for preview and execution. CLI spelling,
path-representation differences, or equivalent default expansion must not
silently produce different semantics. Conversely, changes to content, source
order, declared privacy, cloud intent, model/context profile, or other
decision-relevant values must change the binding and therefore the decision
ID.

### Shared Decision Builder

One pure builder accepts the immutable `GovernedRunInputSnapshot` and explicit
decision-relevant policy/configuration facts and returns one validated
`GovernedDecision`.

The builder must:

- perform deterministic classification without a model, network, backend, or
  socket call;
- keep deterministic ethical-firewall and specialist-policy evaluation inside
  the governed decision;
- derive privacy and egress posture from the existing fail-closed preflight;
- derive context-budget posture from the shared assembled input;
- produce the logical route policy and ordered permitted fallback envelope;
- encode escalation and terminal human-handoff conditions; and
- encode required verification/review without executing those checks.

Preview rendering must accept the completed decision and matching immutable
snapshot. Ordinary execution must accept that same completed decision and
snapshot. Neither consumer may call a classifier, privacy policy, context
planner, specialist-policy selector, or logical router to obtain a second
answer. Neither consumer may create a replacement snapshot.

A consumer may validate the decision and its input/configuration bindings. That
validation is not permission to rebuild or silently replace a stale or
inconsistent decision.

### Logical Route And Fallback Envelope

The governed decision describes policy, not a promise that a physical backend
is healthy. It contains:

- the preferred logical route;
- an ordered, closed set of policy-permitted fallback routes;
- bounded conditions under which each fallback is permitted;
- terminal handoff requirements; and
- egress and human-review constraints that no runtime fact can relax.

The fallback envelope is not a route override or injection surface. It is a
constraint on runtime binding. Runtime code may select only a member already
present in the envelope and only when its stated condition is observed.

If no permitted route is available, execution must produce the existing
governed terminal outcome or fail closed. It must not synthesize a new route,
widen the envelope, downgrade privacy, waive review, or enable cloud egress.

### RuntimeObservation

In CR-DD-012B, `RuntimeObservation` is a validated internal value representing
volatile facts after a valid decision exists. It is never included in
`decision_body` or `decision_id`, and this milestone does not define a durable
public observation schema or require a new ledger event.

It may include:

- the governed decision ID;
- bounded availability results for candidate backends;
- bounded latency or circuit-state observations already available to the
  runtime;
- actual backend/model binding;
- the selected envelope member;
- whether a fallback occurred; and
- bounded fallback or unavailable reason codes.

This slice does not add new health probes, circuit breakers, provider
discovery, or telemetry collection. A later implementation may record only
facts already observed by the existing governed execution path.

Changing backend health may change the runtime observation and actual binding.
It must not change the governed decision ID. Runtime observation cannot convert
cloud intent into authorization, make an ineligible packet egress-eligible, or
satisfy human review.

The value is held only as long as needed to validate envelope compliance and
populate existing bounded evidence. A source-drift flag may be included only
when drift is already known; it cannot cause execution to reopen a source or
replace snapshot bytes.

### Existing Evidence Linkage

CR-DD-012B may add only bounded `decision_id` linkage to existing route and
worker evidence. Existing event shapes and identifiers are preserved where
possible, and no `runtime_observation_id`, `runtime_observation.v1`, or
`execution_record.v1` contract is introduced.

Any added linkage must be metadata-only and pass the existing
persistent-privacy invariant before append. It must not contain snapshot bytes
or claim approval, admission, quality, acceptance, or successful human review
merely because the linked decision was valid or a CR-DD-011 artifact was
confirmed. Durable observation and execution-record schemas require a
separately proposed and approved later CR.

## Authority And Cloud Boundary

The decision records declared cloud intent and derived egress eligibility as
separate fields. Neither field is cloud authorization.

A CR-DD-010 preview's `--allow-cloud` posture remains informational only.
Ordinary execution preserves the existing `--allow-cloud` gate as an explicit,
run-scoped input for that invocation and attempt. The decision may bind that
invocation's declared cloud intent/posture so policy and evidence can be
compared, but it cannot manufacture, cache, replay, transfer, or broaden cloud
authority.

A plan artifact or decision reconstructed in a later attempt cannot carry
`--allow-cloud` authority forward. Each ordinary execution attempt must satisfy
the current run-scoped gate independently. An artifact, confirmation event, or
matching decision ID cannot substitute for that invocation's gate.

A valid decision, matching decision ID, permitted cloud route, CR-DD-011
confirmation event, or runtime observation cannot itself authorize egress. Any
existing explicit, run-scoped operator and policy gates remain independent
execution preconditions. Failure or absence of those gates must fail closed
before a cloud backend call.

Human-only and ethical-firewall outcomes remain terminal. No decision,
observation, confirmation, signature, or digest satisfies a human-review gate.

## Fail-Closed Boundary

Execution must stop before backend construction or invocation when:

- the input snapshot is malformed, mutable, internally inconsistent, or has a
  digest/length/assembly mismatch;
- the decision is malformed, noncanonical, or has an ID mismatch;
- the schema, normalization, policy, or canonicalization version is
  unsupported;
- a required field is missing or an unknown field appears;
- execution did not receive the exact immutable snapshot used to build the
  decision or its privacy-safe binding does not match;
- a decision-relevant configuration or policy binding changed;
- the decision is stale under an explicit version/configuration/input binding;
- the logical route is absent or inconsistent with its fallback envelope;
- runtime binding selects a route outside the permitted envelope;
- privacy, egress, cloud, ethical-firewall, or human-review constraints are
  inconsistent; or
- required verification metadata is internally inconsistent.

Staleness is defined by the immutable snapshot binding and decision-relevant
facts, not elapsed wall-clock time, current source-file contents, or backend
health. Volatile health or known post-snapshot source drift may change the
internal runtime observation; neither changes the decision ID or the bytes
consumed by execution. On a stale or inconsistent decision, the system must
not rebuild transparently. The current attempt terminates, and a new invocation
may produce a new snapshot and decision.

## Invariants

- Snapshot construction, decision building, preview, and execution share one
  immutable governed input snapshot.
- Execution consumes the exact assembled snapshot bytes and never reopens,
  reconstructs, or silently substitutes source content.
- Preview and ordinary execution consume the same canonical decision contract.
- Identical snapshots and policy facts produce the same decision ID.
- A decision is built once per attempt and never independently recomputed by a
  downstream consumer.
- Raw task content is separate from the privacy-safe canonical decision.
- Decision identity is stable across runtime-health changes.
- Internal runtime observations cannot relax or rewrite governed policy.
- Actual routing remains inside the decision's fallback envelope.
- Human handoff remains terminal where current policy requires it.
- Cloud intent, digest agreement, and exact-plan confirmation are not
  authorization.
- Decision or observation linkage is evidence, not approval or acceptance.
- Existing privacy-before-persistence and append-only evidence rules remain
  load-bearing.

## Non-Goals

- No execution from a saved CR-DD-011 plan artifact.
- No `--confirmed-plan`.
- No automatic execution after exact-plan confirmation.
- No `governed_run_plan.v2` or other plan-artifact schema change.
- No durable `RuntimeObservation`, `ExecutionRecord`,
  `runtime_observation.v1`, or `execution_record.v1` schema.
- No route override, route injection, or caller-supplied fallback expansion.
- No new cloud authorization or inference of authorization from intent.
- No approval-and-resume, persistence/resume, session, checkpoint, queue,
  scheduler, retry, daemon, or background execution semantics.
- No artifact acceptance, quality scoring, evaluator invocation, or quality
  gate interpretation.
- No new backend, provider, live health probe, circuit breaker, capability
  discovery, or frontier-cloud integration.
- No token-budget enforcement, compaction, truncation, or context rewriting.
- No TriageDesk or mobile action surface.
- No new identity, signing, admission, or cryptographic authority.
- No claims of token, cost, latency, energy, quality, privacy, or safety
  improvement.

## Acceptance Criteria

### CR-DD-012A — Separate Approval Required

- [ ] A closed, versioned, immutable `GovernedRunInputSnapshot` captures the
  exact raw instruction bytes, raw inline bytes, ordered context-source byte
  snapshots, exact assembled execution bytes, privacy-safe digests/lengths,
  and normalized operator declarations.
- [ ] Snapshot byte assembly and normalization are deterministic, and mutation,
  replacement, digest/length mismatch, or inconsistent assembly fails closed.
- [ ] A closed, versioned `GovernedDecision` schema and canonicalization profile
  are implemented.
- [ ] Canonical arrays preserve contract-defined semantic order; only
  explicitly set-like fields are sorted using their schema-specified key and
  duplicate policy.
- [ ] `decision_id` is reproducible from the canonical, domain-separated
  identity envelope binding the fixed domain tag, contract version,
  canonicalization version, and decision body while excluding only
  `decision_id`.
- [ ] Unknown or altered domain tags, changed contract/canonicalization
  versions, malformed or noncanonical envelopes, unknown fields, unsupported
  versions, and digest mismatches fail closed.
- [ ] One pure deterministic builder consumes the immutable snapshot and
  decision-relevant policy facts.
- [ ] Identical snapshots and decision-relevant policy inputs produce
  byte-identical decision bodies and identical decision IDs.
- [ ] An implicit task identity is deterministic and excludes any generated
  execution correlation ID from the decision body and ID.
- [ ] The shared pure resolver produces one canonical context/model profile and
  never infers a profile from the route.
- [ ] No CLI, preview renderer, execution, ledger, evidence, plan-artifact, or
  runtime-observation persistence behavior changes in CR-DD-012A.

### CR-DD-012B — Separate Approval Required After CR-DD-012A

- [ ] The normalizer, decision builder, preview, and ordinary execution consume
  the same immutable snapshot; execution uses its exact assembled bytes.
- [ ] Preview and execution receive the same completed decision and cannot
  independently reclassify, replan context, recalculate policy, select
  specialist policy, or logically reroute.
- [ ] Privacy, egress, context budget, deterministic classification, logical
  route, fallback envelope, escalation, ethical-firewall, human-review, and
  verification posture come only from the shared decision.
- [ ] Execution never reopens context sources, reconstructs task content, or
  silently replaces snapshot bytes after decision construction.
- [ ] Post-snapshot source drift, when already observed, remains a bounded
  internal observation; execution still consumes the snapshot bytes.
- [ ] Runtime availability and physical backend binding are excluded from the
  governed decision and held in a validated internal observation.
- [ ] Backend-health changes can change the internal observation without
  changing the decision ID.
- [ ] Runtime binding cannot select a route outside the permitted fallback
  envelope or relax privacy, egress, cloud, or human-review constraints.
- [ ] Existing route and worker evidence gains only bounded, privacy-safe
  `decision_id` linkage, preserving existing event shapes where possible.
- [ ] Snapshot-binding, policy, configuration, or version inconsistency fails
  closed before backend invocation and is never repaired by silent
  recomputation.
- [ ] Cloud intent, plan confirmation, or decision validity never becomes cloud
  authorization.
- [ ] CR-DD-010 preview keeps `--allow-cloud` informational, and every ordinary
  execution attempt independently satisfies the existing run-scoped
  `--allow-cloud` gate.
- [ ] The existing v1 plan renderer consumes the completed decision without
  rebuilding it while preserving `governed_run_plan.v1` fields and semantics.
- [ ] `governed_run_plan.v1` remains confirmable, inspectable, and
  non-executable, contains no `decision_id`, and no v2 contract is introduced.
- [ ] Existing stdout preview, plan-artifact confirmation, ordinary `tc run`,
  terminal handoff, privacy, ledger, and task-inspection behavior remains green.
- [ ] No saved plan artifact is accepted as execution input, and no
  `--confirmed-plan` surface exists.

## Required Test Plan

### CR-DD-012A Foundation Tests

- byte-identical input snapshots for repeated identical bytes, declarations,
  assembly rules, and ordered source snapshots;
- snapshot immutability plus rejection of mutated/replaced components,
  digest/length mismatches, and inconsistent assembled bytes;
- byte-identical decision bodies, identity envelopes, and IDs for repeated
  identical snapshots and policy inputs;
- fixed-domain-tag validation plus proof that changing the domain tag, contract
  version, or canonicalization version changes the decision ID;
- closed-schema, missing/unknown-field, duplicate-key, unsupported-version,
  noncanonical envelope serialization, and ID-mismatch rejection;
- proof that context-source and fallback arrays preserve semantic order, plus
  deterministic sorting and duplicate handling only for each explicitly
  set-like field;
- deterministic `implicit_unassigned` task posture with generated execution
  correlation IDs excluded from decision identity;
- explicit/default model-profile resolution parity and fail-closed rejection
  when no canonical profile can be resolved;
- explicit distinction among `decision_id`, `plan_body_digest`, and
  `artifact_byte_digest`; and
- privacy-safe decision checks that reject raw prompts, inline data, context
  content, raw source paths, matched values, secrets, and credentials while
  allowing exact bytes only in the ephemeral input snapshot;
- proof that snapshot construction and decision building perform no model,
  backend, network, socket, or subprocess call; and
- regression proof that CR-DD-012A changes no CLI, ledger, plan artifact,
  preview, or execution behavior.

### CR-DD-012B Preview/Execution Parity

- one fixture matrix covering local routes, cloud-eligible posture, terminal
  human handoff, ethical-firewall cases, fitting/over-budget context, and
  multiple ordered sources;
- assertions that builder, preview, and execution receive the same immutable
  snapshot and that preview and execution receive the same canonical decision
  body and decision ID;
- traps proving preview, v1 plan publication, and execution do not rebuild the
  snapshot or decision;
- traps proving downstream preview and execution paths cannot invoke a second
  classifier, privacy evaluator, context planner, specialist-policy selector,
  or logical router; and
- mutation tests proving any decision-relevant input changes the ID and cannot
  reuse the previous decision.

### CR-DD-012B Runtime Separation

- simulated backend-health changes that preserve the decision ID while changing
  the validated internal observation;
- preferred-route, permitted-fallback, no-permitted-route, and terminal-handoff
  cases;
- rejection of an actual route outside the ordered fallback envelope;
- proof that runtime availability cannot widen egress, cloud, or human-review
  posture; and
- proof that no durable observation/execution record or new ledger event shape
  is introduced.

### CR-DD-012B Fail-Closed And Regression

- file changes after snapshot construction, with traps proving execution does
  not reopen the file and sends the exact snapshot bytes to the worker;
- optional bounded source-drift observation, when already available, without
  content replacement or a new probe;
- reordered, added, removed, or modified context bytes require a new snapshot
  and decision rather than mutating or reusing the prior snapshot;
- policy/configuration binding drift and unsupported contract-version
  rejection;
- malformed or internally inconsistent snapshot, decision, and bounded
  evidence linkage;
- no backend call and no privacy-unsafe ledger write on every rejected case;
- existing `governed_run_plan.v1` confirmation and inspection compatibility,
  rejection of unknown or silently modified v1 fields, proof that the renderer
  does not rebuild, and proof that v1 contains no `decision_id`;
- proof that preview intent, a plan artifact, a confirmation event, or a prior
  attempt cannot replay the ordinary run's `--allow-cloud` gate;
- existing CR-DD-009, CR-DD-010, CR-DD-011, CR-125, and CR-126 regression
  coverage; and
- explicit rejection or absence of saved-plan execution and
  `--confirmed-plan`.

## Security And Privacy

- Decision construction reuses privacy preflight and remains fail closed.
- The governed copy of exact raw input and context bytes is held in the
  immutable, ephemeral `GovernedRunInputSnapshot`, passed only through the
  existing execution path, and never persisted as decision or evidence
  metadata.
- Persistent decision and existing route/worker metadata contains no raw
  prompt, inline data, context content, raw source path, matched value, secret,
  credential, or model output.
- Content hashes are linkage only and remain subject to the low-entropy
  disclosure limitation.
- Decision-relevant configuration bindings expose only bounded, non-secret
  identifiers or digests.
- Runtime reason fields use a closed bounded vocabulary, not backend exception
  text.
- Every persisted record passes the existing persistent-privacy audit.
- Digest agreement proves byte/semantic linkage only; it does not prove
  authenticity or permission.

## Risks And Mitigations

- **Shared code but divergent calls:** parity tests trap every independent
  classifier/planner/router call after decision construction.
- **Health frozen into policy:** backend availability and actual binding exist
  only in `RuntimeObservation`.
- **Fallback used as an override:** execution may select only an enumerated
  envelope member under an enumerated condition.
- **TOCTOU through source reopen:** execution consumes the exact immutable
  snapshot bytes and is trapped from reopening or reconstructing sources.
- **Post-snapshot source drift misunderstood:** bounded observation may report
  drift, but the attempt remains tied to the governed snapshot; callers needing
  current bytes must start a new attempt.
- **Decision mistaken for authority:** schema, CLI output, and evidence state
  that the decision and cloud intent grant no authority.
- **Hash mistaken for secrecy or authenticity:** documentation preserves the
  low-entropy and linkage-only limitations.
- **Silent behavior migration:** the future implementation requires focused
  parity fixtures and full existing-run regression coverage before release.

## Rollout And Rollback

This parent CR changed documentation only, so rollback of its architecture is
revision of this file. Each child implementation is separately governed.

Implementation is delivered as two separately approved, reviewable slices:

1. **CR-DD-012A:** the immutable input snapshot, canonical decision contract,
   pure builder, domain-separated identity, and focused
   contract/privacy/determinism tests are complete and validated on the branch.
   Merge is pending, with no CLI, ledger, plan, preview, or execution behavior
   change.
2. **CR-DD-012B:** after separate human approval, make preview and ordinary
   execution consume the completed decision and same snapshot, enforce the
   runtime fallback envelope, add bounded `decision_id` linkage to existing
   evidence, and run parity/fail-closed/regression validation.

The public CLI and `governed_run_plan.v1` contract remain stable throughout.
Neither slice adds durable observation/execution records. If contract,
runtime-parity, or privacy validation fails, the affected slice does not ship.
Append-only evidence already written by a controlled validation is preserved
and disclosed; it is not rewritten during rollback.

## Dependencies And Sequencing

- Depends on CR-DD-009's governed execution surface.
- Depends on CR-DD-010's deterministic preview.
- Depends on CR-DD-011's canonical plan and exact review-linkage boundary, but
  does not consume confirmed artifacts.
- Preserves CR-125 terminal resilience routes and CR-126
  privacy-before-persistence behavior.
- The implementation in `CR-DD-012A-governed-decision-foundation.md` has
  received bounded approval and passed validation and focused review; it must
  land before CR-DD-012B may receive implementation approval.
- CR-DD-012B must land and prove preview/execution parity before any
  confirmed-plan execution proposal.
- Plan-artifact v2 and durable runtime-observation/execution-record schemas are
  deferred to separately proposed and approved later CRs.
- Confirmed-artifact execution, durable resume, live capability signals,
  circuit breakers, provider expansion, budget enforcement, evaluator/quality
  integration, and TriageDesk authority remain separate later CRs.

## Proposal File Scope

This architecture-approval revision authorizes only documentation/status
alignment in:

- `docs/change/requests/CR-DD-012-shared-governed-run-decision.md`
- `docs/current_backlog.md` — CR-DD-010/011 completion and CR-DD-012
  architecture-approval/decomposition status alignment only
- `docs/architecture/daily_driver_orchestrator_spec.md` — M0.1 through M0.3
  status and sequencing alignment only
- `docs/change/requests/CR-DD-010-governed-run-plan-preview.md` — status-only
  alignment
- `docs/change/requests/CR-DD-011-plan-confirmation-linkage.md` — status-only
  alignment

`docs/change/change_log.md` must remain untouched. No code, tests, runtime
behavior, CLI surface, artifact schema, ledger behavior, or other documentation
change is authorized by this milestone. CR-DD-012A received its own explicit
human implementation approval and separate bounded file allowlist. CR-DD-012B
still requires both.
