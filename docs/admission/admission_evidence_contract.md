# Admission Evidence Contract

## Purpose

Admission evidence JSON is a reviewable evidence object for external runtime admission decisions. It exists so operators and tests can validate structure and render a human-legible readout without executing the proposed runtime.

Admission evidence is not execution permission by itself. It supports review, validation, and rendering, but it does not grant authority to run code or bypass separate admission and operator controls.

## Current Contract Shape

The current implementation maps JSON into `ExternalRuntimeAdmissionEvidence` via `triage_core.admission.admission_evidence_from_mapping`.

The validator currently recognizes these fields:

- `admitted`
- `execution_performed`
- `requested_runtime`
- `requested_capability`
- `approval_required`
- `approval_used`
- `blocked_reasons`
- `manifest_or_source_evidence`
- `approval_evidence`

Fields outside this set are not described by this contract document. This document only covers what the current validator and renderer already support.

## Required Fields

The current validator requires the following fields to be present and correctly typed:

| Field | Type | Meaning |
| --- | --- | --- |
| `admitted` | `bool` | Whether the proposed runtime use has passed the current admission decision. |
| `execution_performed` | `bool` | Whether any execution has actually occurred. Under the documented safe path, this should remain explicit rather than inferred. |
| `requested_runtime` | `str` | The runtime identity being requested. Must be a non-empty string. |
| `requested_capability` | `str` | The capability level being requested from that runtime. Must be a non-empty string. |
| `approval_required` | `bool` | Whether the request requires explicit approval before admission. |
| `approval_used` | `bool` | Whether such approval was actually used for this decision. |
| `blocked_reasons` | `list[str]` | Structured reasons why a proposal is blocked or gated. The list may be empty, but every present item must be a non-empty string. |
| `manifest_or_source_evidence` | `str` | The source evidence or manifest excerpt supporting review. Must be a non-empty string. |

## Optional Fields

The current validator recognizes one optional field:

| Field | Type | Meaning |
| --- | --- | --- |
| `approval_evidence` | `str \| null` | Optional evidence describing the approval used. If present, it must be a non-empty string. `null` is allowed. |

No other optional fields are currently recognized by the documented implementation.

## Forbidden Assumptions

The following assumptions are unsafe and should be treated as invalid operator reasoning even when a JSON object validates successfully:

- Admission evidence is not proof that execution occurred.
- Admission evidence is not proof that a runtime is safe.
- Admission evidence is not proof that a model alias, wrapper, or adapter name is trustworthy.
- Admission evidence does not grant execution authority.
- Admission evidence does not bypass human review.
- Rendered Markdown is an operator aid, not a policy decision by itself.
- A valid evidence object does not replace explicit runtime or model provenance checks.

## Trust Boundaries

The current admission evidence workflow has separate responsibilities:

- Validation checks structure and allowed field types through `admission_evidence_from_mapping`.
- Rendering converts already valid evidence into operator-facing Markdown through `render_admission_evidence_markdown`.
- Admission decision authority remains separate from evidence presentation.
- Runtime and model provenance must remain explicit in the underlying evidence and surrounding workflow.
- Wrappers, aliases, and adapter names are not trust boundaries.
- Any local/cloud boundary claims must be represented honestly in the surrounding workflow and must not be inferred from presentation alone.

## Valid Example

See [docs/examples/admission-evidence.example.json](/C:/Users/corey/Documents/Science/AI/triagecore/docs/examples/admission-evidence.example.json) for the current public valid example.

That fixture demonstrates a blocked, approval-gated request where:

- `admitted` is `false`
- `execution_performed` is `false`
- `approval_required` is `true`
- `approval_used` is `false`
- `blocked_reasons` contains one explicit review reason

## Invalid Example Classes

The validator or surrounding governance should reject or treat as unsafe evidence in classes like these:

- Missing required field such as `requested_runtime`.
- Malformed field type such as a string where a boolean is required.
- Empty required string such as blank `manifest_or_source_evidence`.
- Invalid `blocked_reasons` entries such as empty strings or non-string items.
- Empty `approval_evidence` when approval evidence is claimed to exist.
- Ambiguous runtime identity that relies on labels or aliases without explicit provenance.
- Evidence wording that implies execution authority instead of review support.
- Missing provenance or source evidence where operator review depends on it.

## Relationship To CLI

The current CLI exposes two read-only paths:

```bash
python -m triage_core.tc_cli admission validate --from-json <path>
python -m triage_core.tc_cli admission render --from-json <path>
```

Their roles are different:

- `validate` checks whether the JSON fixture matches the admission evidence contract.
- `render` first validates the fixture, then converts valid evidence into Markdown for operator review.
- Both commands reject `.triagecore/ledger.jsonl` as a fixture source.
- CR-070 asserts these paths are read-only at the controlled workspace boundary.

## Non-Authority Reminder

Even when evidence validates and renders cleanly, the result is still a documentation and review artifact. Admission evidence must remain subordinate to the broader operator workflow, explicit approval policy, and any separate execution boundary enforcement.
