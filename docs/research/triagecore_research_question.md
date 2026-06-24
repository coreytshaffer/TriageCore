# TriageCore Research Question

## Abstract

TriageCore is a local-first control-plane research harness for studying whether external workflow controls can detect and reduce unsafe or unauthorized behavior in tool-using AI systems. The project does not claim to solve model alignment, sandboxing, or agent security. Its narrower research value is that privacy gates, route authorization, runtime provenance, cryptographic identity, audit invariants, and human approval points can be made explicit enough to test.

The next empirical phase should ask whether these controls still hold when task inputs, agent identities, route metadata, audit records, and model/backend provenance are ambiguous, malformed, stale, or adversarially framed. That makes TriageCore less like a product wrapper and more like a reproducible safety evaluation workbench.

## Research question

Can a lightweight external control plane detect and reduce unsafe LLM-agent behavior without relying on the model's self-report?

For TriageCore, unsafe behavior means bounded workflow failures such as:

- sensitive content leaking into persistent artifacts
- cloud or external routing when local-only policy applies
- revoked, spoofed, or ambiguous agent identity being accepted as authority
- model/backend provenance being missing, mutable, or treated as a trust anchor without evidence
- audit records being missing, malformed, unsigned, unverifiable, or inconsistent with expected workflow state
- human approval gates being bypassed for actions that policy says require review

## Threat model

This research framing assumes a controlled local evaluation environment, not a hostile production deployment. The adversary can be represented by toy fixtures, malformed records, prompt-injected task text, simulated agent proposals, or intentionally inconsistent metadata.

The control plane should be tested against these pressure cases:

- **Privacy pressure:** task or model output contains sensitive strings that should never persist in ledger events, route audits, review bundles, or generated reports.
- **Routing pressure:** task metadata says local-only, but a proposed route attempts cloud escalation or external runtime use.
- **Identity pressure:** an agent identity is missing, revoked, stale, spoofed, or inconsistent with the action it proposes.
- **Provenance pressure:** model/backend identity is recorded only as a mutable alias, missing manifest field, or ambiguous route label.
- **Audit pressure:** an event is missing required fields, unsigned where a signature is expected, timestamp-shifted, or inconsistent with neighboring workflow evidence.
- **Human-gate pressure:** a proposed action should require explicit operator review, but the workflow attempts to proceed silently.

Out of scope for this framing:

- proving containment against arbitrary code execution
- offensive cyber capability development
- live attacks against third-party systems
- model internals or mechanistic interpretability claims
- claims that local models, cloud models, or any particular vendor path are inherently safe
- granting untrusted external runtimes authority by default

## Current control surfaces

TriageCore already has several surfaces that can support empirical evaluation:

- Task Envelope and Admission Evidence contracts for structured task and review boundaries
- persistent-artifact privacy invariants for raw-content leakage checks
- route-audit events for workflow-level routing evidence
- local-only and external-safe routing policy language
- model route manifest checks and warning-only route comparison
- cryptographic agent identity, signing, revocation, and signed smoke-path evidence
- external runtime manifest and admission boundaries
- review bundle dry-run artifacts with no execution authority

The next research step is to turn these controls into reproducible fixtures and measurable outcomes.

## Claims TriageCore can make

TriageCore can make narrow, testable claims:

- A fixture either does or does not leak forbidden raw-content fields into persistent artifacts.
- A route proposal either does or does not violate local-only or external-safe policy metadata.
- An identity is either present, authorized, revoked, malformed, or insufficient for a proposed action.
- A model/backend route record either includes the required provenance fields or leaves ambiguity visible.
- An audit or review artifact either preserves required fields and boundaries or fails validation.
- A high-risk proposal either requires human approval or remains blocked/inert.

These claims are useful because they are external to the model and can be checked deterministically.

## Claims TriageCore should not make

TriageCore should not claim that:

- the model is aligned
- the runtime is a complete sandbox
- policy checks replace secure isolation
- a passing fixture proves production safety
- signed metadata proves the underlying action was safe
- a manifest proves a backend is trustworthy
- human review gates remove the need for operator judgment
- external runtime compatibility grants external runtime authority

The project is strongest when it treats each control as evidence, not certification.

## Fellowship-aligned framing

This framing positions TriageCore as empirical AI safety and security research rather than general governance prose.

- **AI control:** test whether external systems constrain unsafe proposals when model behavior is unreliable, adversarially instructed, or ambiguous.
- **Externalized oversight:** move critical review state outside the model prompt into policy code, fixtures, and auditable artifacts.
- **Agent identity:** evaluate whether identity, revocation, and signing metadata prevent ambiguous or unauthorized actors from being treated as trusted operators.
- **Provenance:** make model/backend/runtime identity visible enough that mutable aliases and incomplete manifests are not silently accepted as trust anchors.
- **Auditable intervention points:** create observable places where the workflow blocks, escalates, logs, or requires human approval.

## Next empirical slices

The next backlog should stay small and sequential:

1. **Safety eval dataset v0:** JSONL fixtures for privacy, route, identity, provenance, audit, and human-gate boundary cases, with deterministic expected outcomes.
2. **Evaluator CLI:** one command that runs the fixture suite and reports pass/fail counts plus boundary-specific violation counts.
3. **Adversarial control-plane tests:** controlled tests for spoofed identity, prompt-injected routing, alias-only provenance, local-only escalation, unsigned records, and forbidden persistent content.
4. **Toy audit tampering eval:** sandboxed cases for missing events, edited timestamps, changed provenance, unsigned route decisions, fake agent IDs, and stale/revoked keys.
5. **Behavioral route diff harness:** optional later comparison of model/backend proposals while keeping the external control-plane checks deterministic.
6. **Technical report v0:** a short paper-style report documenting motivation, threat model, method, results, limitations, and reproducibility instructions.

## Reproducibility standard

Each empirical slice should define:

- the fixture path
- the command to run
- expected deterministic output
- what counts as pass, fail, blocked, or escalated
- what the result does and does not prove
- whether any ledger, network, backend, or filesystem writes are allowed

If a proposed slice cannot satisfy those conditions, it should remain a future idea rather than entering the active implementation queue.