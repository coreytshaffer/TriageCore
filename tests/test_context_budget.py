import json

from triage_core.context_budget import (
    build_context_pack,
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
