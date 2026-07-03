import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from triage_core.tc_cli import (
    tc_identity_list, 
    tc_audit_verify_signatures, 
    tc_audit_signed_smoke_test,
    tc_audit_signed_route_decision_smoke_test,
)
from triage_core.agent_identity import AgentIdentityRegistry
from triage_core.task_ledger import TaskLedger

def get_registry(tmp_path):
    registry = AgentIdentityRegistry(ledger_dir=tmp_path)
    return registry

def test_no_agents_json_exits_0(tmp_path, capsys):
    registry = get_registry(tmp_path)
    with patch("triage_core.tc_cli._identity_registry", return_value=registry):
        tc_identity_list()
        captured = capsys.readouterr()
        assert "No identities found" in captured.out

def test_invalid_truncated_agents_json(tmp_path, capsys):
    registry = get_registry(tmp_path)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path.write_text("{ \"agents\": [", encoding="utf-8")
    
    with patch("triage_core.tc_cli._identity_registry", return_value=registry):
        with pytest.raises(SystemExit) as exc:
            tc_identity_list()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "reason=registry_load_failed" in captured.out
        assert "category=malformed_registry" in captured.out
        assert "Traceback" not in captured.out
        assert "Traceback" not in captured.err

def test_wrong_json_shape(tmp_path, capsys):
    registry = get_registry(tmp_path)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    # agents must be a list, here it is a dict
    registry.registry_path.write_text(json.dumps({"agents": {}}), encoding="utf-8")
    
    with patch("triage_core.tc_cli._identity_registry", return_value=registry):
        with pytest.raises(SystemExit) as exc:
            tc_identity_list()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "category=malformed_registry" in captured.out

def test_structurally_invalid_identity_record(tmp_path, capsys):
    registry = get_registry(tmp_path)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path.write_text(json.dumps({
        "agents": [{
            "agent_id": "test", 
            # missing role, public_key, etc.
        }]
    }), encoding="utf-8")
    
    with patch("triage_core.tc_cli._identity_registry", return_value=registry):
        with pytest.raises(SystemExit) as exc:
            tc_identity_list()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "category=invalid_identity_record" in captured.out

def test_unreadable_registry(tmp_path, capsys):
    registry = get_registry(tmp_path)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path.write_text("{}", encoding="utf-8")
    
    with patch("pathlib.Path.read_text", side_effect=PermissionError("simulated unreadable")):
        with patch("triage_core.tc_cli._identity_registry", return_value=registry):
            with pytest.raises(SystemExit) as exc:
                tc_identity_list()
            assert exc.value.code == 1
            captured = capsys.readouterr()
            assert "category=unreadable_registry" in captured.out

def test_secret_leak_regression(tmp_path, capsys):
    registry = get_registry(tmp_path)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    # Corrupt registry containing a secret
    registry.registry_path.write_text("{\"agents\": \"sk-live-EXAMPLE-API-KEY\"}", encoding="utf-8")
    
    with patch("triage_core.tc_cli._identity_registry", return_value=registry):
        with pytest.raises(SystemExit):
            tc_identity_list()
        captured = capsys.readouterr()
        assert "sk-live-EXAMPLE" not in captured.out
        assert "sk-live-EXAMPLE" not in captured.err

def test_no_mutation_after_failure(tmp_path):
    registry = get_registry(tmp_path)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path.write_text("{ malformed }", encoding="utf-8")
    
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text("{\"preseeded\": true}\n", encoding="utf-8")
    
    with patch("triage_core.tc_cli._identity_registry", return_value=registry), \
         patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
         
        with pytest.raises(SystemExit):
            tc_audit_signed_smoke_test("test_agent")
            
        # Ensure ledger is untouched
        assert ledger_path.read_text(encoding="utf-8") == "{\"preseeded\": true}\n"
        
        with pytest.raises(SystemExit):
            tc_audit_signed_route_decision_smoke_test("test_agent")
            
        assert ledger_path.read_text(encoding="utf-8") == "{\"preseeded\": true}\n"

def test_no_partial_verification_output(tmp_path, capsys):
    registry = get_registry(tmp_path)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path.write_text("{ malformed }", encoding="utf-8")
    
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text("{\"event_type\": \"route_audit\", \"signature\": \"foo\"}\n", encoding="utf-8")
    
    with patch("triage_core.tc_cli._identity_registry", return_value=registry), \
         patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
         
        with pytest.raises(SystemExit):
            tc_audit_verify_signatures()
            
        captured = capsys.readouterr()
        assert "PASS" not in captured.out
        assert "FAIL" not in captured.out
        assert "category=malformed_registry" in captured.out
