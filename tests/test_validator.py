import os
import pytest
from triage_core.task_ledger import TaskRecord
from triage_core.validator import SafetyValidator, ValidationResult

def test_scope_violation():
    task = TaskRecord("id1", target_files=["src/main.py"], risk_level="low", permission_profile="read-only")
    result = SafetyValidator.audit(task, ["src/main.py", "src/other.py"])
    assert not result.passed
    assert any("Scope Violation" in v for v in result.violations)

def test_blocked_profile_violation():
    task = TaskRecord("id2", risk_level="high", permission_profile="blocked")
    result = SafetyValidator.audit(task, ["some_file.py"])
    assert not result.passed
    assert any("Profile Violation" in v for v in result.violations)

def test_read_only_violation(tmp_path):
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")
    
    task = TaskRecord("id3", target_files=[str(test_file)], risk_level="low", permission_profile="read-only")
    result = SafetyValidator.audit(task, [str(test_file)])
    assert not result.passed
    assert any("read-only" in v for v in result.violations)

def test_network_violation_on_low_risk(tmp_path):
    test_file = tmp_path / "test.py"
    test_file.write_text("import requests\nprint('hello')")
    
    task = TaskRecord("id4", target_files=[str(test_file)], risk_level="low", permission_profile="workspace-write")
    result = SafetyValidator.audit(task, [str(test_file)])
    assert not result.passed
    assert any("network import" in v for v in result.violations)

def test_passing_audit(tmp_path):
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello():\n    pass")
    
    task = TaskRecord("id5", target_files=[str(test_file)], risk_level="low", permission_profile="workspace-write")
    result = SafetyValidator.audit(task, [str(test_file)])
    assert result.passed
    assert len(result.violations) == 0
