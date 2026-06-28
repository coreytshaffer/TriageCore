import yaml
from triage_core.workspace_review_import import render_import_review

def test_render_import_review(tmp_path):
    preview_file = tmp_path / "preview.yaml"
    
    preview_data = {
        "version": 1,
        "items": [
            {
                "id": "GH-TRIAGECORE-088",
                "project": "triagecore",
                "title": "Add workspace handoff export",
                "type": "feature",
                "kanban": {"status": "backlog", "priority": "medium"},
                "external": {
                    "source": "github",
                    "github": {
                        "issue_number": 88, 
                        "repo": "coreytshaffer/TriageCore",
                        "labels": ["enhancement"],
                        "updated_at": "2026-06-27T10:00:00Z"
                    }
                }
            },
            {
                "id": "GH-TRIAGECORE-089",
                "project": "triagecore",
                "title": "Refactor CLI dispatch",
                "type": "task",
                "kanban": {"status": "backlog", "priority": "medium"},
                "external": {
                    "source": "github",
                    "github": {
                        "issue_number": 89, 
                        "repo": "coreytshaffer/TriageCore",
                        "labels": ["tech-debt"],
                        "updated_at": "2026-06-27T11:00:00Z"
                    }
                }
            },
            {
                "id": "GH-TRIAGECORE-090",
                "project": "triagecore",
                "title": "Old Issue",
                "type": "task",
                "kanban": {"status": "backlog", "priority": "medium"},
                "external": {
                    "source": "github",
                    "github": {
                        "issue_number": 90, 
                        "repo": "coreytshaffer/TriageCore",
                        "labels": [],
                        "updated_at": "2026-05-01T11:00:00Z"
                    }
                }
            }
        ]
    }
    
    with open(preview_file, "w") as f:
        yaml.dump(preview_data, f)
        
    output = render_import_review(str(preview_file))
    
    assert "GitHub Import Review" in output
    assert "GH-TRIAGECORE-088" in output
    assert "GH-TRIAGECORE-089" in output
    assert "GH-TRIAGECORE-090" in output
    
    # Check suggested actions
    assert "| promote |" in output # For 88
    assert "| clarify |" in output # For 89 and 90
    
def test_render_import_review_filters(tmp_path):
    preview_file = tmp_path / "preview.yaml"
    
    preview_data = {
        "version": 1,
        "items": [
            {
                "id": "GH-TRIAGECORE-088",
                "project": "triagecore",
                "title": "Add workspace handoff export",
                "type": "feature",
                "kanban": {"status": "backlog", "priority": "medium"},
                "external": {
                    "source": "github",
                    "github": {
                        "issue_number": 88, 
                        "repo": "coreytshaffer/TriageCore",
                        "labels": ["enhancement"],
                        "updated_at": "2026-06-27T10:00:00Z"
                    }
                }
            },
            {
                "id": "GH-TRIAGECORE-089",
                "project": "triagecore",
                "title": "Refactor CLI dispatch",
                "type": "task",
                "kanban": {"status": "backlog", "priority": "medium"},
                "external": {
                    "source": "github",
                    "github": {
                        "issue_number": 89, 
                        "repo": "coreytshaffer/TriageCore",
                        "labels": ["tech-debt"],
                        "updated_at": "2026-06-27T11:00:00Z"
                    }
                }
            }
        ]
    }
    
    with open(preview_file, "w") as f:
        yaml.dump(preview_data, f)
        
    # Filter by label
    output = render_import_review(str(preview_file), label="tech-debt")
    assert "GH-TRIAGECORE-089" in output
    assert "GH-TRIAGECORE-088" not in output
    
    # Filter by date
    output = render_import_review(str(preview_file), updated_since="2026-06-27T10:30:00Z")
    assert "GH-TRIAGECORE-089" in output
    assert "GH-TRIAGECORE-088" not in output
    
    # Limit
    output = render_import_review(str(preview_file), limit=1)
    # The limit should just pick the first one since we didn't sort
    assert "GH-TRIAGECORE-088" in output
    assert "GH-TRIAGECORE-089" not in output
