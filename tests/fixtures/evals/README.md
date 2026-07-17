# Eval Fixtures

This directory holds deterministic starter fixtures for the safety-boundary evaluation track introduced by CR-077.

## Current contents

- `safety_boundaries_v0.jsonl`: toy-scale JSONL cases covering privacy, routing, identity, provenance, audit, and human approval boundaries

## Intent

These fixtures exist to define what a future evaluator will consume. They do not add runtime behavior by themselves.

## Constraints

- Keep fixtures small and hand-readable.
- Prefer one representative case per boundary family before adding variants.
- Do not add live model prompts, network dependencies, or filesystem side effects.
- Treat these files as research infrastructure, not production safety certification.

## Expected follow-on

- CR-121 added a narrow validator for required fields and deterministic labels.
- CR-122 exposed that validator through `tc eval validate-fixtures --input <path>`.
- CR-123 defined the file-based handoff boundary to the external evaluator suite.
- Future TriageCore slices may package or validate the handoff bundle, but scoring remains external to TriageCore.
