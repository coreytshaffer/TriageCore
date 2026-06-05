from triage_core.project_steward import ProjectSteward
from triage_core.work_orders import WorkOrder


def test_project_steward_escalates_sensitive_context_to_human_only():
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

    result = steward.evaluate(
        "Summarize the README.",
        target_files=["README.md"],
        completed_orders=[review_order],
    )

    assert result["local_result_status"] == "insufficient"
    assert result["recommended_escalation"] == "codex"
    assert "failed validation" in result["reason"]
