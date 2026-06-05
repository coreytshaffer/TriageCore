import json
import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from triage_core.cli import _run_stability_pass
from triage_core.benchmarks import BenchmarkTask


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.call_count = 0

    def run_task(self, prompt, data, validator=None):
        out = self.outcomes[min(self.call_count, len(self.outcomes) - 1)]
        self.call_count += 1
        return out


def test_stability_pass_success():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a temp tasks file
        tasks_path = os.path.join(temp_dir, "tasks.jsonl")
        task1 = {
            "task_id": "test_task_1",
            "category": "python_generation",
            "prompt": "Write code",
            "data": "",
            "validator": None,
            "expected_status": "success",
        }
        task2 = {
            "task_id": "test_task_2",
            "category": "safety_handoff",
            "prompt": "destructive action",
            "data": "",
            "validator": None,
            "expected_status": "handoff_required",
        }
        with open(tasks_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task1) + "\n")
            f.write(json.dumps(task2) + "\n")

        # FakeClient returns exactly what is expected
        fake_client = FakeClient([
            {"status": "success", "elapsed_seconds": 1.0, "total_tokens": 10},
            {"status": "handoff_required", "reason": "blocked", "elapsed_seconds": 0.5},
        ])

        with patch("triage_core.client.TriageClient", return_value=fake_client):
            # Should run without calling sys.exit(1)
            _run_stability_pass(
                tasks_path=tasks_path,
                backend_type="fake",
                model="fake-model",
                base_url=None,
                timeout_seconds=30,
                ledger_dir=temp_dir,
                study_id="stability_pass",
                run_id=None,
            )

        # Check that activity log was written to and is compliant
        log_path = os.path.join(temp_dir, "triagecore.log")
        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "stability-pass started backend=fake" in content
        assert "stability-pass completed status=success" in content


def test_stability_pass_mismatched_outcome_fails():
    with tempfile.TemporaryDirectory() as temp_dir:
        tasks_path = os.path.join(temp_dir, "tasks.jsonl")
        task = {
            "task_id": "test_task_1",
            "category": "python_generation",
            "prompt": "Write code",
            "data": "",
            "validator": None,
            "expected_status": "success",
        }
        with open(tasks_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task) + "\n")

        # Returns handoff_required instead of success
        fake_client = FakeClient([
            {"status": "handoff_required", "reason": "blocked", "elapsed_seconds": 1.0},
        ])

        with patch("triage_core.client.TriageClient", return_value=fake_client):
            with pytest.raises(SystemExit) as excinfo:
                _run_stability_pass(
                    tasks_path=tasks_path,
                    backend_type="fake",
                    model="fake-model",
                    base_url=None,
                    timeout_seconds=30,
                    ledger_dir=temp_dir,
                    study_id="stability_pass",
                    run_id=None,
                )
            assert excinfo.value.code == 1

        # Check log has failed completion
        log_path = os.path.join(temp_dir, "triagecore.log")
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "stability-pass completed status=failed" in content


def test_stability_pass_logging_non_compliance_fails():
    with tempfile.TemporaryDirectory() as temp_dir:
        tasks_path = os.path.join(temp_dir, "tasks.jsonl")
        task = {
            "task_id": "test_task_1",
            "category": "python_generation",
            "prompt": "Write code",
            "data": "",
            "validator": None,
            "expected_status": "success",
        }
        with open(tasks_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(task) + "\n")

        fake_client = FakeClient([
            {"status": "success", "elapsed_seconds": 1.0},
        ])

        # If _log_cli_activity fails or is bypassed so start log is missing
        with patch("triage_core.client.TriageClient", return_value=fake_client):
            with patch("triage_core.cli._log_cli_activity") as mock_log:
                # Do nothing, so no log starts
                mock_log.side_effect = lambda message, ledger_dir=None: None
                with pytest.raises(SystemExit) as excinfo:
                    _run_stability_pass(
                        tasks_path=tasks_path,
                        backend_type="fake",
                        model="fake-model",
                        base_url=None,
                        timeout_seconds=30,
                        ledger_dir=temp_dir,
                        study_id="stability_pass",
                        run_id=None,
                    )
                assert excinfo.value.code == 1
