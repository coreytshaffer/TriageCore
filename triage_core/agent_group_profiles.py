"""Agent/model/runtime group profiles for controlled experiments."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .runtime_backends import SUPPORTED_BACKENDS, RuntimeBackendProfile


@dataclass(frozen=True)
class ExperimentAgent:
    role: str
    model: str
    runtime_backend: RuntimeBackendProfile
    token_budget: int
    required_output_contract: str

    def __post_init__(self) -> None:
        if not self.role:
            raise ValueError("agent role must be non-empty")
        if not self.model:
            raise ValueError("agent model must be non-empty")
        if self.token_budget <= 0:
            raise ValueError("agent token_budget must be positive")
        if not self.required_output_contract:
            raise ValueError("required_output_contract must be non-empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "model": self.model,
            "runtime_backend": self.runtime_backend.to_dict(),
            "token_budget": self.token_budget,
            "required_output_contract": self.required_output_contract,
        }


@dataclass(frozen=True)
class EscalationPolicy:
    enabled: bool = False
    escalate_on_quality_failure: bool = False
    max_escalations: int = 0

    def __post_init__(self) -> None:
        if self.max_escalations < 0:
            raise ValueError("max_escalations must be non-negative")
        if not self.enabled and self.max_escalations:
            raise ValueError("max_escalations requires enabled escalation_policy")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "escalate_on_quality_failure": self.escalate_on_quality_failure,
            "max_escalations": self.max_escalations,
        }


@dataclass(frozen=True)
class AgentGroupProfile:
    group_id: str
    description: str
    agents: Sequence[ExperimentAgent]
    escalation_policy: EscalationPolicy = field(default_factory=EscalationPolicy)
    max_agent_turns: int = 1
    allowed_tools: Sequence[str] = field(default_factory=tuple)
    runtime_backend_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("group_id must be non-empty")
        if not self.description:
            raise ValueError("description must be non-empty")
        if not self.agents:
            raise ValueError("agent group must include at least one agent")
        if self.max_agent_turns <= 0:
            raise ValueError("max_agent_turns must be positive")
        if len(self.agents) > self.max_agent_turns:
            raise ValueError("agent group exceeds max_agent_turns")

    @property
    def runtime_backend_names(self) -> List[str]:
        return [agent.runtime_backend.name for agent in self.agents]

    def validate_allowed_backends(self, allowed_runtime_backends: Sequence[str]) -> None:
        allowed = set(allowed_runtime_backends)
        unknown = allowed - SUPPORTED_BACKENDS
        if unknown:
            raise ValueError(f"unknown allowed runtime backend: {sorted(unknown)[0]}")
        for backend_name in self.runtime_backend_names:
            if backend_name not in allowed:
                raise ValueError(
                    f"runtime backend {backend_name} is not allowed for this experiment"
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "description": self.description,
            "agents": [agent.to_dict() for agent in self.agents],
            "escalation_policy": self.escalation_policy.to_dict(),
            "max_agent_turns": self.max_agent_turns,
            "allowed_tools": list(self.allowed_tools),
            "runtime_backend_metadata": self.runtime_backend_metadata,
        }
