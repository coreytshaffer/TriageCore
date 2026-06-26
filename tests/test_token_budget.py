import pytest
from triage_core.token_budget import TokenBudget, get_token_budget

def test_token_budget_computation():
    budget = TokenBudget("test-model", 1000, 200, 100)
    assert budget.usable_input_tokens == 700

def test_invalid_model_name():
    with pytest.raises(ValueError, match="model_name must be non-empty"):
        TokenBudget("", 1000, 200, 100)

def test_invalid_negative_values():
    with pytest.raises(ValueError, match="context_window must be positive"):
        TokenBudget("m", 0, 100, 100)
    with pytest.raises(ValueError, match="context_window must be positive"):
        TokenBudget("m", -1, 100, 100)
    with pytest.raises(ValueError, match="reserved_output_tokens must be non-negative"):
        TokenBudget("m", 1000, -1, 100)
    with pytest.raises(ValueError, match="safety_margin_tokens must be non-negative"):
        TokenBudget("m", 1000, 200, -1)

def test_exceeding_context_window_fails():
    with pytest.raises(ValueError, match="usable_input_tokens must be positive"):
        TokenBudget("m", 1000, 800, 200)  # usable = 0
    with pytest.raises(ValueError, match="usable_input_tokens must be positive"):
        TokenBudget("m", 1000, 900, 200)  # usable = -100

def test_builtin_profiles():
    budget = get_token_budget("generic-8k")
    assert budget.model_name == "generic-8k"
    assert budget.context_window == 8192
    
    budget2 = get_token_budget("qwen2.5-coder-7b")
    assert budget2.model_name == "qwen2.5-coder-7b"

def test_unknown_profile():
    with pytest.raises(KeyError):
        get_token_budget("unknown-model")

def test_frozen_immutability():
    budget = get_token_budget("generic-8k")
    with pytest.raises(Exception):
        budget.context_window = 4000
