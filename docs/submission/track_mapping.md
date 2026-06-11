# Track Mapping

This document keeps the three hackathon tracks distinct.

## Implemented Primary Demo

Track: TriageCore local-first plus optional Qwen Cloud escalation.

Use this when judges ask:

- what is the main implemented workflow
- where Qwen appears in the system
- how cloud escalation is bounded

What to say:

- TriageCore is the local-first control layer.
- Qwen Cloud is an optional backend path, not the default execution model.
- The Qwen path only exists for external-safe packets and does not override local-only privacy enforcement.

What not to blur:

- do not present Qwen as always-on cloud orchestration
- do not present the demo as a live-cloud requirement

## Implemented Supporting Framing

Track: safer AI-assisted SDLC.

Use this when judges ask:

- why this matters beyond one backend adapter
- how the workflow is safer than a generic prompt-to-agent loop

What to say:

- preflight artifacts create scope before changes
- route audit records provide inspectable metadata
- local-only work fails closed instead of silently escaping to remote execution
- operator review remains explicit

What not to blur:

- do not present the framing as a separate shipped platform
- do not imply that documentation alone proves enterprise governance completeness

## Future Extension

Track: environmental edge workflows such as Clear Lake Watch.

Use this when judges ask:

- where this could go next
- why local-first control matters outside normal coding workflows

What to say:

- environmental and field workflows often need offline-resilient local operation
- TriageCore's local-first, bounded-escalation pattern fits that shape well
- Clear Lake Watch is a future extension path for this control model

What not to blur:

- do not claim that Clear Lake Watch integration is already implemented here
- do not claim that current demo outputs validate environmental deployment outcomes

## One-Sentence Separation

Use this if time is short:

- implemented primary demo: TriageCore plus optional Qwen Cloud escalation
- implemented supporting framing: safer AI-assisted SDLC through bounded review and auditability
- future extension: environmental edge orchestration such as Clear Lake Watch
