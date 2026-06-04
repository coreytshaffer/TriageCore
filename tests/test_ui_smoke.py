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
        artifact_paths=["reports/study_001_trial_002_benchmark_report.md"],
    )

    text = _ledger_detail_text(task)

    assert "Task ID: task-123" in text
    assert "Updated: 2026-06-04T01:05:00+00:00" in text
    assert "Review: accepted, 1.25 review min" in text
    assert "Benchmark: study=study_001, run=trial_002" in text
    assert "validator_passed=True" in text
    assert "reports/study_001_trial_002_benchmark_report.md" in text
