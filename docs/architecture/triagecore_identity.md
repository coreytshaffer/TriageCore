# TriageCore Identity

## Status and Evidence Basis

**Documentation-only identity reference.** Verified against post-merge `main` at
`707a879c29687257332438cd33f257e835a1d978`.

This page is authoritative for consistent repository-level identity wording. It
does not define or authorize runtime behavior, and it does not supersede
component-specific contracts, architecture notes, tests, or evidence. This
documentation-only slice grants no implementation, integration, mutation,
merge, or standing authority.

## Canonical Identity

TriageCore is a local-first, evidence-bound research workbench for governing
AI-assisted decisions and consequential actions through explicit authority,
reviewable artifacts, bounded execution mechanisms, and independently governed
evaluation boundaries.

## Category Vocabulary

- **Workbench** describes TriageCore's research-stage maturity and its use for
  assembling, inspecting, and testing governance controls.
- **Control plane** describes an architectural function: forming bounded
  decisions, preserving authority boundaries, and producing inspectable
  evidence around execution-bearing systems.
- **Harness** describes the experimental and evaluation role of reproducible
  fixtures, controlled pressure cases, and evidence collection.
- **Runtime** applies only to paths that actually execute work. A documented
  contract or implemented foundation is not a runtime integration.

TriageCore is not a platform, a general agent runtime, a complete containment
system, or a safety-certification authority.

## Scope Taxonomy

### Governance kernel

- decision integrity
- identity and authority
- capability and effect bounds
- evidence and reconstruction
- review and human control
- evaluator independence
- privacy and provenance

### Supporting subsystems

- resource-aware routing
- token and context controls
- energy and runtime telemetry
- workspace and presentation surfaces
- model and provider adapters

### Adjacent applications

- AI-assisted software work
- environmental and edge workflows
- external agent frameworks and automation tools

Adjacent applications may exercise the governance kernel; they do not redefine
the project's identity or inherit authority from compatibility alone. The
[external runtime integration doctrine](../integrations/integration_doctrine.md)
defines the replaceable, subordinate integration posture.

## Enduring Principles

1. **Local control and operator sovereignty.** Local state and explicit operator
   choices remain primary.
2. **Evidence before claims.** Artifacts and observations support bounded claims,
   not certification by implication.
3. **Explicit authority.** Recommendation, review, authorization, capability
   possession, and execution permission are distinct.
4. **Separation of governance functions.** Observation, recommendation,
   authorization, execution, and evaluation do not silently confer authority on
   one another.
5. **Fail-closed uncertainty.** Missing, stale, ambiguous, or contradictory
   evidence remains visible and does not become optimistic permission.
6. **Privacy-bounded, reviewable artifacts.** Persistent evidence should be
   inspectable without carrying unnecessary private content.
7. **Human authority at consequential boundaries.** System or supervisor verdicts
   do not replace the identified human authorization required for consequential
   effects.

## Current Architectural Pillars

- **Governed decision formation:** deterministic inputs, route choice, cessation
  points, worker results, and evidence linkage. See the
  [current governed run flow](governed_run_flow.md).
- **Identity, authorization, and capability lifecycle:** request-bound human
  authorization evidence and atomic capability state in a separate lane. See
  the [human authorization lifecycle](human_authorization_lifecycle.md).
- **Effect definition and mediated execution:** exact-effect contracts,
  reservation, capability binding, and constrained mutation foundations whose
  orchestration edge remains disconnected. See
  [mediated execution foundations](mediated_execution_foundations.md).
- **Evidence, observability, and review:** durable events, projections, and
  traceable review artifacts. See
  [reviewer traceability](../operations/reviewer-traceability.md).
- **Evaluation boundaries:** reproducible fixtures and static handoffs preserve
  evaluator independence without making evaluation or scoring an internal
  approval authority. See the
  [research question](../research/triagecore_research_question.md).
- **Workspace and coordination control:** local work state, bounded handoffs,
  review surfaces, and explicit flow boundaries. See
  [fluidic signal paths](fluidic_signal_paths.md).

## Integration Posture

The [current system architecture](current_system_architecture.md) is authoritative
for integration status. This compact identity-level summary preserves its
distinctions:

| Status | Identity-level example | Boundary |
| --- | --- | --- |
| Current and integrated | Governed `tc run` path, local evidence, and review projections | Route selection, execution, and evidence are staged; this is not an end-to-end authorization pipeline |
| Current but optional | Bounded Qwen Cloud route for external-safe packets | Disabled, unavailable, or ineligible routes terminate without implicit cloud authority |
| Implemented separate lane | Human authorization receipts and atomic capability lifecycle | Not consumed by current `tc run` |
| Implemented but disconnected | Mediated effects, request reservation, capability binding, and constrained replacement | No current orchestration edge composes authority, claiming, execution, finalization, and joined evidence |
| Future and disconnected | TriageDesk action/executor bridge and other separately governed execution links | Documentation or design direction grants no implementation authority |
| Conceptual or external | Meta-harnesses, bounded agents, and independent evaluators | Static exports do not prove delivery, execution, evaluation, or result production |

## Resource-Aware Routing

Resource-aware routing remains a current governed decision-and-evidence
subsystem. It makes privacy, local capability, backend choice, quality, token,
latency, and energy considerations inspectable without making resource selection
the whole TriageCore identity. The governed runtime boundary and its non-claims
are detailed in the [current governed run flow](governed_run_flow.md).

## Non-Claims and Scope Test

TriageCore does not claim that:

- it solves model alignment or proves that a model, agent, or provider is safe;
- its policy checks constitute a complete sandbox or containment system;
- a signature, manifest, review verdict, or valid artifact proves approval,
  correctness, or safe execution;
- authorization, capability claiming, mediated effects, and execution are
  currently composed end to end;
- external compatibility grants an external runtime TriageCore authority;
- a passing fixture, handoff, or evaluation certifies production safety; or
- review metadata is universally blocking or equivalent to human authorization.

Public and submission wording should remain within the
[claim boundaries](../submission/claim_boundaries.md). Candidate identity and
governance work remains backlog-only unless separately approved in the
[current backlog](../current_backlog.md).

Every proposed addition should answer:

`Does this strengthen the evidence-bound governance kernel, or is it merely an interesting adjacent capability?`

## Uncertainty and Limitations

- The evidence pin records repository state at one commit. Later changes can
  invalidate this summary; re-verify integration call sites, contracts, tests,
  and terminology when the pin changes.
- Repository integration is not evidence of host deployment, network topology,
  operational configuration, evaluator activity, or operator practice.
- This identity document cannot certify safety, correctness, compliance,
  containment, or effective human control.
- Component-specific documents and tests remain authoritative for exact
  ordering, schemas, reason codes, platform constraints, and non-claims. Where
  this summary conflicts with the
  [current system architecture](current_system_architecture.md), the detailed
  architecture and its verified sources control.
