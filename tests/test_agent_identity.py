import json

import pytest

from triage_core.agent_identity import (
    ACTIVE_STATUS,
    REVOKED_STATUS,
    AgentIdentity,
    AgentIdentityRegistry,
    RevokedAgentError,
    UnauthorizedCapabilityError,
    UnknownAgentError,
    UnsupportedKeyAlgorithmError,
)


def test_agent_identity_computes_safe_public_metadata():
    identity = AgentIdentity(
        agent_id="context-planner",
        role="ContextPlanner",
        public_key="public-key-material",
        key_algorithm="ed25519",
        capabilities=["route_audit:sign"],
    )

    metadata = identity.to_public_metadata()

    assert metadata["agent_id"] == "context-planner"
    assert metadata["role"] == "ContextPlanner"
    assert metadata["public_key"] == "public-key-material"
    assert metadata["key_algorithm"] == "ed25519"
    assert metadata["status"] == ACTIVE_STATUS
    assert metadata["capabilities"] == ["route_audit:sign"]
    assert "public_key_fingerprint" in metadata


def test_registry_save_and_load_public_identity_metadata(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    identity = AgentIdentity(
        agent_id="validator-tools",
        role="ValidatorTools",
        public_key="validator-public-key",
        key_algorithm="ed25519",
        capabilities=["validation_result:sign"],
    )
    registry.register_identity(identity)

    saved_path = registry.save()
    assert saved_path == tmp_path / ".triagecore" / "identity" / "agents.json"

    raw = json.loads(saved_path.read_text(encoding="utf-8"))
    assert len(raw["agents"]) == 1
    assert raw["agents"][0]["agent_id"] == "validator-tools"

    loaded_registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    loaded_registry.load()
    loaded_identity = loaded_registry.get_identity("validator-tools")

    assert loaded_identity.public_key_fingerprint == identity.public_key_fingerprint
    assert loaded_identity.capabilities == ["validation_result:sign"]


def test_registry_refuses_unknown_agent_ids(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")

    with pytest.raises(UnknownAgentError):
        registry.get_identity("missing-agent")


@pytest.mark.parametrize("status", [REVOKED_STATUS, "inactive"])
def test_revoked_or_inactive_agents_fail_authorization_checks(tmp_path, status):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    registry.register_identity(
        AgentIdentity(
            agent_id="project-steward",
            role="ProjectSteward",
            public_key="steward-public-key",
            key_algorithm="ed25519",
            status=status,
            capabilities=["project_steward_decision:sign"],
        )
    )

    with pytest.raises(RevokedAgentError):
        registry.require_authorized_capability(
            "project-steward",
            "project_steward_decision:sign",
        )


def test_events_outside_declared_capability_set_fail_authorization(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    registry.register_identity(
        AgentIdentity(
            agent_id="context-planner",
            role="ContextPlanner",
            public_key="planner-public-key",
            key_algorithm="ed25519",
            capabilities=["route_audit:sign"],
        )
    )

    with pytest.raises(UnauthorizedCapabilityError):
        registry.require_authorized_capability(
            "context-planner",
            "validation_result:sign",
        )


def test_unsupported_key_algorithms_fail_clearly():
    with pytest.raises(UnsupportedKeyAlgorithmError):
        AgentIdentity(
            agent_id="implementer",
            role="Implementer",
            public_key="implementer-public-key",
            key_algorithm="rsa2048",
            capabilities=["route_audit:sign"],
        )


def test_authorized_active_agent_passes_capability_check(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    identity = AgentIdentity(
        agent_id="llm-review-worker",
        role="LLMReviewWorker",
        public_key="review-public-key",
        key_algorithm="ed25519",
        capabilities=["route_audit:sign", "validation_result:sign"],
    )
    registry.register_identity(identity)

    authorized = registry.require_authorized_capability(
        "llm-review-worker",
        "validation_result:sign",
    )

    assert authorized.agent_id == "llm-review-worker"
