import json
import os
import pytest

from triage_core.workspace_now import load_today_file, render_now, TodayFocus, TodayLimits
from triage_core.workspace_board import load_work_items

# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

EXAMPLE_WORK_ITEMS = "docs/examples/workspace_work_items.example.yaml"
EXAMPLE_TODAY = "docs/examples/workspace_today.example.yaml"

# ---------------------------------------------------------------------------
# Tests: Loader
# ---------------------------------------------------------------------------

class TestTodayLoader:
    def test_load_example_file(self):
        """The example today file should load cleanly."""
        today = load_today_file(EXAMPLE_TODAY)
        assert len(today.focus) == 3
        assert today.date == "2026-06-27"
        assert today.limits is not None
        assert today.limits.max_active_items == 3
        assert today.limits.max_high_risk_items == 1
        assert len(today.notes) == 2

    def test_load_minimal_json(self, tmp_path):
        """A minimal JSON file with only focus should load."""
        file_path = tmp_path / "today.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"focus": ["DEMO-001"]}, f)
            
        today = load_today_file(str(file_path))
        assert today.focus == ["DEMO-001"]
        assert today.date is None
        assert today.limits is None
        assert today.notes == []

    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_today_file("does_not_exist.yaml")

    def test_malformed_yaml(self, tmp_path):
        file_path = tmp_path / "bad.yaml"
        file_path.write_text("focus: [unclosed bracket", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            load_today_file(str(file_path))

    def test_unsupported_extension(self, tmp_path):
        file_path = tmp_path / "today.txt"
        file_path.write_text('{"focus": []}', encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_today_file(str(file_path))

    def test_missing_focus(self, tmp_path):
        file_path = tmp_path / "today.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"date": "2026-06-27"}, f)
        with pytest.raises(ValueError, match="Missing required field 'focus'"):
            load_today_file(str(file_path))

    def test_focus_not_list(self, tmp_path):
        file_path = tmp_path / "today.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"focus": "DEMO-001"}, f)
        with pytest.raises(ValueError, match="'focus' must be a list"):
            load_today_file(str(file_path))

# ---------------------------------------------------------------------------
# Tests: Renderer
# ---------------------------------------------------------------------------

class TestNowRenderer:
    @pytest.fixture
    def work_items(self):
        return load_work_items(EXAMPLE_WORK_ITEMS)

    def test_render_example(self, work_items):
        today = load_today_file(EXAMPLE_TODAY)
        output = render_now(work_items, today)
        
        # Verify focus items are rendered
        assert "Focus:" in output
        assert "1. DEMO-001 | example-control-plane | Implement workspace registry schema" in output
        assert "2. DEMO-002 | example-commons | Draft consent and key custody flow" in output
        assert "3. DEMO-003 | example-monitoring | Clarify resource freshness vs observation freshness" in output
        
        # Verify next action and tool are rendered
        assert "Next: Implement schema loader and brief renderer" in output
        assert "Tool: codex" in output
        assert "Risk: medium" in output
        
        # Verify limits are checked (this example shouldn't have warnings since limits match count)
        assert "Warnings:" not in output
        
        # Verify blocked items are listed
        assert "Blocked:" in output
        assert "DEMO-004 | example-safety | Synthetic evidence pipeline for local integration tests" in output
        assert "Blocker: Privacy/NAS boundary plan not ready" in output
        
    def test_unknown_focus_id(self, work_items):
        today = TodayFocus(focus=["UNKNOWN-001"])
        with pytest.raises(ValueError, match="Focus ID 'UNKNOWN-001' not found"):
            render_now(work_items, today)

    def test_limit_warnings(self, work_items):
        today = TodayFocus(
            focus=["DEMO-001", "DEMO-002", "DEMO-003", "DEMO-004"],
            limits=TodayLimits(max_active_items=2, max_high_risk_items=0)
        )
        output = render_now(work_items, today)
        
        assert "Warnings:" in output
        assert "Focus list contains 4 items; limit is 2." in output
        assert "Focus list contains 1 high risk items; limit is 0." in output

    def test_review_items(self, work_items):
        today = TodayFocus(focus=[])
        output = render_now(work_items, today)
        
        # The example has DEMO-003 in review status
        assert "Review:" in output
        assert "DEMO-003 | example-monitoring | Clarify resource freshness vs observation freshness" in output
        assert "Next: Review public claims language for accuracy" in output
