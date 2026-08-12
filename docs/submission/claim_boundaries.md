# Claim Boundaries

## Status and Evidence Basis

**Documentation-only public-claim reference.** Verified against post-merge
`main` at `b228e0d1d55d5b1e7995232015d321e016214113`.

The [canonical identity](../architecture/triagecore_identity.md) governs
repository-level identity wording, and the
[current system architecture](../architecture/current_system_architecture.md)
governs integration status. Detailed component documents and tests control exact
behavior, ordering, platform constraints, and reason codes. This slice grants no
implementation, integration, mutation, merge, or standing authority.

## Canonical Public Claim

TriageCore is a local-first, evidence-bound research workbench for governing
AI-assisted decisions and consequential actions through explicit authority,
reviewable artifacts, bounded execution mechanisms, and independently governed
evaluation boundaries.

Resource-aware routing is one governed subsystem rather than the whole project
identity. TriageCore should not be described as a production platform, general
agent runtime, complete containment system, or safety-certification authority.

## Current and Integrated

Current repository evidence supports these claims:

- The governed `tc run` path performs packet preflight, resolves recorded
  local-runtime capability evidence, forms a route decision, handles terminal
  routes, invokes an eligible configured backend, validates results, and records
  ledger evidence. Route choice and backend execution remain separate stages;
  see the [governed run flow](../architecture/governed_run_flow.md).
- Local evidence and review projections support inspection and bounded human
  review; see [reviewer traceability](../operations/reviewer-traceability.md).
- Workspace Unifier provides current local YAML views, explicit mutations,
  static dashboards, bounded handoffs, and evaluator-input exports. Exports do
  not prove delivery, evaluation, or result production; see the
  [Workspace Unifier architecture](../architecture/workspace_unifier_architecture.md).
- TriageDesk is a current read-only review and observability surface. It has no
  action/executor bridge and no independent approval authority.

## Current but Optional

The bounded Qwen Cloud route may receive an eligible `ExternalSafeTaskPacket`
when the route is selected and the backend is enabled and configured. Ineligible,
disabled, or unavailable paths terminate or return a handoff rather than gaining
implicit cloud authority.

External-safe classification is an egress and routing boundary, not human
approval or execution authorization.

The adapter path has mocked test coverage, and the bounded reviewer workflow
does not require live Qwen credentials. These facts do not demonstrate live
remote-service reliability, broad provider support, or production cloud
operation.

## Implemented Separate Lane

Request-bound WebAuthn authorization receipts and the atomic SQLite capability
lifecycle are implemented as a separate lane. Current `tc run` does not consume
that lane. A valid receipt or capability state does not prove execution
correctness or human acceptance of a result; see the
[human authorization lifecycle](../architecture/human_authorization_lifecycle.md).

## Implemented but Disconnected

Exact mediated effects, request reservation, capability binding, and constrained
single-file replacement are implemented foundations. No current orchestration
edge composes authorization, reservation, capability claiming, effect execution,
finalization, and joined evidence end to end. See
[mediated execution foundations](../architecture/mediated_execution_foundations.md)
and the
[constrained replacement sequence](../architecture/constrained_replacement_sequence.md).

## Future, Conceptual, or External

- A TriageDesk action/executor bridge is future and separately governed.
- Meta-harnesses and bounded agents are conceptual or externally operated; this
  repository does not deploy them.
- Independent evaluator invocation, scoring, and score interpretation remain
  external. Static handoffs and evaluator-input exports are not evaluator runs.
- Environmental and edge workflows are adjacent application directions, not
  implemented field deployments.

Compatibility does not grant authority. Future external integrations remain
subject to the
[external runtime integration doctrine](../integrations/integration_doctrine.md).

## Evidence Semantics

- Hash or manifest agreement supports internal integrity relative to recorded
  bytes; it does not establish authorship, authenticity, safety, or correctness.
- A valid cryptographic signature supports integrity and signer attribution
  under its verification assumptions; it is not human approval or proof that an
  action was safe.
- A structurally valid authority manifest records bounded declared scope; it
  grants no approval, capability, routing enforcement, or execution authority.
- A valid runtime or route manifest does not by itself make a backend trustworthy
  or authorize its use.
- Review metadata supports evidence and queue projections; it is not a universal
  execution block or a human authorization token.
- An artifact-review or quality verdict, however labeled, is evidence about
  output quality only; it does not authorize mutation, commit, push, merge,
  consequential effects, or recorded human acceptance.
- Evaluator output is assessment evidence, not authorization, mutation
  permission, or recorded human acceptance.
- An observation records what was measured under stated conditions; it does not
  by itself establish causation, correctness, or deployment fitness.

The broader empirical boundary is defined in the
[TriageCore research question](../research/triagecore_research_question.md).

## Concise Submission Wording

TriageCore is a local-first, evidence-bound research workbench with a current
governed CLI run path, reviewable evidence and workspace surfaces, an optional
bounded Qwen route, a separate human-authorization and capability lane, and
implemented-but-disconnected mediated-execution foundations. It keeps routing,
authority, review, execution, and external evaluation boundaries explicit
without presenting them as one end-to-end safety system.

## Non-Claims

TriageCore does not claim:

- to solve model alignment or prove model, agent, provider, or workflow safety;
- safety certification, complete sandboxing, or complete containment;
- complete organizational governance or replacement of operator judgment;
- end-to-end composition of human authorization through consequential
  execution;
- deployment of an independent evaluator, meta-harness, or bounded-agent
  runtime;
- that signatures, manifests, reviews, or evaluator outputs independently grant
  authority; or
- implemented environmental or edge deployment outcomes.

## Uncertainty and Limitations

- The evidence pin describes one repository state. Re-verify architecture,
  component contracts, tests, and call sites when the pin changes.
- Repository integration does not establish host deployment, network topology,
  operational configuration, evaluator activity, or operator practice.
- Mocked Qwen tests establish bounded adapter behavior under test conditions,
  not live service availability, reliability, or production readiness.
- This document cannot certify safety or override component-specific sources,
  tests, or stricter non-claims. It grants no implementation, integration,
  mutation, merge, approval, or standing authority.
