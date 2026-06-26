import pytest
from triage_core.context_planner import estimate_tokens_conservative, plan_context_for_text, ContextPlan
from triage_core.token_budget import TokenBudget

def test_estimate_tokens_conservative():
    assert estimate_tokens_conservative("") == 0
    assert estimate_tokens_conservative("a") == 1
    assert estimate_tokens_conservative("1234") == 1
    assert estimate_tokens_conservative("12345") == 1
    assert estimate_tokens_conservative("12345678") == 2

def test_plan_context_fits():
    budget = TokenBudget("test-model", 100, 10, 10)  # usable = 80
    text = "a" * (80 * 4)  # 320 chars -> 80 tokens
    plan = plan_context_for_text("some/path.txt", text, budget)
    
    assert plan.status == "fits"
    assert plan.estimated_input_tokens == 80
    assert "use full input" in plan.recommended_action

def test_plan_context_over_budget():
    budget = TokenBudget("test-model", 100, 10, 10)  # usable = 80
    text = "a" * (81 * 4)  # 324 chars -> 81 tokens
    plan = plan_context_for_text("some/path.txt", text, budget)
    
    assert plan.status == "over budget"
    assert plan.estimated_input_tokens == 81
    assert "include summary only" in plan.recommended_action
    assert "split into chunks" in plan.recommended_action
    assert "attach file reference" in plan.recommended_action

def test_plan_context_empty():
    budget = TokenBudget("test-model", 100, 10, 10)
    plan = plan_context_for_text("empty.txt", "", budget)
    assert plan.status == "fits"
    assert plan.estimated_input_tokens == 0
