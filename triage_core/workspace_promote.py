import yaml
import os
import shutil
import datetime
from copy import deepcopy
from triage_core.workspace_board import load_work_items


def promote_items(live_path: str, preview_path: str, output_path: str, target_ids: list[str], force: bool = False, backup: bool = False):
    """Promote selected GitHub preview items into the real work_items.yaml.
    
    If an item already exists in the live file, its `external` block is updated,
    but all other user-authored fields are preserved.
    If it is new, it is appended.
    """
    if os.path.exists(output_path) and not force:
        raise FileExistsError(f"Output file {output_path} already exists. Use --force to overwrite.")
            
    # Load raw dicts to preserve structure/order as best as possible
    with open(live_path, 'r', encoding='utf-8') as f:
        live_data = yaml.safe_load(f)
        
    with open(preview_path, 'r', encoding='utf-8') as f:
        preview_data = yaml.safe_load(f)
        
    live_items = live_data.get("items", [])
    preview_items = preview_data.get("items", [])
    
    # Map by ID for quick lookup
    live_map = {item["id"]: item for item in live_items}
    preview_map = {item["id"]: item for item in preview_items}
    
    for tid in target_ids:
        if tid not in preview_map:
            raise ValueError(f"Target ID {tid} not found in preview file {preview_path}")
            
        preview_item = preview_map[tid]
        
        if tid in live_map:
            # Item exists: merge logic
            # Preserve user-authored fields, just update the external block
            # and maybe sync the updated_at timestamp or title if we want, but safer to just update external.
            live_map[tid]["external"] = deepcopy(preview_item.get("external"))
        else:
            # New item: append
            live_items.append(deepcopy(preview_item))
            live_map[tid] = live_items[-1]
            
    # Prepare output payload
    output_data = {
        "version": live_data.get("version", 1),
        "items": live_items
    }
    
    # Write to a temporary file first to validate
    tmp_path = output_path + ".tmp.yaml"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
    # Validate the written file using the rigorous dataclass loader
    try:
        load_work_items(tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        raise RuntimeError(f"Promotion failed validation: {e}")
        
    # Validation passed, move to final destination
    if os.path.exists(output_path):
        if backup and os.path.abspath(output_path) == os.path.abspath(live_path):
            # The user asked for a backup of the live file before we overwrite it
            backup_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%S")
            basename = os.path.basename(output_path)
            name, ext = os.path.splitext(basename)
            backup_file = os.path.join(backup_dir, f"{name}.{timestamp}{ext}")
            shutil.copy2(output_path, backup_file)
            
        os.remove(output_path)
    os.rename(tmp_path, output_path)
