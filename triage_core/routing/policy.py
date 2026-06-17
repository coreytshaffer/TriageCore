from dataclasses import dataclass
from typing import Any, Literal


RouteTarget = Literal["local", "deterministic", "amd_cloud", "blocked"]
DecisionStatus = Literal["allowed", "blocked", "approval_required"]

SENSITIVE_PRIVACY_VALUES = {"local_only", "private", "repo_private", "sensitive"}
LOCAL_RISK_VALUES = {"low", "minor"}
AMD_ROUTE_VALUES = {"amd_cloud", "cloud_heavy"}
DETERMINISTIC_ROUTE_VALUES = {"deterministic", "deterministic_tool"}


@dataclass(frozen=True)
class RouteDecision:
    route: RouteTarget
    status: DecisionStatus
    reason: str
    requires_approval: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "route": self.route,
            "status": self.status,
            "reason": self.reason,
            "requires_approval": self.requires_approval,
        }


def classify_route(task_packet: dict[str, Any], manifest: dict[str, Any]) -> RouteDecision:
    requested_route = _normalize(
        task_packet.get("requested_route") or task_packet.get("recommended_route")
    )
    requested_backend = _normalize(task_packet.get("requested_backend"))
    privacy_class = _normalize(
        task_packet.get("privacy_class") or task_packet.get("privacy_level")
    )
    risk_level = _normalize(task_packet.get("risk_level") or task_packet.get("risk"))
    deterministic_requested = bool(task_packet.get("deterministic_tool_requested"))
    deterministic_allowed = bool(task_packet.get("deterministic_tool_allowed", False))
    amd_requested = bool(task_packet.get("amd_cloud_requested")) or requested_route in AMD_ROUTE_VALUES
    cloud_egress_allowed = bool(task_packet.get("cloud_egress_allowed", True))
    approval_granted = bool(task_packet.get("approval_granted", False))

    manifest_provider = _normalize(manifest.get("provider"))
    manifest_route = _normalize(manifest.get("route_target") or manifest.get("route_class"))
    manifest_allowed_for = {_normalize(value) for value in manifest.get("allowed_for", [])}
    manifest_requires_approval = bool(manifest.get("requires_human_approval", False))

    if deterministic_requested and deterministic_allowed:
        return RouteDecision(
            route="deterministic",
            status="allowed",
            reason="deterministic_tool_requested_and_allowed",
            requires_approval=False,
        )

    if amd_requested and _is_sensitive_without_egress(privacy_class, cloud_egress_allowed):
        return RouteDecision(
            route="blocked",
            status="blocked",
            reason="sensitive_data_disallows_cloud_egress",
            requires_approval=False,
        )

    if amd_requested and not _manifest_supports_amd(manifest_provider, manifest_route):
        return RouteDecision(
            route="blocked",
            status="blocked",
            reason="manifest_does_not_allow_amd_cloud_route",
            requires_approval=False,
        )

    if amd_requested and requested_backend not in {"", "amd_cloud", manifest_provider}:
        return RouteDecision(
            route="blocked",
            status="blocked",
            reason="requested_backend_not_in_manifest",
            requires_approval=False,
        )

    if amd_requested and "external_safe" not in manifest_allowed_for:
        return RouteDecision(
            route="blocked",
            status="blocked",
            reason="manifest_external_safe_boundary_missing",
            requires_approval=False,
        )

    if amd_requested and manifest_requires_approval and not approval_granted:
        return RouteDecision(
            route="amd_cloud",
            status="approval_required",
            reason="amd_cloud_route_requires_human_approval",
            requires_approval=True,
        )

    if amd_requested:
        return RouteDecision(
            route="amd_cloud",
            status="allowed",
            reason="amd_cloud_route_allowed_by_manifest",
            requires_approval=manifest_requires_approval,
        )

    if requested_route in DETERMINISTIC_ROUTE_VALUES and deterministic_allowed:
        return RouteDecision(
            route="deterministic",
            status="allowed",
            reason="deterministic_route_requested_and_allowed",
            requires_approval=False,
        )

    if risk_level in LOCAL_RISK_VALUES:
        return RouteDecision(
            route="local",
            status="allowed",
            reason="low_risk_task_stays_local",
            requires_approval=False,
        )

    return RouteDecision(
        route="local",
        status="allowed",
        reason="default_local_route_without_cloud_request",
        requires_approval=False,
    )


def _is_sensitive_without_egress(privacy_class: str, cloud_egress_allowed: bool) -> bool:
    return privacy_class in SENSITIVE_PRIVACY_VALUES and not cloud_egress_allowed


def _manifest_supports_amd(provider: str, route_target: str) -> bool:
    return provider == "amd_developer_cloud" or route_target in AMD_ROUTE_VALUES


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()
