import os
import shutil
import yaml
from datetime import datetime, timezone
from triage_core.workspace_board import load_work_items

def touch_work_item(filepath: str, item_id: str, output_path: str, note: str = None, force: bool = False, backup: bool = False) -> None:
    """
    Touch a work item by updating its review.last_touched timestamp.
    Optionally sets review.review_note.
    """
    in_place = os.path.abspath(filepath) == os.path.abspath(output_path)
    
    if in_place and not force:
        raise ValueError(f"Output path '{output_path}' is the same as the input path. You must use --force to overwrite in-place.")
        
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Source file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        live_data = yaml.safe_load(f)
        
    if not isinstance(live_data, dict):
        raise ValueError(f"Expected a dictionary at the root of {filepath}")

    live_items = live_data.get("items", [])
    if not isinstance(live_items, list):
        raise ValueError(f"Expected 'items' to be a list in {filepath}")

    found = False
    for i, item_dict in enumerate(live_items):
        if not isinstance(item_dict, dict):
            continue
            
        if item_dict.get("id") == item_id:
            found = True
            
            # Create review block if it doesn't exist
            if "review" not in item_dict or not isinstance(item_dict["review"], dict):
                item_dict["review"] = {}
                
            # Update last_touched
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            item_dict["review"]["last_touched"] = now_str
            
            # Update review_note if provided
            if note is not None:
                item_dict["review"]["review_note"] = note
                
            break
            
    if not found:
        raise ValueError(f"Work item {item_id} not found in {filepath}")
        
    output_data = {
        "version": live_data.get("version", 1),
        "items": live_items
    }

    # Write candidate to a temporary file
    temp_output = f"{output_path}.tmp.yaml"
    try:
        with open(temp_output, "w", encoding="utf-8") as f:
            yaml.safe_dump(output_data, f, sort_keys=False, allow_unicode=True)
            
        # Validate candidate
        try:
            load_work_items(temp_output)
        except Exception as e:
            raise ValueError(f"Updated YAML failed validation: {e}")
            
        # Backup if requested and overwriting in-place
        if backup and in_place and os.path.exists(filepath):
            backup_path = f"{filepath}.bak"
            shutil.copy2(filepath, backup_path)
            
        # Commit to output_path
        os.replace(temp_output, output_path)
    finally:
        if os.path.exists(temp_output):
            os.remove(temp_output)
