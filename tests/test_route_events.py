import json

import pytest

from triage_core.routing import (
    ResilienceRouteDecision,
    ResilienceRouteInput,
    SpecialistOffloadPayloadError,
    build_route_decision_payload,
    build_specialist_offload_payload,
    build_worker_result_payload,
    validate_specialist_offload_payload,
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


# --- CR-DD-018: specialist-offload payload builder / validator ----------------

def _high_risk_cause(**overrides):
    cause = {
        "offload_reason_code": "high_risk",
        "risk_level": "high",
        "risk_categories": ["destructive_ops"],
    }
    cause.update(overrides)
    return cause


def test_build_specialist_offload_payload_canonicalizes_category_order():
    route_task_result = {
        "specialist_offload_cause": _high_risk_cause(
            risk_categories=["system_modifications", "destructive_ops", "destructive_ops"],
        )
    }
    payload = build_specialist_offload_payload(route_task_result)
    assert payload["risk_categories"] == ["destructive_ops", "system_modifications"]
    validate_specialist_offload_payload(payload)  # canonicalized output must validate


def test_build_specialist_offload_payload_requires_cause_from_same_invocation():
    with pytest.raises(SpecialistOffloadPayloadError):
        build_specialist_offload_payload({"offload_recommended": True})


def test_build_specialist_offload_payload_variant_field_shapes():
    medium = build_specialist_offload_payload({
        "specialist_offload_cause": {
            "offload_reason_code": "medium_risk_online",
            "risk_level": "medium",
            "risk_categories": ["package_management"],
            "internet_available": True,
        }
    })
    assert medium == {
        "offload_reason_code": "medium_risk_online",
        "risk_level": "medium",
        "risk_categories": ["package_management"],
        "internet_available": True,
    }

    context = build_specialist_offload_payload({
        "specialist_offload_cause": {
            "offload_reason_code": "context_limit_online",
            "risk_level": "low",
            "risk_categories": [],
            "internet_available": True,
            "context_limit_exceeded": True,
        }
    })
    assert context == {
        "offload_reason_code": "context_limit_online",
        "risk_level": "low",
        "risk_categories": [],
        "internet_available": True,
        "context_limit_exceeded": True,
    }


def test_validate_specialist_offload_payload_accepts_each_variant():
    for payload in (
        _high_risk_cause(),
        {"offload_reason_code": "safety_handoff", "risk_level": "low", "risk_categories": []},
        {
            "offload_reason_code": "medium_risk_online",
            "risk_level": "medium",
            "risk_categories": ["deployment_config"],
            "internet_available": True,
        },
        {
            "offload_reason_code": "context_limit_online",
            "risk_level": "low",
            "risk_categories": [],
            "internet_available": True,
            "context_limit_exceeded": True,
        },
    ):
        validate_specialist_offload_payload(payload)  # must not raise


def test_validate_specialist_offload_payload_rejects_unknown_reason_code():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(_high_risk_cause(offload_reason_code="bogus"))


def test_validate_specialist_offload_payload_rejects_unknown_category():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(_high_risk_cause(risk_categories=["not_a_real_category"]))


def test_validate_specialist_offload_payload_rejects_duplicate_categories():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(
            _high_risk_cause(risk_categories=["destructive_ops", "destructive_ops"])
        )


def test_validate_specialist_offload_payload_rejects_noncanonical_order():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(
            _high_risk_cause(risk_categories=["system_modifications", "destructive_ops"])
        )


def test_validate_specialist_offload_payload_rejects_forbidden_variant_field():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(_high_risk_cause(internet_available=True))


def test_validate_specialist_offload_payload_rejects_null_placeholder():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(_high_risk_cause(internet_available=None))


def test_validate_specialist_offload_payload_rejects_missing_required_field():
    payload = {
        "offload_reason_code": "medium_risk_online",
        "risk_level": "medium",
        "risk_categories": ["package_management"],
        # internet_available omitted -- required True for this variant.
    }
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(payload)


def test_validate_specialist_offload_payload_rejects_false_for_required_true_field():
    payload = {
        "offload_reason_code": "medium_risk_online",
        "risk_level": "medium",
        "risk_categories": ["package_management"],
        "internet_available": False,
    }
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(payload)


@pytest.mark.parametrize(
    "reason_code,risk_level,categories",
    [
        ("high_risk", "low", ["destructive_ops"]),
        ("high_risk", "high", []),
        ("medium_risk_online", "high", ["package_management"]),
        ("context_limit_online", "medium", []),
        ("context_limit_online", "low", ["destructive_ops"]),
    ],
)
def test_validate_specialist_offload_payload_rejects_impossible_cross_field_combinations(
    reason_code, risk_level, categories
):
    payload = {
        "offload_reason_code": reason_code,
        "risk_level": risk_level,
        "risk_categories": categories,
    }
    if reason_code == "medium_risk_online":
        payload["internet_available"] = True
    elif reason_code == "context_limit_online":
        payload["internet_available"] = True
        payload["context_limit_exceeded"] = True
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(payload)


def test_validate_specialist_offload_payload_safety_handoff_accepts_any_risk_level_consistently():
    validate_specialist_offload_payload(
        {"offload_reason_code": "safety_handoff", "risk_level": "high", "risk_categories": ["secrets_and_auth"]}
    )
    validate_specialist_offload_payload(
        {"offload_reason_code": "safety_handoff", "risk_level": "medium", "risk_categories": ["deployment_config"]}
    )
    # But the categories must still be internally consistent with the risk level.
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(
            {"offload_reason_code": "safety_handoff", "risk_level": "high", "risk_categories": []}
        )


# --- CR-DD-018: malformed types must reject via the dedicated error, never TypeError

def test_validate_specialist_offload_payload_rejects_unhashable_reason_code():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(
            _high_risk_cause(offload_reason_code=["high_risk"])
        )


def test_validate_specialist_offload_payload_rejects_unhashable_risk_level():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(
            _high_risk_cause(risk_level={"level": "high"})
        )


def test_validate_specialist_offload_payload_rejects_unhashable_category_element():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(
            _high_risk_cause(risk_categories=[["destructive_ops"]])
        )


def test_validate_specialist_offload_payload_rejects_non_string_category_element():
    with pytest.raises(SpecialistOffloadPayloadError):
        validate_specialist_offload_payload(_high_risk_cause(risk_categories=[42]))


def test_build_specialist_offload_payload_rejects_unhashable_reason_code():
    with pytest.raises(SpecialistOffloadPayloadError):
        build_specialist_offload_payload({
            "specialist_offload_cause": _high_risk_cause(offload_reason_code={"x": 1})
        })


def test_build_specialist_offload_payload_rejects_unhashable_risk_level():
    with pytest.raises(SpecialistOffloadPayloadError):
        build_specialist_offload_payload({
            "specialist_offload_cause": _high_risk_cause(risk_level=["high"])
        })


def test_build_specialist_offload_payload_rejects_unhashable_category_element():
    with pytest.raises(SpecialistOffloadPayloadError):
        build_specialist_offload_payload({
            "specialist_offload_cause": _high_risk_cause(risk_categories=[{"a": 1}])
        })
