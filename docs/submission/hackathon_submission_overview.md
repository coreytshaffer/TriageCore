# Hackathon Submission Overview

## Project

TriageCore is a local-first developer-agent control harness.

Its job is not to replace operator judgment. Its job is to keep AI-assisted work bounded, reviewable, privacy-aware, and auditable before optional cloud escalation is even considered.

## Fastest Judge Path

Read these in order:

1. [judge_quickstart.md](judge_quickstart.md)
2. [track_mapping.md](track_mapping.md)
3. [claim_boundaries.md](claim_boundaries.md)

## What Problem This Addresses

Many AI coding workflows still blur together:

- local vs cloud execution
- safe review vs hidden autonomy
- privacy-safe metadata vs raw task leakage

TriageCore separates those concerns with explicit preflight artifacts, local-first control, route audit inspection, and bounded optional escalation.

## Implemented Primary Demo

Primary demo: TriageCore local-first orchestration with optional Qwen Cloud escalation.

What is implemented today:

- local-first operator workflow
- privacy scanning and fail-closed local-only enforcement
- preflight and handoff artifact generation
- privacy-safe route audit inspection
- a narrow Qwen Cloud adapter for external-safe packets only

This is the main hackathon story.

## Implemented Supporting Framing

Supporting framing: safer AI-assisted SDLC.

What this means in practice:

- reviewable artifacts before implementation work
- explicit boundaries around local-only and external-safe work
- route audit evidence without raw prompt/data exposure
- human review preserved as a first-class part of the workflow

This is a framing layer around the same implemented system, not a separate product.

## Future Extension

Future extension: Clear Lake Watch and environmental-edge workflows.

What we mean by that:

- the same local-first control pattern can support environmental monitoring and edge-resilient software
- offline-resilient local operation matters in field and constrained settings
- optional cloud help should remain bounded, explicit, and secondary

This future extension is not presented as a finished runtime integration in the current repo.

## Exact Judge Commands

Use the existing command path:

```powershell
tc doctor
tc preflight CR-017
tc handoff latest --print
tc audit --self-test
tc audit --kind route_audit --last 10
```

Optional deeper verification:

```powershell
tc model check --manifest docs\security\examples\model_route_manifest_local_ollama.json
tc model warn --manifest docs\security\examples\model_route_manifest_local_ollama.json --route docs\security\examples\route_payload_local_ollama.json
tc model warn --manifest docs\security\examples\model_route_manifest_cloud_qwen.json --route docs\security\examples\route_payload_local_ollama.json
python -m pytest -q
git status
```

The warning command remains non-blocking. Warnings are evidence that the route
metadata and manifest can be compared visibly; they are not runtime
enforcement.

## Expected Outputs

- `tc doctor` confirms repo-root, Python, CLI, ledger, and pytest visibility.
- `tc preflight CR-017` writes a handoff artifact under `.triagecore/handoffs/`.
- `tc handoff latest --print` prints a reviewable handoff packet.
- `tc audit --self-test` writes one privacy-safe `route_audit` event.
- `tc audit --kind route_audit --last 10` shows routing metadata without raw payload fields.
- `tc model check` validates the documented manifest example.
- `tc model warn` shows matching metadata or warning-only mismatches without
  failing the demo path.

## Related Docs

- [judge_quickstart.md](judge_quickstart.md)
- [track_mapping.md](track_mapping.md)
- [claim_boundaries.md](claim_boundaries.md)
- [hackathon_demo.md](../workflows/hackathon_demo.md)


