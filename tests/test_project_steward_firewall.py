import os
from unittest.mock import patch
from triage_core.project_steward import ProjectSteward
from triage_core.work_orders import WorkOrder


def test_project_steward_escalates_sensitive_context_to_human_only_fallback():
    # Force default fallback by patching get_boundary_rules_path to a missing file
    with patch("triage_core.project_steward.default_config.get_boundary_rules_path", return_value="missing_rules.yaml"):
        steward = ProjectSteward()
        
        result = steward.evaluate(
            "Generate a map overlay for Bloody Island.",
            target_files=[],
            completed_orders=[],
        )

        assert result["local_result_status"] == "insufficient"
        assert result["recommended_escalation"] == "human_only"
        assert "Sensitive context detected" in result["reason"]


def test_project_steward_escalates_failed_review_to_codex():
    steward = ProjectSteward()
    review_order = WorkOrder(
        task_id="review-1",
        assigned_role="review_worker",
        input_artifacts=[],
        output_required="Review local output.",
        result={"is_valid": False},
    )

    # Force fallback / verify review fail escalation
    with patch("triage_core.project_steward.default_config.get_boundary_rules_path", return_value="missing_rules.yaml"):
        result = steward.evaluate(
            "Summarize the README.",
            target_files=["README.md"],
            completed_orders=[review_order],
        )

        assert result["local_result_status"] == "insufficient"
        assert result["recommended_escalation"] == "codex"
        assert "failed validation" in result["reason"]


def test_project_steward_loads_rules_and_matches_terms():
    # Using the actual policies/cybernetic_ecology_boundary.yaml we created
    steward = ProjectSteward()
    assert len(steward.rules) > 0

    # 1. Tribal Sovereignty rule (decision: human_only)
    res1 = steward.evaluate("Select tribal region maps.", [], [])
    assert res1["local_result_status"] == "insufficient"
    assert res1["recommended_escalation"] == "human_only"
    assert "Triggered rule 'tribal_sovereignty_and_confidentiality'" in res1["reason"]

    # 2. Public health rule (decision: codex)
    res2 = steward.evaluate("Locate the water intake.", [], [])
    assert res2["local_result_status"] == "insufficient"
    assert res2["recommended_escalation"] == "codex"
    assert "Triggered rule 'public_health_and_safety'" in res2["reason"]

    # 3. Regulatory rule (decision: codex)
    res3 = steward.evaluate("Determine if this violates regulation.", [], [])
    assert res3["local_result_status"] == "insufficient"
    assert res3["recommended_escalation"] == "codex"
    assert "Triggered rule 'regulatory_interpretation'" in res3["reason"]


def test_project_steward_matches_regex_coordinates():
    steward = ProjectSteward()
    
    # Precise GPS coordinates (decision: human_only)
    res = steward.evaluate("Coordinate target is at 38°56'24\"N.", [], [])
    assert res["local_result_status"] == "insufficient"
    assert res["recommended_escalation"] == "human_only"
    assert "Triggered rule 'sensitive_coordinates'" in res["reason"]
