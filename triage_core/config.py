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
    except Exception:
        # Parser diagnostics can quote arbitrary keys or values before CLI dispatch.
        print(f"Warning: Failed to parse TOML file {path}.")
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

    def read_governed_backend_configuration(self):
        """Read the attempt's endpoint inputs once, failing closed on an unreadable file.

        The credential is handed privately to backend construction. Only its presence
        belongs to the immutable effective configuration.
        """
        from .destination_policy import DestinationPolicyError, resolve_effective_configuration

        environment = dict(os.environ)
        try:
            with open(self.global_config_path, "rb") as stream:
                if tomllib is None:
                    raise DestinationPolicyError("configuration_unreadable")
                settings = tomllib.load(stream)
        except FileNotFoundError:
            settings = None
        except (OSError, ValueError):
            raise DestinationPolicyError("configuration_unreadable") from None

        try:
            configuration = resolve_effective_configuration(environment, settings)
        except OverflowError:
            raise DestinationPolicyError("configuration_unreadable") from None
        text_values = (configuration.backend_type, configuration.model, configuration.cloud_model)
        urls = (configuration.local_base_url, configuration.cloud_base_url)
        if not all(isinstance(item.value, str) for item in text_values):
            raise DestinationPolicyError("configuration_unreadable")
        if any(item.value is not None and not isinstance(item.value, str) for item in urls):
            raise DestinationPolicyError("configuration_unreadable")
        return configuration, environment.get("TRIAGE_QWEN_API_KEY")

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

    def get_qwen_api_key(self) -> str | None:
        return os.getenv("TRIAGE_QWEN_API_KEY")

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

    # --- [capability] (CR-DD-013) -------------------------------------------
    # Explicit operator capability declarations. Ordinary backend settings
    # (endpoint, enabled backend, model name) deliberately do NOT qualify: they
    # declare intent, not current executability.

    def get_capability_probe_record_path(self) -> str:
        """Path to an already-recorded local backend probe record, if any.

        Empty by default. Reading this file is the only capability input
        ``tc run`` consults; it never probes.
        """
        return self.get_global("capability", "local_probe_record_path", "")

    def get_capability_freshness_seconds(self) -> int:
        """Max age of a probe record, in seconds, before it becomes unknown."""
        return int(self.get_global("capability", "freshness_seconds", 300))

    def get_capability_declare_local_fast(self) -> bool:
        return bool(self.get_global("capability", "declare_local_fast", False))

    def get_capability_declare_local_heavy(self) -> bool:
        return bool(self.get_global("capability", "declare_local_heavy", False))

    def get_capability_local_fast_model(self) -> str:
        """Explicit model binding for the ``local_fast`` route class."""
        return str(self.get_global("capability", "local_fast_model", "")).strip()

    def get_capability_local_heavy_model(self) -> str:
        """Explicit model binding for the ``local_heavy`` route class."""
        return str(self.get_global("capability", "local_heavy_model", "")).strip()


default_config = Config()
