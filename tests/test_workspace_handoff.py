import json
import subprocess
import pytest

from triage_core.workspace_board import load_work_items, WorkItem, KanbanState, Status, Priority
from triage_core.workspace_handoff import generate_handoff

# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

EXAMPLE_WORK_ITEMS = "docs/examples/workspace_work_items.example.yaml"

@pytest.fixture
def work_items():
    return load_work_items(EXAMPLE_WORK_ITEMS)

@pytest.fixture
def demo_item(work_items):
    for item in work_items:
        if item.id == "DEMO-001":
            return item
    raise ValueError("DEMO-001 not found in test data")

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_handoff_cli_resolves_valid_item_id(tmp_path):
    """The CLI command should resolve a valid ID and print the handoff."""
    cmd = [
        "python", "-m", "triage_core.tc_cli", "workspace", "handoff",
        "--items", EXAMPLE_WORK_ITEMS,
        "--id", "DEMO-001",
        "--tool", "codex",
        "--format", "text"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "HANDOFF: DEMO-001" in result.stdout
    assert "Target tool: Codex" in result.stdout

def test_handoff_cli_fails_on_unknown_item_id(tmp_path):
    """The CLI command should fail closed and return an error on unknown ID."""
    cmd = [
        "python", "-m", "triage_core.tc_cli", "workspace", "handoff",
        "--items", EXAMPLE_WORK_ITEMS,
        "--id", "UNKNOWN-001",
        "--tool", "codex"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "not found" in result.stdout

def test_renders_codex_handoff(demo_item):
    """Codex handoff contains objective, next action, stop rule, checks, return format."""
    out = generate_handoff(demo_item, tool="codex", fmt="text")
    assert "HANDOFF: DEMO-001" in out
    assert "Objective:" in out
    assert "Reduce orientation cost" in out
    assert "Next action:" in out
    assert "Implement schema loader" in out
    assert "Stop rule:" in out
    assert "Stop after schema loader works" in out
    assert "Required checks:" in out
    assert "git diff --check" in out
    assert "Return format:" in out
    assert "changed_files" in out

def test_renders_chatgpt_review_handoff(demo_item):
    """ChatGPT handoff contains review framing."""
    out = generate_handoff(demo_item, tool="chatgpt", fmt="text")
    assert "REVIEW HANDOFF: DEMO-001" in out
    assert "Please assess:" in out
    assert "- scope creep" in out
    assert "- privacy boundary" in out
    
def test_renders_status_summary(demo_item):
    """Status summary is short and includes project, title, next action."""
    out = generate_handoff(demo_item, tool="status", fmt="text")
    assert "STATUS UPDATE: DEMO-001" in out
    assert "example-control-plane - Workspace Schema" in out
    assert "Current focus: Implement schema loader and brief renderer" in out
    
def test_renders_closing_packet(demo_item):
    """Closing packet includes checkboxes for criteria and checks."""
    out = generate_handoff(demo_item, tool="closing", fmt="text")
    assert "CLOSING PACKET: DEMO-001" in out
    assert "Verified criteria:" in out
    assert "[ ] Schema validates registry files" in out
    assert "Checks passed:" in out
    assert "[ ] git diff --check" in out
    assert "Evidence:" in out
    
def test_json_output_is_parseable(demo_item):
    """JSON output format is valid and parseable."""
    out = generate_handoff(demo_item, tool="codex", fmt="json")
    data = json.loads(out)
    assert data["id"] == "DEMO-001"
    assert data["project"] == "example-control-plane"
    assert "title" in data
    assert "risk" in data
    assert "stop_rule" in data

def test_output_is_deterministic(demo_item):
    """Multiple calls generate the exact same string."""
    out1 = generate_handoff(demo_item, tool="codex", fmt="markdown")
    out2 = generate_handoff(demo_item, tool="codex", fmt="markdown")
    assert out1 == out2
    
def test_private_fields_are_omitted(demo_item):
    """Private fields (like notes) are omitted from standard output."""
    assert demo_item.notes is not None
    assert demo_item.notes != ""
    
    out_text = generate_handoff(demo_item, tool="codex", fmt="text")
    out_json = generate_handoff(demo_item, tool="codex", fmt="json")
    
    assert demo_item.notes not in out_text
    assert demo_item.notes not in out_json

def test_handles_missing_optional_fields():
    """Existing items without optional ux/handoff fields still render correctly."""
    minimal_item = WorkItem(
        id="MINIMAL-001",
        project="test",
        title="Minimal item",
        type="bug",
        kanban=KanbanState(status=Status.READY, priority=Priority.MEDIUM)
    )
    
    # Should not crash and should render basics
    out = generate_handoff(minimal_item, tool="codex", fmt="text")
    assert "HANDOFF: MINIMAL-001" in out
    assert "Minimal item" in out
    
    out_json = generate_handoff(minimal_item, tool="status", fmt="json")
    data = json.loads(out_json)
    assert data["id"] == "MINIMAL-001"
    assert data["stop_rule"] == ""
    assert data["objective"] == ""
