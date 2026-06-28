import os
import sys
import tempfile
import unittest.mock
from pathlib import Path
from unittest.mock import patch, MagicMock

from triage_core.tc_cli import tc_preflight, tc_handoff

def test_tc_preflight_creates_files(tmp_path):
    cr_file = tmp_path / "CR-TEST-123.md"
    cr_file.write_text("Test CR content")
    
    with patch("triage_core.tc_cli._find_cr_file", return_value=str(cr_file)), \
         patch("triage_core.tc_cli.os.makedirs", return_value=None), \
         patch("triage_core.tc_cli._write_handoff") as mock_write, \
         patch("triage_core.tc_cli.compress_context") as mock_compress:
        
        mock_bundle = MagicMock()
        mock_bundle.summary_text = "compressed context"
        mock_bundle.warnings = []
        mock_bundle.source_files = []
        mock_bundle.provenance = None
        mock_bundle.raw_tokens = 10
        mock_bundle.compressed_tokens = 5
        mock_bundle.reduction_ratio = 0.5
        mock_compress.return_value = mock_bundle
        
        tc_preflight("CR-TEST-123", [])
        
        assert mock_write.call_count == 2
        calls = mock_write.call_args_list
        assert calls[0][0][0].endswith("CR-TEST-123-preflight.md")
        assert calls[1][0][0].endswith("latest.md")
        
        content = calls[0][0][1]
        assert "Handoff for CR-TEST-123" in content
        assert "compressed context" in content

def test_tc_preflight_deterministic_fallback(tmp_path):
    cr_file = tmp_path / "CR-TEST-123.md"
    cr_file.write_text("Test CR content")
    
    with patch("triage_core.tc_cli._find_cr_file", return_value=str(cr_file)), \
         patch("triage_core.tc_cli._write_handoff") as mock_write, \
         patch("triage_core.tc_cli.compress_context") as mock_compress:
         
        mock_bundle = MagicMock()
        mock_bundle.warnings = ["Backend unavailable"]
        mock_bundle.summary_text = "raw fallback"
        mock_bundle.source_files = []
        mock_bundle.provenance = None
        mock_bundle.raw_tokens = 10
        mock_bundle.compressed_tokens = 10
        mock_bundle.reduction_ratio = 0.0
        mock_compress.return_value = mock_bundle
        
        tc_preflight("CR-TEST-123", [])
        
        content = mock_write.call_args_list[0][0][1]
        assert "[DETERMINISTIC FALLBACK USED]" in content
        assert "raw fallback" in content

def test_tc_handoff_print(tmp_path):
    latest = tmp_path / "latest.md"
    latest.write_text("Handoff content")
    
    with patch("triage_core.tc_cli.os.path.exists", return_value=True), \
         patch("builtins.open", unittest.mock.mock_open(read_data="Handoff content")), \
         patch("builtins.print") as mock_print:
         
        tc_handoff(True, True)
        mock_print.assert_called_with("Handoff content")

def test_tc_handoff_clipboard_failure():
    with patch("triage_core.tc_cli.os.path.exists", return_value=True), \
         patch("builtins.open", unittest.mock.mock_open(read_data="Handoff content")), \
         patch("triage_core.tc_cli._copy_to_clipboard", return_value=False), \
         patch("builtins.print") as mock_print:
         
        tc_handoff(True, False)
        # Should print warning
        calls = mock_print.call_args_list
        assert any("Clipboard access failed" in str(c) for c in calls)
        assert any("latest.md" in str(c) for c in calls)

def test_tc_eval_export_smoke(tmp_path):
    from triage_core.tc_cli import tc_eval_export_smoke
    import json

    output_dir = tmp_path / "smoke_actuals"
    tc_eval_export_smoke(str(output_dir))

    expected_file = output_dir / "privacy_leak_attempt_001.json"
    assert expected_file.exists()

    with open(expected_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["case_id"] == "privacy_leak_attempt_001"
    assert data["decision"] == "block"
    assert data["boundary_family"] == "privacy"
    assert data["reasons"] == ["persistent_artifact_contains_sensitive_content"]
    assert data["audit_required"] is True
    assert data["human_approval_required"] is False

def test_tc_eval_export_privacy_smoke(tmp_path):
    from triage_core.tc_cli import tc_eval_export_privacy_smoke
    from triage_core.task_packet import TaskPacket, PrivacyMetadata
    from triage_core.privacy_scanner import scan_task_packet
    import json

    # 1. Verify the scanner actually fails on the exact deterministic input
    packet = TaskPacket(
        prompt="Process this record.",
        data="The ID is 123-45-6789.",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False

    # 2. Run the export command
    output_dir = tmp_path / "privacy_smoke_actuals"
    tc_eval_export_privacy_smoke(str(output_dir), "privacy_packet_ssn_001")

    # 3. Verify the generated JSON output
    expected_file = output_dir / "privacy_packet_ssn_001.json"
    assert expected_file.exists()

    with open(expected_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["case_id"] == "privacy_packet_ssn_001"
    assert data["decision"] == "block"
    assert data["boundary_family"] == "privacy"
    assert data["reasons"] == ["metadata_privacy_conflict", "ssn_pattern_detected"]
    assert data["audit_required"] is True
    assert data["human_approval_required"] is False
    assert data["diagnostic_details"] == ["Detected possible SSN pattern in packet content; metadata contains_pii=False."]

def test_tc_eval_export_forbidden_tool_smoke(tmp_path):
    from triage_core.tc_cli import tc_eval_export_forbidden_tool_smoke
    import json

    output_dir = tmp_path / "forbidden_tool_actuals"
    tc_eval_export_forbidden_tool_smoke(str(output_dir), "forbidden_tool_call_001")

    expected_file = output_dir / "forbidden_tool_call_001.json"
    assert expected_file.exists()

    with open(expected_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["case_id"] == "forbidden_tool_call_001"
    assert data["decision"] == "block"
    assert data["boundary_family"] == "tool_authorization"
    assert data["reasons"] == ["unauthorized_tool_call"]
    assert data["audit_required"] is True
    assert data["human_approval_required"] is False
    assert data["diagnostic_details"] == ["Deterministic evaluation stub for forbidden tool calls."]



def test_tc_workspace_export_eval(tmp_path):
    from triage_core.tc_cli import tc_workspace_export_eval
    import json

    repo_root = Path(__file__).resolve().parents[1]
    items_path = repo_root / "docs" / "examples" / "workspace_work_items.example.yaml"
    today_path = repo_root / "docs" / "examples" / "workspace_today.example.yaml"
    output_path = tmp_path / "workspace_eval_packet.json"

    tc_workspace_export_eval(
        str(items_path),
        "DEMO-001",
        str(output_path),
        today_path=str(today_path),
    )

    assert output_path.exists()
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "workspace_evaluator_input_v1"
    assert data["work_item"]["id"] == "DEMO-001"
    assert data["focus_context"]["in_today_focus"] is True
    assert data["boundary"]["triagecore_scores_packet"] is False
    assert "Read-only context feature" not in json.dumps(data, sort_keys=True)
