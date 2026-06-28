import pytest
import os
import json
from unittest.mock import patch, MagicMock

from triage_core.workspace_github_import import (
    fetch_github_issues,
    map_issue_to_work_item,
    generate_preview_yaml
)
from triage_core.workspace_board import load_work_items

# Mock GitHub API Response
MOCK_ISSUES = [
    {
        "number": 88,
        "title": "Bug in the matrix",
        "html_url": "https://github.com/example/repo/issues/88",
        "state": "open",
        "labels": [{"name": "bug"}, {"name": "high-priority"}],
        "created_at": "2026-06-25T10:00:00Z",
        "updated_at": "2026-06-26T12:00:00Z",
    },
    {
        "number": 89,
        "title": "Add laser beams",
        "html_url": "https://github.com/example/repo/issues/89",
        "state": "open",
        "labels": [{"name": "enhancement"}],
        "created_at": "2026-06-26T10:00:00Z",
        "updated_at": "2026-06-26T10:00:00Z",
    },
    {
        "number": 90,
        "title": "Some pull request",
        "html_url": "https://github.com/example/repo/pull/90",
        "state": "open",
        "labels": [],
        "created_at": "2026-06-26T10:00:00Z",
        "updated_at": "2026-06-26T10:00:00Z",
        "pull_request": {} # Should be filtered out
    }
]

@patch("urllib.request.urlopen")
def test_fetch_github_issues_filters_prs(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(MOCK_ISSUES).encode('utf-8')
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    issues = fetch_github_issues("example/repo")
    assert len(issues) == 2
    assert issues[0]["number"] == 88
    assert issues[1]["number"] == 89
    # PR #90 should be missing

def test_map_issue_to_work_item():
    issue = MOCK_ISSUES[0]
    repo = "example/repo"
    item = map_issue_to_work_item(repo, issue)
    
    assert item["id"] == "GH-REPO-088"
    assert item["project"] == "repo"
    assert item["title"] == "Bug in the matrix"
    assert item["type"] == "bug"
    assert item["kanban"]["status"] == "backlog"
    assert item["gtd"]["next_action"] == "Clarify imported GitHub issue and decide whether to promote it into active work."
    assert item["external"]["source"] == "github"
    assert item["external"]["github"]["repo"] == "example/repo"
    assert item["external"]["github"]["issue_number"] == 88
    assert item["external"]["github"]["labels"] == ["bug", "high-priority"]

@patch("triage_core.workspace_github_import.fetch_github_issues")
def test_generate_preview_yaml_validates(mock_fetch, tmp_path):
    mock_fetch.return_value = MOCK_ISSUES[:2] # Exclude the PR
    
    out_file = tmp_path / "preview.yaml"
    
    generate_preview_yaml("example/repo", str(out_file))
    
    assert out_file.exists()
    
    # Load it using the official workspace loader to ensure it passes the rigorous dataclass schema rules
    items = load_work_items(str(out_file))
    
    assert len(items) == 2
    assert items[0].id == "GH-REPO-088"
    assert items[0].external.source == "github"
    assert items[0].external.github.issue_number == 88
    assert items[1].id == "GH-REPO-089"
    assert items[1].type == "feature"

@patch("triage_core.workspace_github_import.fetch_github_issues")
def test_generate_preview_yaml_prevents_overwrite(mock_fetch, tmp_path):
    mock_fetch.return_value = MOCK_ISSUES[:2]
    
    out_file = tmp_path / "preview.yaml"
    out_file.write_text("existing content")
    
    with pytest.raises(FileExistsError):
        generate_preview_yaml("example/repo", str(out_file))
        
    # Should work with --force
    generate_preview_yaml("example/repo", str(out_file), force=True)
