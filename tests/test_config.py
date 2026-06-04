from pathlib import Path

from triage_core.config import Config


def test_config_reads_project_defaults(tmp_path):
    config_path = tmp_path / "triagecore.toml"
    config_path.write_text(
        "\n".join(
            [
                "[backend]",
                'default_type = "custom"',
                'default_model = "local-test-model"',
                'base_url = "http://localhost:1234/v1"',
                "timeout_seconds = 45",
                "",
                "[paths]",
                'ledger_dir = ".custom-ledger"',
                'tasks_dir = ".custom-tasks"',
                'codex_tasks_dir = "custom-codex-tasks"',
                'benchmarks_path = "custom/benchmarks.jsonl"',
                'benchmark_report_path = "custom/report.md"',
            ]
        ),
        encoding="utf-8",
    )

    config = Config(root_dir=str(tmp_path))

    assert config.get_backend_type() == "custom"
    assert config.get_backend_model() == "local-test-model"
    assert config.get_backend_base_url() == "http://localhost:1234/v1"
    assert config.get_timeout_seconds() == 45
    assert config.get_ledger_dir() == ".custom-ledger"
    assert config.get_tasks_dir() == ".custom-tasks"
    assert config.get_codex_tasks_dir() == "custom-codex-tasks"
    assert config.get_benchmarks_path() == "custom/benchmarks.jsonl"
    assert config.get_report_path() == "custom/report.md"


def test_config_environment_overrides_backend_values(tmp_path, monkeypatch):
    (tmp_path / "triagecore.toml").write_text(
        "\n".join(
            [
                "[backend]",
                'default_type = "ollama"',
                'default_model = "configured-model"',
                'base_url = "http://configured.local/v1"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "vllm")
    monkeypatch.setenv("TRIAGE_MODEL", "env-model")
    monkeypatch.setenv("TRIAGE_BASE_URL", "http://env.local/v1")

    config = Config(root_dir=str(tmp_path))

    assert config.get_backend_type() == "vllm"
    assert config.get_backend_model() == "env-model"
    assert config.get_backend_base_url() == "http://env.local/v1"
