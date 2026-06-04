from triage_core.orchestration import ProjectManager
from triage_core.worker_registry import WorkerBase
import traceback

# Mock process to simulate successful LLM generation
def fake_process(self, order, stream_callback=None):
    return {
        "worker_id": self.role,
        "resource_usage": {"energy_kwh_estimate": 0.01, "duration_seconds": 2},
        "is_valid": True,
        "summary": "Fake summary",
        "repaired_code": "print('fixed')"
    }
WorkerBase.process = fake_process

def test_dispatch():
    try:
        pm = ProjectManager()
        result = pm.dispatch_task(
            prompt="Refactor this code to follow PEP-8, add type hints, and fix the bare except clause.",
            target_files=["examples/messy_test.py"],
            required_roles=["repo_mapper", "code_repair", "validator"]
        )
        print("Success:", result.keys())
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    test_dispatch()
