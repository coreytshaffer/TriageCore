# AMD Cloud Demo Workflow

This workflow is the AMD-specific operator path for presenting TriageCore as a governed cloud-agent control plane.

## Purpose

Use this walkthrough to show that TriageCore does not treat cloud GPU inference as the default answer to every task.

Instead, it:

- structures the incoming task
- performs local privacy and risk classification first
- escalates only when the workload justifies cloud execution
- validates the returned output
- preserves a human approval gate
- records route and approval evidence in the ledger

## Demo Path

1. Show the input task from `docs/examples/taskpacket_amd_cloud_escalation.json`.
2. Explain why the task is a bad fit for a small local route.
3. Show the allowed AMD escalation target in `docs/examples/model_route_manifest_amd_cloud.json`.
4. Walk through the route decision: local preflight passes, AMD escalation is allowed, and heavier inference is selected.
5. Show the post-inference validation and approval boundary using `docs/examples/ledger_event_amd_cloud_route_audit.json`.
6. Close by explaining that the ledger preserves a reviewable record of the cloud decision.

## Talk Track

A concise talk track:

- TriageCore starts with governance, not with raw model power.
- Sensitive or small tasks can stay local.
- Heavier tasks can escalate onto AMD cloud GPUs when policy allows it.
- Cloud output is still validated before acceptance.
- Human review remains the decision boundary.
- The ledger records who approved the route and what backend was used.

## What To Point Out

- AMD cloud is an explicit route target, not just hosting.
- The escalation decision happens after local checks.
- Validation and approval happen after cloud inference, not before.
- The evidence trail is part of the system, not an after-demo explanation.

## Claim Boundaries

Do not imply that this walkthrough requires a live AMD credential or a production-complete cloud deployment. The point of the demo is to show governed escalation logic and auditable workflow structure.