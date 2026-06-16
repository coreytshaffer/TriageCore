# CR-031: Runtime Integrity and Model Provenance Policy

## Status

Implemented

## Scope

Documentation only.

This change defines:

- runtime integrity expectations for model routes
- model provenance requirements
- local/cloud boundary reporting expectations
- future CLI expectations for route or model integrity checks
- non-goals for convenience wrappers, aliases, and mutable tags

This change does not modify routing, backends, signatures, verification,
ledger behavior, or runtime CLI behavior.

## Description

TriageCore already enforces privacy routing, signed audit evidence, and local
identity policy. The next missing trust boundary is model-route integrity.

A route is not trustworthy merely because it returns output. TriageCore should
be able to answer:

- what backend actually ran
- what exact model or artifact was selected
- where that model came from
- whether the runtime stayed inside the intended local/cloud boundary
- whether a convenience wrapper, alias, or mutable tag obscured the real source

CR-031 establishes the documentation-first integrity invariant so later runtime
work such as `tc model check` or route manifests can implement the right trust
model instead of guessing at it.

## Acceptance Criteria

- [x] Defines runtime integrity expectations for model routes.
- [x] Defines required provenance fields such as backend, exact model identity,
  source, artifact integrity, quantization, template behavior, and boundary
  metadata.
- [x] States that aliases, wrappers, and mutable tags are not trust
  boundaries.
- [x] Defines future CLI expectations for integrity validation.
- [x] Keeps CR-031 documentation-only.
- [x] Does not alter routing, signing, verification, revocation, or ledger
  behavior.

## Validation

```powershell
python -m pytest -q
tc identity check
tc audit --privacy-invariants
tc audit --verify-signatures
```
