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

class Config:
    def __init__(self, root_dir: str = "."):
        self.global_config_path = os.path.join(root_dir, "triagecore.toml")
        self.work_rules_path = os.path.join(root_dir, ".triagecore", "work_rules.toml")
        
        self.global_config = load_toml(self.global_config_path)
        self.work_rules = load_toml(self.work_rules_path)

    def get_global(self, section: str, key: str, default=None):
        return self.global_config.get(section, {}).get(key, default)
        
    def get_rule(self, section: str, key: str, default=None):
        return self.work_rules.get(section, {}).get(key, default)

    def get_worker_config(self, worker_name: str) -> dict:
        return self.work_rules.get("workers", {}).get(worker_name, {})

    def get_backend_type(self) -> str:
        return os.getenv(
            "TRIAGE_BACKEND_TYPE",
            self.get_global("backend", "default_type", "ollama"),
        )

    def get_backend_model(self) -> str:
        return os.getenv(
            "TRIAGE_MODEL",
            self.get_global("backend", "default_model", "qwen2.5-coder:7b"),
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

    def get_boundary_rules_path(self) -> str:
        return self.get_global("policies", "boundary_rules_path", "policies/cybernetic_ecology_boundary.yaml")

# Default singleton for convenience
default_config = Config()
