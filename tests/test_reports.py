from triage_core.reports import build_benchmark_report, render_benchmark_report_markdown
from triage_core.task_ledger import TaskRecord


def test_build_benchmark_report_summarizes_model_and_category():
    records = [
        TaskRecord(
            task_id="task-1",
            benchmark_task_id="python_generation_small_v1",
            benchmark_category="python_generation",
            expected_status="success",
            observed_status="success",
            backend_name="ollama",
            model="qwen2.5-coder:7b",
            elapsed_seconds=2.0,
            total_tokens=100,
            tokens_per_second=50.0,
            validator_passed=True,
        ),
        TaskRecord(
            task_id="task-2",
            benchmark_task_id="python_repair_syntax_v1",
            benchmark_category="python_repair",
            expected_status="success",
            observed_status="handoff_required",
            backend_name="ollama",
            model="qwen2.5-coder:7b",
            elapsed_seconds=4.0,
            total_tokens=40,
            tokens_per_second=10.0,
            validator_passed=False,
            handoff_reason="Local output failed quality gate validation.",
        ),
        TaskRecord(task_id="non-benchmark"),
    ]

    report = build_benchmark_report(records)

    assert report.total_runs == 2
    assert report.overall.runs == 2
    assert report.overall.successes == 1
    assert report.overall.handoffs == 1
    assert report.overall.mismatches == 1
    assert report.overall.validator_failures == 1
    assert report.overall.total_tokens == 140
    assert report.overall.average_elapsed_seconds == 3.0
    assert report.overall.average_tokens_per_second == 30.0
    assert report.by_model[0].label == "ollama/qwen2.5-coder:7b"
    assert report.by_category[0].label == "python_generation"
    assert report.by_category[1].label == "python_repair"


def test_render_benchmark_report_markdown_handles_empty_report():
    report = build_benchmark_report([])

    markdown = render_benchmark_report_markdown(report)

    assert "# Benchmark Report" in markdown
    assert "_No benchmark evidence found._" in markdown


def test_render_benchmark_report_markdown_includes_rates():
    report = build_benchmark_report([
        TaskRecord(
            task_id="task-1",
            benchmark_task_id="log_summary_markdown_v1",
            benchmark_category="log_summary",
            expected_status="success",
            observed_status="success",
            backend_name="custom",
            model="local-model",
        )
    ])

    markdown = render_benchmark_report_markdown(report)

    assert "custom/local-model" in markdown
    assert "100.0%" in markdown


def test_build_benchmark_report_filters_by_study_id():
    report = build_benchmark_report([
        TaskRecord(
            task_id="study-task",
            study_id="study_001",
            benchmark_task_id="log_summary_markdown_v1",
            benchmark_category="log_summary",
            expected_status="success",
            observed_status="success",
        ),
        TaskRecord(
            task_id="exploratory-task",
            benchmark_task_id="log_summary_markdown_v1",
            benchmark_category="log_summary",
            expected_status="success",
            observed_status="handoff_required",
        ),
    ], study_id="study_001")

    markdown = render_benchmark_report_markdown(report)

    assert report.total_runs == 1
    assert report.overall.successes == 1
    assert report.overall.mismatches == 0
    assert "Study ID: `study_001`" in markdown


def test_build_benchmark_report_filters_by_run_id():
    report = build_benchmark_report([
        TaskRecord(
            task_id="trial-task",
            study_id="study_001",
            run_id="trial_001",
            benchmark_task_id="json_extraction_small_v1",
            benchmark_category="structured_extraction",
            expected_status="success",
            observed_status="handoff_required",
            validator_passed=False,
        ),
        TaskRecord(
            task_id="other-trial-task",
            study_id="study_001",
            run_id="trial_002",
            benchmark_task_id="json_extraction_small_v1",
            benchmark_category="structured_extraction",
            expected_status="success",
            observed_status="success",
            validator_passed=True,
        ),
    ], study_id="study_001", run_id="trial_001")

    markdown = render_benchmark_report_markdown(report)

    assert report.total_runs == 1
    assert report.overall.handoffs == 1
    assert report.overall.mismatches == 1
    assert report.overall.validator_failures == 1
    assert "Study ID: `study_001`" in markdown
    assert "Run ID: `trial_001`" in markdown
