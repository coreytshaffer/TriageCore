# Hackathon Submission Bundle

This folder is the judge-facing submission bundle for TriageCore.

Use it when you want the fastest path through the project without reading the full repository documentation first.

## Reading Order

1. [qwen_optional_reviewer_video_runbook.md](qwen_optional_reviewer_video_runbook.md)
2. [hackathon_submission_overview.md](hackathon_submission_overview.md)
3. [judge_quickstart.md](judge_quickstart.md)
4. [track_mapping.md](track_mapping.md)
5. [claim_boundaries.md](claim_boundaries.md)
6. [public_evidence_example.md](public_evidence_example.md)
7. [public_launch_metadata_pack.md](public_launch_metadata_pack.md)
8. [final_validation_evidence_redacted.md](final_validation_evidence_redacted.md)

## Fastest Judge Path

If you only have a few minutes:

1. Watch the linked demo video or read the video runbook.
2. Read the overview.
3. Run the quickstart commands.
   For redacted final validation excerpts, see [final_validation_evidence_redacted.md](final_validation_evidence_redacted.md).
4. Check the public evidence example.
5. Check the track mapping so the primary demo, supporting framing, and future extension stay distinct.
6. Use the public launch metadata pack when preparing GitHub About text, topics, release notes, and the first public tag.

## Related Workflow

The operator-facing walkthrough is here:

- [hackathon_demo.md](../workflows/hackathon_demo.md)

That document is the live demo script. This `docs/submission/` bundle is the judge packet.

## Alternate Framing Draft

- [amd_cloud_submission_overview.md](amd_cloud_submission_overview.md)

This is a separate AMD-oriented framing draft. It does not replace the existing Qwen-centered judge path.

### AMD routing policy evidence

TriageCore's AMD cloud path is not only documented. CR-040 adds executable
routing-policy evidence showing when tasks remain local, use deterministic
tools, require approval for AMD cloud escalation, or are blocked from cloud
egress due to privacy policy.

This keeps AMD cloud acceleration inside an inspectable governance layer: task
metadata and route manifests drive the decision, while approval gates and audit
expectations prevent cloud escalation from becoming an unbounded default.
