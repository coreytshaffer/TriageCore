# CR-015: Hackathon Demo Scenario

## Status
Implemented

## Scope
- Add `docs/workflows/hackathon_demo.md` as a documentation-first operator walkthrough.
- Add a short README section linking to the hackathon demo workflow.
- Reuse existing commands for doctor, preflight, handoff, and route audit inspection.
- Keep the main demo centered on TriageCore local-first operation with optional Qwen Cloud escalation framing.

## Implementation Authority
Implemented in repo.

## Description
This change adds a bounded hackathon demo workflow that can be run with existing commands and without live Qwen Cloud credentials. The demo explains TriageCore as a local-first control harness, shows reviewable preflight and handoff artifacts, demonstrates privacy-safe route audit inspection, and frames Qwen Cloud as an optional external-safe escalation path rather than the default runtime.

## Acceptance Criteria
- [x] `docs/workflows/hackathon_demo.md` exists.
- [x] The demo uses existing commands only.
- [x] The walkthrough includes purpose, prerequisites, exact commands, expected outputs, privacy/local-first explanation, optional Qwen explanation, route audit inspection, 3-minute talk track, claim boundaries, and troubleshooting.
- [x] README links to the demo workflow.
- [x] The demo explicitly supports the TriageCore/Qwen primary slot, safer AI-assisted SDLC secondary framing, and Clear Lake Watch future extension.
