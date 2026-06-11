import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def load_toml(path: str) -> dict:
    if not tomllib or not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Warning: Failed to parse TOML file {path}: {e}")
        return {}


_BACKEND_ENV_OVERRIDES = {
    ("backend", "default_type"): "TRIAGE_BACKEND_TYPE",
    ("backend", "default_model"): "TRIAGE_MODEL",
    ("backend", "base_url"): "TRIAGE_BASE_URL",
    ("backend", "timeout_seconds"): "TRIAGE_TIMEOUT_SECONDS",
    ("qwen", "enabled"): "TRIAGE_QWEN_ENABLED",
    ("qwen", "api_key"): "TRIAGE_QWEN_API_KEY",
    ("qwen", "base_url"): "TRIAGE_QWEN_BASE_URL",
    ("qwen", "model"): "TRIAGE_QWEN_MODEL",
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    def __init__(self, root_dir: str = "."):
        self.global_config_path = os.path.join(root_dir, "triagecore.toml")
        self.work_rules_path = os.path.join(root_dir, ".triagecore", "work_rules.toml")

        self.global_config = load_toml(self.global_config_path)
        self.work_rules = load_toml(self.work_rules_path)

    def get_global(self, section: str, key: str, default=None):
        env_name = _BACKEND_ENV_OVERRIDES.get((section, key))
        if env_name and os.getenv(env_name) is not None:
            return os.getenv(env_name)
        if section == "backend" and key == "default_model":
            return self.global_config.get(section, {}).get(key, "auto")
        return self.global_config.get(section, {}).get(key, default)

    def get_rule(self, section: str, key: str, default=None):
        return self.work_rules.get(section, {}).get(key, default)

    def get_worker_config(self, worker_name: str) -> dict:
        return self.work_rules.get("workers", {}).get(worker_name, {})

    def get_backend_type(self) -> str:
        return os.getenv(
            "TRIAGE_BACKEND_TYPE",
            self.get_global("backend", "default_type", "lmstudio"),
        )

    def get_backend_model(self) -> str:
        return os.getenv(
            "TRIAGE_MODEL",
            self.get_global("backend", "default_model", "auto"),
        )

    def get_backend_base_url(self):
        return os.getenv(
            "TRIAGE_BASE_URL",
            self.get_global("backend", "base_url", None),
        )

    def get_ledger_dir(self) -> str:
        return self.get_global("paths", "ledger_dir", ".triagecore")

    def get_benchmarks_path(self) -> str:
        return self.get_global("paths", "benchmarks_path", "benchmarks/tasks.jsonl")

    def get_tasks_dir(self) -> str:
        return self.get_global("paths", "tasks_dir", ".agent_tasks")

    def get_codex_tasks_dir(self) -> str:
        return self.get_global("paths", "codex_tasks_dir", "triage_tasks")

    def get_report_path(self) -> str:
        return self.get_global("paths", "benchmark_report_path", "reports/benchmark-report.md")

    def get_timeout_seconds(self) -> int:
        return int(self.get_global("backend", "timeout_seconds", 30))

    def get_qwen_enabled(self) -> bool:
        env_value = os.getenv("TRIAGE_QWEN_ENABLED")
        if env_value is not None:
            return _env_bool("TRIAGE_QWEN_ENABLED", False)
        return bool(self.get_global("qwen", "enabled", False))

    def get_qwen_api_key(self):
        return self.get_global("qwen", "api_key", None)

    def get_qwen_base_url(self) -> str:
        return self.get_global(
            "qwen",
            "base_url",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )

    def get_qwen_model(self) -> str:
        return self.get_global("qwen", "model", "qwen-max")

    def get_boundary_rules_path(self) -> str:
        return self.get_global("policies", "boundary_rules_path", "policies/cybernetic_ecology_boundary.yaml")


default_config = Config()
