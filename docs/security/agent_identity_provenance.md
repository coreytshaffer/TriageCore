# Agent Identity and Provenance

**Agent signatures prove provenance, not approval.**

The TriageCore persistent cryptographic identity foundation (Ed25519) allows local AI agents to cryptographically sign the ledger events they emit (such as `route_audit`). 

## Provenance vs. Authority

It is critical for reviewers, operators, and downstream systems to understand the explicit boundary of this capability:

1. **Provenance:** A valid signature guarantees *who* emitted the payload (which agent identity key) and that the payload has not been tampered with since emission. 
2. **Not Approval:** A valid signature **does not** imply safety, correctness, or human approval. An agent can correctly sign a completely hallucinated, destructive, or incorrect decision.
3. **Not Authority Escalation:** Identity capabilities (e.g., `route_audit:sign`) only authorize the agent to *create* the cryptographic record of that event. They do not bypass existing human review gates, admission controls, or CI/CD branch protections.

Cryptographic identity in TriageCore is a tamper-evident audit trail designed to solve the "which agent did this?" problem, keeping AI-generated actions accountable and traceable. It is intentionally decoupled from trust and safety enforcement.
