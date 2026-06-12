import json

from triage_core.context_budget import (
    build_context_pack,
    context_pack_event_payload,
    create_context_pack_artifact,
    estimate_tokens,
)


def test_estimate_tokens_uses_conservative_character_ratio():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_context_pack_classifies_missing_and_existing_files(tmp_path):
    small_file = tmp_path / "small.py"
    small_file.write_text("print('hello')\n", encoding="utf-8")

    pack = build_context_pack(
        task_id="task-context",
        prompt="Repair this tiny script.",
        files=[str(small_file), str(tmp_path / "missing.py")],
        runner="local_llm",
        category="python_repair",
    )

    assert pack.budget_tokens == 2500
    assert pack.budget_status == "within_budget"
    assert [item.role for item in pack.items] == ["required", "helpful"]
    assert len(pack.excluded_items) == 1
    assert pack.excluded_items[0].exists is False


def test_create_context_pack_artifact_writes_json_payload(tmp_path):
    pack, path, payload = create_context_pack_artifact(
        task_id="abcdef123456",
        prompt="Summarize the README.",
        files=[],
        runner="codex",
        ledger_dir=str(tmp_path),
        category="log_summary",
    )

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["task_id"] == "abcdef123456"
    assert data["estimated_tokens"] == pack.estimated_tokens
    assert payload["context_pack_path"] == path
    assert payload["context_strategy"] == "context_budget_planner_v1"


def test_context_pack_marks_prompt_as_task_prompt_facet():
    pack = build_context_pack(
        task_id="task-facets",
        prompt="Repair this script.",
        files=[],
        runner="local_llm",
    )

    assert len(pack.items) == 1
    assert pack.items[0].facet == "task_prompt"
    assert pack.items[0].included is True


def test_context_pack_marks_files_as_target_file_facet(tmp_path):
    source_file = tmp_path / "example.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")

    pack = build_context_pack(
        task_id="task-files",
        prompt="Inspect the file.",
        files=[str(source_file)],
        runner="local_llm",
    )

    assert pack.items[1].facet == "target_file"
    assert pack.items[1].included is True


def test_context_pack_excludes_requested_facet():
    pack = build_context_pack(
        task_id="task-exclude",
        prompt="Do not include the prompt.",
        files=[],
        runner="local_llm",
        exclude_facets={"task_prompt"},
    )

    assert pack.items == []
    assert len(pack.excluded_items) == 1
    assert pack.excluded_items[0].facet == "task_prompt"
    assert pack.excluded_items[0].included is False
    assert "deterministic facet policy" in pack.excluded_items[0].rationale


def test_context_pack_counts_excluded_facets():
    pack = build_context_pack(
        task_id="task-count",
        prompt="Exclude the prompt.",
        files=[],
        runner="local_llm",
        exclude_facets={"task_prompt"},
    )

    payload = context_pack_event_payload(pack, "artifact.json")

    assert payload["context_excluded_items"] == 1


def test_context_pack_event_payload_has_no_raw_prompt_or_data(tmp_path):
    source_file = tmp_path / "example.py"
    source_file.write_text("print('hello')\n", encoding="utf-8")
    pack = build_context_pack(
        task_id="task-privacy",
        prompt="Sensitive prompt text.",
        files=[str(source_file)],
        runner="local_llm",
    )

    payload = context_pack_event_payload(pack, "artifact.json")
    payload_json = json.dumps(payload)

    assert "prompt" not in payload
    assert "data" not in payload
    assert "snippet" not in payload
    assert "Sensitive prompt text." not in payload_json
    assert "print('hello')" not in payload_json


def test_context_pack_preserves_existing_budget_behavior():
    pack = build_context_pack(
        task_id="task-budget",
        prompt="Repair the script.",
        files=[],
        runner="local_llm",
        category="python_repair",
    )

    assert pack.budget_tokens == 2500
    assert pack.budget_status == "within_budget"
    assert pack.estimated_tokens == estimate_tokens("Repair the script.")
