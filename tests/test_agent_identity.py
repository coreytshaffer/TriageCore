import json

import pytest

from triage_core.agent_identity import (
    ACTIVE_STATUS,
    REVOKED_STATUS,
    AgentIdentity,
    AgentIdentityError,
    AgentIdentityRegistry,
    RevokedAgentError,
    UnauthorizedCapabilityError,
    UnknownAgentError,
    UnsupportedKeyAlgorithmError,
    canonical_payload_hash,
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


def test_local_signing_keys_can_be_generated_and_registered(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")

    identity = registry.generate_identity(
        "context-planner",
        "ContextPlanner",
        ["route_audit:sign"],
    )

    key_path = tmp_path / ".triagecore" / "identity" / "keys" / "context-planner.key"
    registry_path = tmp_path / ".triagecore" / "identity" / "agents.json"

    assert key_path.exists()
    assert registry_path.exists()
    assert "PRIVATE KEY" in key_path.read_text(encoding="utf-8")

    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    assert raw["agents"][0]["agent_id"] == "context-planner"
    assert "private_key" not in raw["agents"][0]
    assert raw["agents"][0]["public_key"] == identity.public_key


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


def test_unauthorized_capability_fails_before_signing(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    registry.generate_identity(
        "context-planner",
        "ContextPlanner",
        ["route_audit:sign"],
    )

    with pytest.raises(UnauthorizedCapabilityError):
        registry.sign_payload(
            "context-planner",
            "validation_result:sign",
            {"event_type": "validation_result"},
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


def test_sign_and_verify_payload_success(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    registry.generate_identity(
        "validator-tools",
        "ValidatorTools",
        ["validation_result:sign"],
    )
    payload = {
        "event_type": "validation_result",
        "validator_name": "deterministic_demo_validator",
        "status": "passed",
    }

    signature_metadata = registry.sign_payload(
        "validator-tools",
        "validation_result:sign",
        payload,
    )

    assert signature_metadata["signature_algorithm"] == "ed25519"
    assert signature_metadata["payload_hash"] == canonical_payload_hash(payload)
    assert registry.verify_signed_payload(payload, signature_metadata) is True


def test_tampering_with_signed_payload_metadata_fails_verification(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    registry.generate_identity(
        "validator-tools",
        "ValidatorTools",
        ["validation_result:sign"],
    )
    payload = {"event_type": "validation_result", "status": "passed"}
    signature_metadata = registry.sign_payload(
        "validator-tools",
        "validation_result:sign",
        payload,
    )

    tampered_payload = {"event_type": "validation_result", "status": "failed"}
    assert registry.verify_signed_payload(tampered_payload, signature_metadata) is False

    tampered_metadata = dict(signature_metadata)
    tampered_metadata["capability"] = "route_audit:sign"
    with pytest.raises(UnauthorizedCapabilityError):
        registry.verify_signed_payload(payload, tampered_metadata)


def test_unknown_agents_fail_verification(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    signature_metadata = {
        "agent_id": "unknown-agent",
        "capability": "route_audit:sign",
        "payload_hash": canonical_payload_hash({"event_type": "route_audit"}),
        "signature_algorithm": "ed25519",
        "signed_at": "2026-06-13T00:00:00+00:00",
        "signature": "ZmFrZQ==",
    }

    with pytest.raises(UnknownAgentError):
        registry.verify_signed_payload({"event_type": "route_audit"}, signature_metadata)


def test_revoked_agents_fail_verification(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    active_identity = registry.generate_identity(
        "project-steward",
        "ProjectSteward",
        ["project_steward_decision:sign"],
    )
    payload = {"event_type": "project_steward_decision", "decision": "approved"}
    signature_metadata = registry.sign_payload(
        "project-steward",
        "project_steward_decision:sign",
        payload,
    )
    registry.register_identity(
        AgentIdentity(
            agent_id=active_identity.agent_id,
            role=active_identity.role,
            public_key=active_identity.public_key,
            public_key_fingerprint=active_identity.public_key_fingerprint,
            key_algorithm=active_identity.key_algorithm,
            created_at=active_identity.created_at,
            status=REVOKED_STATUS,
            capabilities=active_identity.capabilities,
        )
    )

    with pytest.raises(RevokedAgentError):
        registry.verify_signed_payload(payload, signature_metadata)


def test_verification_dispatches_by_signature_algorithm(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    registry.generate_identity(
        "validator-tools",
        "ValidatorTools",
        ["validation_result:sign"],
    )
    payload = {"event_type": "validation_result", "status": "passed"}
    signature_metadata = registry.sign_payload(
        "validator-tools",
        "validation_result:sign",
        payload,
    )
    signature_metadata["signature_algorithm"] = "rsa2048"

    with pytest.raises(UnsupportedKeyAlgorithmError):
        registry.verify_signed_payload(payload, signature_metadata)


def test_private_key_material_is_not_in_public_metadata_or_errors(tmp_path):
    registry = AgentIdentityRegistry(tmp_path / ".triagecore")
    identity = registry.generate_identity(
        "implementer",
        "Implementer",
        ["route_audit:sign"],
    )
    key_material = (tmp_path / ".triagecore" / "identity" / "keys" / "implementer.key").read_text(
        encoding="utf-8"
    )

    metadata = identity.to_public_metadata()
    assert "PRIVATE KEY" not in json.dumps(metadata)

    with pytest.raises(AgentIdentityError) as exc:
        registry.generate_identity(
            "implementer",
            "Implementer",
            ["route_audit:sign"],
        )

    assert "PRIVATE KEY" not in str(exc.value)
    assert key_material not in str(exc.value)
