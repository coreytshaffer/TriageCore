import os
import yaml
import shutil
import datetime
from typing import Optional
from triage_core.workspace_board import WorkItem, load_work_items

def generate_closing_packet(item: WorkItem, commit: Optional[str] = None, tests: Optional[str] = None, summary: Optional[str] = None) -> str:
    """Generate a Markdown closing packet for a work item."""
    
    commit_str = commit if commit else "N/A"
    tests_str = tests if tests else "N/A"
    summary_str = summary if summary else "No summary provided."
    
    # We will safely pull other fields from the item if present.
    # The packet should include: item ID, title, completed deliverable (summary), tests run, evidence/commits.
    # It will also leave stubs for unresolved risks, lessons learned, recommended next item.
    
    packet = f"""# Workspace Closing Packet: {item.id}

## Item Details
- **ID:** {item.id}
- **Title:** {item.title}
- **Project:** {item.project}

## Completion Evidence
- **Summary:** {summary_str}
- **Tests Run:** `{tests_str}`
- **Commit/Evidence:** `{commit_str}`

## Review (Operator Fill-in)
- **Unresolved Risks:** None identified.
- **Lessons Learned:** 
- **Recommended Next Item:** 

"""
    return packet


def close_work_item(live_path: str, target_id: str, output_path: str, force: bool = False, backup: bool = False):
    """Mutate the work_items.yaml to mark the target_id as done."""
    if os.path.exists(output_path) and not force:
        raise FileExistsError(f"Output file {output_path} already exists. Use --force to overwrite.")
        
    with open(live_path, 'r', encoding='utf-8') as f:
        live_data = yaml.safe_load(f)
        
    live_items = live_data.get("items", [])
    
    found = False
    for i, it in enumerate(live_items):
        if it.get("id") == target_id:
            found = True
            if "kanban" not in it:
                it["kanban"] = {}
            it["kanban"]["status"] = "done"
            # Keep manual fields like priority, etc. intact
            break
            
    if not found:
        raise ValueError(f"Target ID {target_id} not found in {live_path}")
        
    output_data = {
        "version": live_data.get("version", 1),
        "items": live_items
    }
    
    tmp_path = output_path + ".tmp.yaml"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        
    try:
        load_work_items(tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        raise RuntimeError(f"Close mutation failed validation: {e}")
        
    if os.path.exists(output_path):
        if backup and os.path.abspath(output_path) == os.path.abspath(live_path):
            backup_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%S")
            basename = os.path.basename(output_path)
            name, ext = os.path.splitext(basename)
            backup_file = os.path.join(backup_dir, f"{name}.{timestamp}{ext}")
            shutil.copy2(output_path, backup_file)
            
        os.remove(output_path)
    os.rename(tmp_path, output_path)
