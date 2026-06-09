import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .validators import ErrorWarningMarkdownValidator, MonitoringJsonValidator, PythonSyntaxValidator, ModestToolsValidator, CyberneticReportValidator


class ValidatorWrapper:
    def __init__(self, func: Callable[[str], bool], name: str, scope: str, version: str = "1"):
        self.func = func
        self.name = name
        self.scope = scope
        self.version = version

    def __call__(self, text: str) -> bool:
        return self.func(text)


@dataclass
class BenchmarkTask:
    task_id: str
    category: str
    prompt: str
    data: str
    validator: Optional[str] = None
    expected_status: str = "success"
    target_files: List[str] = field(default_factory=list)
    notes: str = ""


def load_benchmark_tasks(path: str) -> List[BenchmarkTask]:
    benchmark_path = Path(path)
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark task file not found: {path}")

    tasks: List[BenchmarkTask] = []
    with benchmark_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            try:
                tasks.append(BenchmarkTask(**payload))
            except TypeError as exc:
                raise ValueError(f"Invalid benchmark task on line {line_number}: {exc}") from exc

    return tasks


def resolve_validator(name: Optional[str]) -> Optional[Callable[[str], bool]]:
    if name in (None, "", "none"):
        return None
    if name == "python_syntax":
        return ValidatorWrapper(PythonSyntaxValidator.validate, "python_syntax", "syntax_only")
    if name == "monitoring_json":
        return ValidatorWrapper(MonitoringJsonValidator.validate, "monitoring_json", "json_format")
    if name == "error_warning_markdown":
        return ValidatorWrapper(ErrorWarningMarkdownValidator.validate, "error_warning_markdown", "markdown_format")
    if name == "modest_tools":
        return ValidatorWrapper(ModestToolsValidator.validate, "modest_tools", "dependency_check")
    if name == "cybernetic_report":
        return ValidatorWrapper(CyberneticReportValidator.validate, "cybernetic_report", "ethical_report")
    raise ValueError(f"Unknown benchmark validator: {name}")


def result_to_model_event(task: BenchmarkTask, result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "benchmark_task_id": task.task_id,
        "benchmark_category": task.category,
        "expected_status": task.expected_status,
        "observed_status": result.get("status"),
        "backend_name": result.get("backend_name"),
        "model": result.get("model"),
        "timeout_seconds": result.get("timeout_seconds"),
        "elapsed_seconds": result.get("elapsed_seconds", 0.0),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "total_tokens": result.get("total_tokens", 0),
        "tokens_per_second": result.get("tokens_per_second", 0.0),
        "validator_passed": result.get("validator_passed"),
        "worker_result_status": result.get("worker_result_status", "not_attempted"),
        "failure_type": result.get("failure_type"),
        "failure_stage": result.get("failure_stage"),
        "validation_status": result.get("validation_status", "not_run"),
        "validator_name": result.get("validator_name"),
        "validator_version": result.get("validator_version"),
        "validator_scope": result.get("validator_scope"),
        "handoff_reason": result.get("handoff_reason") or result.get("reason"),
        "early_stopped": result.get("early_stopped", False),
        "early_stop_reason": result.get("early_stop_reason", ""),
        "firewall_triggered": result.get("firewall_triggered", False),
        "firewall_reason": result.get("firewall_reason", ""),
        "credit_allowance_total": result.get("credit_allowance_total", 0),
        "credit_allowance_used": result.get("credit_allowance_used", 0),
        "credit_allowance_remaining": result.get("credit_allowance_remaining", 0),
        "credit_allowance_exhausted": result.get("credit_allowance_exhausted", False),
    }
