from dataclasses import dataclass, field


ROUTE_CLOUD_PRIMARY = "cloud_primary"
ROUTE_CLOUD_SECONDARY = "cloud_secondary"
ROUTE_LOCAL_HEAVY = "local_heavy"
ROUTE_LOCAL_FAST = "local_fast"
ROUTE_DETERMINISTIC = "deterministic"
ROUTE_HUMAN_HANDOFF = "human_handoff"

HIGH_SENSITIVITY_VALUES = {"high", "human_only", "regulated", "secret"}
LOCAL_ONLY_VALUES = {"local_only", "private", "repo_private"}
EXHAUSTED_CREDIT_VALUES = {"exhausted", "none", "blocked"}
LOW_CREDIT_VALUES = {"low", "limited"}

DETERMINISTIC_TASK_CLASSES = {
    "csv_transform",
    "formatting",
    "json_validation",
    "lint",
    "schema_validation",
    "test_run",
}

LOCAL_FAST_TASK_CLASSES = {
    "classification",
    "copy_edit",
    "docs_update",
    "log_summary",
    "small_edit",
    "triage",
}

LOCAL_HEAVY_TASK_CLASSES = {
    "architecture_planning",
    "code_generation",
    "code_repair",
    "configuration_review",
    "multi_file_change",
    "smoke_check_design",
    "ui_api_slice",
}

CLOUD_PRIMARY_TASK_CLASSES = {
    "novel_design",
    "security_review",
    "large_refactor",
}


@dataclass
class ResilienceRouteInput:
    task_class: str = "general"
    complexity: str = "medium"
    sensitivity: str = "low"
    privacy_level: str = "local_ok"
    internet_ok: bool = True
    cloud_primary_available: bool = True
    cloud_secondary_available: bool = False
    cloud_credit_state: str = "ok"
    lm_studio_ok: bool = True
    local_heavy_available: bool = True
    local_fast_available: bool = True
    memory_headroom_mb: int = 4096
    deterministic_tool_available: bool = False
    recent_cloud_failures: int = 0
    recent_local_heavy_failures: int = 0
    recent_local_fast_failures: int = 0
    human_review_required: bool = False
    required_checks: list[str] = field(default_factory=list)


@dataclass
class ResilienceRouteDecision:
    selected_route: str
    reason: str
    fallback_depth: int
    human_review_required: bool
    required_checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_route": self.selected_route,
            "reason": self.reason,
            "fallback_depth": self.fallback_depth,
            "human_review_required": self.human_review_required,
            "required_checks": self.required_checks,
        }


