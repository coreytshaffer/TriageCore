# Runtime Integrity and Model Provenance Policy

## Principle

Integrity before convenience.

A model route is not trustworthy unless TriageCore can identify what actually
ran, where it came from, how it was templated, and whether it stayed inside the
intended boundary.

This document defines the policy baseline for runtime integrity and model
provenance. It is documentation only and does not change current runtime
behavior.

## Purpose

TriageCore supports local-first routing, cloud escalation boundaries, audit
records, and identity-backed control-plane evidence. Those controls are weaker
than they appear if the runtime cannot answer what backend and model artifact
actually executed.

This policy exists to prevent convenience adapters, mutable tags, registry
aliases, and wrapper defaults from becoming implicit trust boundaries.

## Runtime Integrity Invariant

A route should not be considered integrity-valid unless TriageCore can expose,
at minimum:

- backend type
- concrete runtime endpoint or local execution boundary
- exact model identity
- model source or distribution channel
- artifact integrity metadata
- quantization or build variant
- prompt or template behavior in effect
- local/cloud boundary classification
- operator-visible provenance and failure status

If these fields are unknown, inferred only loosely, or hidden by a wrapper,
TriageCore should treat the route as integrity-incomplete rather than silently
trusted.

## Required Provenance Fields

### Backend

TriageCore should record the actual backend that executed the route, not only a
friendly label.

Examples:

- `ollama`
- `lmstudio`
- `qwen_cloud`
- future direct Hugging Face runtime

If a wrapper or adapter sits between TriageCore and the real engine, the
wrapper name alone is insufficient.

### Exact Model Identity

TriageCore should prefer immutable, specific model identifiers over mutable or
human-friendly references.

Examples of stronger identity:

- exact model name
- exact tag or digest
- exact repository or artifact name
- explicit version or snapshot identifier

Examples of weaker identity that should not stand alone:

- `latest`
- `default`
- generic alias names
- wrapper-side nicknames without underlying artifact identity

### Source and Distribution

TriageCore should be able to describe where the model came from.

Examples:

- local imported artifact
- Ollama pull source
- Hugging Face repository
- cloud vendor model identifier
- internally packaged runtime bundle

Source matters because two routes can share a display name while deriving from
different artifacts or trust boundaries.

### Artifact Integrity

Future runtime integrity work should expose whether the model artifact is backed
by any of the following:

- digest or hash
- signed manifest
- pinned snapshot
- operator-approved local registry entry

If no integrity metadata exists, that absence should be surfaced explicitly.

### Quantization and Build Variant

The route should expose the build variant that materially changes behavior or
performance.

Examples:

- quantization family
- parameter scale when available
- GGUF or other artifact format
- vendor or packager variant

This helps separate "same model family" from "same actual runtime artifact."

### Template and Prompt Behavior

TriageCore should be able to describe whether the runtime injects or mutates
prompt structure through:

- backend-side chat templates
- wrapper-side system prompts
- model-specific formatting transforms
- hidden defaults that alter the effective request

This does not require exposing sensitive task content. It requires exposing the
mechanism and identity of the template behavior.

### Boundary Metadata

Every route should remain explicit about whether execution is:

- local
- cloud
- hybrid
- unknown

Unknown boundary state should fail the integrity policy for trust-sensitive
workflows.

## Convenience Adapter Policy

Convenience support is allowed. Implicit trust is not.

This means wrappers such as Ollama adapters may remain fully supported, but
they should not be treated as sufficient provenance on their own. A wrapper is
an access path, not the final identity of what ran.

The following must not become implicit trust boundaries:

- mutable tags like `latest`
- registry aliases without underlying artifact identity
- backend defaults that select an artifact silently
- wrapper-generated template behavior that is not disclosed

## Historical and Audit Expectations

Future route or model integrity records should help the operator answer:

- which backend actually ran
- which exact model or artifact was selected
- whether the route stayed in the intended local/cloud class
- whether provenance was complete, partial, or missing

This policy does not require retroactively rewriting old ledger entries. It
defines what future integrity-aware routing evidence should make visible.

## Future CLI Expectations

Future runtime work may add commands such as:

- `tc model check`
- `tc route check`
- route manifest inspection
- backend provenance summaries

Those future commands should:

- surface provenance completeness clearly
- distinguish immutable identity from convenience labels
- expose integrity failures without printing sensitive task content
- treat missing provenance as a policy problem, not a cosmetic warning only

Those future commands should not:

- silently bless wrapper defaults as trustworthy provenance
- treat `latest` as a stable identity
- hide cloud/local ambiguity
- rewrite ledger history to pretend provenance existed when it did not

## License and Governance Expectations

Where practical, future provenance checks should also surface:

- declared model license
- source repository or vendor
- operator approval state for use in TriageCore

This is especially important when routes are candidates for product demos,
research outputs, or cloud escalation policy.

## Failure Semantics

When provenance is incomplete, TriageCore should prefer one of the following
future behaviors instead of silently trusting the route:

- mark route integrity as incomplete
- restrict route use for sensitive or evidence-bearing workflows
- require explicit operator acceptance
- fail closed when the boundary or source cannot be established

The correct runtime behavior belongs to a later CR. This document only defines
the trust expectation.

## Non-Goals

This policy does not:

- implement `tc model check`
- add runtime manifests yet
- redesign the router
- ban convenience adapters
- require every model source to have perfect cryptographic provenance today
- change current routing or backend behavior

## Implementation Guidance

Before any runtime CR implements integrity checks, it should answer at least:

1. What fields are mandatory for a route to be integrity-valid?
2. Which fields are backend-specific but still required to normalize?
3. How are mutable tags represented and downgraded in trust?
4. How are local wrappers distinguished from actual artifact identity?
5. What minimum evidence is required before a cloud route can be presented as
   trustworthy?

Until those answers are implemented, TriageCore should not imply that backend
selection alone proves runtime integrity.
