# CR-076: TriageCore Research Framing Doc

## Status
Implemented

## Scope

- Add a docs-only research framing document at `docs/research/triagecore_research_question.md`.
- Define the empirical research question for TriageCore as an external control-plane evaluation harness.
- Document the threat model, current control surfaces, narrow claims, non-claims, fellowship-aligned framing, and next empirical slices.
- Update backlog and changelog entries for this slice.

## Non-Goals

- No evaluator CLI
- No new fixtures
- No tests
- No runtime behavior changes
- No ledger writes
- No network calls
- No external model/backend calls
- No README changes
- No PR dependency on the reviewer README branch

## Description

This slice reframes the next TriageCore phase around a concrete empirical AI safety/security research question: whether a lightweight external control plane can detect and reduce unsafe LLM-agent workflow behavior without relying on the model's self-report. The document keeps the claim narrow and testable, then sequences future eval work into small slices such as fixture datasets, evaluator CLI output, adversarial control-plane tests, toy audit tampering cases, behavioral route diffing, and a paper-style technical report.

## Acceptance Criteria

- [x] Research framing doc exists at `docs/research/triagecore_research_question.md`.
- [x] Research question is stated as a falsifiable control-plane evaluation question.
- [x] Threat model is explicit and bounded to controlled local evaluation.
- [x] Claims and non-claims are separated.
- [x] Next empirical slices are listed without implementing them.
- [x] Backlog and change log updated.
- [x] No code, CLI, fixture, or runtime behavior changes.
- [x] `git diff --check` is clean.