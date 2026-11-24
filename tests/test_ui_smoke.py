from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from triage_core.task_review_service import ReviewState


def test_ui_import_graceful_degradation():
    from triage_core.ui.app import UI_AVAILABLE, TriageDeskApp
    # As long as it imports without throwing an error when customtkinter isn't present,
    # or loads fine when it is, the smoke test passes.
    assert TriageDeskApp is not None


def test_ui_paths_use_config(tmp_path, monkeypatch):
    import os

    from triage_core.config import Config
    from triage_core.ui import app

    (tmp_path / "triagecore.toml").write_text(
        "\n".join(
            [
                "[paths]",
                'ledger_dir = "configured-ledger"',
                'tasks_dir = "configured-agent-tasks"',
                'codex_tasks_dir = "configured-codex-tasks"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(app, "default_config", Config(root_dir=str(tmp_path)))

    assert app._log_file_path() == os.path.join("configured-ledger", "triagecore.log")
    assert app._ledger_file_path() == os.path.join("configured-ledger", "ledger.jsonl")
    assert app._ipc_inbox_path() == os.path.join("configured-ledger", "ipc_inbox.json")
    assert app._codex_task_path("123456789") == os.path.join(
        "configured-codex-tasks",
        "codex_task_12345678.md",
    )
    assert app._antigravity_task_dir("123456789") == os.path.join(
        "configured-agent-tasks",
        "12345678",
    )


def test_ledger_detail_text_includes_review_and_benchmark_context():
    from triage_core.task_ledger import LegacyReviewObservation, TaskRecord
    from triage_core.ui.app import _ledger_detail_text

    task = TaskRecord(
        task_id="task-123",
        created_at="2026-06-04T01:00:00+00:00",
        updated_at="2026-06-04T01:05:00+00:00",
        title="Benchmark",
        description="Extract monitoring fields",
        runner="local_benchmark",
        status="reviewed",
        study_id="study_001",
        run_id="trial_002",
        backend_name="ollama",
        model="qwen2.5-coder:7b-triagecore",
        benchmark_task_id="json_extraction_small_v1",
        benchmark_category="structured_extraction",
        expected_status="success",
        observed_status="success",
        validator_passed=True,
        review=ReviewState(status="pending", pending_count=1),
        legacy_review_observation_count=2,
        legacy_review_history=[
            LegacyReviewObservation(
                event_id="unsigned-event",
                timestamp="2026-06-04T01:03:00+00:00",
                event_type="review_completed",
                decision="rejected",
                accepted=False,
                reported_outcome="unresolved",
            )
        ],
        supervisor_tool="codex",
        supervisor_model="gpt-5",
        supervisor_profile="high",
        supervisor_decision="needs_revision",
        supervisor_notes="Local draft needs tests.",
        supervisor_input_tokens_est=1200,
        supervisor_output_tokens_est=300,
        context_pack_path=".triagecore/context_packs/context_pack_task-123.json",
        context_estimated_tokens=640,
        context_budget_tokens=1200,
        context_budget_status="within_budget",
        artifact_paths=["reports/study_001_trial_002_benchmark_report.md"],
    )

    text = _ledger_detail_text(task)

    assert "Task ID: task-123" in text
    assert "Updated: 2026-06-04T01:05:00+00:00" in text
    assert "Review: Pending local confirmation" in text
    assert "Historical unsigned observations: 2" in text
    assert "Unsigned · 2026-06-04T01:03:00+00:00 · rejected · reported outcome unresolved" in text
    assert "Supervisor: tool=codex, decision=needs_revision, model=gpt-5" in text
    assert "tokens_est=1200 in/300 out" in text
    assert "Supervisor notes: Local draft needs tests." in text
    assert "Context budget: 640/1200 tokens (within_budget)" in text
    assert ".triagecore/context_packs/context_pack_task-123.json" in text
    assert "Benchmark: study=study_001, run=trial_002" in text
    assert "validator_passed=True" in text
    assert "reports/study_001_trial_002_benchmark_report.md" in text


def test_review_assessment_text_keeps_decision_signal_compact():
    from triage_core.task_ledger import TaskRecord
    from triage_core.ui.app import _review_assessment_text

    task = TaskRecord(
        task_id="task-456",
        runner="local_benchmark",
        status="handoff_generated",
        backend_name="ollama",
        model="qwen2.5-coder:7b-triagecore",
        expected_status="success",
        observed_status="handoff_required",
        human_review_required=True,
        total_tokens=128,
        energy_kwh_estimate=0.002,
        review_workload="high",
        supervisor_tool="antigravity",
        supervisor_decision="accepted",
    )

    text = _review_assessment_text(task)

    assert "Decision needed: review required before adoption" in text
    assert "Path: local_benchmark / ollama / qwen2.5-coder:7b-triagecore" in text
    assert "Supervisor: antigravity · accepted" in text
    assert "Benchmark: expected success, observed handoff_required" in text


def test_read_text_tail_returns_last_lines(tmp_path):
    from triage_core.ui.app import _read_text_tail

    path = tmp_path / "activity.log"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert _read_text_tail(str(path), max_lines=2) == "two\nthree\n"


def test_agent_state_helpers_are_human_readable():
    from triage_core.ui.app import _agent_display_name, _agent_state_style

    color, label = _agent_state_style("running")

    assert _agent_display_name("repo_mapper") == "Repo Mapper"
    assert color == "#22c55e"
    assert label == "Running"


def test_compact_ledger_line_prioritizes_recent_status():
    from triage_core.task_ledger import TaskRecord
    from triage_core.ui.app import _compact_ledger_line

    task = TaskRecord(
        task_id="abcdef123456",
        updated_at="2026-06-04T08:00:00+00:00",
        title="Review local draft",
        status="local_draft_generated",
        runner="local_llm",
        model="local-model",
        human_review_required=True,
        supervisor_tool="codex",
        supervisor_decision="needs_revision",
    )

    line = _compact_ledger_line(task)

    assert "2026-06-04T08:00:00+00:00" in line
    assert "Review local draft" in line
    assert "#abcdef12" in line
    assert "local draft generated" in line
    assert "review required" in line
    assert "supervisor: codex/needs_revision" in line


def test_dashboard_review_queue_uses_the_tasks_from_its_own_ledger(monkeypatch):
    from triage_core.task_ledger import TaskRecord
    from triage_core.ui import app

    def reject_other_ledger():
        pytest.fail("Dashboard must not query the repository-default review queue")

    monkeypatch.setattr(app, "_TD_ADAPTER_AVAILABLE", True)
    monkeypatch.setattr(app, "_td_adapter", SimpleNamespace(
        get_review_queue_snapshot=reject_other_ledger,
        get_status_snapshot=lambda: SimpleNamespace(
            git_status="clean", ledger_exists=True, ledger_writable=True, last_event_timestamp="recent",
        ),
    ))
    monkeypatch.setattr(app, "ctk", Mock())
    frame = Mock()
    frame.winfo_children.return_value = []
    desk = SimpleNamespace(
        _review_list_frame=frame,
        _review_queue_summary_lbl=Mock(),
        _op_reviews_lbl=Mock(),
        _op_adapter_lbl=Mock(),
        _op_repo_lbl=Mock(),
        _op_ledger_lbl=Mock(),
        _op_last_event_lbl=Mock(),
    )
    tasks = [
        TaskRecord(task_id="local-required", human_review_required=True),
        TaskRecord(
            task_id="local-mobile", human_review_required=False,
            review=ReviewState("verified", "accepted", pending_count=1),
        ),
        TaskRecord(
            task_id="local-complete", human_review_required=True,
            review=ReviewState("verified", "rejected"),
        ),
    ]

    app.TriageDeskApp._refresh_review_queue_panel(desk, tasks)
    app.TriageDeskApp._refresh_status_panel(desk, tasks)

    desk._op_reviews_lbl.configure.assert_called_once_with(text="1")
    assert desk._review_queue_summary_lbl.configure.call_args.kwargs["text"] == (
        "1 required reviews · 1 pending mobile requests"
    )
    labels = [call.kwargs["text"] for call in app.ctk.CTkLabel.call_args_list]
    assert len(labels) == 2
    assert labels[0].startswith("[local-mo]") and "pending local requests" in labels[0]
    assert labels[1].startswith("[local-re]")


def test_telemetry_local_benefit_metrics_are_evidence_bound():
    from triage_core.task_ledger import TaskRecord
    from triage_core.ui.app import _telemetry_local_benefit_metrics

    tasks = [
        TaskRecord(
            task_id="local-accepted",
            runner="local_llm",
            review=ReviewState(status="verified", decision="accepted"),
            total_tokens=100,
        ),
        TaskRecord(
            task_id="council-review",
            runner="worker_council",
            review=ReviewState(status="unavailable"),
            estimated_input_tokens=50,
            estimated_output_tokens=25,
            human_review_required=True,
        ),
        TaskRecord(
            task_id="codex-task",
            runner="codex",
            review=ReviewState(status="verified", decision="rejected"),
        ),
        TaskRecord(
            task_id="legacy-task",
            runner="codex",
            legacy_review_observation_count=3,
        ),
    ]

    metrics = _telemetry_local_benefit_metrics(tasks)

    assert metrics["accepted_yield_pct"] == 50.0
    assert metrics["local_first_pct"] == 50.0
    assert metrics["review_light_pct"] == 75.0
    assert metrics["local_tokens"] == 175
    assert metrics["local_accepted"] == 1
    assert metrics["binary_review_sample_size"] == 2
    assert metrics["excluded_from_binary_sample"] == 2
    assert metrics["excluded_review_observations"] == 3
    assert metrics["review_verification_status"] == "incomplete"


def test_telemetry_excludes_stale_evidence_without_reporting_a_verifier_failure():
    from triage_core.task_ledger import TaskRecord
    from triage_core.ui.app import _telemetry_local_benefit_metrics

    tasks = [
        TaskRecord(task_id="changed", review=ReviewState("evidence_changed")),
        TaskRecord(task_id="verified", review=ReviewState("verified", "accepted")),
    ]
    metrics = _telemetry_local_benefit_metrics(tasks)
    assert metrics["binary_review_sample_size"] == 1
    assert metrics["excluded_from_binary_sample"] == 1
    assert metrics["review_verification_status"] == "complete"
    assert metrics["evidence_changed_reviews"] == 1
    assert metrics["unavailable_reviews"] == 0


def test_telemetry_control_summary_surfaces_story_118_signals():
    from triage_core.task_ledger import TaskRecord
    from triage_core.ui.app import _telemetry_control_summary

    tasks = [
        TaskRecord(
            task_id="early-stop",
            updated_at="2026-06-04T10:00:00+00:00",
            early_stopped=True,
            early_stop_reason="Exceeded energy budget (0.0300 > 0.02).",
            total_tokens=400,
        ),
        TaskRecord(
            task_id="firewall",
            updated_at="2026-06-04T10:01:00+00:00",
            firewall_triggered=True,
            firewall_reason="Ethical Firewall: Triggered rule 'public_health_and_safety'.",
            total_tokens=300,
        ),
        TaskRecord(
            task_id="credit",
            updated_at="2026-06-04T10:02:00+00:00",
            credit_allowance_total=1000,
            credit_allowance_used=1100,
            credit_allowance_remaining=0,
            credit_allowance_exhausted=True,
            total_tokens=1100,
        ),
        TaskRecord(
            task_id="stability-1",
            updated_at="2026-06-04T10:03:00+00:00",
            runner="stability_pass",
            study_id="stability_pass",
            expected_status="success",
            observed_status="success",
        ),
        TaskRecord(
            task_id="stability-2",
            updated_at="2026-06-04T10:04:00+00:00",
            runner="stability_pass",
            study_id="stability_pass",
            expected_status="handoff_required",
            observed_status="handoff_required",
        ),
    ]

    summary = _telemetry_control_summary(
        tasks,
        log_tail="stability-pass completed status=success",
        token_credit_allowance=1000,
    )

    assert summary["early_stop"]["value"] == "1 event(s)"
    assert "Exceeded energy budget" in summary["early_stop"]["detail"]
    assert summary["firewall"]["value"] == "1 trigger(s)"
    assert "Ethical Firewall" in summary["firewall"]["detail"]
    assert summary["credit"]["value"] == "Exhausted"
    assert summary["credit"]["detail"] == "1800/1000 tokens used"
    assert summary["stability"]["value"] == "PASS"
    assert summary["stability"]["detail"] == "2/2 fixtures matched expected outcomes"
