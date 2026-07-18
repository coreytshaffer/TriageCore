# CR-DD-012: Shared Governed Run Decision

## Status

Proposed — pending human approval.

This is a documentation-only proposal. It grants no implementation authority
and changes no runtime, CLI, ledger, artifact, approval, or cloud behavior.
Current CR-DD-009 through CR-DD-011 behavior remains unchanged until a later
explicit implementation approval.

## Decision

Introduce one immutable `GovernedDecision` contract that is constructed by one
shared pure decision path and consumed by both:

1. CR-DD-010 preview generation, including the CR-DD-011 plan-artifact
   renderer; and
2. ordinary `tc run` execution.

For identical normalized task inputs and identical decision-relevant policy
facts, preview and execution must receive the same canonical decision body and
`decision_id`. Neither path may independently classify, calculate privacy or
context-budget posture, choose a logical route, expand a fallback envelope, or
derive verification requirements after the shared decision is built.

Volatile backend health is not part of the governed policy decision. Runtime
availability and the physical backend selected within the decision's permitted
fallback envelope are captured separately as `RuntimeObservation` evidence.
An `ExecutionRecord` links the immutable decision, the runtime observation, and
the resulting route and artifact evidence.

This CR deliberately does not make a CR-DD-011 plan artifact executable.

## Problem

CR-DD-010 and CR-DD-011 provide deterministic preview, artifact, and exact
review-confirmation foundations. Ordinary `tc run` still has decision seams
that can diverge from that preview:

- preview uses deterministic classification while execution may use the
  model-assisted classifier;
- specialist routing currently mixes policy-sensitive handling with a live
  socket-dependent branch;
- preview and execution can call policy components independently; and
- volatile runtime health can affect a physical route without an explicit
  distinction between reviewed policy and observed availability.

Adding `--confirmed-plan` before these seams are removed would imply that
execution honors the reviewed decision when the system cannot yet prove that
claim.

## Scope

A future approved implementation of this proposal is limited to:

- a closed, versioned, canonical `GovernedDecision` schema;
- a deterministic, content-addressed `decision_id`;
- one versioned normalization path for operator intent and task inputs;
- one shared pure decision builder used by preview and ordinary execution;
- shared privacy, egress, context-budget, classification, logical-route,
  fallback-envelope, escalation, human-review, and verification fields;
- a separate runtime-observation contract for volatile execution facts;
- metadata-only execution evidence linking the decision and observation IDs;
- fail-closed validation at the decision-to-execution boundary; and
- focused parity, safety, privacy, and regression tests.

The implementation must preserve the existing public `tc run` and
`tc run --plan` command meanings. This proposal branch may align only the
bounded planning/status documents listed under **Proposal File Scope**. Any
runtime implementation file allowlist requires a separate approval after this
proposal is reviewed.

## Contract Model

```text
GovernedDecision
├── normalized operator intent binding
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

ExecutionRecord
├── governed decision ID
├── runtime observation ID
├── resulting logical and physical route
└── artifact and route evidence linkage
```

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
- privacy-safe normalized operator-intent bindings;
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
duplicate-key rejection, recursively sorted object keys, deterministic array
ordering where order is semantic, no floats, no BOM, and a specified newline
policy.

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

### Plan Artifact Decision Identity

CR-DD-011 plan publication must render the already-built
`GovernedDecision` and retain its exact `decision_id`. The renderer must not
call the decision builder again, reconstruct a decision from rendered fields,
or derive a replacement identity from `plan_body_digest` or
`artifact_byte_digest`.

`governed_run_plan.v1` is an existing closed contract and must not be silently
changed to add `decision_id` or any other field. Existing v1 artifacts remain
valid for CR-DD-011 confirmation and inspection, subject to their existing
validation rules. They remain non-executable.

New plan publication under a future CR-DD-012 implementation must use an
explicitly new artifact contract version, such as `governed_run_plan.v2`, that
contains the exact `decision_id` received from the shared builder. The new
version must preserve the distinct `decision_id`, `plan_body_digest`, and
`artifact_byte_digest` meanings. Any later artifact-contract evolution must
receive another explicit version; readers must never infer a new contract from
an old version.

