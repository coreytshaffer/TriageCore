# AMD Cloud Submission Overview

## Project Title

TriageCore: Governed AI Agents on AMD Cloud

## Short Description

TriageCore is a privacy-first control plane for AI agents that routes tasks across local and AMD cloud GPU infrastructure with risk checks, approval gates, revocable permissions, and auditable task ledgers.

## Project Story

Many agent demos focus on how powerful a model becomes once it already has compute, tools, and context. TriageCore focuses on the control problem before that point.

A user starts with a messy task. TriageCore converts that request into a structured `TaskPacket`, performs local privacy and risk checks, and then decides whether the task should stay local, use a deterministic tool, or escalate to an AMD cloud GPU path for heavier inference.

That means AMD cloud compute is not just a deployment detail. It becomes a governed capability inside the system. TriageCore keeps smaller, sensitive, or deterministic work local whenever possible, while using AMD-backed cloud inference when a workload needs more model capacity, broader context handling, or faster high-compute execution.

## Technical Architecture

```text
User Task
    |
    v
TaskPacket Builder
    |
    v
Privacy + Risk Preflight
    |
    +--> Local model route
    |
    +--> Deterministic tool route
    |
    +--> AMD cloud GPU escalation route
              |
              v
      Heavy inference on approved AMD backend
              |
              v
      Output validation + policy checks
              |
              v
      Human approval / rejection
              |
              v
      Append-only audit ledger
```

## Demo Control Flow

1. User submits a messy task.
2. TriageCore converts it into a structured `TaskPacket`.
3. Local preflight classifies privacy, sensitivity, and execution risk.
4. Router selects local execution, deterministic tooling, or AMD cloud GPU escalation.
5. The AMD route performs the heavier inference workload.
6. TriageCore validates the returned output before it can be accepted.
7. Human review approves or rejects the result.
8. The ledger records route, backend, validation outcome, and approval metadata.

## Why This Fits AMD

The AMD hackathon emphasizes AI agents and high-performance AI applications built on AMD cloud infrastructure. TriageCore fits that framing best when AMD compute is part of the actual control logic instead of an afterthought.

The AMD version of TriageCore highlights:

- cloud GPU routing as a first-class route decision
- performance-aware escalation for harder workloads
- revocable permissions before external execution
- post-inference validation before acceptance
- auditable evidence for route, backend, and approval state

## Practical Business Value

Teams want stronger AI capabilities without losing control over data movement, review boundaries, or accountability. TriageCore addresses that operational gap. It helps organizations decide when a task can use high-performance cloud inference and when it must stay local, then records what happened in a reviewable ledger.

That makes the system relevant for regulated engineering workflows, privacy-conscious development teams, and any setting where powerful agent execution needs governance instead of blind trust.

## AMD Routing Policy Evidence

The AMD cloud path is not only documented. CR-040 adds executable
routing-policy evidence showing when tasks remain local, use deterministic
tools, require approval for AMD cloud escalation, or are blocked from cloud
egress due to privacy policy.

That matters for judges because it turns the AMD story from a slide-level
architecture claim into test-backed governance behavior. Task metadata and
route manifests drive the decision, while approval gates and audit expectations
keep cloud escalation from becoming an unbounded default.

## Claim Boundaries

This AMD framing should be presented as a governed demo path, not as proof that every production cloud-safety concern is fully solved.

Safe claims:

- TriageCore can represent AMD cloud as an explicit escalation target.
- TriageCore can preserve preflight, validation, and approval boundaries around a cloud route.
- The demo shows governance and auditability around high-performance agent execution.

Avoid these claims:

- that all cloud routes are production hardened
- that every AMD path is live during the walkthrough
- that cloud escalation bypasses privacy review or human approval
