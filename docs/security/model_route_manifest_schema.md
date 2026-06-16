# Model Route Manifest Schema

## Purpose

This document defines the canonical artifact shape for model-route integrity
metadata in TriageCore.

CR-031 defined the policy invariant. This document defines the manifest schema
that future runtime checks, route manifests, or `tc model check` logic should
consume.

This is documentation only. It does not change current runtime behavior.

## Design Goal

The manifest should make it possible to answer, without ambiguity:

- what backend actually ran
- what exact model or artifact was selected
- where that model came from
- whether the route stayed local or crossed a cloud boundary
- whether a mutable tag or alias is masking real identity
- whether artifact integrity and template behavior are known

If the manifest cannot answer those questions, the route should be considered
integrity-incomplete.

## Schema Overview

Top-level shape:

```json
{
  "schema_version": "1.0.0",
  "route_id": "local-ollama-qwen2.5-7b-instruct-q4km",
  "display_name": "Local Ollama Qwen 2.5 7B Instruct Q4_K_M",
  "boundary": {
    "execution_class": "local",
    "network_dependency": false,
    "intended_privacy_class": "local_only"
  },
  "backend": {
    "backend_type": "ollama",
    "backend_label": "ollama-local",
    "runtime_endpoint": "http://127.0.0.1:11434",
    "wrapper_identity": "ollama"
  },
  "model": {
    "model_family": "qwen2.5",
    "exact_model_id": "qwen2.5:7b-instruct-q4_K_M",
    "mutable_reference": false,
    "source_channel": "ollama_registry",
    "source_uri": "ollama://qwen2.5:7b-instruct-q4_K_M",
    "license": "unknown"
  },
  "artifact": {
    "artifact_format": "gguf",
    "quantization": "Q4_K_M",
    "parameter_scale": "7b",
    "digest": "sha256:example",
    "digest_required": true
  },
  "template_behavior": {
    "template_source": "backend_chat_template",
    "template_id": "ollama-qwen2.5-chat",
    "hidden_wrapper_prompt": false
  },
  "integrity": {
    "provenance_complete": true,
    "integrity_status": "complete",
    "operator_notes": ""
  }
}
```

## Required Fields

The following fields are required for a manifest to be schema-complete:

- `schema_version`
- `route_id`
- `display_name`
- `boundary.execution_class`
- `boundary.network_dependency`
- `boundary.intended_privacy_class`
- `backend.backend_type`
- `backend.wrapper_identity`
- `model.exact_model_id`
- `model.mutable_reference`
- `model.source_channel`
- `artifact.digest_required`
- `template_behavior.template_source`
- `integrity.provenance_complete`
- `integrity.integrity_status`

If any required field is missing, the manifest should fail validation in a
future runtime check.

## Optional but Strongly Recommended Fields

These fields may be absent in early integrations, but their absence should be
treated as weaker provenance:

- `backend.backend_label`
- `backend.runtime_endpoint`
- `model.model_family`
- `model.source_uri`
- `model.license`
- `artifact.artifact_format`
- `artifact.quantization`
- `artifact.parameter_scale`
- `artifact.digest`
- `template_behavior.template_id`
- `template_behavior.hidden_wrapper_prompt`
- `integrity.operator_notes`

Missing recommended fields should not be silently ignored in future runtime
checks. They should downgrade the manifest to partial provenance rather than
full provenance.

## Field Semantics

### `boundary`

Defines the actual and intended trust boundary.

Allowed `execution_class` values:

- `local`
- `cloud`
- `hybrid`
- `unknown`

`unknown` should fail future integrity validation for trust-sensitive routes.

### `backend`

Describes the real execution path, not just a friendly label.

Examples:

- direct LM Studio local runtime
- Ollama wrapper over a specific local artifact
- Qwen Cloud API route

`wrapper_identity` exists because a wrapper may be useful operationally while
still being insufficient as the final identity of what ran.

### `model`

Defines exact model identity and provenance source.

`exact_model_id` must be more specific than aliases such as:

- `latest`
- `default`
- `qwen-fast`

`mutable_reference=true` should be treated as an integrity warning or failure
in a future runtime check unless additional immutable identity is also present.

### `artifact`

Defines build and integrity properties for the executable model artifact.

`digest_required=true` means the operator or runtime policy expects a digest to
exist for this route class. If `digest_required=true` and `digest` is absent,
the manifest should be treated as incomplete.

### `template_behavior`

Defines whether backend-side or wrapper-side prompt formatting is in effect.

This section is required because template behavior changes the effective route
contract even when raw user content is not shown.

### `integrity`

Provides the operator-visible assessment.

Recommended `integrity_status` values:

- `complete`
- `partial`
- `invalid`

`provenance_complete=true` should only be used when the manifest contains
enough immutable identity and boundary information to satisfy CR-031.

## Failure Cases

A manifest should be considered invalid or incomplete if it has any of the
following traits:

- exact model identity missing
- only alias names with no immutable identifier
- `mutable_reference=true` with no stronger artifact identity
- boundary class `unknown`
- digest required but missing
- wrapper identity present but no underlying model provenance
- template behavior omitted entirely

## Example Files

This CR includes the following example manifests:

- `docs/security/examples/model_route_manifest_local_ollama.json`
- `docs/security/examples/model_route_manifest_cloud_qwen.json`
- `docs/security/examples/model_route_manifest_invalid_alias_only.json`

The invalid example is intentionally incomplete so future runtime checks have a
documented failure target.

## Future Runtime Expectations

Future `tc model check` or route-manifest validation should:

- validate required fields
- distinguish complete versus partial provenance
- fail closed for invalid boundary or alias-only identity cases
- avoid printing sensitive task content
- report why a manifest is incomplete or invalid

Future runtime checks should not:

- silently accept `latest` as stable identity
- treat wrapper names as sufficient provenance
- hide missing template behavior
- infer cloud/local boundary when the manifest does not declare it

## Non-Goals

This schema document does not:

- define the runtime CLI output format
- require JSON Schema tooling yet
- implement validation code
- redesign routing or backend selection
- alter current route behavior
