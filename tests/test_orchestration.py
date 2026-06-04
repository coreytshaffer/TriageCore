import pytest
from unittest.mock import MagicMock, patch
from triage_core.orchestration import ProjectManager
from triage_core.work_orders import WorkOrder

class DummyWorker:
    def __init__(self, role, outputs):
        self.role = role
        self.outputs = outputs
        self.call_count = 0
        self.model = "dummy-model"

    def process(self, order, stream_callback=None):
        out = self.outputs[min(self.call_count, len(self.outputs) - 1)]
        self.call_count += 1
        return out

def test_dispatch_task_success():
    pm = ProjectManager()
    
    # Mock registry
    repo_mapper = DummyWorker("repo_mapper", [{"summary": "Repo analyzed", "files_identified": []}])
    code_repair = DummyWorker("code_repair", [{"repaired_code": "print('ok')"}])
    validator = DummyWorker("validator", [{"is_valid": True, "issues_found": []}])
    
    pm.registry.workers = {
        "repo_mapper": repo_mapper,
        "code_repair": code_repair,
        "validator": validator
    }
    
    result = pm.dispatch_task(
        prompt="Fix issues",
        target_files=["file.py"],
        required_roles=["repo_mapper", "code_repair", "validator"]
    )
    
    assert result["evaluation"]["local_result_status"] == "sufficient"
    assert repo_mapper.call_count == 1
    assert code_repair.call_count == 1
    assert validator.call_count == 1

def test_dispatch_task_loopback():
    pm = ProjectManager()
    pm.budgets = {"max_local_attempts": 2}
    
    # Mock registry: Validator fails first time, succeeds second time
    repo_mapper = DummyWorker("repo_mapper", [{"summary": "Repo analyzed", "files_identified": []}])
    code_repair = DummyWorker("code_repair", [
        {"repaired_code": "print('bad')"},
        {"repaired_code": "print('fixed')"}
    ])
    validator = DummyWorker("validator", [
        {"is_valid": False, "issues_found": ["syntax error"]},
        {"is_valid": True, "issues_found": []}
    ])
    
    pm.registry.workers = {
        "repo_mapper": repo_mapper,
        "code_repair": code_repair,
        "validator": validator
    }
    
    result = pm.dispatch_task(
        prompt="Fix issues",
        target_files=["file.py"],
        required_roles=["repo_mapper", "code_repair", "validator"]
    )
    
    # Should resolve successfully after loopback repair
    assert result["evaluation"]["local_result_status"] == "sufficient"
    assert repo_mapper.call_count == 1
    # Code repair called twice: once initially, once on loopback
    assert code_repair.call_count == 2
    # Validator called twice: once initially, once on loopback
    assert validator.call_count == 2

def test_dispatch_task_early_delegation():
    pm = ProjectManager()
    
    # Mock registry: code_repair decides to delegate to antigravity immediately
    repo_mapper = DummyWorker("repo_mapper", [{"summary": "Repo analyzed", "files_identified": []}])
    code_repair = DummyWorker("code_repair", [{"delegate_to": "antigravity"}])
    validator = DummyWorker("validator", [{"is_valid": True}])
    
    pm.registry.workers = {
        "repo_mapper": repo_mapper,
        "code_repair": code_repair,
        "validator": validator
    }
    
    result = pm.dispatch_task(
        prompt="Extreme refactoring",
        target_files=["file.py"],
        required_roles=["repo_mapper", "code_repair", "validator"]
    )
    
    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert result["evaluation"]["recommended_escalation"] == "antigravity"
    assert code_repair.call_count == 1
    # Validator should NEVER be called since execution halted
    assert validator.call_count == 0

def test_dispatch_task_next_worker():
    pm = ProjectManager()
    
    # Mock registry: repo_mapper suggests running test_stubber next
    repo_mapper = DummyWorker("repo_mapper", [{"summary": "Repo analyzed", "next_worker": "test_stubber"}])
    test_stubber = DummyWorker("test_stubber", [{"test_code": "def test(): pass"}])
    
    pm.registry.workers = {
        "repo_mapper": repo_mapper,
        "test_stubber": test_stubber
    }
    
    result = pm.dispatch_task(
        prompt="Analyze and stub tests",
        target_files=["file.py"],
        required_roles=["repo_mapper"]
    )
    
    assert repo_mapper.call_count == 1
    assert test_stubber.call_count == 1
    assert len(result["work_orders"]) == 2

def test_escalation_packet_uses_configured_tasks_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "triagecore.toml").write_text(
        "\n".join(
            [
                "[paths]",
                'tasks_dir = "custom_tasks"',
                "",
                "[budgets]",
                "max_energy_kwh_per_task = 0.001",
            ]
        ),
        encoding="utf-8",
    )

    from triage_core import config as config_module
    from triage_core import orchestration as orchestration_module

    fresh_config = config_module.Config(root_dir=str(tmp_path))
    monkeypatch.setattr(orchestration_module, "default_config", fresh_config)

    pm = ProjectManager()
    repo_mapper = DummyWorker("repo_mapper", [
        {
            "summary": "Repo analyzed",
            "resource_usage": {"energy_kwh_estimate": 0.01, "duration_seconds": 1},
        }
    ])
    pm.registry.workers = {"repo_mapper": repo_mapper}

    result = pm.dispatch_task(
        prompt="Trigger energy escalation",
        target_files=["file.py"],
        required_roles=["repo_mapper"],
    )

    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert result["escalation_packet"].startswith("custom_tasks")
    assert (tmp_path / result["escalation_packet"]).exists()
