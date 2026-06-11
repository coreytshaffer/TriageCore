# CR-017: Public Legibility Pass

## Status
Implemented

## Scope

- Compress the README opening so a first-time reviewer can understand TriageCore from the first screen.
- Add clear sections for what the project does today, why it matters, and how to review it quickly.
- Add a 5-minute reviewer path using existing safe commands only.
- Add an in-repo public evidence example that demonstrates the audit trail without leaking prompt or task data.
- Preserve links to deeper methodology, benchmark, evidence-schema, submission, and verification docs rather than removing them.

## Implementation Authority

Implemented in repo.

## Description

This change improves public legibility without changing routing, privacy, benchmark, or backend behavior. The README now front-loads plain-English explanation, a quick reviewer path, current capability boundaries, and proof markers that are visible from repository contents rather than relying on stars, forks, or generic activity signals. A canonical public evidence example is also added so reviewers can see a privacy-safe route audit record without reading raw prompt or task data.

## Acceptance Criteria

- [x] A new visitor can answer "What is TriageCore?" from the first screen of the README.
- [x] A reviewer can run or inspect one demo path without reading the whole repo.
- [x] README distinguishes between current capabilities, planned capabilities, and research framing.
- [x] Existing docs remain linked rather than deleted.
- [x] A canonical public evidence example exists and does not leak prompts or task data.