Neither the new version nor its decision-ID linkage authorizes saved-artifact
execution. A plan artifact remains review evidence and a non-executing
representation of the governed decision.

### Normalized Operator Intent Binding

Preview and execution must use one versioned input normalizer before building a
decision. The normalized binding includes, at minimum:

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

Raw task material remains in the separately held execution input. The
`GovernedDecision` carries only the privacy-safe binding needed to prove that
the execution input is the input that was governed.

Low-entropy values can be guessable from unsalted digests. Decision metadata
therefore remains operator-controlled and is not a public redaction artifact.

Normalization must be identical for preview and execution. CLI spelling,
path-representation differences, or equivalent default expansion must not
silently produce different semantics. Conversely, changes to content, source
order, declared privacy, cloud intent, model/context profile, or other
decision-relevant values must change the binding and therefore the decision
ID.

### Shared Decision Builder

One pure builder accepts the normalized inputs and explicit decision-relevant
policy/configuration facts and returns one validated `GovernedDecision`.

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

Preview rendering must accept the completed decision. Ordinary execution must
accept the completed decision plus the separately held matching execution
input. Neither consumer may call a classifier, privacy policy, context planner,
specialist-policy selector, or logical router to obtain a second answer.

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

`RuntimeObservation` records volatile facts after a valid decision exists. It
is a separate, versioned, privacy-safe record and is never included in
`decision_body` or `decision_id`.

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

Each evidence snapshot receives its own `runtime_observation_id`. Later
observations append or supersede by explicit linkage; they do not mutate the
governed decision.

### ExecutionRecord

Execution evidence must link:

- `decision_id`;
- `runtime_observation_id`;
- the resulting logical route and physical backend binding;
- whether a permitted fallback occurred;
- route-decision and worker-result evidence identifiers;
- output artifact evidence when one exists; and
- the terminal result posture.

The record must be metadata-only and pass the existing persistent-privacy
invariant before append. It must not claim approval, admission, quality,
acceptance, or successful human review merely because the linked decision was
valid or a CR-DD-011 artifact was confirmed.

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

- the decision is malformed, noncanonical, or has an ID mismatch;
- the schema, normalization, policy, or canonicalization version is
  unsupported;
- a required field is missing or an unknown field appears;
- the current execution input does not match the normalized content binding;
- ordered source membership or source content changed after decision creation;
- a decision-relevant configuration or policy binding changed;
- the decision is stale under an explicit version/configuration/input binding;
- the logical route is absent or inconsistent with its fallback envelope;
- runtime binding selects a route outside the permitted envelope;
- privacy, egress, cloud, ethical-firewall, or human-review constraints are
  inconsistent; or
- required verification metadata is internally inconsistent.

Staleness is defined by bound facts, not elapsed wall-clock time or backend
health. Volatile health changes create a new runtime observation; they do not
make the policy decision stale. On a stale or inconsistent decision, the
system must not rebuild transparently. The current attempt terminates, and a
new invocation may produce a new decision.

## Invariants

- Preview and ordinary execution consume the same canonical decision contract.
- Identical normalized input and policy facts produce the same decision ID.
- A decision is built once per attempt and never independently recomputed by a
  downstream consumer.
- Raw task content is separate from the privacy-safe canonical decision.
- Decision identity is stable across runtime-health changes.
- Runtime observations cannot relax or rewrite governed policy.
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

- [ ] A closed, versioned `GovernedDecision` schema and canonicalization profile
  are documented and implemented.
- [ ] `decision_id` is reproducible from the canonical, domain-separated
  identity envelope binding the fixed domain tag, contract version,
  canonicalization version, and decision body while excluding only
  `decision_id`.
- [ ] Unknown or altered domain tags, changed contract/canonicalization
  versions, malformed or noncanonical envelopes, unknown fields, unsupported
  versions, and digest mismatches fail closed.
