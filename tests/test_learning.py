import json
import os
import tempfile

from triage_core.learning import (
    append_learning_proposals,
    append_learning_review,
    build_learning_proposals,
    import_learning_seed_records,
    load_learning_proposals,
)
from triage_core.task_ledger import TaskRecord


def _seed_preflight() -> dict:
    return {
        "preflight_id": "preflight-1",
        "created_at": "2026-06-05T00:00:00Z",
        "source_project": "safetask-ai",
        "assignment_goal": "Classify a compliance copy task.",
        "task_class": "docs_update",
        "complexity": "low",
        "sensitivity": "medium",
        "required_context": ["policy excerpt"],
        "context_pack_type": "bounded_docs",
        "candidate_combo": "local-small+validator",
        "required_checks": ["schema_check"],
        "stop_conditions": ["missing_policy_source"],
        "human_review_required": True,
        "confidence_before_assignment": 0.72,
        "rationale": "Bounded source material with a required review gate.",
    }


def _seed_context_pack() -> dict:
    return {
        "context_pack_id": "context-1",
        "pack_type": "bounded_docs",
        "source_project": "safetask-ai",
        "task_goal": "Classify a compliance copy task.",
        "source_artifacts": ["docs/policy.md"],
        "constraints": ["do not approve routing automatically"],
        "required_checks": ["schema_check"],
        "budget_note": "Small enough for local review.",
    }


def _seed_outcome() -> dict:
    return {
        "task_id": "task-1",
        "preflight_id": "preflight-1",
        "context_pack_id": "context-1",
        "observed_at": "2026-06-05T00:05:00Z",
        "source_project": "safetask-ai",
        "source_artifacts": ["docs/policy.md"],
        "task_class": "docs_update",
        "complexity": "low",
        "sensitivity": "medium",
        "assignment_goal": "Classify a compliance copy task.",
        "model_combo": "local-small+validator",
        "tool_path": "local",
        "result_status": "accepted_with_review",
        "verification": {"schema_check": "passed"},
        "correction_burden": "low",
        "waste_signal": "low",
        "confidence_after_review": 0.84,
        "lesson": "Bounded docs can route locally when review gates stay explicit.",
        "human_review_required": True,
    }


def _write_seed_file(path: str, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def _write_seed_files(source_dir: str, outcome: dict | None = None) -> None:
    os.makedirs(source_dir, exist_ok=True)
    _write_seed_file(
        os.path.join(source_dir, "triagecore-assignment-preflights.safetask.jsonl"),
        [_seed_preflight()],
    )
    _write_seed_file(
        os.path.join(source_dir, "triagecore-context-packs.safetask.jsonl"),
        [_seed_context_pack()],
    )
    _write_seed_file(
        os.path.join(source_dir, "triagecore-assignment-outcomes.safetask.jsonl"),
        [outcome or _seed_outcome()],
    )


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


def test_import_learning_seed_records_dry_run_does_not_write():
    with tempfile.TemporaryDirectory() as temp_dir:
        source_dir = os.path.join(temp_dir, "examples")
        ledger_dir = os.path.join(temp_dir, "ledger")
        _write_seed_files(source_dir)

        result = import_learning_seed_records(source_dir, ledger_dir, dry_run=True)

        assert result.ok
        assert result.preflight_count == 1
        assert result.context_pack_count == 1
        assert result.outcome_count == 1
        assert not os.path.exists(os.path.join(ledger_dir, "learning_seeds"))


def test_import_learning_seed_records_rejects_broken_references():
    with tempfile.TemporaryDirectory() as temp_dir:
        source_dir = os.path.join(temp_dir, "examples")
        outcome = _seed_outcome()
        outcome["preflight_id"] = "missing-preflight"
        _write_seed_files(source_dir, outcome=outcome)

        result = import_learning_seed_records(source_dir, os.path.join(temp_dir, "ledger"), dry_run=True)

        assert not result.ok
        assert any("missing-preflight" in error for error in result.errors)


def test_import_learning_seed_records_write_is_idempotent():
    with tempfile.TemporaryDirectory() as temp_dir:
        source_dir = os.path.join(temp_dir, "examples")
        ledger_dir = os.path.join(temp_dir, "ledger")
        _write_seed_files(source_dir)

        first = import_learning_seed_records(source_dir, ledger_dir, dry_run=False)
        second = import_learning_seed_records(source_dir, ledger_dir, dry_run=False)

        assert first.ok
        assert first.total_imported == 3
        assert second.ok
        assert second.total_imported == 0
        with open(first.output_paths["outcomes"], "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        assert len(lines) == 1
