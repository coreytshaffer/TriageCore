import pytest
import subprocess
import json
import os

def test_admission_validate_success(tmp_path):
    fixture_path = tmp_path / "valid.json"
    valid_data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test"
    }
    fixture_path.write_text(json.dumps(valid_data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Validation successful." in result.stdout

def test_admission_validate_missing_field(tmp_path):
    fixture_path = tmp_path / "missing.json"
    data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "local",
        "requested_capability": "read_only",
        "approval_required": False,
        # missing approval_used
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test"
    }
    fixture_path.write_text(json.dumps(data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error validating Admission Evidence JSON" in result.stderr

def test_admission_validate_invalid_json(tmp_path):
    fixture_path = tmp_path / "invalid.json"
    fixture_path.write_text("{ unquoted_key: true }", encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error parsing JSON" in result.stderr

def test_admission_validate_rejects_ledger(tmp_path):
    triagecore_dir = tmp_path / ".triagecore"
    triagecore_dir.mkdir()
    ledger_path = triagecore_dir / "ledger.jsonl"
    ledger_path.write_text("{}", encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(ledger_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "ledger.jsonl is not allowed as a --from-json fixture source." in result.stderr

def test_admission_validate_requires_from_json():
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate"],
        capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "the following arguments are required: --from-json" in result.stderr

def test_admission_validate_empty_required_string(tmp_path):
    fixture_path = tmp_path / "empty_string.json"
    data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "", # empty string should fail validation
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test"
    }
    fixture_path.write_text(json.dumps(data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error validating Admission Evidence JSON" in result.stderr
