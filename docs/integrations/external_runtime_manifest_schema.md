# External Runtime Manifest Schema

## Status

Documentation-only schema for CR-044.

## Purpose

Define the canonical manifest artifact an external runtime must provide before
TriageCore can classify it, reason about its authority boundary, or admit it
into a governed workflow.

CR-043 defined the doctrine. This document defines the contract shape that
future examples, adapters, or validation logic should consume.

This is documentation only. It does not change current runtime behavior.

## Design Goal

The manifest should make it possible to answer, without ambiguity:

- what runtime is asking to participate
- what version and adapter surface it is presenting
- what capability profile it claims
- what tool policy boundary it expects
- whether it can reach network, credentials, or mutable tools
- what model provider or model identity may act under that runtime
- whether explicit approval is required before mutation
- whether provenance evidence is required for use
- whether the runtime can be revoked or disabled cleanly

If the manifest cannot answer those questions, the runtime should be treated as
authority-incomplete.

## Schema Overview

Top-level shape:

```yaml
schema_version: "1.0.0"
runtime_name: "example-runtime"
runtime_version: "0.0.0"
runtime_kind: "external_agent"
adapter_version: "0.0.0"
capability_profile: "read_only_summary"
tool_policy_hash: "sha256:example"
sandbox_mode: "workspace_write"
network_access: "blocked"
credential_access: "none"
model_provider: "local_only"
model_identity: "none"
approval_required: true
provenance_required: true
revocation_supported: true
notes: ""
```

## Required Fields

The following fields are required for a manifest to be schema-complete:

- `schema_version`
- `runtime_name`
- `runtime_version`
- `runtime_kind`
- `adapter_version`
- `capability_profile`
- `tool_policy_hash`
- `sandbox_mode`
- `network_access`
- `credential_access`
- `model_provider`
- `model_identity`
- `approval_required`
- `provenance_required`
- `revocation_supported`

If any required field is missing, the manifest should fail validation in a
future runtime check.

## Optional but Strongly Recommended Fields

These fields may be absent in early integrations, but their absence should be
treated as weaker operator clarity:

- `notes`
- future `declared_tools`
- future `channel_origin`
- future `revocation_contact`

Missing recommended fields should not silently expand trust. They should lower
operator confidence and preserve manual review.

## Field Semantics

### `runtime_name`

The stable human-readable identity of the external runtime.

Examples:

- `openclaw`
- `remote-agent-gateway`
- `browser-review-runner`

This should identify the runtime itself, not the current task or channel.

### `runtime_version`

The exact runtime release or build identifier exposed to TriageCore. Mutable
labels such as `latest` are insufficient on their own.

### `runtime_kind`

The broad class of external participant.

Recommended values:

- `external_agent`
- `automation_gateway`
- `tool_router`
- `model_host`
- `unknown`

`unknown` should fail future authority-sensitive validation.

### `adapter_version`

The version of the TriageCore-side adapter or declared compatibility contract.
This keeps runtime identity separate from integration-surface identity.

### `capability_profile`

The declared behavior tier the runtime is requesting.

Examples:

- `read_only_summary`
- `draft_only`
- `approved_mutation`
- `scheduled_check`

This field should map to TriageCore-native policy categories rather than
vendor marketing language.

### `tool_policy_hash`

The immutable digest of the tool-policy contract expected by the runtime.

This exists so TriageCore can compare declared authority against a known policy
surface instead of trusting descriptive text alone.

### `sandbox_mode`

The runtime's effective filesystem or execution boundary as presented to
TriageCore.

Recommended values:

- `read_only`
- `workspace_write`
- `full_access`
- `unknown`

`unknown` should fail future authority-sensitive validation.

### `network_access`

The runtime's effective network reach.

Recommended values:

- `blocked`
- `egress_only`
- `scoped_allowlist`
- `unrestricted`
- `unknown`

### `credential_access`

Whether the runtime can directly read, request, or use credentials.

Recommended values:

- `none`
- `indirect`
- `scoped`
- `broad`
- `unknown`

This field matters because credential reach changes the real mutation surface
even when the visible tool list looks narrow.

### `model_provider`

The provider class for any model-assisted behavior the runtime may invoke.

Examples:

- `none`
- `local_only`
- `openai`
- `anthropic`
- `mixed`
- `unknown`

### `model_identity`

The exact model identifier or explicit `none` when no model surface exists.

