import pytest
import os
import yaml
from triage_core.workspace_promote import promote_items
from triage_core.workspace_board import load_work_items

def test_promote_new_item(tmp_path):
    live_file = tmp_path / "live.yaml"
    preview_file = tmp_path / "preview.yaml"
    output_file = tmp_path / "out.yaml"
    
    live_data = {
        "version": 1,
        "items": [
            {
                "id": "ITEM-1",
                "project": "triagecore",
                "title": "Existing Item",
                "type": "feature",
                "kanban": {"status": "active", "priority": "high"}
            }
        ]
    }
    
    preview_data = {
        "version": 1,
        "items": [
            {
                "id": "GH-REPO-001",
                "project": "triagecore",
                "title": "New GitHub Issue",
                "type": "bug",
                "kanban": {"status": "backlog", "priority": "medium"},
                "external": {
                    "source": "github",
                    "github": {"issue_number": 1, "repo": "example/repo"}
                }
            }
        ]
    }
    
    with open(live_file, "w") as f:
        yaml.dump(live_data, f)
        
    with open(preview_file, "w") as f:
        yaml.dump(preview_data, f)
        
    promote_items(str(live_file), str(preview_file), str(output_file), ["GH-REPO-001"])
    
    # Verify via our official dataclass loader
    items = load_work_items(str(output_file))
    
    assert len(items) == 2
    assert items[0].id == "ITEM-1"
    assert items[1].id == "GH-REPO-001"
    assert items[1].external.source == "github"

def test_promote_existing_item_merges_external_only(tmp_path):
    live_file = tmp_path / "live.yaml"
    preview_file = tmp_path / "preview.yaml"
    output_file = tmp_path / "out.yaml"
    
    live_data = {
        "version": 1,
        "items": [
            {
                "id": "GH-REPO-001",
                "project": "triagecore",
                "title": "Renamed Issue manually",
                "type": "bug",
                "kanban": {"status": "active", "priority": "high"},
                "gtd": {"next_action": "Manually authored next action"},
                "external": {
                    "source": "github",
                    "github": {"issue_number": 1, "repo": "example/repo", "updated_at": "old"}
                }
            }
        ]
    }
    
    preview_data = {
        "version": 1,
        "items": [
            {
                "id": "GH-REPO-001",
                "project": "triagecore",
                "title": "Original Title from GitHub",
                "type": "bug",
                "kanban": {"status": "backlog", "priority": "medium"},
                "external": {
                    "source": "github",
                    "github": {"issue_number": 1, "repo": "example/repo", "updated_at": "new"}
                }
            }
        ]
    }
    
    with open(live_file, "w") as f:
        yaml.dump(live_data, f)
        
    with open(preview_file, "w") as f:
        yaml.dump(preview_data, f)
        
    promote_items(str(live_file), str(preview_file), str(output_file), ["GH-REPO-001"])
    
    # Load raw to verify exact preservation
    with open(output_file, "r") as f:
        out_data = yaml.safe_load(f)
        
    item = out_data["items"][0]
    # Check that manual overrides are preserved
    assert item["title"] == "Renamed Issue manually"
    assert item["kanban"]["status"] == "active"
    assert item["gtd"]["next_action"] == "Manually authored next action"
    
    # Check that external was updated
    assert item["external"]["github"]["updated_at"] == "new"

def test_promote_missing_id_raises(tmp_path):
    live_file = tmp_path / "live.yaml"
    preview_file = tmp_path / "preview.yaml"
    output_file = tmp_path / "out.yaml"
    
    live_file.write_text("version: 1\nitems: []")
    preview_file.write_text("version: 1\nitems: []")
    
    with pytest.raises(ValueError, match="not found in preview file"):
        promote_items(str(live_file), str(preview_file), str(output_file), ["MISSING"])

def test_promote_prevents_overwrite_without_force(tmp_path):
    live_file = tmp_path / "live.yaml"
    preview_file = tmp_path / "preview.yaml"
    
    live_file.write_text("version: 1\nitems: []")
    preview_file.write_text("version: 1\nitems: []")
    
    # Output points to live file
    with pytest.raises(FileExistsError):
        promote_items(str(live_file), str(preview_file), str(live_file), [])
        
    # With force it should work
    promote_items(str(live_file), str(preview_file), str(live_file), [], force=True)
