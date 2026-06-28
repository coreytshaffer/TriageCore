import os
import tempfile
import json
import ast
from pathlib import Path
from triage_core.evaluator_result_history import (
    load_evaluator_result_folder,
    load_evaluator_result_files,
    EvaluatorResultSummary
)

def test_no_forbidden_imports():
    """Ensure we don't import execution/network libs that violate observation-only boundary."""
    path = Path(__file__).parent.parent / "triage_core" / "evaluator_result_history.py"
    content = path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    
    forbidden = {"subprocess", "requests", "urllib", "http", "socket"}
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                base = name.name.split('.')[0]
                assert base not in forbidden, f"Forbidden import found: {base}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                base = node.module.split('.')[0]
                assert base not in forbidden, f"Forbidden import found: {base}"

def test_load_empty_folder():
    with tempfile.TemporaryDirectory() as d:
        res = load_evaluator_result_folder(d)
        assert len(res) == 0

def test_load_mix_of_files():
    with tempfile.TemporaryDirectory() as d:
        valid_json_1 = {
            "result_type": "workspace_packet_evaluation_result",
            "item_id": "DEMO-001",
            "packet_id": "packet_1",
            "decision": "observe",
            "approval_status": "not_approval",
            "target_invocation": "not_invoked",
            "score": "pass",
            "reasons": [],
            "warnings": [],
            "generated_at": "2026-06-27T00:00:00Z"
        }
        
        valid_json_2 = {
            "result_type": "workspace_packet_evaluation_result",
            "item_id": "DEMO-002",
            "packet_id": "packet_2",
            "decision": "fail",
            "approval_status": "not_approval",
            "target_invocation": "not_invoked",
            "score": "fail",
            "reasons": [],
            "warnings": [],
            "generated_at": "2026-06-28T00:00:00Z"
        }
        
        unsafe_json = {
            "result_type": "workspace_packet_evaluation_result",
            "item_id": "DEMO-UNSAFE",
            "packet_id": "packet_3",
            "decision": "approve", # unsafe
            "approval_status": "not_approval",
            "target_invocation": "not_invoked",
            "score": "pass",
            "reasons": []
        }
        
        missing_fields_json = {
            "result_type": "workspace_packet_evaluation_result",
            "item_id": "DEMO-MISSING"
        }

        with open(os.path.join(d, "valid1.json"), "w") as f:
            json.dump(valid_json_1, f)
        with open(os.path.join(d, "valid2.json"), "w") as f:
            json.dump(valid_json_2, f)
        with open(os.path.join(d, "unsafe.json"), "w") as f:
            json.dump(unsafe_json, f)
        with open(os.path.join(d, "invalid.json"), "w") as f:
            json.dump(missing_fields_json, f)
        with open(os.path.join(d, "malformed.json"), "w") as f:
            f.write("{ bad json ]")
        with open(os.path.join(d, "not_json.txt"), "w") as f:
            f.write("hello")
            
        summaries = load_evaluator_result_folder(d)
        
        # We wrote 5 JSON files, should be 5 summaries
        assert len(summaries) == 5
        
        # Check sorting
        # Order should be:
        # 1. valid2 (2026-06-28)
        # 2. valid1 (2026-06-27)
        # 3,4,5. invalid, malformed, unsafe (sorted by filename) -> invalid.json, malformed.json, unsafe.json
        
        assert summaries[0].item_id == "DEMO-002"
        assert summaries[0].status_label == "FAIL"
        
        assert summaries[1].item_id == "DEMO-001"
        assert summaries[1].status_label == "PASS"
        
        assert os.path.basename(summaries[2].filepath) == "invalid.json"
        assert summaries[2].status_label == "INVALID"
        
        assert os.path.basename(summaries[3].filepath) == "malformed.json"
        assert summaries[3].status_label == "MALFORMED"
        
        assert os.path.basename(summaries[4].filepath) == "unsafe.json"
        assert summaries[4].status_label == "UNSAFE"
