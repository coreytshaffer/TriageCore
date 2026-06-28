import json
from pathlib import Path

import pytest

from triage_core.workspace_board import load_work_items
from triage_core.workspace_eval_packet import (
    build_workspace_evaluator_packet,
    write_workspace_evaluator_packet,
)
from triage_core.workspace_now import load_today_file


def test_build_workspace_evaluator_packet_omits_private_and_today_notes():
    items = load_work_items("docs/examples/workspace_work_items.example.yaml")
    today = load_today_file("docs/examples/workspace_today.example.yaml")
    target = next(item for item in items if item.id == "DEMO-001")

    packet = build_workspace_evaluator_packet(target, today=today)
    rendered = json.dumps(packet, sort_keys=True)

    assert packet["schema_version"] == "workspace_evaluator_input_v1"
    assert packet["case_id"] == "workspace_demo-001"
    assert packet["focus_context"]["in_today_focus"] is True
    assert packet["focus_context"]["focus_rank"] == 1
    assert packet["omissions"]["work_item_notes"] is True
    assert packet["omissions"]["today_notes"] is True
    assert "Read-only context feature" not in rendered
    assert "Close one slice before opening another." not in rendered

    observations = {entry["code"]: entry["value"] for entry in packet["observations"]}
    assert observations["has_handoff"] is True
    assert observations["has_required_checks"] is True
    assert observations["private_notes_omitted"] is True


def test_build_workspace_evaluator_packet_projects_external_reference():
    items = load_work_items("docs/examples/github_issues_preview.example.yaml")
    target = items[0]

    packet = build_workspace_evaluator_packet(target)

    assert packet["work_item"]["id"] == "GH-TRIAGECORE-999"
    assert packet["evidence_summary"]["external_reference"]["source"] == "github"
    assert packet["evidence_summary"]["external_reference"]["github"]["repo"] == "coreytshaffer/TriageCore"
    observations = {entry["code"]: entry["value"] for entry in packet["observations"]}
    assert observations["has_external_reference"] is True


def test_write_workspace_evaluator_packet_requires_force(tmp_path):
    items = load_work_items("docs/examples/workspace_work_items.example.yaml")
    packet = build_workspace_evaluator_packet(items[0])
    output_path = tmp_path / "workspace_eval_packet.json"

    write_workspace_evaluator_packet(packet, output_path)
    with pytest.raises(FileExistsError):
        write_workspace_evaluator_packet(packet, output_path)

    write_workspace_evaluator_packet(packet, output_path, force=True)
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["case_id"] == packet["case_id"]


def test_workspace_eval_packet_example_fixture_stays_stable():
    items = load_work_items("docs/examples/workspace_work_items.example.yaml")
    today = load_today_file("docs/examples/workspace_today.example.yaml")
    target = next(item for item in items if item.id == "DEMO-001")

    packet = build_workspace_evaluator_packet(
        target,
        today=today,
        generated_at="2026-06-27T00:00:00Z",
    )

    fixture_path = Path("docs/examples/workspace_eval_packet.example.json")
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert packet == expected

    rendered = json.dumps(packet, sort_keys=True)
    assert "Read-only context feature" not in rendered
    assert "Close one slice before opening another." not in rendered
