"""
Dry-run context planning module.
Provides deterministic estimates of input tokens to verify safety limits
before full context assembly or LLM execution.
"""
from dataclasses import dataclass
from triage_core.token_budget import TokenBudget

@dataclass
class ContextPlan:
    input_path: str
    model_profile: str
    estimated_input_tokens: int
    usable_input_budget: int
    status: str
    recommended_action: str

def estimate_tokens_conservative(text: str) -> int:
    """
    Returns a conservative token estimate based on character count.
    Assuming roughly 4 characters per token.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)

def plan_context_for_text(path: str, text: str, budget: TokenBudget) -> ContextPlan:
    estimated = estimate_tokens_conservative(text)
    usable = budget.usable_input_tokens

    if estimated <= usable:
        status = "fits"
        recommended_action = "use full input"
    else:
        status = "over budget"
        recommended_action = "include summary only\nsplit into chunks\nattach file reference instead of full text"

    return ContextPlan(
        input_path=path,
        model_profile=budget.model_name,
        estimated_input_tokens=estimated,
        usable_input_budget=usable,
        status=status,
        recommended_action=recommended_action
    )
