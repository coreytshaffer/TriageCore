import json

from triage_core.routing import (
    ResilienceRouteDecision,
    ResilienceRouteInput,
    build_route_decision_payload,
    build_worker_result_payload,
)


def test_build_route_decision_payload_is_json_serializable():
    route_input = ResilienceRouteInput(
        task_class="docs_update",
        complexity="low",
        sensitivity="low",
        cloud_primary_available=False,
        local_fast_available=True,
        deterministic_tool_available=True,
        required_checks=["validator"],
    )
    route_decision = ResilienceRouteDecision(
        selected_route="local_fast",
        reason="local_fast_available_for_small_or_repetitive_task",
        fallback_depth=3,
        human_review_required=False,
        required_checks=["validator"],
    )

    payload = build_route_decision_payload(
        route_input,
        route_decision,
        selected_backend="ollama",
        selected_model="qwen2.5-coder:7b",
    )

    assert payload["task_class"] == "docs_update"
    assert payload["selected_route"] == "local_fast"
    assert payload["selected_backend"] == "ollama"
    assert payload["fallback_depth"] == 3
    json.dumps(payload)


def test_build_worker_result_payload_marks_router_handoff_as_not_backend_failure():
    route_payload = {
        "selected_route": "human_handoff",
        "selected_backend": "ollama",
        "selected_model": "qwen2.5-coder:7b",
        "reason": "sensitivity_requires_human_review",
        "fallback_depth": 5,
    }
    result = {
        "status": "handoff_required",
        "source": "router",
        "worker_result_status": "not_attempted",
        "failure_type": "safety_handoff",
        "failure_stage": "router",
        "validation_status": "not_run",
        "elapsed_seconds": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    payload = build_worker_result_payload(route_payload, result)

    assert payload["selected_route"] == "human_handoff"
    assert payload["worker_result_status"] == "not_attempted"
    assert payload["backend_failure"] is False
    json.dumps(payload)
