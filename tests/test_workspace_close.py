import yaml
import pytest
from triage_core.workspace_board import WorkItem, load_work_items
from triage_core.workspace_close import generate_closing_packet, close_work_item

def test_generate_closing_packet(tmp_path):
    live_file = tmp_path / "live.yaml"
    live_data = {
        "version": 1,
        "items": [
            {
                "id": "CR-WU-011",
                "project": "triagecore",
                "title": "Workspace Closing Packet",
                "type": "feature",
                "kanban": {"status": "active", "priority": "high"},
                "risk": {"level": "low"}
            }
        ]
    }
    with open(live_file, "w") as f:
        yaml.dump(live_data, f)
        
    items = load_work_items(str(live_file))
    item = items[0]
    
    packet = generate_closing_packet(
        item,
        commit="abcdef123",
        tests="pytest tests/test_workspace_close.py",
        summary="Added closing packet generation."
    )
    
    assert "Workspace Closing Packet: CR-WU-011" in packet
    assert "Title:** Workspace Closing Packet" in packet
    assert "Summary:** Added closing packet generation." in packet
    assert "Tests Run:** `pytest tests/test_workspace_close.py`" in packet
    assert "Commit/Evidence:** `abcdef123`" in packet


def test_close_work_item_mutates_status(tmp_path):
    live_file = tmp_path / "live.yaml"
    output_file = tmp_path / "out.yaml"
    
    live_data = {
        "version": 1,
        "items": [
            {
                "id": "CR-WU-011",
                "project": "triagecore",
                "title": "Workspace Closing Packet",
                "type": "feature",
                "kanban": {"status": "active", "priority": "high"},
                "risk": {"level": "low"}
            },
            {
                "id": "OTHER-1",
                "project": "triagecore",
                "title": "Other",
                "type": "task",
                "kanban": {"status": "backlog", "priority": "low"},
                "risk": {"level": "low"}
            }
        ]
    }
    
    with open(live_file, "w") as f:
        yaml.dump(live_data, f)
        
    close_work_item(str(live_file), "CR-WU-011", str(output_file))
    
    with open(output_file, "r") as f:
        out_data = yaml.safe_load(f)
        
    # Check that CR-WU-011 is done
    assert out_data["items"][0]["id"] == "CR-WU-011"
    assert out_data["items"][0]["kanban"]["status"] == "done"
    assert out_data["items"][0]["kanban"]["priority"] == "high" # Preserved
    
    # Check that OTHER-1 is unchanged
    assert out_data["items"][1]["id"] == "OTHER-1"
    assert out_data["items"][1]["kanban"]["status"] == "backlog"


def test_close_work_item_missing_id_raises(tmp_path):
    live_file = tmp_path / "live.yaml"
    output_file = tmp_path / "out.yaml"
    
    live_data = {
        "version": 1,
        "items": []
    }
    
    with open(live_file, "w") as f:
        yaml.dump(live_data, f)
        
    with pytest.raises(ValueError, match="not found in"):
        close_work_item(str(live_file), "CR-WU-011", str(output_file))


def test_close_work_item_prevents_overwrite_without_force(tmp_path):
    live_file = tmp_path / "live.yaml"
    
    live_data = {
        "version": 1,
        "items": [
            {
                "id": "CR-WU-011",
                "project": "triagecore",
                "title": "Workspace Closing Packet",
                "type": "feature",
                "kanban": {"status": "active", "priority": "high"},
                "risk": {"level": "low"}
            }
        ]
    }
    
    with open(live_file, "w") as f:
        yaml.dump(live_data, f)
        
    # Output points to live file
    with pytest.raises(FileExistsError):
        close_work_item(str(live_file), "CR-WU-011", str(live_file))
        
    # With force it should work
    close_work_item(str(live_file), "CR-WU-011", str(live_file), force=True)
