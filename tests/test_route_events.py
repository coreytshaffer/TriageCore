import json

import pytest

import triage_core.routing.route_events as route_events

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


# CR-DD-019: a policy reason and the observed binding cause have different roles.
def _cr019_route(*, evidence=None, **overrides):
    values = dict(
        selected_route="local_fast",
        reason="local_heavy_available_for_medium_or_complex_task",
        fallback_depth=1,
        human_review_required=False,
    )
    sensitivity = overrides.pop("sensitivity", "low")
    decision_id = overrides.pop("decision_id", "sha256:" + "a" * 64)
    values.update(overrides)
    return build_route_decision_payload(
        ResilienceRouteInput(sensitivity=sensitivity),
        ResilienceRouteDecision(**values),
        decision_id=decision_id,
        governed_evidence=(
            {
                "governed_risk_posture": "low",
                "binding_outcome": "authorized_fallback",
                "binding_reason_codes": [
                    "local_capability_unavailable", "bound_authorized_fallback"
                ],
            }
            if evidence is None else evidence
        ),
    )


def test_cr019_route_and_worker_preserve_policy_and_binding_with_owned_lists():
    evidence = {
        "governed_risk_posture": "low",
        "binding_outcome": "authorized_fallback",
        "binding_reason_codes": [
            "local_capability_unavailable", "bound_authorized_fallback"
        ],
    }
    route = _cr019_route(evidence=evidence)
    worker = build_worker_result_payload(
        route, {"status": "success", "binding_outcome": "closed",
                "governed_risk_posture": "high", "binding_reason_codes": []}
    )
    for payload in (route, worker):
        assert payload["reason"] == "local_heavy_available_for_medium_or_complex_task"
        assert payload["selected_route"] == "local_fast"
        assert payload["decision_id"] == "sha256:" + "a" * 64
        assert payload["governed_risk_posture"] == "low"
        assert payload["binding_outcome"] == "authorized_fallback"
        assert payload["binding_reason_codes"] == [
            "local_capability_unavailable", "bound_authorized_fallback"
        ]
        json.dumps(payload)
    evidence["binding_reason_codes"].clear()
    worker["binding_reason_codes"].clear()
    assert route["binding_reason_codes"] == [
        "local_capability_unavailable", "bound_authorized_fallback"
    ]


@pytest.mark.parametrize("route,outcome,depth,codes", [
    ("local_heavy", "primary", 0, ["bound_preferred_route"]),
    ("cloud_primary", "primary", 0, ["bound_preferred_route"]),
    ("human_handoff", "primary", 0, ["terminal_human_handoff"]),
    ("local_fast", "authorized_fallback", 1,
     ["route_model_binding_missing", "bound_authorized_fallback"]),
    ("human_handoff", "authorized_fallback", 2,
     ["local_capability_unknown", "local_capability_unknown", "terminal_human_handoff"]),
    ("cloud_secondary", "authorized_fallback", 5,
     ["deterministic_executor_not_wired", "cloud_route_not_enabled",
      "local_capability_unavailable", "local_capability_unknown",
      "route_model_binding_missing", "bound_authorized_fallback"]),
])
@pytest.mark.parametrize("risk", ["low", "medium", "high"])
def test_cr019_bound_sequences_are_preserved(route, outcome, depth, codes, risk):
    payload = _cr019_route(
        evidence={"governed_risk_posture": risk, "binding_outcome": outcome,
                  "binding_reason_codes": codes},
        selected_route=route, fallback_depth=depth,
        sensitivity="high" if risk == "high" else "medium",
        human_review_required=risk == "high",
    )
    assert payload["binding_reason_codes"] == codes
    assert payload["governed_risk_posture"] == risk
    assert build_worker_result_payload(payload, {})["binding_outcome"] == outcome