- [ ] Preview and execution use the same versioned normalizer and shared pure
  decision builder.
- [ ] Identical normalized task and decision-relevant policy inputs produce
  byte-identical decision bodies and identical decision IDs.
- [ ] An implicit task identity is deterministic and excludes any generated
  execution correlation ID from the decision body and ID.
- [ ] Preview and ordinary execution resolve one canonical context/model
  profile through the same pure resolver, preserve existing CLI defaults and
  compatibility, and never infer a profile from the route.
- [ ] Privacy, egress, context budget, deterministic classification, logical
  route, fallback envelope, escalation, ethical-firewall, human-review, and
  verification posture come only from the shared decision.
- [ ] Preview and execution cannot independently reclassify, replan context,
  recalculate policy, or reroute after decision construction.
- [ ] Runtime availability and physical backend binding are excluded from the
  governed decision and captured in a separately identified observation.
- [ ] Backend-health changes can change the runtime observation without
  changing the decision ID.
- [ ] Runtime binding cannot select a route outside the permitted fallback
  envelope or relax privacy, egress, cloud, or human-review constraints.
- [ ] Execution evidence links the governed decision ID, runtime observation
  ID, resulting route, and artifact/worker evidence without raw task content.
- [ ] Content, source-order, policy, configuration, or version drift fails
  closed before backend invocation and is never repaired by silent
  recomputation.
- [ ] Cloud intent, plan confirmation, or decision validity never becomes cloud
  authorization.
- [ ] CR-DD-010 preview keeps `--allow-cloud` informational, and every ordinary
  execution attempt independently satisfies the existing run-scoped
  `--allow-cloud` gate.
- [ ] New plan publication carries the exact decision ID received from the
  shared builder without rebuilding the decision.
- [ ] `governed_run_plan.v1` is unchanged; existing v1 artifacts remain
  confirmable, inspectable, and non-executable, while new decision-ID-bearing
  artifacts use an explicitly new closed contract version.
- [ ] For identical normalized inputs and decision-relevant policy facts, the
  new plan artifact's embedded decision ID equals the decision ID consumed by
  ordinary execution.
- [ ] Existing stdout preview, plan-artifact confirmation, ordinary `tc run`,
  terminal handoff, privacy, ledger, and task-inspection behavior remains green.
- [ ] No saved plan artifact is accepted as execution input, and no
  `--confirmed-plan` surface exists.

## Required Test Plan

### Canonical Contract

- byte-identical decision bodies, identity envelopes, and IDs for repeated
  identical inputs;
- fixed-domain-tag validation plus proof that changing the domain tag, contract
  version, or canonicalization version changes the decision ID;
- closed-schema, missing/unknown-field, duplicate-key, unsupported-version,
  noncanonical envelope serialization, and ID-mismatch rejection;
- deterministic `implicit_unassigned` task posture with generated execution
  correlation IDs excluded from decision identity;
- explicit/default model-profile resolution parity and fail-closed rejection
  when no canonical profile can be resolved;
- explicit distinction among `decision_id`, `plan_body_digest`, and
  `artifact_byte_digest`; and
- privacy-safe binding checks that reject raw prompts, inline data, context
  content, raw source paths, matched values, secrets, and credentials.

### Preview/Execution Parity

- one fixture matrix covering local routes, cloud-eligible posture, terminal
  human handoff, ethical-firewall cases, fitting/over-budget context, and
  multiple ordered sources;
- assertions that preview and execution receive the same canonical decision
  body and decision ID for each identical normalized input/configuration set;
- assertions that a newly published versioned plan artifact carries that same
  decision ID and that ordinary execution consumes the matching identity;
- traps proving plan publication does not rebuild or independently derive the
  decision;
- traps proving downstream preview and execution paths cannot invoke a second
  classifier, privacy evaluator, context planner, specialist-policy selector,
  or logical router; and
- mutation tests proving any decision-relevant input changes the ID and cannot
  reuse the previous decision.

