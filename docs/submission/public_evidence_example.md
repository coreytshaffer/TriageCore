# Public Evidence Example

This is a canonical privacy-safe evidence example for public reviewers.

It uses the `tc audit --self-test` path so the example proves the audit trail format without exposing prompt text, task data, or raw payload contents.

## Example Event Shape

```json
{
  "event_type": "route_audit",
  "decision": "allowed",
  "reason": "audit_self_test",
  "privacy_level": "public",
  "privacy_passed": true,
  "local_only": false,
  "requested_backend": "self_test",
  "selected_backend": "self_test"
}
```

The actual ledger event also carries timestamp, task ID, schema metadata, and the nested payload wrapper used by the current ledger format.

## Example CLI Output

```text
> tc audit --self-test
Success: Wrote privacy-safe route_audit self-test event to ...\.triagecore\ledger.jsonl.

> tc audit --kind route_audit --last 10
[2026-06-11T03:39:17.292773+00:00] Task: audit-self-test | Type: route_audit
  Decision: allowed | Reason: audit_self_test
  Privacy: public (Scan Passed: True)
  Local Only: False | Route: self_test | Backend: self_test
```

## What This Proves

- TriageCore can write an inspectable route audit record.
- The record can be inspected without reading raw prompt or task data.
- The audit path is usable as a public proof marker because it is metadata-only.

## What This Does Not Prove

- live production cloud execution
- end-to-end task quality
- environmental deployment outcomes

For the full reviewer path, see [judge_quickstart.md](judge_quickstart.md).

## Optional Manifest Warning Evidence

For a stronger provenance-oriented proof marker, reviewers can also run:

```powershell
tc model check --manifest docs\security\examples\model_route_manifest_local_ollama.json
tc model warn --manifest docs\security\examples\model_route_manifest_local_ollama.json --route docs\security\examples\route_payload_local_ollama.json
tc model warn --manifest docs\security\examples\model_route_manifest_cloud_qwen.json --route docs\security\examples\route_payload_local_ollama.json
```

What this adds:

- `tc model check` proves the documented manifest can be validated locally.
- `tc model warn` proves route metadata can be compared against a manifest with
  visible pass/warn output.
- warning output is non-blocking and does not enforce runtime behavior.

What this still does not prove:

- live backend or model-artifact probing
- production-grade route enforcement
- certification of model provenance

