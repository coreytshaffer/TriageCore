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

# Default singleton for convenience
default_config = Config()