### Runtime Separation

- simulated backend-health changes that preserve the decision ID but produce
  distinct observation IDs;
- preferred-route, permitted-fallback, no-permitted-route, and terminal-handoff
  cases;
- rejection of an actual route outside the ordered fallback envelope;
- proof that runtime availability cannot widen egress, cloud, or human-review
  posture; and
- proof that no new probe, model, network, socket, or subprocess call occurs
  during decision construction or preview.

### Fail-Closed And Regression

- input-file TOCTOU between decision construction and backend invocation;
- reordered, added, removed, or modified context-source rejection;
- policy/configuration binding drift and unsupported contract-version
  rejection;
- malformed or internally inconsistent decision and observation linkage;
- no backend call and no privacy-unsafe ledger write on every rejected case;
- existing `governed_run_plan.v1` confirmation and inspection compatibility,
  plus rejection of unknown or silently modified v1 fields;
- proof that preview intent, a plan artifact, a confirmation event, or a prior
  attempt cannot replay the ordinary run's `--allow-cloud` gate;
- existing CR-DD-009, CR-DD-010, CR-DD-011, CR-125, and CR-126 regression
  coverage; and
- explicit rejection or absence of saved-plan execution and
  `--confirmed-plan`.

## Security And Privacy

- Decision construction reuses privacy preflight and remains fail closed.
- Persistent decision, observation, and execution metadata contains no raw
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
- **Stale content executed:** input and ordered-source bindings are revalidated
  before backend invocation; mismatch terminates the attempt.
- **Decision mistaken for authority:** schema, CLI output, and evidence state
  that the decision and cloud intent grant no authority.
- **Hash mistaken for secrecy or authenticity:** documentation preserves the
  low-entropy and linkage-only limitations.
- **Silent behavior migration:** the future implementation requires focused
  parity fixtures and full existing-run regression coverage before release.

## Rollout And Rollback

This proposal changes documentation only, so rollback is removal or revision of
this file before implementation approval.

A future implementation should be delivered as one bounded, reviewable slice:

1. introduce the canonical immutable contract and pure builder;
2. add parity and fail-closed tests;
3. make preview render the returned decision;
4. make ordinary execution consume that returned decision;
5. record separate runtime observation and linked execution evidence; and
6. run focused, full-suite, persistent-privacy, and diff-integrity validation.

The public CLI remains stable throughout. If runtime parity or privacy
validation fails, the implementation does not ship. Append-only evidence
already written by a test or controlled validation is preserved and disclosed;
it is not rewritten during rollback.

## Dependencies And Sequencing

- Depends on CR-DD-009's governed execution surface.
- Depends on CR-DD-010's deterministic preview.
- Depends on CR-DD-011's canonical plan and exact review-linkage boundary, but
  does not consume confirmed artifacts.
- Preserves CR-125 terminal resilience routes and CR-126
  privacy-before-persistence behavior.
- Must land and prove preview/execution parity before any confirmed-plan
  execution proposal.
- Confirmed-artifact execution, durable resume, live capability signals,
  circuit breakers, provider expansion, budget enforcement, evaluator/quality
  integration, and TriageDesk authority remain separate later CRs.

## Proposal File Scope

This proposal authorizes only:

- `docs/change/requests/CR-DD-012-shared-governed-run-decision.md`
- `docs/current_backlog.md` — CR-DD-010/011 completion and CR-DD-012 proposal
  status alignment only
- `docs/architecture/daily_driver_orchestrator_spec.md` — M0.1 through M0.3
  status and sequencing alignment only
- `docs/change/requests/CR-DD-010-governed-run-plan-preview.md` — status-only
  alignment
- `docs/change/requests/CR-DD-011-plan-confirmation-linkage.md` — status-only
  alignment

`docs/change/change_log.md` must remain untouched. No code, tests, runtime
behavior, CLI surface, artifact schema, ledger behavior, or other documentation
change is authorized until explicit human implementation approval establishes
a separate file allowlist.
