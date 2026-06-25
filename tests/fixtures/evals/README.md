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

- CR-078 should add a narrow validator for required fields and deterministic labels.
- CR-079 can add a small evaluator CLI only after the schema is stable.