def choose_resilience_route(route_input: ResilienceRouteInput) -> ResilienceRouteDecision:
    task_class = _normalize(route_input.task_class)
    complexity = _normalize(route_input.complexity)
    sensitivity = _normalize(route_input.sensitivity)
    privacy_level = _normalize(route_input.privacy_level)
    cloud_credit_state = _normalize(route_input.cloud_credit_state)
    review_required = route_input.human_review_required or sensitivity in {"medium", "high"}
    local_only = privacy_level in LOCAL_ONLY_VALUES

    candidates = []

    if sensitivity in HIGH_SENSITIVITY_VALUES:
        candidates.append((ROUTE_HUMAN_HANDOFF, "sensitivity_requires_human_review"))
    elif _should_use_deterministic_first(route_input, task_class):
        candidates.append((ROUTE_DETERMINISTIC, "deterministic_tool_available_for_task_class"))
    else:
        if not local_only and task_class in CLOUD_PRIMARY_TASK_CLASSES:
            candidates.append((ROUTE_CLOUD_PRIMARY, "cloud_primary_healthy_for_high_complexity_task"))
            candidates.append((ROUTE_CLOUD_SECONDARY, "cloud_primary_degraded_using_secondary"))

        if _prefers_local_heavy(task_class, complexity):
            candidates.append((ROUTE_LOCAL_HEAVY, "local_heavy_available_for_medium_or_complex_task"))

        if _prefers_local_fast(task_class, complexity):
            candidates.append((ROUTE_LOCAL_FAST, "local_fast_available_for_small_or_repetitive_task"))

        candidates.append((ROUTE_LOCAL_HEAVY, "local_heavy_available_after_preferred_route_unavailable"))
        candidates.append((ROUTE_LOCAL_FAST, "local_fast_available_after_preferred_route_unavailable"))

        if not local_only:
            candidates.append((ROUTE_CLOUD_PRIMARY, "cloud_primary_available_after_local_routes_unavailable"))
            candidates.append((ROUTE_CLOUD_SECONDARY, "cloud_secondary_available_after_local_routes_unavailable"))

        if route_input.deterministic_tool_available:
            candidates.append((ROUTE_DETERMINISTIC, "deterministic_tool_available_as_last_automated_route"))

        candidates.append((ROUTE_HUMAN_HANDOFF, "no_reliable_automated_route_available"))

    unique_candidates = []
    seen = set()
    for route, reason in candidates:
        if route not in seen:
            seen.add(route)
            unique_candidates.append((route, reason))

    for depth, (route, reason) in enumerate(unique_candidates):
        is_available = False
        requires_review = review_required

        if route == ROUTE_HUMAN_HANDOFF:
            is_available = True
            requires_review = True
        elif route == ROUTE_DETERMINISTIC:
            is_available = route_input.deterministic_tool_available
            if not _should_use_deterministic_first(route_input, task_class):
                requires_review = True
        elif route == ROUTE_CLOUD_PRIMARY:
            is_available = _cloud_primary_ok(route_input, cloud_credit_state)
        elif route == ROUTE_CLOUD_SECONDARY:
            is_available = _cloud_secondary_ok(route_input, cloud_credit_state)
        elif route == ROUTE_LOCAL_HEAVY:
            is_available = _local_heavy_ok(route_input)
        elif route == ROUTE_LOCAL_FAST:
            is_available = _local_fast_ok(route_input)

        if is_available:
            return _decision(
                selected_route=route,
                reason=reason,
                fallback_depth=depth,
                human_review_required=requires_review,
                route_input=route_input,
            )

    # Fallback to human handoff if all else fails
    return _decision(
        selected_route=ROUTE_HUMAN_HANDOFF,
        reason="no_reliable_automated_route_available",
        fallback_depth=len(unique_candidates),
        human_review_required=True,
        route_input=route_input,
    )


def _cloud_primary_ok(route_input: ResilienceRouteInput, credit_state: str) -> bool:
    return (
        route_input.internet_ok
        and route_input.cloud_primary_available
        and credit_state not in EXHAUSTED_CREDIT_VALUES
        and credit_state not in LOW_CREDIT_VALUES
        and route_input.recent_cloud_failures < 3
    )


def _cloud_secondary_ok(route_input: ResilienceRouteInput, credit_state: str) -> bool:
    return (
        route_input.internet_ok
        and route_input.cloud_secondary_available
        and credit_state not in EXHAUSTED_CREDIT_VALUES
        and credit_state not in LOW_CREDIT_VALUES
        and route_input.recent_cloud_failures < 5
    )


def _local_heavy_ok(route_input: ResilienceRouteInput) -> bool:
    return (
        route_input.lm_studio_ok
        and route_input.local_heavy_available
        and route_input.memory_headroom_mb >= 4096
        and route_input.recent_local_heavy_failures < 2
    )


def _local_fast_ok(route_input: ResilienceRouteInput) -> bool:
    return (
        route_input.lm_studio_ok
        and route_input.local_fast_available
        and route_input.memory_headroom_mb >= 1024
        and route_input.recent_local_fast_failures < 5
    )


def _should_use_deterministic_first(
    route_input: ResilienceRouteInput,
    task_class: str,
) -> bool:
    return route_input.deterministic_tool_available and task_class in DETERMINISTIC_TASK_CLASSES


def _prefers_local_heavy(task_class: str, complexity: str) -> bool:
    return task_class in LOCAL_HEAVY_TASK_CLASSES or complexity in {"medium", "high"}


def _prefers_local_fast(task_class: str, complexity: str) -> bool:
    return task_class in LOCAL_FAST_TASK_CLASSES or complexity in {"low", "small"}


def _decision(
    selected_route: str,
    reason: str,
    fallback_depth: int,
    human_review_required: bool,
    route_input: ResilienceRouteInput,
) -> ResilienceRouteDecision:
    return ResilienceRouteDecision(
        selected_route=selected_route,
        reason=reason,
        fallback_depth=fallback_depth,
        human_review_required=human_review_required,
        required_checks=list(route_input.required_checks),
    )


def _normalize(value: str) -> str:
    return str(value or "").strip().lower()