@pytest.mark.parametrize("changes,options,code", [
    ({"prompt": "PRIVATE_VALUE"}, {}, "invalid_governed_evidence_shape"),
    ({"governed_risk_posture": None}, {}, "invalid_governed_evidence_shape"),
    ({"binding_outcome": None}, {}, "invalid_governed_evidence_shape"),
    ({"binding_reason_codes": None}, {}, "invalid_governed_evidence_shape"),
    ({"governed_risk_posture": []}, {}, "invalid_governed_evidence_value"),
    ({"governed_risk_posture": "HIGH"}, {}, "invalid_governed_evidence_value"),
    ({"binding_outcome": "closed"}, {}, "invalid_governed_evidence_value"),
    ({"binding_outcome": {}}, {}, "invalid_governed_evidence_value"),
    ({"binding_reason_codes": "bound_authorized_fallback"}, {}, "invalid_governed_evidence_value"),
    ({"binding_reason_codes": ("bound_authorized_fallback",)}, {}, "invalid_governed_evidence_value"),
    ({"binding_reason_codes": []}, {}, "invalid_governed_evidence_value"),
    ({"binding_reason_codes": ["local_capability_unknown"] * 7}, {}, "invalid_governed_evidence_value"),
    ({"binding_reason_codes": [[]]}, {}, "invalid_governed_evidence_value"),
    ({"binding_reason_codes": ["PRIVATE_VALUE"]}, {}, "invalid_governed_evidence_value"),
    ({"binding_reason_codes": ["no_authorized_binding_available"]}, {}, "invalid_governed_evidence_value"),
    ({}, {"decision_id": None}, "invalid_governed_evidence_linkage"),
    ({}, {"decision_id": "sha256:" + "A" * 64}, "invalid_governed_evidence_linkage"),
    ({}, {"decision_id": "sha256:" + "a" * 64 + "\n"}, "invalid_governed_evidence_linkage"),
    ({}, {"decision_id": []}, "invalid_governed_evidence_linkage"),
    ({}, {"fallback_depth": True}, "invalid_governed_evidence_value"),
    ({}, {"fallback_depth": -1}, "invalid_governed_evidence_value"),
    ({}, {"fallback_depth": 6}, "invalid_governed_evidence_value"),
    ({}, {"fallback_depth": 1.0}, "invalid_governed_evidence_value"),
    ({}, {"selected_route": "deterministic"}, "invalid_governed_evidence_value"),
    ({}, {"selected_route": []}, "invalid_governed_evidence_value"),
    ({}, {"sensitivity": []}, "invalid_governed_evidence_value"),
    ({}, {"human_review_required": 1}, "invalid_governed_evidence_value"),
    ({"binding_outcome": "primary"}, {}, "inconsistent_governed_evidence"),
    ({}, {"fallback_depth": 2}, "inconsistent_governed_evidence"),
    ({"binding_reason_codes": ["bound_preferred_route", "bound_authorized_fallback"]}, {}, "inconsistent_governed_evidence"),
    ({"binding_reason_codes": ["terminal_human_handoff", "bound_authorized_fallback"]}, {}, "inconsistent_governed_evidence"),
    ({"binding_reason_codes": ["local_capability_unknown", "bound_preferred_route"]}, {}, "inconsistent_governed_evidence"),
    ({}, {"selected_route": "human_handoff"}, "inconsistent_governed_evidence"),
    ({"governed_risk_posture": "high"}, {}, "inconsistent_governed_evidence"),
    ({"governed_risk_posture": "high"}, {"sensitivity": "high"}, "inconsistent_governed_evidence"),
])
def test_cr019_malformed_extensions_fail_with_bounded_codes(changes, options, code):
    evidence = {"governed_risk_posture": "low", "binding_outcome": "authorized_fallback",
                "binding_reason_codes": ["local_capability_unavailable", "bound_authorized_fallback"]}
    evidence.update(changes)
    with pytest.raises(ValueError) as caught:
        _cr019_route(evidence=evidence, **options)
    assert type(caught.value) is route_events.GovernedEvidencePayloadError
    assert caught.value.reason_code == code
    assert str(caught.value) == code


@pytest.mark.parametrize("evidence", [{}, [], {"binding_outcome": "primary"}])
def test_cr019_extension_shape_precedes_linkage_and_values(evidence):
    with pytest.raises(ValueError) as caught:
        _cr019_route(evidence=evidence, decision_id=None)
    assert str(caught.value) == "invalid_governed_evidence_shape"


