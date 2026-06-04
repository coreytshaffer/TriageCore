import json
import os
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class SupervisorUsageRecord:
    task_id: str
    tool: str
    decision: str
    notes: str = ""
    model: str = ""
    profile: str = ""
    artifact_path: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    token_source: str = "imported_estimate"


@dataclass
class SupervisorUsageCandidate:
    path: str
    records: int
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


def load_supervisor_usage_records(
    path: str,
    default_tool: str = "",
    default_decision: str = "accepted",
    default_model: str = "",
    default_profile: str = "",
    default_notes: str = "",
    default_artifact_path: str = "",
    token_source: str = "imported_estimate",
) -> list[SupervisorUsageRecord]:
    """Load supervisor usage records from JSON, JSON array, or JSONL."""
    items = _load_items(path)
    records: list[SupervisorUsageRecord] = []
    for item in items:
        record = _coerce_record(
            item,
            default_tool=default_tool,
            default_decision=default_decision,
            default_model=default_model,
            default_profile=default_profile,
            default_notes=default_notes,
            default_artifact_path=default_artifact_path,
            token_source=token_source,
        )
        if record:
            records.append(record)
    return records


def scan_supervisor_usage_paths(
    paths: list[str],
    default_tool: str = "",
    token_source: str = "imported_estimate",
    max_file_bytes: int = 1_000_000,
) -> list[SupervisorUsageCandidate]:
    """Find JSON/JSONL files that contain importable supervisor usage records."""
    candidates: list[SupervisorUsageCandidate] = []
    for path in paths:
        for file_path in _candidate_files(path):
            try:
                if os.path.getsize(file_path) > max_file_bytes:
                    continue
                records = load_supervisor_usage_records(
                    file_path,
                    default_tool=default_tool,
                    token_source=token_source,
                )
            except (OSError, UnicodeDecodeError):
                continue
            if not records:
                continue
            candidates.append(
                SupervisorUsageCandidate(
                    path=file_path,
                    records=len(records),
                    total_input_tokens=sum(record.input_tokens for record in records),
                    total_output_tokens=sum(record.output_tokens for record in records),
                )
            )
    return candidates


def _candidate_files(path: str) -> Iterable[str]:
    if os.path.isfile(path):
        if _looks_like_usage_artifact(path):
            yield path
        return

    if not os.path.isdir(path):
        return

    for root, _, files in os.walk(path):
        for filename in files:
            file_path = os.path.join(root, filename)
            if _looks_like_usage_artifact(file_path):
                yield file_path


def _looks_like_usage_artifact(path: str) -> bool:
    lower = path.lower()
    return lower.endswith(".json") or lower.endswith(".jsonl")


def _load_items(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return _load_jsonl_items(text.splitlines())

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        if isinstance(parsed.get("records"), list):
            return [item for item in parsed["records"] if isinstance(item, dict)]
        if isinstance(parsed.get("supervisor_reviews"), list):
            return [item for item in parsed["supervisor_reviews"] if isinstance(item, dict)]
        return [parsed]
    return []


def _load_jsonl_items(lines: Iterable[str]) -> list[dict[str, Any]]:
    items = []
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            items.append(parsed)
    return items


def _coerce_record(
    item: dict[str, Any],
    default_tool: str,
    default_decision: str,
    default_model: str,
    default_profile: str,
    default_notes: str,
    default_artifact_path: str,
    token_source: str,
) -> SupervisorUsageRecord | None:
    task_id = _first_text(item, ["task_id", "taskId", "triage_task_id"])
    if not task_id:
        return None

    usage = item.get("usage") if isinstance(item.get("usage"), dict) else {}
    tool = _first_text(item, ["supervisor_tool", "tool", "source"]) or default_tool
    decision = _first_text(item, ["supervisor_decision", "decision"]) or default_decision
    model = _first_text(item, ["supervisor_model", "model", "model_name"]) or _first_text(
        usage, ["model", "model_name"]
    ) or default_model
    profile = _first_text(item, ["supervisor_profile", "profile", "mode"]) or default_profile
    notes = _first_text(item, ["supervisor_notes", "notes", "summary"]) or default_notes
    artifact_path = _first_text(
        item,
        ["supervisor_artifact_path", "artifact_path", "artifactPath", "path", "file"],
    ) or default_artifact_path
    input_tokens = _first_int(
        item,
        [
            "supervisor_input_tokens_est",
            "supervisor_input_tokens",
            "input_tokens",
            "prompt_tokens",
            "inputTokens",
            "promptTokens",
        ],
    ) or _first_int(usage, ["input_tokens", "prompt_tokens", "inputTokens", "promptTokens"])
    output_tokens = _first_int(
        item,
        [
            "supervisor_output_tokens_est",
            "supervisor_output_tokens",
            "output_tokens",
            "completion_tokens",
            "outputTokens",
            "completionTokens",
        ],
    ) or _first_int(usage, ["output_tokens", "completion_tokens", "outputTokens", "completionTokens"])
    record_token_source = _first_text(
        item,
        ["supervisor_token_source", "token_source", "tokenSource"],
    ) or token_source

    return SupervisorUsageRecord(
        task_id=task_id,
        tool=tool,
        decision=decision,
        notes=notes,
        model=model,
        profile=profile,
        artifact_path=artifact_path,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        token_source=record_token_source,
    )


def _first_text(item: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_int(item: dict[str, Any], keys: list[str]) -> int:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0
