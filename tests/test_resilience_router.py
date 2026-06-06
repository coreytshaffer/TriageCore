from triage_core.routing import ResilienceRouteInput, choose_resilience_route


def test_cloud_healthy_routes_high_complexity_work_to_primary_cloud():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            task_class="novel_design",
            complexity="high",
            sensitivity="low",
            required_checks=["human_review"],
        )
    )

    assert decision.selected_route == "cloud_primary"
    assert decision.reason == "cloud_primary_healthy_for_high_complexity_task"
    assert decision.fallback_depth == 0
    assert decision.required_checks == ["human_review"]


def test_cloud_credits_unavailable_routes_complex_work_to_local_heavy():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            task_class="large_refactor",
            complexity="high",
            cloud_credit_state="exhausted",
            local_heavy_available=True,
            memory_headroom_mb=8192,
        )
    )

    assert decision.selected_route == "local_heavy"
    assert decision.reason == "local_heavy_available_for_medium_or_complex_task"


def test_local_only_privacy_skips_cloud_routes():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            task_class="novel_design",
            complexity="high",
            privacy_level="local_only",
            cloud_primary_available=True,
            local_heavy_available=True,
            memory_headroom_mb=8192,
        )
    )

    assert decision.selected_route == "local_heavy"


def test_local_heavy_unavailable_routes_small_work_to_local_fast():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            task_class="docs_update",
            complexity="low",
            local_heavy_available=False,
            local_fast_available=True,
            memory_headroom_mb=2048,
        )
    )

    assert decision.selected_route == "local_fast"
    assert decision.fallback_depth == 3


def test_deterministic_task_uses_tool_route_first():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            task_class="schema_validation",
            deterministic_tool_available=True,
        )
    )

    assert decision.selected_route == "deterministic"
    assert decision.reason == "deterministic_tool_available_for_task_class"


def test_degraded_primary_cloud_uses_secondary_when_local_is_unavailable():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            task_class="security_review",
            complexity="high",
            sensitivity="low",
            cloud_secondary_available=True,
            recent_cloud_failures=3,
            lm_studio_ok=False,
        )
    )

    assert decision.selected_route == "cloud_secondary"
    assert decision.reason == "cloud_primary_degraded_using_secondary"


def test_high_sensitivity_routes_to_human_handoff():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            task_class="smoke_check_design",
            sensitivity="high",
            local_heavy_available=True,
            cloud_primary_available=True,
        )
    )

    assert decision.selected_route == "human_handoff"
    assert decision.human_review_required is True


def test_no_reliable_route_uses_human_handoff():
    decision = choose_resilience_route(
        ResilienceRouteInput(
            internet_ok=False,
            lm_studio_ok=False,
            deterministic_tool_available=False,
            cloud_primary_available=False,
            cloud_secondary_available=False,
        )
    )

    assert decision.selected_route == "human_handoff"
    assert decision.reason == "no_reliable_automated_route_available"
