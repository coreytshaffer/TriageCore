"""
Tests for the workspace board module (CR-WU-002).

Covers:
  - Valid item loading (YAML and JSON)
  - Empty items list
  - Missing file
  - Malformed YAML/JSON
  - Unknown enum values (status, priority, process_group, risk, response_strategy)
  - Missing required fields
  - Board rendering (grouping, sorting, filtering)
  - WBS rendering (hierarchy)
  - GTD section validation (next_action required when gtd present)
  - Risk register entry validation
  - No private paths in example file
"""

import json
import os
import re
import textwrap

import pytest
import yaml

from triage_core.workspace_board import (
    WorkItem,
    load_work_items,
    render_board,
    render_wbs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EXAMPLE_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "docs",
    "examples",
    "workspace_work_items.example.yaml",
)


def _write_yaml(tmp_path, data, filename="items.yaml"):
    """Helper to write a YAML file and return its path."""
    path = tmp_path / filename
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return str(path)


def _write_json(tmp_path, data, filename="items.json"):
    """Helper to write a JSON file and return its path."""
    path = tmp_path / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(path)


def _minimal_item(**overrides):
    """Return a minimal valid work item dict with optional overrides."""
    item = {
        "id": "TEST-001",
        "project": "test-project",
        "title": "Test item",
        "type": "feature",
        "kanban": {
            "status": "active",
            "priority": "medium",
        },
    }
    item.update(overrides)
    return item


def _minimal_file(**item_overrides):
    """Return a minimal valid work items file dict."""
    return {
        "version": 1,
        "items": [_minimal_item(**item_overrides)],
    }


# ---------------------------------------------------------------------------
# Loading: valid cases
# ---------------------------------------------------------------------------

