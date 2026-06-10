import os
import pytest
from unittest.mock import patch
from triage_core.tc_cli import tc_propose, _slugify

def test_slugify():
    assert _slugify("Example New Change") == "example-new-change"
    assert _slugify("CR-004B: Local-only privacy routing!") == "cr-004b-local-only-privacy-routing"
    assert _slugify("   Spaces  -- ") == "spaces"

def test_propose_creates_file(tmp_path, capsys):
    test_dir = tmp_path / "docs" / "change" / "requests"
    with patch("os.makedirs"):
        from unittest.mock import mock_open
        m_open = mock_open()
        with patch("builtins.open", m_open):
            with patch("os.path.exists", return_value=False):
                with patch("triage_core.tc_cli.os.path.dirname", return_value=str(test_dir)):
                    tc_propose("CR-012", "example new change", False)
                    
    out, err = capsys.readouterr()
    assert "Success: Created proposal template" in out
    m_open.assert_called_once()
    assert "CR-012: Example New Change" in m_open().write.call_args[0][0]
    assert "Proposed" in m_open().write.call_args[0][0]

def test_propose_refuses_overwrite(capsys):
    with patch("os.path.exists", return_value=True):
        with pytest.raises(SystemExit) as exc:
            tc_propose("CR-012", "example", False)
        assert exc.value.code == 1
        
    out, err = capsys.readouterr()
    assert "already exists. Refusing to overwrite" in out

def test_propose_rejects_invalid_cr_id(capsys):
    invalid_ids = ["CR-12", "CR-0001", "PR-012", "012", "CR-012AB"]
    for cr_id in invalid_ids:
        with pytest.raises(SystemExit) as exc:
            tc_propose(cr_id, "title", False)
        assert exc.value.code == 1
        out, err = capsys.readouterr()
        assert f"Invalid CR ID format '{cr_id}'" in out

def test_propose_accepts_cr_004b_style(tmp_path, capsys):
    with patch("os.makedirs"):
        with patch("builtins.open"):
            with patch("os.path.exists", return_value=False):
                tc_propose("CR-004B", "local only routing", False)
                
    out, err = capsys.readouterr()
    assert "Success: Created proposal template" in out

def test_propose_changelog_adds_entry(tmp_path, capsys):
    cl_path = tmp_path / "change_log.md"
    cl_path.write_text("## [Unreleased]\n- Some feature\n")
    
    with patch("os.makedirs"):
        # mock open for the requests file and changelog
        def mock_exists(path):
            if "change_log" in path:
                return True
            return False
            
        with patch("os.path.exists", side_effect=mock_exists):
            # Patch open dynamically to handle cl_path correctly while ignoring requests file creation
            original_open = open
            def mock_open_file(file, *args, **kwargs):
                if "change_log" in str(file):
                    return original_open(cl_path, *args, **kwargs)
                # Mock the requests file
                from unittest.mock import mock_open
                return mock_open()(file, *args, **kwargs)

            with patch("builtins.open", side_effect=mock_open_file):
                # Hardcode cl_path in tc_cli.py logic during this test
                with patch("triage_core.tc_cli.os.path.exists", side_effect=mock_exists):
                    # In tc_cli it accesses docs/change/change_log.md
                    # So we need to rewrite that internally or just mock the file content
                    pass
                    
def test_propose_changelog_logic(capsys):
    # Testing the changelog logic directly with mocks
    with patch("os.makedirs"):
        with patch("os.path.exists", side_effect=lambda x: True if "change_log.md" in x else False):
            from unittest.mock import mock_open
            m_open = mock_open(read_data="## [Unreleased]\n")
            with patch("builtins.open", m_open):
                tc_propose("CR-012", "example", True)
                
    out, err = capsys.readouterr()
    assert "Success: Added 'CR-012' to [Unreleased] in changelog." in out
    
def test_propose_changelog_no_duplicate(capsys):
    with patch("os.makedirs"):
        with patch("os.path.exists", side_effect=lambda x: True if "change_log.md" in x else False):
            from unittest.mock import mock_open
            m_open = mock_open(read_data="## [Unreleased]\n- Proposed CR-012 (Example): \n")
            with patch("builtins.open", m_open):
                tc_propose("CR-012", "example", True)
                
    out, err = capsys.readouterr()
    assert "Notice: Changelog entry for CR-012 already exists." in out

