import pytest


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
    from triage_core.task_ledger import TaskRecord
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
        accepted=True,
        human_review_minutes=1.25,
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
    assert "Review: accepted, 1.25 review min" in text
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


def test_review_workload_value_maps_labels_to_ledger_values():
    from triage_core.ui.app import _review_workload_value

    assert _review_workload_value("Not set") == "not_recorded"
    assert _review_workload_value("Low") == "low"
    assert _review_workload_value("Medium") == "medium"
    assert _review_workload_value("High") == "high"
    assert _review_workload_value("Unexpected") == "not_recorded"


def test_telemetry_local_benefit_metrics_are_evidence_bound():
    from triage_core.task_ledger import TaskRecord
    from triage_core.ui.app import _telemetry_local_benefit_metrics

    tasks = [
        TaskRecord(
            task_id="local-accepted",
            runner="local_llm",
            accepted=True,
            total_tokens=100,
        ),
        TaskRecord(
            task_id="council-review",
            runner="worker_council",
            accepted=False,
            estimated_input_tokens=50,
            estimated_output_tokens=25,
            human_review_required=True,
        ),
        TaskRecord(task_id="codex-task", runner="codex", accepted=True),
    ]

    metrics = _telemetry_local_benefit_metrics(tasks)

    assert metrics["accepted_yield_pct"] == pytest.approx(66.666666)
    assert metrics["local_first_pct"] == pytest.approx(66.666666)
    assert metrics["review_light_pct"] == pytest.approx(66.666666)
    assert metrics["local_tokens"] == 175
    assert metrics["local_accepted"] == 1
