import pytest

from triage_core.agent_group_profiles import (
    AgentGroupProfile,
    EscalationPolicy,
    ExperimentAgent,
)
from triage_core.runtime_backends import RuntimeBackendProfile


def agent(role="worker", model="qwen2.5-coder-7b", backend=None):
    if backend is None:
        backend = RuntimeBackendProfile.ollama(model=model)
    return ExperimentAgent(
        role=role,
        model=model,
        runtime_backend=backend,
        token_budget=1000,
        required_output_contract="route_decision_review_packet.v1",
    )


def test_valid_single_large_model_group_loads():
    group = AgentGroupProfile(
        group_id="single_large_model",
        description="One larger model handles the whole task.",
        agents=[
            agent(
                model="qwen3-coder-30b",
                backend=RuntimeBackendProfile.llama_cpp(
                    model_file="qwen3-coder-30b.gguf",
                    quantization="Q4_K_M",
                ),
            )
        ],
    )

    assert group.to_dict()["group_id"] == "single_large_model"
    assert group.runtime_backend_names == ["llama_cpp"]


def test_valid_small_specialist_agent_group_loads():
    group = AgentGroupProfile(
        group_id="small_specialist_agents",
        description="Planner, executor, and reviewer are small bounded agents.",
        agents=[agent("planner"), agent("executor"), agent("reviewer")],
        max_agent_turns=3,
    )

    assert [a["role"] for a in group.to_dict()["agents"]] == [
        "planner",
        "executor",
        "reviewer",
    ]


def test_valid_escalation_group_loads():
    group = AgentGroupProfile(
        group_id="small_first_escalation",
        description="Small model first, larger model only after quality failure.",
        agents=[
            agent("executor"),
            agent(
                "escalation_reviewer",
                model="qwen3-coder-30b",
                backend=RuntimeBackendProfile.llama_cpp("qwen3-coder-30b.gguf"),
            ),
        ],
        escalation_policy=EscalationPolicy(
            enabled=True,
            escalate_on_quality_failure=True,
            max_escalations=1,
        ),
        max_agent_turns=2,
    )

    assert group.to_dict()["escalation_policy"]["max_escalations"] == 1


def test_group_with_no_agents_fails():
    with pytest.raises(ValueError, match="at least one agent"):
        AgentGroupProfile(
            group_id="empty",
            description="Invalid empty group.",
            agents=[],
        )


def test_group_exceeding_max_agent_turns_fails():
    with pytest.raises(ValueError, match="exceeds max_agent_turns"):
        AgentGroupProfile(
            group_id="too_many_turns",
            description="Invalid turn limit.",
            agents=[agent("planner"), agent("executor")],
            max_agent_turns=1,
        )
