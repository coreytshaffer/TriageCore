# CR-032: Model Route Manifest Schema

## Status

Implemented

## Scope

Documentation only.

This change defines:

- a canonical model-route manifest shape
- required versus optional provenance fields
- example manifests for local, cloud, and invalid routes
- failure cases for incomplete or alias-only provenance
- the artifact contract that future runtime checks must validate

This change does not modify routing, backends, signatures, verification,
ledger behavior, or runtime CLI behavior.

## Description

CR-031 defined the policy invariant for runtime integrity and model provenance.
CR-032 defines the concrete artifact shape that can express that invariant.

The goal is to pin down what a route manifest must contain before any runtime
command such as `tc model check` is implemented. This avoids encoding the trust
model in code before the expected manifest fields and failure cases are
explicitly documented.

## Acceptance Criteria

- [x] Defines a canonical model-route manifest schema.
- [x] Distinguishes required and optional fields.
- [x] Covers local and cloud route boundary metadata.
- [x] Covers backend, model identity, source, artifact integrity,
  quantization/build, and template behavior fields.
- [x] Provides concrete manifest examples.
- [x] Provides at least one invalid example or failure case.
- [x] Keeps CR-032 documentation-only.
- [x] Does not alter runtime routing, signing, verification, or ledger
  behavior.

## Validation

```powershell
python -m pytest -q
tc identity check
tc audit --privacy-invariants
tc audit --verify-signatures
```
