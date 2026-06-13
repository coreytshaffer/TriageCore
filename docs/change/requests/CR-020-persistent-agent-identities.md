# CR-020: Persistent Cryptographic Agent Identities

## Status

Partially Implemented - Phase 3 route_audit signed ledger metadata

## Linked Issue

- GitHub Issue: #4 â€” Add persistent cryptographic agent identities

## Goal

Add persistent agent identities backed by cryptographic signing keys so TriageCore can attribute important control-plane and audit-ledger actions to known, authorized agents.

The goal is accountable continuity, tamper evidence, and scoped authorization for local agents. This change must not grant agents unchecked autonomy or bypass human approval gates.

## Motivation

TriageCore is becoming a local-first control plane for task routing, privacy enforcement, validation, scoped cloud handoff, and human review. As the system grows from a single workflow into a council of named workers, the audit layer should be able to answer:

- Which agent performed this action?
- Was that agent authorized to perform this action?
- Was the payload changed after the event was recorded?
- Was the signing key active, revoked, or unknown?
- Did this event come from a local trusted component or an external/cloud worker handoff?

Persistent cryptographic identities provide inspectable provenance for important internal actions while preserving local-first control and human decision authority.

## Scope

This change request covers the design and implementation of a lightweight cryptographic identity layer for TriageCore agents.

Initial scope:

- Define an `AgentIdentity` model.
- Define an `AgentKeyStore` or equivalent local key-management boundary.
- Define signed ledger-event metadata.
- Add explicit signing-algorithm metadata for crypto agility.
- Add local key initialization for core agents.
- Add event signing and verification helpers.
- Add revocation checks.
- Add capability checks.
- Add tests for success and failure paths.
- Ensure private keys are never written to prompts, TaskPackets, logs, cloud handoffs, CLI output, or audit output.

## Non-Goals

This CR does not introduce:

- Public blockchain storage.
- Agent self-sovereignty.
- Remote key custody.
- Automatic trust in cloud workers.
- Internet-safe hosting.
- TLS termination.
- User accounts.
- Replacement of privacy scanning.
- Replacement of validation.
- Replacement of human approval gates.
- Signing of raw sensitive prompt or data content.

## Proposed Architecture

### AgentIdentity

Each persistent agent identity should include at least:

```python
agent_id: str
role: str
public_key: str
public_key_fingerprint: str
key_algorithm: str
created_at: str
status: str
capabilities: list[str]
```

Recommended initial `key_algorithm` value:

```text
ed25519
```

The `key_algorithm` field is required even in the Ed25519-only MVP so the design remains crypto-agile.

### AgentKeyStore

The key store should manage the local boundary between public identity metadata and private signing material.

Responsibilities:

- Initialize local signing keys for named agents.
- Store public identity metadata in an inspectable registry.
- Store private keys locally only.
- Ensure private key files are excluded from git.
- Load signing keys for local agents.
- Support identity revocation.
- Leave room for later key rotation.

Suggested layout:

```text
.triagecore/identity/
  agents.json
  keys/
    contextplanner.key
    implementer.key
    validator-tools.key
    llm-review-worker.key
    project-steward.key
```

The private key directory must be gitignored:

```gitignore
.triagecore/identity/keys/
```

### SignedLedgerEvent

Important ledger events should include enough metadata to verify attribution and tamper evidence without exposing raw sensitive inputs.

Suggested fields:

```python
event_type: str
agent_id: str
payload_hash: str
previous_event_hash: str | None
timestamp: str
signature_algorithm: str
signature: str
```

The signed material should be canonicalized before signing. The signature should cover the event payload hash and relevant event metadata, not raw prompt or raw data content.

### Initial Agents

Initial persistent identities may include:

- `ContextPlanner`
- `Implementer`
- `ValidatorTools`
- `LLMReviewWorker`
- `ProjectSteward`
- Optional local supervisor/controller identity

### Initial Signed Events

Start with high-value control-plane and audit events:

- `taskpacket_created`
- `route_decision`
- `route_audit`
- `validation_result`
- `project_steward_decision`

## Authorization Model

Signature verification and authorization should remain separate.

Verification answers:

