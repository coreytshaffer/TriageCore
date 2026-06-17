# CR-039: AMD Cloud Agent Routing Demo

## Status
Implemented

## Scope
- Add an AMD-specific submission overview that reframes TriageCore around governed cloud GPU agent execution.
- Add an AMD-specific demo walkthrough that shows local preflight, cloud escalation, validation, and human approval.
- Add example artifacts for AMD cloud route manifest, TaskPacket escalation, and ledger evidence.
- Keep the existing Qwen submission path intact instead of overwriting it.

## Implementation Authority
Documentation-first repo slice.

## Description
This change creates a second hackathon framing for TriageCore that is centered on AMD cloud GPU routing rather than Qwen-specific backend branding. The AMD version presents TriageCore as a governed control plane for AI agents running across local and AMD cloud infrastructure. The focus is on when cloud escalation is allowed, how it is bounded, and what evidence is preserved before and after heavier inference runs.

## Acceptance Criteria
- [x] `docs/submission/amd_cloud_submission_overview.md` exists and includes project story, technical architecture, AMD fit, and claim boundaries.
- [x] `docs/workflows/amd_cloud_demo.md` exists and shows a bounded end-to-end AMD escalation path.
- [x] `docs/examples/model_route_manifest_amd_cloud.json` exists and represents AMD cloud as an explicit escalation target.
- [x] `docs/examples/taskpacket_amd_cloud_escalation.json` exists and can justify the AMD route.
- [x] `docs/examples/ledger_event_amd_cloud_route_audit.json` exists and records route, backend, validation, and approval metadata.
- [x] Submission docs preserve the existing Qwen bundle instead of silently replacing it.