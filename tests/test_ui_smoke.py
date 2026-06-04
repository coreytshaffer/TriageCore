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
