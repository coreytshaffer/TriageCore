from dataclasses import dataclass
from typing import Dict, Iterable, List

from .task_ledger import TaskRecord


@dataclass
class BenchmarkSummary:
    label: str
    runs: int = 0
    successes: int = 0
    handoffs: int = 0
    mismatches: int = 0
    validator_failures: int = 0
    total_elapsed_seconds: float = 0.0
    total_tokens: int = 0
    total_tokens_per_second: float = 0.0
    token_speed_runs: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0

    @property
    def handoff_rate(self) -> float:
        return self.handoffs / self.runs if self.runs else 0.0

    @property
    def average_elapsed_seconds(self) -> float:
        return self.total_elapsed_seconds / self.runs if self.runs else 0.0

    @property
    def average_tokens_per_second(self) -> float:
        if not self.token_speed_runs:
            return 0.0
        return self.total_tokens_per_second / self.token_speed_runs


@dataclass
class BenchmarkReport:
    total_runs: int
    overall: BenchmarkSummary
    by_backend: List[BenchmarkSummary]
    by_model: List[BenchmarkSummary]
    by_category: List[BenchmarkSummary]
    study_id: str | None = None
    run_id: str | None = None


def build_benchmark_report(
    records: Iterable[TaskRecord],
    study_id: str | None = None,
    run_id: str | None = None,
) -> BenchmarkReport:
    benchmark_records = [record for record in records if record.benchmark_task_id]
    if study_id:
        benchmark_records = [record for record in benchmark_records if record.study_id == study_id]
    if run_id:
        benchmark_records = [record for record in benchmark_records if record.run_id == run_id]

    overall = BenchmarkSummary(label="overall")
    by_backend: Dict[str, BenchmarkSummary] = {}
    by_model: Dict[str, BenchmarkSummary] = {}
    by_category: Dict[str, BenchmarkSummary] = {}

    for record in benchmark_records:
        _apply_record(overall, record)
        backend = record.backend_name or "unknown-backend"
        _apply_record(by_backend.setdefault(backend, BenchmarkSummary(label=backend)), record)
        _apply_record(by_model.setdefault(_model_label(record), BenchmarkSummary(label=_model_label(record))), record)
        category = record.benchmark_category or "uncategorized"
        _apply_record(by_category.setdefault(category, BenchmarkSummary(label=category)), record)

    return BenchmarkReport(
        total_runs=len(benchmark_records),
        overall=overall,
        by_backend=_sorted_summaries(by_backend),
        by_model=_sorted_summaries(by_model),
        by_category=_sorted_summaries(by_category),
        study_id=study_id,
        run_id=run_id,
    )


def render_benchmark_report_markdown(report: BenchmarkReport) -> str:
    lines = [
        "# Benchmark Report",
        "",
    ]
    if report.study_id:
        lines.extend([
            f"Study ID: `{report.study_id}`",
            "",
        ])
    if report.run_id:
        lines.extend([
            f"Run ID: `{report.run_id}`",
            "",
        ])
    lines.extend([
        "## Overall",
        "",
        _summary_table([report.overall]),
        "",
        "## By Backend",
        "",
        _summary_table(report.by_backend),
        "",
        "## By Model",
        "",
        _summary_table(report.by_model),
        "",
        "## By Category",
        "",
        _summary_table(report.by_category),
    ])
    return "\n".join(lines)


def _apply_record(summary: BenchmarkSummary, record: TaskRecord) -> None:
    summary.runs += 1
    if record.observed_status == "success":
        summary.successes += 1
    if record.observed_status == "handoff_required" or record.handoff_reason:
        summary.handoffs += 1
    if record.expected_status and record.observed_status and record.expected_status != record.observed_status:
        summary.mismatches += 1
    if record.validator_passed is False:
        summary.validator_failures += 1

    summary.total_elapsed_seconds += record.elapsed_seconds
    summary.total_tokens += record.total_tokens
    if record.tokens_per_second > 0:
        summary.total_tokens_per_second += record.tokens_per_second
        summary.token_speed_runs += 1


def _model_label(record: TaskRecord) -> str:
    backend = record.backend_name or "unknown-backend"
    model = record.model or "unknown-model"
    return f"{backend}/{model}"


def _sorted_summaries(groups: Dict[str, BenchmarkSummary]) -> List[BenchmarkSummary]:
    return sorted(groups.values(), key=lambda item: item.label)


def _summary_table(summaries: List[BenchmarkSummary]) -> str:
    if not summaries:
        return "_No benchmark evidence found._"

    rows = [
        "| Group | Runs | Success Rate | Handoff Rate | Mismatches | Validator Failures | Avg Seconds | Total Tokens | Avg Tok/s |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        rows.append(
            "| "
            + " | ".join(
                [
                    summary.label,
                    str(summary.runs),
                    _format_percent(summary.success_rate),
                    _format_percent(summary.handoff_rate),
                    str(summary.mismatches),
                    str(summary.validator_failures),
                    f"{summary.average_elapsed_seconds:.2f}",
                    str(summary.total_tokens),
                    f"{summary.average_tokens_per_second:.2f}",
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"
