# CR-004: Local LLM Provenance and Smoke Tests

## Status
Proposed

## Scope
Implement comprehensive health checks, canary generation tests, and provenance tracking for local LLM backends (Ollama and LM Studio) to verify local execution integrity and prevent silent cloud fallback.

## Implementation Authority
Not authorized until human approval.

## Human Approval Requirement
Explicit human review and approval of this Change Request is required before any source code implementation begins.

## Description
To ensure the Self-Observing Harness accurately observes local executions and respects the ethical firewall and boundaries, we must behaviorally demonstrate local execution through endpoint health checks, canary generation, adapter transport tests, and ledger provenance, while leaving room for stronger cryptographic provenance later.

The implementation is split into two phases:

### CR-004A: Local Backend Provenance (Independent of CR-001)
1. **Ollama Endpoint Health Check**: Verify the Ollama API is reachable.
2. **LM Studio Endpoint Health Check**: Verify the LM Studio API is reachable.
3. **Ollama Canary Generation**: Run a tiny, deterministic prompt through Ollama to confirm generation works.
4. **LM Studio Canary Generation**: Run a tiny, deterministic prompt through LM Studio to confirm generation works.
5. **Adapter-Level Transport Tests**: Unit tests mocking the HTTP transport layer to ensure adapters correctly format payloads and handle errors.
6. **Ledger Provenance Fields**: Add fields to `.triagecore/ledger.jsonl` explicitly tracking the backend URI, backend type, and model version that actually serviced the request.
7. **Fake Local Server Testing**: Use a fake/mock local server to simulate latency, failures, and malformed responses to ensure TriageCore handles them gracefully.
8. **Clear Failure on Unavailable Local Backend**: If the local backend is offline or unavailable, the system must fail closed and emit a clear error.

### CR-004B: Local-Only Privacy-Routing Enforcement (Depends on CR-001 / CR-002)
1. **Routing Constraints**: Verify that a task marked with a CR-001-approved local-only routing constraint cannot route to cloud.
2. **No Silent Fallback**: Verify that there is no silent cloud fallback for local-only/sensitive tasks.

## Implementation Notes
- Unit tests should use fake/mock local servers and should not require Ollama or LM Studio to be running.
- Live Ollama and LM Studio checks should be marked as integration/smoke tests and should be opt-in or environment-gated.

## Acceptance Criteria
### CR-004A
- [ ] `pytest` includes explicitly named smoke tests for Ollama and LM Studio endpoints.
- [ ] Canary generation tests exist and validate the local model can return text.
- [ ] Transport adapters have unit tests with a fake local server (mocking 200 OK, 404, 500 errors).
- [ ] Task records in `.triagecore/ledger.jsonl` include new provenance fields (e.g., `backend_uri`, `execution_node`).
- [ ] A test asserts that if a local backend is unreachable, an explicit failure is thrown.

### CR-004B
- [ ] A test asserts that when a task is marked with a CR-001-approved local-only routing constraint, no cloud API keys are accessed or network calls made.
- [ ] A test asserts that a task with a CR-001-approved local-only routing constraint fails closed immediately if the local backend is unavailable, without silent cloud fallback.
