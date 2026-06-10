# CR-005: Local Preflight Context Compression

## Status
Implemented

## Scope
Define how TriageCore can use deterministic tools and verified local LLM backends to create compact, provenance-tracked context bundles for Antigravity.

## Implementation Authority
Not authorized until human approval.

## Human Approval Requirement
Explicit human review and approval of this Change Request is required before any source code implementation begins.

## Description
As context windows grow, feeding raw logs, files, and outputs to the cloud model becomes inefficient and increases latency. TriageCore should perform local preflight context compression, leveraging deterministic context selection/extraction plus optional local LLM summarization to condense task inputs into a tight context bundle before handing off to Antigravity or a cloud model.

### Explicit Statement on Source Verification
Local preflight summaries reduce context size and improve routing efficiency, but they **do not replace source verification**. The flagship model must still have the ability to retrieve raw source files or logs when necessary to verify facts or dive deeper into compressed summaries.

## Relationships to Existing Change Requests

### Relationship to CR-004A Provenance
Any preflight compression performed by a local LLM must be tightly coupled with CR-004A provenance tracking. The resulting context bundle must carry a CR-004A-compatible provenance record identifying backend type, sanitized backend URI, model ID, execution node, and timestamp, so the flagship model can gauge the trustworthiness of the condensed context.

### Relationship to CR-001 TaskPacket Metadata
Preflight context compression must operate on `TaskPacket` structures defined in CR-001. The compression logic must respect the `PrivacyMetadata` fields. If TaskPacket metadata indicates sensitive content, redaction_required, or external_model_allowed=false, CR-005 must either bypass summarization or defer processing policy to CR-002/CR-003. CR-005 should not create its own redaction/scanning policy.

## Acceptance Criteria
- [x] A deterministic context selection/extraction module is defined, with optional local LLM summarization through CR-004A-provenance-capable backends.
- [x] TriageCore can invoke a local LLM backend to summarize a `TaskPacket` payload.
- [x] The generated context bundle includes explicit provenance metadata indicating the summarizing agent/backend.
- [x] Context bundles are associated with a TaskPacket or referenced by it, without overwriting the original prompt, data, or privacy metadata.
- [x] If TaskPacket metadata indicates sensitive content, redaction_required, or external_model_allowed=false, summarization is bypassed or policy deferred to CR-002/CR-003.
- [x] Generated context bundles include source file references or fingerprints sufficient for later source verification.
- [x] Generated context bundles include an estimated raw-token count, compressed-token count, and reduction estimate.