@pytest.mark.parametrize("field", [
    "governed_risk_posture", "binding_outcome", "binding_reason_codes",
])
@pytest.mark.parametrize("decision_id", [None, "malformed", "sha256:" + "a" * 64])
@pytest.mark.parametrize("consumer", ["route", "worker"])
def test_cr019_null_fields_are_shape_errors_before_linkage(field, decision_id, consumer):
    evidence = {
        "governed_risk_posture": "low", "binding_outcome": "authorized_fallback",
        "binding_reason_codes": ["local_capability_unavailable", "bound_authorized_fallback"],
    }
    evidence[field] = None
    if consumer == "worker":
        route = _cr019_route()
        route.update(evidence)
        route["decision_id"] = decision_id
    with pytest.raises(ValueError) as caught:
        if consumer == "route":
            _cr019_route(evidence=evidence, decision_id=decision_id)
        else:
            build_worker_result_payload(route, {})
    assert type(caught.value) is route_events.GovernedEvidencePayloadError
    assert caught.value.reason_code == "invalid_governed_evidence_shape"
    assert str(caught.value) == "invalid_governed_evidence_shape"


def test_cr019_linkage_precedes_value_validation():
    with pytest.raises(ValueError) as caught:
        _cr019_route(evidence={"governed_risk_posture": [], "binding_outcome": [],
                               "binding_reason_codes": []}, decision_id=None)
    assert str(caught.value) == "invalid_governed_evidence_linkage"


def test_cr019_worker_rejects_partial_and_inconsistent_source_groups():
    route = _cr019_route()
    del route["binding_outcome"]
    with pytest.raises(ValueError, match="^invalid_governed_evidence_shape$"):
        build_worker_result_payload(route, {})
    route = _cr019_route()
    route["fallback_depth"] = 0
    with pytest.raises(ValueError, match="^inconsistent_governed_evidence$"):
        build_worker_result_payload(route, {})


def test_cr019_legacy_linkage_only_records_gain_no_extension():
    route = build_route_decision_payload(
        ResilienceRouteInput(), ResilienceRouteDecision("local_fast", "legacy", 0, False),
        decision_id="sha256:" + "a" * 64, governed_evidence=None,
    )
    for payload in (route, build_worker_result_payload(route, {})):
        assert payload["decision_id"] == "sha256:" + "a" * 64
        assert not {"governed_risk_posture", "binding_outcome", "binding_reason_codes"} & payload.keys()


def test_cr019_validator_vocabulary_does_not_drift_from_observation_contract():
    from triage_core.governed_decision import RISK_POSTURE_VALUES, LOGICAL_ROUTE_VALUES
    from triage_core.runtime_observation import BINDING_OUTCOMES, BINDING_REASON_CODES

    assert RISK_POSTURE_VALUES == {"low", "medium", "high"}
    assert LOGICAL_ROUTE_VALUES == {
        "local_fast", "local_heavy", "cloud_primary", "cloud_secondary",
        "deterministic", "human_handoff",
    }
    assert BINDING_OUTCOMES == {"primary", "authorized_fallback", "closed"}
    assert BINDING_REASON_CODES == {
        "bound_preferred_route", "bound_authorized_fallback", "terminal_human_handoff",
        "deterministic_executor_not_wired", "cloud_route_not_enabled",
        "local_capability_unavailable", "local_capability_unknown",
        "route_model_binding_missing", "no_authorized_binding_available",
    }
    assert route_events._GOVERNED_RISKS == RISK_POSTURE_VALUES
    assert route_events._GOVERNED_OUTCOMES == BINDING_OUTCOMES - {"closed"}
    assert route_events._GOVERNED_BOUND_ROUTES == LOGICAL_ROUTE_VALUES - {"deterministic"}
    assert route_events._GOVERNED_BINDING_CODES == BINDING_REASON_CODES - {
        "no_authorized_binding_available",
    }
    assert route_events._GOVERNED_FAILURE_CODES == BINDING_REASON_CODES - {
        "bound_preferred_route", "bound_authorized_fallback", "terminal_human_handoff",
        "no_authorized_binding_available",
    }


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
