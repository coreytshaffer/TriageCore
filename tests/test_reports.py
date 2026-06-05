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
    assert report.by_backend[0].label == "ollama"
    assert report.by_backend[0].runs == 2
    assert report.by_supervision[0].label == "local-only"
    assert report.by_supervision[0].runs == 2
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
    assert "## By Supervision" in markdown
    assert "## By Backend" in markdown
    assert "| local-only | 1 | 100.0%" in markdown
    assert "| custom | 1 | 100.0%" in markdown
    assert "100.0%" in markdown


def test_build_benchmark_report_groups_supervised_workflows():
    report = build_benchmark_report([
        TaskRecord(
            task_id="local-task",
            benchmark_task_id="log_summary_markdown_v1",
            benchmark_category="log_summary",
            observed_status="success",
        ),
        TaskRecord(
            task_id="codex-task",
            benchmark_task_id="log_summary_markdown_v1",
            benchmark_category="log_summary",
            observed_status="success",
            supervisor_tool="codex",
            supervisor_decision="accepted",
            supervisor_input_tokens_est=100,
            supervisor_output_tokens_est=25,
            supervisor_token_source="imported_exact",
        ),
        TaskRecord(
            task_id="antigravity-task",
            benchmark_task_id="log_summary_markdown_v1",
            benchmark_category="log_summary",
            observed_status="handoff_required",
            supervisor_tool="antigravity",
            supervisor_decision="needs_revision",
            supervisor_input_tokens_est=200,
            supervisor_output_tokens_est=50,
        ),
    ])

    labels = [summary.label for summary in report.by_supervision]
    supervisor_labels = [summary.label for summary in report.supervisor_reviews]
    markdown = render_benchmark_report_markdown(report)

    assert labels == ["antigravity-supervised", "codex-supervised", "local-only"]
    assert supervisor_labels == ["antigravity", "codex"]
    assert "| antigravity-supervised | 1 | 0.0%" in markdown
    assert "| codex-supervised | 1 | 100.0%" in markdown
    assert "| local-only | 1 | 100.0%" in markdown
    assert "## Supervisor Reviews" in markdown
    assert "| antigravity | 1 | 0 | 1 | 0 | 0 | 0 | 200 | 50 | 250 |" in markdown
    assert "| codex | 1 | 1 | 0 | 0 | 0 | 1 | 100 | 25 | 125 |" in markdown


def test_supervisor_review_summary_respects_study_and_run_filters():
    report = build_benchmark_report([
        TaskRecord(
            task_id="study-task",
            study_id="study_002",
            run_id="trial_001",
            benchmark_task_id="log_summary_markdown_v1",
            observed_status="success",
            supervisor_tool="codex",
            supervisor_decision="accepted",
            supervisor_input_tokens_est=300,
            supervisor_output_tokens_est=90,
            supervisor_token_source="imported_exact",
        ),
        TaskRecord(
            task_id="other-study-task",
            study_id="study_002",
            run_id="trial_002",
            benchmark_task_id="log_summary_markdown_v1",
            observed_status="success",
            supervisor_tool="antigravity",
            supervisor_decision="escalated",
            supervisor_input_tokens_est=500,
            supervisor_output_tokens_est=120,
        ),
    ], study_id="study_002", run_id="trial_001")

    markdown = render_benchmark_report_markdown(report)

    assert len(report.supervisor_reviews) == 1
    assert report.supervisor_reviews[0].label == "codex"
    assert report.supervisor_reviews[0].accepted == 1
    assert report.supervisor_reviews[0].total_tokens_est == 390
    assert report.supervisor_reviews[0].exact_token_records == 1
    assert "| codex | 1 | 1 | 0 | 0 | 0 | 1 | 300 | 90 | 390 |" in markdown
    assert "antigravity" not in markdown


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


def test_build_benchmark_report_includes_runner_and_wasted_tokens():
    records = [
        TaskRecord(
            task_id="task-1",
            benchmark_task_id="python_generation_small_v1",
            benchmark_category="python_generation",
            expected_status="success",
            observed_status="success",
            runner="council",
            total_tokens=100,
            wasted_tokens=20,
        ),
        TaskRecord(
            task_id="task-2",
            benchmark_task_id="python_repair_syntax_v1",
            benchmark_category="python_repair",
            expected_status="success",
            observed_status="handoff_required",
            runner="pipeline",
            total_tokens=200,
            wasted_tokens=200,
        ),
    ]

    report = build_benchmark_report(records)

    assert report.total_runs == 2
    assert report.overall.total_wasted_tokens == 220
    assert len(report.by_runner) == 2
    assert report.by_runner[0].label == "council"
    assert report.by_runner[0].total_wasted_tokens == 20
    assert report.by_runner[1].label == "pipeline"
    assert report.by_runner[1].total_wasted_tokens == 200

    markdown = render_benchmark_report_markdown(report)
    assert "## By Runner" in markdown
    # efficiency for council: 80% (80.0%)
    # efficiency for pipeline: 0% (0.0%)
    assert "| council | 1 | 100.0% |" in markdown
    assert "| pipeline | 1 | 0.0% |" in markdown
