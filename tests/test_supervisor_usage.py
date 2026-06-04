import json

from triage_core.supervisor_usage import load_supervisor_usage_records
from triage_core.supervisor_usage import scan_supervisor_usage_paths


def test_load_supervisor_usage_records_from_json_object(tmp_path):
    path = tmp_path / "usage.json"
    path.write_text(
        json.dumps({
            "task_id": "task-1",
            "tool": "codex",
            "decision": "accepted",
            "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 45,
            },
        }),
        encoding="utf-8",
    )

    records = load_supervisor_usage_records(
        str(path),
        default_model="gpt-5",
        default_profile="high",
        token_source="imported_exact",
    )

    assert len(records) == 1
    assert records[0].task_id == "task-1"
    assert records[0].tool == "codex"
    assert records[0].decision == "accepted"
    assert records[0].model == "gpt-5"
    assert records[0].profile == "high"
    assert records[0].input_tokens == 123
    assert records[0].output_tokens == 45
    assert records[0].token_source == "imported_exact"


def test_load_supervisor_usage_records_from_jsonl_with_defaults(tmp_path):
    path = tmp_path / "usage.jsonl"
    path.write_text(
        "\n".join([
            json.dumps({"taskId": "task-1", "inputTokens": 10, "outputTokens": 4}),
            json.dumps({"taskId": "task-2", "prompt_tokens": 20, "completion_tokens": 8}),
        ]),
        encoding="utf-8",
    )

    records = load_supervisor_usage_records(
        str(path),
        default_tool="antigravity",
        default_decision="needs_revision",
        default_notes="Imported from IDE usage log.",
    )

    assert len(records) == 2
    assert records[0].tool == "antigravity"
    assert records[0].decision == "needs_revision"
    assert records[0].notes == "Imported from IDE usage log."
    assert records[0].input_tokens == 10
    assert records[0].output_tokens == 4
    assert records[1].input_tokens == 20
    assert records[1].output_tokens == 8


def test_load_supervisor_usage_records_skips_records_without_task_id(tmp_path):
    path = tmp_path / "usage.json"
    path.write_text(
        json.dumps([
            {"tool": "codex", "input_tokens": 10},
            {"task_id": "task-1", "input_tokens": 20},
        ]),
        encoding="utf-8",
    )

    records = load_supervisor_usage_records(str(path), default_tool="codex")

    assert len(records) == 1
    assert records[0].task_id == "task-1"


def test_scan_supervisor_usage_paths_finds_importable_jsonl(tmp_path):
    candidate = tmp_path / "usage.jsonl"
    candidate.write_text(
        "\n".join([
            json.dumps({"task_id": "task-1", "prompt_tokens": 10, "completion_tokens": 4}),
            json.dumps({"task_id": "task-2", "prompt_tokens": 20, "completion_tokens": 8}),
        ]),
        encoding="utf-8",
    )
    ignored = tmp_path / "notes.md"
    ignored.write_text("tokens: 999", encoding="utf-8")

    candidates = scan_supervisor_usage_paths([str(tmp_path)], default_tool="codex")

    assert len(candidates) == 1
    assert candidates[0].path == str(candidate)
    assert candidates[0].records == 2
    assert candidates[0].total_input_tokens == 30
    assert candidates[0].total_output_tokens == 12
    assert candidates[0].total_tokens == 42


def test_scan_supervisor_usage_paths_skips_large_files(tmp_path):
    candidate = tmp_path / "usage.json"
    candidate.write_text(
        json.dumps({"task_id": "task-1", "prompt_tokens": 10}),
        encoding="utf-8",
    )

    candidates = scan_supervisor_usage_paths([str(tmp_path)], max_file_bytes=5)

    assert candidates == []
