# Agent Authority Manifest

## Purpose

Agent signatures answer who produced an artifact. They do not answer what that
agent was allowed to do.

The agent authority manifest is a static, task-scoped contract for that second
question. It binds an agent identity to an owner, purpose, action scope,
resource scope, approval gates, expiration, and revocation state before any
future workflow treats the agent as safe to act.

This is a metadata-only validation surface. It does not grant approval,
execute tools, mutate the identity registry, or change routing behavior.

## Why This Exists

TriageCore already separates provenance from approval. Signed route decisions
can prove that a local identity produced a route-decision event, but a valid
signature does not prove the decision was safe, approved, or inside the
agent's task authority.

The authority manifest fills that gap as a boring, inspectable artifact:

- identity says which agent signed or proposed the action
- authority says which action class, resource scope, purpose, and approval
  boundary apply
- admission and human review remain separate controls

This gives TriageCore a practical bridge from local identity and signed
evidence toward evaluation-environment work, where verifiers can score whether
an agent stayed inside a declared authority boundary.

## Manifest Shape

```json
{
  "schema_version": "1.0.0",
  "agent_id": "agent.local.triagecore.reviewer",
  "owner": "operator",
  "purpose": "Review route decisions and write non-executing recommendations.",
  "allowed_actions": [
    "read_task_packet",
    "propose_route_decision",
    "write_review_artifact"
  ],
  "denied_actions": [
    "execute_shell",
    "access_secrets",
    "deploy_code",
    "modify_identity_registry",
    "write_to_main_branch"
  ],
  "allowed_resources": [
    "docs/",
    "tests/fixtures/",
    ".triagecore/evidence/"
  ],
  "requires_human_approval_for": [
    "network_access",
    "write_to_main_branch",
    "credential_rotation",
    "external_api_call"
  ],
  "expires_at": "2099-12-31T23:59:59Z",
  "revocation_status": "active"
}
```

## Required Fields

- `schema_version`: currently `1.0.0`
- `agent_id`: stable agent identity id using the same safe character set as
  local identities
- `owner`: accountable human or operator role
- `purpose`: short task-purpose statement
- `allowed_actions`: explicit action names allowed by the manifest
- `denied_actions`: explicit action names denied by the manifest
- `allowed_resources`: explicit file, artifact, or resource scopes
- `requires_human_approval_for`: actions that must remain inert until human
  approval evidence exists
- `expires_at`: timezone-aware ISO-8601 expiration timestamp
- `revocation_status`: `active`, `revoked`, `disabled`, or `expired`

## Validation Rules

`tc authority check --manifest <path>` fails closed when:

- any required field is missing or empty
- list fields are not lists of non-empty strings
- `schema_version` is unsupported
- `agent_id` uses unsafe characters
- `revocation_status` is not `active`
- `expires_at` is invalid, timezone-free, or expired
- an action appears in both `allowed_actions` and `denied_actions`
- `allowed_actions` or `allowed_resources` uses wildcard authority
- high-risk allowed actions lack matching human approval gates

High-risk actions currently include:

- `access_secrets`
- `credential_rotation`
- `deploy_code`
- `execute_shell`
- `external_api_call`
- `modify_identity_registry`
- `network_access`
- `write_to_main_branch`

## CLI Usage

```powershell
tc authority check --manifest docs\security\examples\agent_authority_manifest_reviewer.json
```

Expected success shape:

```text
Agent authority manifest check passed
manifest=docs\security\examples\agent_authority_manifest_reviewer.json
agent_id=agent.local.triagecore.reviewer
owner=operator
revocation_status=active
allowed_actions=3
denied_actions=5
approval_gates=4
```

## Boundaries

This validator does not:

- verify that the agent exists in `.triagecore/identity/agents.json`
- sign the manifest
- grant execution authority
- satisfy human approval
- mutate ledger or identity state
- enforce routing decisions at runtime

Future slices may bind authority manifests to signed route decisions or
admission checks. That should remain separate from this static contract and
validator.
