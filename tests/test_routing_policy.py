from triage_core.routing.policy import classify_route


def _amd_manifest(**overrides: object) -> dict[str, object]:
    manifest = {
        "provider": "amd_developer_cloud",
        "route_target": "amd_cloud",
        "allowed_for": ["external_safe", "performance_escalation"],
        "requires_human_approval": True,
    }
    manifest.update(overrides)
    return manifest


def _task_packet(**overrides: object) -> dict[str, object]:
    packet = {
        "privacy_class": "external_safe",
        "risk_level": "low",
        "requested_route": "local",
        "requested_backend": "",
        "deterministic_tool_requested": False,
        "deterministic_tool_allowed": False,
        "amd_cloud_requested": False,
        "cloud_egress_allowed": True,
        "approval_granted": False,
    }
    packet.update(overrides)
    return packet


def test_low_risk_task_routes_local():
    decision = classify_route(_task_packet(), _amd_manifest())

    assert decision.route == "local"
    assert decision.status == "allowed"
    assert decision.reason == "low_risk_task_stays_local"
    assert decision.requires_approval is False


def test_deterministic_task_routes_deterministic():
    decision = classify_route(
        _task_packet(
            requested_route="deterministic",
            deterministic_tool_requested=True,
            deterministic_tool_allowed=True,
            risk_level="medium",
        ),
        _amd_manifest(),
    )

    assert decision.route == "deterministic"
    assert decision.status == "allowed"
    assert decision.reason == "deterministic_tool_requested_and_allowed"
    assert decision.requires_approval is False


def test_amd_cloud_requires_approval_when_policy_requires_it():
    decision = classify_route(
        _task_packet(
            requested_route="amd_cloud",
            requested_backend="amd_developer_cloud",
            amd_cloud_requested=True,
            risk_level="moderate",
        ),
        _amd_manifest(requires_human_approval=True),
    )

    assert decision.route == "amd_cloud"
    assert decision.status == "approval_required"
    assert decision.reason == "amd_cloud_route_requires_human_approval"
    assert decision.requires_approval is True


def test_sensitive_task_blocks_amd_cloud_when_egress_disallowed():
    decision = classify_route(
        _task_packet(
            requested_route="amd_cloud",
            requested_backend="amd_developer_cloud",
            amd_cloud_requested=True,
            privacy_class="local_only",
            risk_level="high",
            cloud_egress_allowed=False,
        ),
        _amd_manifest(),
    )

    assert decision.route == "blocked"
    assert decision.status == "blocked"
    assert decision.reason == "sensitive_data_disallows_cloud_egress"
    assert decision.requires_approval is False


def test_amd_cloud_allowed_after_approval():
    decision = classify_route(
        _task_packet(
            requested_route="amd_cloud",
            requested_backend="amd_developer_cloud",
            amd_cloud_requested=True,
            risk_level="moderate",
            approval_granted=True,
        ),
        _amd_manifest(requires_human_approval=True),
    )

    assert decision.route == "amd_cloud"
    assert decision.status == "allowed"
    assert decision.reason == "amd_cloud_route_allowed_by_manifest"
    assert decision.requires_approval is True