Alias-only labels such as `default` or `fast` should be treated as incomplete
identity in future validation.

### `approval_required`

Whether TriageCore must require explicit approval before the runtime can perform
mutation-capable or trust-sensitive actions.

For external runtimes, the expected default is `true`.

### `provenance_required`

Whether provenance evidence must be recorded before or alongside use of the
runtime.

For external runtimes, the expected default is `true`.

### `revocation_supported`

Whether the runtime can be disabled, rejected, or de-authorized without
breaking TriageCore's core policy model.

If this is `false`, the integration should be treated as structurally suspect.

## Failure Cases

A manifest should be considered invalid or incomplete if it has any of the
following traits:

- runtime identity missing or alias-only
- adapter version omitted
- capability profile described only in prose with no stable category
- tool policy declared without a hash or stable identifier
- sandbox, network, or credential boundary marked `unknown`
- model use implied but provider or model identity absent
- `approval_required=false` for a mutation-capable external runtime
- `provenance_required=false` with no stronger documented control
- `revocation_supported=false` for a runtime expected to participate repeatedly

## Future Runtime Expectations

Future manifest validation or adapter admission checks should:

- validate required fields
- reject alias-only or unknown identity for authority-sensitive use
- compare declared capability profile to the expected TriageCore policy tier
- require explicit approval and provenance for mutation-capable runtimes
- report why a manifest is incomplete or structurally unsafe

Future checks should not:

- infer missing authority fields from vendor docs
- treat runtime branding as sufficient identity
- assume sandbox, network, or credential limits that are not declared
- allow a runtime example to redefine the canonical contract

## Example Files

This schema now has companion examples:

- `docs/integrations/examples/external_runtime_manifest_read_only.yaml`
- `docs/integrations/examples/external_runtime_manifest_draft_only.yaml`
- `docs/integrations/examples/external_runtime_manifest_invalid_unknowns.yaml`

The invalid example is intentionally authority-incomplete so future validation work has a documented failure target.

## Relation to Runtime Integrity and Model Provenance

This manifest contract directly implements the requirements set forth in the [Runtime Integrity and Model Provenance Policy](../security/runtime_integrity_model_provenance_policy.md).

By requiring explicit identity, exact tool policy boundaries, and mandatory provenance tracking fields (`provenance_required`), the adapter ensures that TriageCore never grants authority to an anonymous or opaque executor. The manifest forces the external runtime to declare its surface area in advance, allowing TriageCore to enforce the policy boundary before any action occurs.

### Why Aliases Are Not Trust Boundaries

Convenience names like `default`, `latest`, `fast`, or blank strings do not provide cryptographic or stable identity. If an operator authorizes a capability profile for `model_identity: "latest"`, a silent downstream change could swap a safe model for an unsafe one without changing the alias.

Therefore, aliases and wrappers **are not trust boundaries**. The TriageCore adapter will actively reject alias-only identities (e.g. `runtime_version: "latest"` or `model_identity: "default"`) to prevent policy circumvention. Trust requires an explicit version string, a digest, or a fully qualified identifier.

## Minimal Examples

### Minimal Valid Manifest

This manifest contains all required fields and uses explicit versions, which the adapter will successfully parse as a valid proposal.

```yaml
schema_version: "1.0.0"
runtime_name: "example-runtime"
runtime_version: "0.1.0"
runtime_kind: "external_agent"
adapter_version: "0.1.0"
capability_profile: "read_only_summary"
tool_policy_hash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
sandbox_mode: "read_only"
network_access: "blocked"
credential_access: "none"
model_provider: "none"
model_identity: "none"
approval_required: true
provenance_required: true
revocation_supported: true
```

### Minimal Invalid Manifest (Missing `schema_version`)

This manifest is invalid because it omits `schema_version`. The adapter will reject it with a `missing_or_blank:schema_version` block reason.

```yaml
# Missing 'schema_version'
runtime_name: "example-runtime"
runtime_version: "0.1.0"
runtime_kind: "external_agent"
adapter_version: "0.1.0"
capability_profile: "read_only_summary"
tool_policy_hash: "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
sandbox_mode: "read_only"
network_access: "blocked"
credential_access: "none"
model_provider: "none"
model_identity: "none"
approval_required: true
provenance_required: true
revocation_supported: true
```

## Non-Goals

This schema document does not:

- define a runtime adapter interface
- add JSON Schema tooling yet
- implement validation code
- permit any external runtime execution
