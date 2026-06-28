import json
import urllib.request
import urllib.error
import datetime
import os
import yaml
from typing import Any


def fetch_github_issues(repo: str) -> list[dict[str, Any]]:
    """Fetch open issues from a public GitHub repository.
    
    Args:
        repo: Format "owner/repo"
        
    Returns:
        List of issue dictionaries from GitHub API.
    """
    url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100"
    
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TriageCore-Workspace-Importer"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            # Filter out PRs (GitHub API returns PRs in the issues endpoint)
            issues_only = [item for item in data if "pull_request" not in item]
            return issues_only
            
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to fetch issues for {repo}: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GitHub response: {e}")


def map_issue_to_work_item(repo: str, issue: dict[str, Any]) -> dict[str, Any]:
    """Map a raw GitHub issue dict to a TriageCore WorkItem dict.
    
    Returns a dict that conforms to the workspace_work_items schema.
    """
    issue_number = issue.get("number")
    # Clean repo name for ID, e.g., coreytshaffer/TriageCore -> TRIAGECORE
    repo_clean = repo.split('/')[-1].upper()
    item_id = f"GH-{repo_clean}-{issue_number:03d}"
    
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    labels = [lbl.get("name") for lbl in issue.get("labels", []) if isinstance(lbl, dict)]
    
    return {
        "id": item_id,
        "project": repo.split('/')[-1],
        "title": issue.get("title", "Untitled Issue"),
        "type": "feature" if "enhancement" in labels else "bug" if "bug" in labels else "task",
        "kanban": {
            "status": "backlog",
            "priority": "medium"
        },
        "pmi": {
            "process_group": "initiating",
            "lifecycle_model": "hybrid"
        },
        "gtd": {
            "list": "inbox",
            "next_action": "Clarify imported GitHub issue and decide whether to promote it into active work."
        },
        "risk": {
            "level": "low"
        },
        "external": {
            "source": "github",
            "github": {
                "repo": repo,
                "issue_number": issue_number,
                "url": issue.get("html_url"),
                "state": issue.get("state"),
                "labels": labels,
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "imported_at": now_iso
            }
        }
    }


def generate_preview_yaml(repo: str, output_path: str, force: bool = False):
    """Fetch GitHub issues and generate a preview YAML file."""
    if os.path.exists(output_path) and not force:
        raise FileExistsError(f"Output file {output_path} already exists. Use --force to overwrite.")
        
    issues = fetch_github_issues(repo)
    
    work_items = []
    for issue in issues:
        work_items.append(map_issue_to_work_item(repo, issue))
        
    payload = {
        "version": 1,
        "items": work_items
    }
    
    # Create parent dirs if needed
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Avoid yaml anchors and make it human readable
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
