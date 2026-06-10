import os
import sys
import tempfile
import unittest.mock
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
