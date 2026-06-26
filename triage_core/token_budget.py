"""
Token budget model for TriageCore context planning.
Provides deterministic calculations for usable input tokens based on
conservative model profiles, reserved output space, and safety margins.
"""
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class TokenBudget:
    model_name: str
    context_window: int
    reserved_output_tokens: int
    safety_margin_tokens: int

    def __post_init__(self):
        if not self.model_name:
            raise ValueError("model_name must be non-empty")
        if self.context_window <= 0:
            raise ValueError("context_window must be positive")
        if self.reserved_output_tokens < 0:
            raise ValueError("reserved_output_tokens must be non-negative")
        if self.safety_margin_tokens < 0:
            raise ValueError("safety_margin_tokens must be non-negative")
        
        if self.usable_input_tokens <= 0:
            raise ValueError("usable_input_tokens must be positive")

    @property
    def usable_input_tokens(self) -> int:
        return self.context_window - self.reserved_output_tokens - self.safety_margin_tokens


MODEL_PROFILES: Dict[str, TokenBudget] = {
    "generic-8k": TokenBudget("generic-8k", 8192, 1024, 256),
    "generic-16k": TokenBudget("generic-16k", 16384, 2048, 512),
    "generic-32k": TokenBudget("generic-32k", 32768, 4096, 1024),
    "generic-128k": TokenBudget("generic-128k", 131072, 8192, 4096),
    "qwen2.5-coder-7b": TokenBudget("qwen2.5-coder-7b", 32768, 4096, 1024),
    "qwen3-30b-a3b": TokenBudget("qwen3-30b-a3b", 8192, 1024, 256),
}

def get_token_budget(profile_name: str) -> TokenBudget:
    """
    Returns a TokenBudget for a known model profile.
    Raises KeyError if the profile is unknown.
    """
    if profile_name not in MODEL_PROFILES:
        raise KeyError(f"Unknown model profile: {profile_name}")
    return MODEL_PROFILES[profile_name]
