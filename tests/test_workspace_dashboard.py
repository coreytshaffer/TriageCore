import os
import subprocess
import pytest

from triage_core.workspace_dashboard import render_html
from triage_core.workspace_board import load_work_items
from triage_core.workspace_now import load_today_file, TodayFocus, TodayLimits
from triage_core.workspace_board import WorkItem, Status, Priority, RiskLevel, KanbanState

# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

EXAMPLE_WORK_ITEMS = "docs/examples/workspace_work_items.example.yaml"
EXAMPLE_TODAY = "docs/examples/workspace_today.example.yaml"

@pytest.fixture
def work_items():
    return load_work_items(EXAMPLE_WORK_ITEMS)

@pytest.fixture
def today():
    return load_today_file(EXAMPLE_TODAY)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_dashboard_escapes_html(work_items):
    """HTML escaping prevents script injection from YAML."""
    malicious_title = "<script>alert('x')</script>"
    
    # Inject malicious title into the first item
    work_items[0].title = malicious_title
    
    today_focus = TodayFocus(focus=[work_items[0].id])
    html_out = render_html(work_items, today_focus)
    
    # The literal script tags should be escaped
    assert "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;" in html_out
    assert "<script>alert('x')</script>" not in html_out


def test_dashboard_preserves_focus_order(work_items):
    """The rendered focus cards should match the order in today.yaml."""
    # Deliberately out of order from priority or definition
    today_focus = TodayFocus(focus=["DEMO-003", "DEMO-001", "DEMO-002"])
    html_out = render_html(work_items, today_focus)
    
    pos3 = html_out.find("DEMO-003")
    pos1 = html_out.find("DEMO-001")
    pos2 = html_out.find("DEMO-002")
    
    assert -1 < pos3 < pos1 < pos2, "Cards must be rendered in the order of today.focus"


def test_dashboard_contains_disabled_handoff_placeholders(work_items, today):
    """Placeholders must be disabled so the UI does not imply functionality."""
    html_out = render_html(work_items, today)
    
    assert "<button disabled" in html_out
    assert "Coming in CR-WU-006" in html_out
    assert "Copy Codex Handoff" in html_out


def test_dashboard_has_no_external_resources(work_items, today):
    """No CDNs or external CSS/JS dependencies allowed."""
    html_out = render_html(work_items, today)
    
    assert "<link rel=" not in html_out
    assert "<script src=" not in html_out
    assert "https://" not in html_out  # Basic check that no URLs are embedded for resources
    assert "<style>" in html_out  # Should be inline


def test_dashboard_output_command_writes_only_requested_file(tmp_path):
    """The CLI command must only write the requested output file."""
    output_file = tmp_path / "dashboard.html"
    
    cmd = [
        "python", "-m", "triage_core.tc_cli", "workspace", "dashboard",
        "--items", EXAMPLE_WORK_ITEMS,
        "--today", EXAMPLE_TODAY,
        "--output", str(output_file)
    ]
    
    # Run the command
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "Dashboard generated at" in result.stdout
    
    # Verify the file was created
    assert output_file.exists()
    
    # Verify no other unexpected files were created in the directory
    files_created = list(tmp_path.iterdir())
    assert len(files_created) == 1
    assert files_created[0] == output_file


def test_dashboard_handles_missing_optional_ux_and_handoff_fields():
    """Existing work item files without ux/handoff fields must still load and render."""
    minimal_item = WorkItem(
        id="MINIMAL-001",
        project="test",
        title="Minimal item",
        type="bug",
        kanban=KanbanState(status=Status.READY, priority=Priority.MEDIUM)
    )
    
    today_focus = TodayFocus(focus=["MINIMAL-001"])
    html_out = render_html([minimal_item], today_focus)
    
    assert "MINIMAL-001" in html_out
    assert "Minimal item" in html_out
    assert "Ready" in html_out