> Did the registered key for this agent sign this event?

Authorization answers:

> Was this agent allowed to perform this event type?

Each agent identity should have a declared capability set. Events outside the declared capability set should fail authorization checks even if the cryptographic signature is valid.

## Security Model

This identity system proves only that a known local component signed a specific event. It does not prove that the event is correct, safe, ethical, or approved.

The identity layer must remain subordinate to:

- privacy scanning
- local-only routing constraints
- validation
- human approval gates
- ProjectSteward review
- audit visibility

Private key material must remain local and must never be sent to cloud workers. Cloud workers may produce outputs that are recorded by TriageCore, but they do not receive local signing authority.

## Post-Quantum Cryptography Stretch Goal

Design the identity and ledger-signing layer to be crypto-agile so TriageCore can later support post-quantum signature algorithms without redesigning the audit model.

Initial implementation should use Ed25519 for simplicity and maturity, but identity records and signed ledger events should include explicit algorithm metadata.

Potential future algorithms:

- `ed25519`
- `ml-dsa`
- `slh-dsa`

PQC support is out of scope for the first implementation. It should not be enabled until mature, reviewed Python library support is available and the project has a clear verification strategy.

## Acceptance Criteria

- [ ] TriageCore can initialize persistent local identities for core agents.
- [ ] Each identity has an agent ID, role, public key fingerprint, status, capability list, and key algorithm.
- [ ] Private key files are excluded from git.
- [ ] Public identity metadata can be safely inspected.
- [ ] Ledger events can be signed by an agent identity.
- [ ] Signed events include `signature_algorithm`.
- [ ] Signed events can be verified against the registered public key.
- [ ] Verification dispatches by algorithm instead of assuming Ed25519 everywhere.
- [ ] Tampering with a signed event payload causes verification to fail.
- [ ] Unknown agent IDs fail verification.
- [ ] Revoked agent IDs fail verification.
- [ ] Events outside an agent's declared capability set fail authorization checks.
- [ ] No private key material is written to prompts, TaskPackets, logs, cloud handoffs, CLI output, or audit output.
- [ ] Tests cover valid signature, tampered payload, unknown agent, revoked agent, unauthorized capability, and unsupported algorithm cases.

## Validation Plan

Minimum validation:

```powershell
python -m py_compile triage_core\*.py
python -m pytest -q
```

Targeted validation should include any new test files added for:

- identity model behavior
- key initialization
- event signing
- event verification
- revocation
- capability enforcement
- unsupported algorithm handling
- no private key leakage in exported or printed records

## Implementation Notes

## Implementation Progress

### Phase 1: Agent identity foundation

Implemented public identity metadata, local registry loading/saving, status
checks, capability authorization checks, algorithm metadata validation, and
gitignore protection for private key storage.

### Phase 2: Signing foundation

Implemented local Ed25519 key generation, private key storage under
`.triagecore/identity/keys/`, public identity registration in
`.triagecore/identity/agents.json`, canonical payload hashing, signing
helpers, verification helpers, tamper-failure checks, and capability/status
enforcement around signing and verification.

### Phase 3: route_audit signed ledger metadata

Implemented an opt-in signed ledger path for `route_audit` events only, using
metadata-only event envelopes and existing Ed25519 signing helpers. Added
verification helpers and compatibility coverage proving that unsigned legacy
ledger events still read normally.

Global ledger signing, automatic signing across all event types, and signing of
raw prompt or data content remain out of scope for this phase.

Recommended phased implementation:

1. Add data models and tests.
2. Add local identity registry and key initialization.
3. Add signing and verification helpers.
4. Add revocation and capability checks.
5. Integrate with one low-risk event type first.
6. Expand to route and validation events after the verification path is stable.

Good first implementation target:

```text
route_audit
```

This keeps the first integration close to the existing audit ledger without forcing every workflow path to change at once.

## Remaining Risks

- Local private key storage needs careful permissions and gitignore hygiene.
- Canonicalization must be deterministic or signatures will be fragile.
- The system must not imply correctness merely because a record is signed.
- Cloud handoffs must remain scoped and external-safe only.
- Future PQC support may change signature size, performance, and dependency requirements.
