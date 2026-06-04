import tempfile

from triage_core.learning import (
    append_learning_proposals,
    append_learning_review,
    build_learning_proposals,
    load_learning_proposals,
)
from triage_core.task_ledger import TaskRecord


def test_build_learning_proposal_from_benchmark_mismatch():
    record = TaskRecord(
        task_id="task-1",
        benchmark_category="python_repair",
        expected_status="success",
        observed_status="handoff_required",
        handoff_reason="Validator failed.",
    )

    proposals = build_learning_proposals([record])

    assert len(proposals) == 2
    triggers = {proposal.trigger for proposal in proposals}
    assert "benchmark_status_mismatch:python_repair" in triggers
    assert "unexpected_handoff:python_repair" in triggers


def test_append_learning_proposals_deduplicates_ids():
    record = TaskRecord(
        task_id="task-1",
        benchmark_category="python_repair",
        expected_status="success",
        observed_status="handoff_required",
        handoff_reason="Validator failed.",
    )
    proposals = build_learning_proposals([record])

    with tempfile.TemporaryDirectory() as temp_dir:
        path = f"{temp_dir}/learning_proposals.jsonl"

        first_write = append_learning_proposals(path, proposals)
        second_write = append_learning_proposals(path, proposals)
        loaded = load_learning_proposals(path)

        assert len(first_write) == len(proposals)
        assert second_write == []
        assert len(loaded) == len(proposals)


def test_append_learning_review_records_human_decision():
    with tempfile.TemporaryDirectory() as temp_dir:
        path = f"{temp_dir}/learning_reviews.jsonl"

        review = append_learning_review(
            path=path,
            proposal_id="abc123",
            decision="accepted",
            notes="Good evidence.",
        )

        assert review["proposal_id"] == "abc123"
        assert review["decision"] == "accepted"
        assert review["notes"] == "Good evidence."
