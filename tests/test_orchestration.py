import pytest
from unittest.mock import MagicMock, patch
from triage_core.orchestration import ProjectManager
from triage_core.work_orders import WorkOrder
from triage_core.validator_tools import ValidationResult

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
    context_planner = DummyWorker("context_planner", [{"summary": "Repo analyzed", "files_identified": []}])
    implementer = DummyWorker("implementer", [{"repaired_code": "print('ok')"}])
    review_worker = DummyWorker("review_worker", [{"is_valid": True, "issues_found": []}])
    
    pm.registry.workers = {
        "context_planner": context_planner,
        "implementer": implementer,
        "review_worker": review_worker
    }
    
    with patch("triage_core.orchestration.ValidatorTools.run") as mock_val_run:
        mock_val_run.return_value = [ValidationResult(passed=True, validator="dummy")]
        result = pm.dispatch_task(
            prompt="Fix issues",
            target_files=["file.py"],
            required_roles=["context_planner", "implementer", "review_worker"]
        )
    
    assert result["evaluation"]["local_result_status"] == "sufficient"
    assert context_planner.call_count == 1
    assert implementer.call_count == 1
    assert review_worker.call_count == 1

def test_dispatch_task_loopback():
    pm = ProjectManager()
    pm.budgets = {"max_local_attempts": 2}
    
    # Mock registry
    context_planner = DummyWorker("context_planner", [{"summary": "Repo analyzed", "files_identified": []}])
    implementer = DummyWorker("implementer", [
        {"repaired_code": "print('bad')"},
        {"repaired_code": "print('fixed')"}
    ])
    review_worker = DummyWorker("review_worker", [{"is_valid": True, "issues_found": []}])
    
    pm.registry.workers = {
        "context_planner": context_planner,
        "implementer": implementer,
        "review_worker": review_worker
    }
    
    with patch("triage_core.orchestration.ValidatorTools.run") as mock_val_run:
        # Fails first time, passes second time
        mock_val_run.side_effect = [
            [ValidationResult(passed=False, validator="dummy", issues=["syntax error"])],
            [ValidationResult(passed=True, validator="dummy", issues=[])]
        ]
        
        result = pm.dispatch_task(
            prompt="Fix issues",
            target_files=["file.py"],
            required_roles=["context_planner", "implementer", "review_worker"]
        )
    
    # Should resolve successfully after loopback repair
    assert result["evaluation"]["local_result_status"] == "sufficient"
    assert context_planner.call_count == 1
    # implementer called twice: once initially, once on loopback
    assert implementer.call_count == 2
    # review_worker called once after it finally passes
    assert review_worker.call_count == 1

def test_dispatch_task_early_delegation():
    pm = ProjectManager()
    
    # Mock registry: implementer decides to delegate to antigravity immediately
    context_planner = DummyWorker("context_planner", [{"summary": "Repo analyzed", "files_identified": []}])
    implementer = DummyWorker("implementer", [{"delegate_to": "antigravity"}])
    review_worker = DummyWorker("review_worker", [{"is_valid": True}])
    
    pm.registry.workers = {
        "context_planner": context_planner,
        "implementer": implementer,
        "review_worker": review_worker
    }
    
    result = pm.dispatch_task(
        prompt="Extreme refactoring",
        target_files=["file.py"],
        required_roles=["context_planner", "implementer", "review_worker"]
    )
    
    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert result["evaluation"]["recommended_escalation"] == "antigravity"
    assert implementer.call_count == 1
    # review_worker should NEVER be called since execution halted
    assert review_worker.call_count == 0

def test_dispatch_task_next_worker():
    pm = ProjectManager()
    
    # Mock registry: context_planner suggests running test_stubber next
    context_planner = DummyWorker("context_planner", [{"summary": "Repo analyzed", "next_worker": "test_stubber"}])
    test_stubber = DummyWorker("test_stubber", [{"test_code": "def test(): pass"}])
    
    pm.registry.workers = {
        "context_planner": context_planner,
        "test_stubber": test_stubber
    }
    
    result = pm.dispatch_task(
        prompt="Analyze and stub tests",
        target_files=["file.py"],
        required_roles=["context_planner"]
    )
    
    assert context_planner.call_count == 1
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
    context_planner = DummyWorker("context_planner", [
        {
            "summary": "Repo analyzed",
            "resource_usage": {"energy_kwh_estimate": 0.01, "duration_seconds": 1},
        }
    ])
    pm.registry.workers = {"context_planner": context_planner}

    result = pm.dispatch_task(
        prompt="Trigger energy escalation",
        target_files=["file.py"],
        required_roles=["context_planner"],
    )

    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert result["escalation_packet"].startswith("custom_tasks")
    assert (tmp_path / result["escalation_packet"]).exists()


def test_dispatch_task_early_stopping_by_kwh():
    from triage_core.project_steward import ProjectSteward
    pm = ProjectManager()
    pm.budgets = {"max_energy_kwh_per_task": 0.005}
    pm.steward = ProjectSteward(budgets=pm.budgets)

    # We have context_planner and implementer.
    # The context_planner exceeds the budget.
    # The implementer should never be run (its work order cancelled).
    context_planner = DummyWorker("context_planner", [{
        "summary": "Analysing structural files...",
        "resource_usage": {"energy_kwh_estimate": 0.01}
    }])
    implementer = DummyWorker("implementer", [{"repaired_code": "print('ok')"}])

    pm.registry.workers = {
        "context_planner": context_planner,
        "implementer": implementer
    }

    result = pm.dispatch_task(
        prompt="Test early stopping",
        target_files=["file.py"],
        required_roles=["context_planner", "implementer"]
    )

    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert "Early stopping: Exceeded energy budget" in result["evaluation"]["reason"]
    assert result["evaluation"]["recommended_escalation"] == "antigravity"
    assert context_planner.call_count == 1
    assert implementer.call_count == 0

    # Ensure the implementer order exists on the board but is marked as cancelled
    cancelled_orders = [o for o in pm.board.orders.values() if o.status == "cancelled"]
    assert len(cancelled_orders) == 1
    assert cancelled_orders[0].assigned_role == "implementer"


def test_dispatch_task_early_stopping_joules_fallback():
    from triage_core.project_steward import ProjectSteward
    pm = ProjectManager()
    pm.budgets = {"max_energy_kwh_per_task": 0.001}
    pm.steward = ProjectSteward(budgets=pm.budgets)

    # Let's say energy_kwh_estimate is 0, but energy_estimated is 7200 Joules (= 0.002 kWh)
    context_planner = DummyWorker("context_planner", [{
        "summary": "Analysing structural files...",
        "resource_usage": {"energy_estimated": 7200.0}
    }])
    implementer = DummyWorker("implementer", [{"repaired_code": "print('ok')"}])

    pm.registry.workers = {
        "context_planner": context_planner,
        "implementer": implementer
    }

    result = pm.dispatch_task(
        prompt="Test early stopping fallback",
        target_files=["file.py"],
        required_roles=["context_planner", "implementer"]
    )

    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert "Early stopping: Exceeded energy budget" in result["evaluation"]["reason"]
    assert result["evaluation"]["recommended_escalation"] == "antigravity"
    assert context_planner.call_count == 1
    assert implementer.call_count == 0