class TestLoadValid:
    def test_load_example_file(self):
        """The shipped example file loads without errors."""
        items = load_work_items(EXAMPLE_FILE)
        assert len(items) == 5
        assert items[0].id == "DEMO-001"
        assert items[0].kanban.status.value == "active"
        assert items[0].kanban.priority.value == "high"

    def test_load_empty_items(self, tmp_path):
        """An empty items list is valid."""
        path = _write_yaml(tmp_path, {"version": 1, "items": []})
        items = load_work_items(path)
        assert items == []

    def test_load_minimal_item(self, tmp_path):
        """An item with only required fields loads successfully."""
        path = _write_yaml(tmp_path, _minimal_file())
        items = load_work_items(path)
        assert len(items) == 1
        assert items[0].id == "TEST-001"
        assert items[0].pmi is None
        assert items[0].gtd is None
        assert items[0].wbs is None
        assert items[0].risk is None

    def test_load_json(self, tmp_path):
        """JSON files load identically to YAML."""
        path = _write_json(tmp_path, _minimal_file())
        items = load_work_items(path)
        assert len(items) == 1
        assert items[0].id == "TEST-001"

    def test_all_statuses_valid(self, tmp_path):
        """All allowed statuses load without error."""
        for status in ("backlog", "ready", "active", "review", "blocked", "done", "parked"):
            data = _minimal_file()
            data["items"][0]["kanban"]["status"] = status
            path = _write_yaml(tmp_path, data, filename=f"items_{status}.yaml")
            items = load_work_items(path)
            assert items[0].kanban.status.value == status

    def test_all_priorities_valid(self, tmp_path):
        """All allowed priorities load without error."""
        for priority in ("critical", "high", "medium", "low", "someday"):
            data = _minimal_file()
            data["items"][0]["kanban"]["priority"] = priority
            path = _write_yaml(tmp_path, data, filename=f"items_{priority}.yaml")
            items = load_work_items(path)
            assert items[0].kanban.priority.value == priority

    def test_pmi_fields_parsed(self, tmp_path):
        """PMI section fields are correctly parsed."""
        data = _minimal_file()
        data["items"][0]["pmi"] = {
            "process_group": "planning",
            "lifecycle_model": "hybrid",
            "deliverable": "Test deliverable",
            "acceptance_criteria": ["Criterion 1"],
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        assert items[0].pmi is not None
        assert items[0].pmi.process_group.value == "planning"
        assert items[0].pmi.lifecycle_model.value == "hybrid"
        assert items[0].pmi.deliverable == "Test deliverable"

    def test_gtd_fields_parsed(self, tmp_path):
        """GTD section fields are correctly parsed."""
        data = _minimal_file()
        data["items"][0]["gtd"] = {
            "list": "next-actions",
            "next_action": "Do the thing",
            "context": ["computer"],
            "energy": "medium",
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        assert items[0].gtd is not None
        assert items[0].gtd.next_action == "Do the thing"
        assert items[0].gtd.gtd_list.value == "next-actions"
        assert items[0].gtd.energy.value == "medium"

    def test_risk_register_parsed(self, tmp_path):
        """Risk register entries are correctly parsed."""
        data = _minimal_file()
        data["items"][0]["risk"] = {
            "level": "high",
            "register": [
                {
                    "id": "R-001",
                    "description": "Test risk",
                    "probability": "medium",
                    "impact": "high",
                    "response_strategy": "mitigate",
                    "response": "Do something about it",
                }
            ],
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        assert items[0].risk is not None
        assert items[0].risk.level.value == "high"
        assert len(items[0].risk.register) == 1
        assert items[0].risk.register[0].id == "R-001"
        assert items[0].risk.register[0].response_strategy.value == "mitigate"

    def test_closing_fields_parsed(self, tmp_path):
        """Closing section with evidence is correctly parsed."""
        data = _minimal_file()
        data["items"][0]["closing"] = {
            "done_definition": ["Tests pass"],
            "lessons_learned": ["Keep it simple"],
            "evidence": {
                "commits": ["abc1234"],
                "prs": [],
                "docs": ["docs/example.md"],
            },
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        assert items[0].closing is not None
        assert items[0].closing.done_definition == ["Tests pass"]
        assert items[0].closing.evidence.commits == ["abc1234"]


# ---------------------------------------------------------------------------
# Loading: error cases
# ---------------------------------------------------------------------------

class TestLoadErrors:
    def test_missing_file(self):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_work_items("/nonexistent/path/items.yaml")

    def test_malformed_yaml(self, tmp_path):
        """Broken YAML raises ValueError."""
        path = tmp_path / "bad.yaml"
        path.write_text("items:\n  - id: [unterminated", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed YAML"):
            load_work_items(str(path))

    def test_malformed_json(self, tmp_path):
        """Broken JSON raises ValueError."""
        path = tmp_path / "bad.json"
        path.write_text('{"version": 1, "items": [', encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed JSON"):
            load_work_items(str(path))

    def test_unsupported_extension(self, tmp_path):
        """Unsupported file extension raises ValueError."""
        path = tmp_path / "items.toml"
        path.write_text("version = 1", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            load_work_items(str(path))

    def test_missing_version(self, tmp_path):
        """Missing version field raises ValueError."""
        path = _write_yaml(tmp_path, {"items": []})
        with pytest.raises(ValueError, match="Missing required field 'version'"):
            load_work_items(path)

    def test_wrong_version(self, tmp_path):
        """Unsupported version raises ValueError."""
        path = _write_yaml(tmp_path, {"version": 99, "items": []})
        with pytest.raises(ValueError, match="Unsupported schema version"):
            load_work_items(path)

    def test_missing_items(self, tmp_path):
        """Missing items field raises ValueError."""
        path = _write_yaml(tmp_path, {"version": 1})
        with pytest.raises(ValueError, match="Missing required field 'items'"):
            load_work_items(path)

    def test_items_not_list(self, tmp_path):
        """Non-list items field raises ValueError."""
        path = _write_yaml(tmp_path, {"version": 1, "items": "not-a-list"})
        with pytest.raises(ValueError, match="'items' must be a list"):
            load_work_items(path)

    def test_unknown_status(self, tmp_path):
        """Unknown status value raises ValueError with clear message."""
        data = _minimal_file()
        data["items"][0]["kanban"]["status"] = "invented"
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid kanban\.status for item TEST-001: 'invented'"):
            load_work_items(path)

    def test_unknown_priority(self, tmp_path):
        """Unknown priority value raises ValueError."""
        data = _minimal_file()
        data["items"][0]["kanban"]["priority"] = "mega"
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid kanban\.priority for item TEST-001: 'mega'"):
            load_work_items(path)

    def test_unknown_process_group(self, tmp_path):
        """Unknown PMI process group raises ValueError."""
        data = _minimal_file()
        data["items"][0]["pmi"] = {"process_group": "deploying"}
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid pmi\.process_group.*'deploying'"):
            load_work_items(path)

    def test_unknown_risk_level(self, tmp_path):
        """Unknown risk probability raises ValueError."""
        data = _minimal_file()
        data["items"][0]["risk"] = {
            "register": [{
                "id": "R-001",
                "description": "test",
                "probability": "extreme",
            }],
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid risk\.register\[0\]\.probability.*'extreme'"):
            load_work_items(path)

    def test_unknown_response_strategy(self, tmp_path):
        """Unknown response strategy raises ValueError."""
        data = _minimal_file()
        data["items"][0]["risk"] = {
            "register": [{
                "id": "R-001",
                "description": "test",
                "response_strategy": "pray",
            }],
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid risk\.register\[0\]\.response_strategy.*'pray'"):
            load_work_items(path)

    def test_missing_required_id(self, tmp_path):
        """Item without id raises ValueError."""
        data = {
            "version": 1,
            "items": [{
                "project": "test",
                "title": "Missing id",
                "type": "bug",
                "kanban": {"status": "active", "priority": "low"},
            }],
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="Missing required field 'id'"):
            load_work_items(path)

    def test_missing_kanban(self, tmp_path):
        """Item without kanban section raises ValueError."""
        data = {
            "version": 1,
            "items": [{
                "id": "TEST-001",
                "project": "test",
                "title": "No kanban",
                "type": "bug",
            }],
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match="Missing required section 'kanban'"):
            load_work_items(path)

    def test_gtd_without_next_action(self, tmp_path):
        """GTD section without next_action raises ValueError."""
        data = _minimal_file()
        data["items"][0]["gtd"] = {
            "list": "next-actions",
            "desired_outcome": "Something",
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Missing gtd\.next_action.*TEST-001"):
            load_work_items(path)

    def test_risk_entry_missing_id(self, tmp_path):
        """Risk register entry without id raises ValueError."""
        data = _minimal_file()
        data["items"][0]["risk"] = {
            "register": [{"description": "No id"}],
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Missing risk\.register\[0\]\.id"):
            load_work_items(path)

    def test_risk_entry_missing_description(self, tmp_path):
        """Risk register entry without description raises ValueError."""
        data = _minimal_file()
        data["items"][0]["risk"] = {
            "register": [{"id": "R-001"}],
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Missing risk\.register\[0\]\.description"):
            load_work_items(path)

    def test_unknown_gtd_list(self, tmp_path):
        """Unknown GTD list value raises ValueError."""
        data = _minimal_file()
        data["items"][0]["gtd"] = {
            "list": "invalid-list",
            "next_action": "something",
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid gtd\.list.*'invalid-list'"):
            load_work_items(path)

    def test_unknown_energy(self, tmp_path):
        """Unknown GTD energy value raises ValueError."""
        data = _minimal_file()
        data["items"][0]["gtd"] = {
            "next_action": "something",
            "energy": "extreme",
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid gtd\.energy.*'extreme'"):
            load_work_items(path)

    def test_unknown_lifecycle_model(self, tmp_path):
        """Unknown PMI lifecycle model raises ValueError."""
        data = _minimal_file()
        data["items"][0]["pmi"] = {
            "process_group": "planning",
            "lifecycle_model": "waterfall",
        }
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid pmi\.lifecycle_model.*'waterfall'"):
            load_work_items(path)

    def test_unknown_data_sensitivity(self, tmp_path):
        """Unknown data_sensitivity raises ValueError."""
        data = _minimal_file()
        data["items"][0]["data_sensitivity"] = "top-secret"
        path = _write_yaml(tmp_path, data)
        with pytest.raises(ValueError, match=r"Invalid data_sensitivity.*'top-secret'"):
            load_work_items(path)


# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

class TestBoardRender:
    def test_empty_items(self):
        """Empty items list renders 'No work items found.'"""
        output = render_board([])
        assert "No work items found." in output

    def test_groups_by_status(self, tmp_path):
        """Items are grouped under their status headers."""
        data = {
            "version": 1,
            "items": [
                _minimal_item(id="A-001", kanban={"status": "active", "priority": "high"}),
                _minimal_item(id="B-001", kanban={"status": "review", "priority": "medium"}),
            ],
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_board(items)
        assert "## Active" in output
        assert "## Review" in output
        # Active should appear before Review in lifecycle order
        assert output.index("## Active") < output.index("## Review")

    def test_sorts_by_priority(self, tmp_path):
        """Within a status, items are sorted by priority (critical first)."""
        data = {
            "version": 1,
            "items": [
                _minimal_item(id="LOW-001", kanban={"status": "active", "priority": "low"}),
                _minimal_item(id="CRIT-001", kanban={"status": "active", "priority": "critical"}),
                _minimal_item(id="HIGH-001", kanban={"status": "active", "priority": "high"}),
            ],
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_board(items)
        # Find the order of IDs in the output
        crit_pos = output.index("CRIT-001")
        high_pos = output.index("HIGH-001")
        low_pos = output.index("LOW-001")
        assert crit_pos < high_pos < low_pos

    def test_status_filter(self, tmp_path):
        """--status filter only shows requested statuses."""
        data = {
            "version": 1,
            "items": [
                _minimal_item(id="A-001", kanban={"status": "active", "priority": "high"}),
                _minimal_item(id="B-001", kanban={"status": "done", "priority": "low"}),
                _minimal_item(id="C-001", kanban={"status": "review", "priority": "medium"}),
            ],
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_board(items, statuses=["active", "review"])
        assert "A-001" in output
        assert "C-001" in output
        assert "B-001" not in output
        assert "## Done" not in output

    def test_invalid_status_filter(self, tmp_path):
        """Invalid status in filter raises ValueError."""
        items = load_work_items(_write_yaml(tmp_path, _minimal_file()))
        with pytest.raises(ValueError, match="Invalid status filter"):
            render_board(items, statuses=["nonexistent"])

    def test_board_includes_pmi_phase(self, tmp_path):
        """Board output includes PMI phase column data."""
        data = _minimal_file()
        data["items"][0]["pmi"] = {"process_group": "executing"}
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_board(items)
        assert "executing" in output

    def test_board_includes_next_action(self, tmp_path):
        """Board output includes GTD next action."""
        data = _minimal_file()
        data["items"][0]["gtd"] = {"next_action": "Do the next thing"}
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_board(items)
        assert "Do the next thing" in output

    def test_board_includes_risk(self, tmp_path):
        """Board output includes risk level."""
        data = _minimal_file()
        data["items"][0]["risk"] = {"level": "high"}
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_board(items)
        assert "high" in output

    def test_no_matching_statuses(self, tmp_path):
        """Filtering to a status with no items shows appropriate message."""
        items = load_work_items(_write_yaml(tmp_path, _minimal_file()))
        output = render_board(items, statuses=["done"])
        assert "No work items match" in output


# ---------------------------------------------------------------------------
# WBS rendering
# ---------------------------------------------------------------------------

class TestWbsRender:
    def test_empty_items(self):
        """Empty items list renders 'No work items found.'"""
        output = render_wbs([])
        assert "No work items found." in output

    def test_groups_by_area(self, tmp_path):
        """Items are grouped by WBS area."""
        data = {
            "version": 1,
            "items": [
                {**_minimal_item(id="A-001"), "wbs": {"area": "ai_control_plane"}},
                {**_minimal_item(id="B-001", project="other"), "wbs": {"area": "environmental_monitoring"}},
            ],
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_wbs(items)
        assert "Ai Control Plane" in output
        assert "Environmental Monitoring" in output

    def test_unclassified_items(self, tmp_path):
        """Items without WBS section are grouped under (Unclassified)."""
        data = _minimal_file()  # no wbs
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_wbs(items)
        assert "(Unclassified)" in output

    def test_wbs_shows_status_and_priority(self, tmp_path):
        """WBS output includes status and priority badges."""
        data = _minimal_file()
        data["items"][0]["wbs"] = {"area": "test_area", "component": "test_comp"}
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_wbs(items)
        assert "[active]" in output
        assert "[medium]" in output

    def test_wbs_component_grouping(self, tmp_path):
        """Items are further grouped by component within a project."""
        data = {
            "version": 1,
            "items": [
                {**_minimal_item(id="A-001"), "wbs": {"area": "test", "component": "alpha"}},
                {**_minimal_item(id="A-002"), "wbs": {"area": "test", "component": "beta"}},
            ],
        }
        path = _write_yaml(tmp_path, data)
        items = load_work_items(path)
        output = render_wbs(items)
        assert "**alpha**" in output
        assert "**beta**" in output


# ---------------------------------------------------------------------------
# Privacy guardrail: example file must not contain private paths
# ---------------------------------------------------------------------------

class TestPrivacyGuardrails:
    def test_example_no_private_paths(self):
        """The example file must not contain real local absolute paths."""
        with open(EXAMPLE_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for Windows absolute paths (C:\, D:\, etc.)
        assert not re.search(r"[A-Za-z]:\\Users\\", content), \
            "Example file contains a Windows user path"

        # Check for Unix home paths
        assert not re.search(r"/home/\w+", content), \
            "Example file contains a Unix home path"
        assert not re.search(r"~/.triagecore", content), \
            "Example file contains a ~/.triagecore reference"

        # Check for common private identifiers
        assert "corey" not in content.lower() or "coreytshaffer" not in content.lower(), \
            "Example file contains a private username"
