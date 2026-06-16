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


def test_config_reads_qwen_non_secret_settings(tmp_path):
    (tmp_path / "triagecore.toml").write_text(
        "\n".join(
            [
                "[qwen]",
                "enabled = true",
                'base_url = "https://configured.qwen/v1"',
                'model = "qwen-plus"',
            ]
        ),
        encoding="utf-8",
    )

    config = Config(root_dir=str(tmp_path))

    assert config.get_qwen_enabled() is True
    assert config.get_qwen_api_key() is None
    assert config.get_qwen_base_url() == "https://configured.qwen/v1"
    assert config.get_qwen_model() == "qwen-plus"


def test_config_ignores_qwen_api_key_from_project_config(tmp_path, monkeypatch):
    monkeypatch.delenv("TRIAGE_QWEN_API_KEY", raising=False)
    (tmp_path / "triagecore.toml").write_text(
        "\n".join(
            [
                "[qwen]",
                'api_key = "configured-qwen-key"',
            ]
        ),
        encoding="utf-8",
    )

    config = Config(root_dir=str(tmp_path))

    assert config.get_qwen_api_key() is None


def test_config_environment_overrides_qwen_settings(tmp_path, monkeypatch):
    (tmp_path / "triagecore.toml").write_text(
        "\n".join(
            [
                "[qwen]",
                "enabled = false",
                'api_key = "configured-qwen-key"',
                'base_url = "https://configured.qwen/v1"',
                'model = "configured-qwen-model"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "true")
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "env-qwen-key")
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", "https://env.qwen/v1")
    monkeypatch.setenv("TRIAGE_QWEN_MODEL", "env-qwen-model")

    config = Config(root_dir=str(tmp_path))

    assert config.get_qwen_enabled() is True
    assert config.get_qwen_api_key() == "env-qwen-key"
    assert config.get_qwen_base_url() == "https://env.qwen/v1"
    assert config.get_qwen_model() == "env-qwen-model"
