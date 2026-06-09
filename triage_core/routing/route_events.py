from typing import Any, Dict

from .resilience_router import ResilienceRouteDecision, ResilienceRouteInput


def build_route_decision_payload(
    route_input: ResilienceRouteInput,
    route_decision: ResilienceRouteDecision,
    *,
    selected_backend: str = "",
    selected_model: str = "",
    route_source: str = "resilience_router_v1",
) -> Dict[str, Any]:
    return {
        "task_class": route_input.task_class,
        "task_complexity": route_input.complexity,
        "task_sensitivity": route_input.sensitivity,
        "task_privacy_level": route_input.privacy_level,
        "selected_route": route_decision.selected_route,
        "selected_backend": selected_backend,
        "selected_model": selected_model,
        "reason": route_decision.reason,
        "fallback_depth": route_decision.fallback_depth,
        "human_review_required": route_decision.human_review_required,
        "required_checks": list(route_decision.required_checks),
        "internet_ok": route_input.internet_ok,
        "cloud_primary_available": route_input.cloud_primary_available,
        "cloud_secondary_available": route_input.cloud_secondary_available,
        "cloud_credit_state": route_input.cloud_credit_state,
        "lm_studio_ok": route_input.lm_studio_ok,
        "local_heavy_available": route_input.local_heavy_available,
        "local_fast_available": route_input.local_fast_available,
        "memory_headroom_mb": route_input.memory_headroom_mb,
        "deterministic_tool_available": route_input.deterministic_tool_available,
        "recent_cloud_failures": route_input.recent_cloud_failures,
        "recent_local_heavy_failures": route_input.recent_local_heavy_failures,
        "recent_local_fast_failures": route_input.recent_local_fast_failures,
        "route_source": route_source,
    }


def build_worker_result_payload(
    route_payload: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    failure_type = result.get("failure_type")
    failure_stage = result.get("failure_stage")
    backend_failure = bool(failure_type == "backend_error" and failure_stage == "local_backend_generate")

    return {
        "selected_route": route_payload.get("selected_route"),
        "selected_backend": route_payload.get("selected_backend", ""),
        "selected_model": route_payload.get("selected_model", ""),
        "reason": route_payload.get("reason", ""),
        "fallback_depth": route_payload.get("fallback_depth"),
        "worker_result_status": result.get("worker_result_status", "not_attempted"),
        "validation_status": result.get("validation_status", "not_run"),
        "failure_type": failure_type,
        "failure_stage": failure_stage,
        "backend_failure": backend_failure,
        "status": result.get("status", ""),
        "source": result.get("source", ""),
        "elapsed_seconds": result.get("elapsed_seconds", 0.0),
        "timeout_seconds": result.get("timeout_seconds"),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "total_tokens": result.get("total_tokens", 0),
        "tokens_per_second": result.get("tokens_per_second", 0.0),
        "validator_name": result.get("validator_name"),
        "validator_version": result.get("validator_version"),
        "validator_scope": result.get("validator_scope"),
    }
