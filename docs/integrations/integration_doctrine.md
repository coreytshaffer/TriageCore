# External Runtime Integration Doctrine

## Status

Documentation-only doctrine for CR-043.

## Purpose

Define how TriageCore works with external runtimes, gateways, automation tools,
 and model providers without inheriting their identity, permission model, or
 roadmap.

## Core Doctrine

TriageCore works with external tools without becoming them.

External runtimes may request capability, but only TriageCore grants
 authority.

No external tool permission is TriageCore authorization.

## Compatibility Without Capture

TriageCore integrations must be replaceable. If removing an external runtime
 breaks TriageCore's core policy, approval, provenance, or audit model, the
 integration has crossed from compatibility into capture.

## Stable Internal Contracts

External integrations should map into TriageCore-native contracts rather than
 redefining the core around third-party abstractions.

Canonical objects:

- `TaskPacket`
- `RouteDecision`
- `CapabilityRequest`
- `ApprovalRecord`
- `ExecutionReceipt`
- `ProvenanceRecord`
- `AuditLedgerEvent`

## Integration Layers

### Inbound adapters

Inbound adapters convert external events into TriageCore `TaskPacket` objects.
They translate; they do not approve, route, or mutate.

### Capability drivers

Capability drivers execute already-approved actions against external systems.
They act only on approved `CapabilityRequest` objects.

### Contract tests

Every integration should prove the same boundaries:

- can normalize an external request into a `TaskPacket`
- can describe requested capabilities explicitly
- cannot mutate state without approval
- cannot bypass privacy or route policy
- can emit provenance and audit evidence
- can be disabled cleanly without breaking the core

## Integration Maturity Levels

| Level | Meaning |
| :--- | :--- |
| 0 | Documented boundary only |
| 1 | Read-only adapter |
| 2 | Draft-only mode |
| 3 | Bounded approved mutation |
| 4 | Scheduled or repeated checks under strict policy |
| 5 | Autonomous delegated authority, normally prohibited |

New external runtime work should begin at Level 0 or Level 1.

## CR-043 Scope Boundary

Included in CR-043:

- compatibility without capture
- subordinate external runtime posture
- adapter or driver or contract-test model
- OpenClaw as the first documented example
- maturity levels for future integrations

Excluded from CR-043:

- installing OpenClaw
- running OpenClaw
- adapter implementation
- shell execution pathways
- plugin or skill loading
- network exposure
- new authority surfaces
