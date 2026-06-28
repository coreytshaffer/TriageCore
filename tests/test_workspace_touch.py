import os
import yaml
import pytest
import datetime
from pathlib import Path
from triage_core.workspace_touch import touch_work_item

def create_yaml(filepath, content):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def read_yaml(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
        return doc["items"]

def test_touch_creates_review_block(tmp_path):
    """If review block doesn't exist, it should be created."""
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    
    yaml_content = """
version: 1
items:
  - id: "CR-001"
    project: "Proj A"
    title: "Test"
    type: "task"
    kanban:
      status: "active"
      priority: "high"
"""
    create_yaml(input_file, yaml_content)
    
    touch_work_item(str(input_file), "CR-001", str(output_file))
    
    result = read_yaml(output_file)
    assert len(result) == 1
    item = result[0]
    
    assert "review" in item
    assert "last_touched" in item["review"]
    
    # Check timestamp format
    dt = datetime.datetime.strptime(item["review"]["last_touched"], "%Y-%m-%dT%H:%M:%SZ")
    assert dt is not None

def test_touch_preserves_unrelated_fields(tmp_path):
    """Touching should preserve unrelated fields."""
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    
    yaml_content = """
version: 1
items:
  - id: "CR-001"
    project: "Proj A"
    title: "Test"
    type: "task"
    kanban:
      status: "active"
      priority: "high"
    notes: "Don't lose this"
    handoff:
      preferred_tool: "codex"
"""
    create_yaml(input_file, yaml_content)
    
    touch_work_item(str(input_file), "CR-001", str(output_file))
    
    result = read_yaml(output_file)
    item = result[0]
    
    assert item["notes"] == "Don't lose this"
    assert item["handoff"]["preferred_tool"] == "codex"

def test_touch_preserves_existing_review_fields(tmp_path):
    """Touching should preserve existing review fields like last_reviewed."""
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    
    yaml_content = """
version: 1
items:
  - id: "CR-001"
    project: "Proj A"
    title: "Test"
    type: "task"
    kanban:
      status: "active"
      priority: "high"
    review:
      last_reviewed: "2026-06-01T00:00:00Z"
      stale_after_days: 20
      review_note: "Old note"
"""
    create_yaml(input_file, yaml_content)
    
    touch_work_item(str(input_file), "CR-001", str(output_file))
    
    result = read_yaml(output_file)
    item = result[0]
    
    assert item["review"]["last_reviewed"] == "2026-06-01T00:00:00Z"
    assert item["review"]["stale_after_days"] == 20
    assert item["review"]["review_note"] == "Old note"
    assert "last_touched" in item["review"]

def test_touch_updates_note(tmp_path):
    """If --note is provided, it should update review_note."""
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    
    yaml_content = """
version: 1
items:
  - id: "CR-001"
    project: "Proj A"
    title: "Test"
    type: "task"
    kanban:
      status: "active"
      priority: "high"
    review:
      review_note: "Old note"
"""
    create_yaml(input_file, yaml_content)
    
    touch_work_item(str(input_file), "CR-001", str(output_file), note="New note")
    
    result = read_yaml(output_file)
    item = result[0]
    
    assert item["review"]["review_note"] == "New note"

def test_inplace_without_force_fails(tmp_path):
    """In-place update without force should fail."""
    input_file = tmp_path / "input.yaml"
    
    yaml_content = """
version: 1
items:
  - id: "CR-001"
    project: "Proj A"
    title: "Test"
    type: "task"
    kanban:
      status: "active"
      priority: "high"
"""
    create_yaml(input_file, yaml_content)
    
    with pytest.raises(ValueError, match="You must use --force"):
        touch_work_item(str(input_file), "CR-001", str(input_file))

def test_inplace_with_backup(tmp_path):
    """In-place update with backup should create a .bak file."""
    input_file = tmp_path / "input.yaml"
    
    yaml_content = """
version: 1
items:
  - id: "CR-001"
    project: "Proj A"
    title: "Test"
    type: "task"
    kanban:
      status: "active"
      priority: "high"
"""
    create_yaml(input_file, yaml_content)
    
    touch_work_item(str(input_file), "CR-001", str(input_file), force=True, backup=True)
    
    backup_file = tmp_path / "input.yaml.bak"
    assert backup_file.exists()

def test_unknown_id_fails(tmp_path):
    """Touching an unknown ID should fail."""
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    
    yaml_content = """
version: "1.0"
items:
  - id: "CR-001"
    project: "Proj A"
    title: "Test"
    type: "task"
    kanban:
      status: "active"
      priority: "high"
"""
    create_yaml(input_file, yaml_content)
    
    with pytest.raises(ValueError, match="not found"):
        touch_work_item(str(input_file), "UNKNOWN-001", str(output_file))
