import sys
import subprocess

def test_task_envelope_preview_command_returns_success():
    result = subprocess.run(
        [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "preview"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "# EXAMPLE-CR-001 Task Envelope" in result.stdout
    assert "## Scope & Risk" in result.stdout
    assert "## Governance" in result.stdout
    assert "## Admission State" in result.stdout
    assert "**Next Allowed Action:** Close preview" in result.stdout
    assert "- None" in result.stdout  # Checks that empty lists render correctly

def test_task_envelope_preview_command_is_deterministic():
    result1 = subprocess.run(
        [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "preview"],
        capture_output=True,
        text=True,
    )
    result2 = subprocess.run(
        [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "preview"],
        capture_output=True,
        text=True,
    )
    assert result1.stdout == result2.stdout

def test_task_envelope_draft_command_returns_success():
    cmd = [
        sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft",
        "--task-id", "CR-055",
        "--title", "CLI Task Envelope Wizard Draft Mode",
        "--objective", "Draft an envelope from CLI flags.",
        "--repo", "TriageCore",
        "--operator-agent-lane", "cli-operator",
        "--route", "local-cli",
        "--risk-level", "Low",
        "--requested-capability", "read_only",
        "--allowed-file", "triage_core/tc_cli.py",
        "--allowed-file", "tests/test_task_envelope_cli.py",
        "--forbidden-area", ".triagecore/ledger.jsonl",
        "--non-scope", "file writes",
        "--approval-gates", "human review",
        "--validation-plan", "pytest",
        "--evidence", "stdout markdown",
        "--current-status", "proposed",
        "--operator-decision", "Pending",
        "--next-allowed-action", "review markdown"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "# CR-055 Task Envelope" in result.stdout
    assert "CLI Task Envelope Wizard Draft Mode" in result.stdout
    assert "triage_core/tc_cli.py" in result.stdout
    assert "tests/test_task_envelope_cli.py" in result.stdout
    assert ".triagecore/ledger.jsonl" in result.stdout
    assert "## Scope & Risk" in result.stdout
    assert "## Governance" in result.stdout
    assert "## Admission State" in result.stdout

def test_task_envelope_draft_command_missing_required_returns_nonzero():
    cmd = [
        sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft",
        "--task-id", "CR-055"
        # missing other required fields
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "the following arguments are required" in result.stderr

def test_task_envelope_draft_command_missing_list_field_returns_nonzero():
    cmd = [
        sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft",
        "--task-id", "CR-055",
        "--title", "CLI Task Envelope Wizard Draft Mode",
        "--objective", "Draft an envelope from CLI flags.",
        "--repo", "TriageCore",
        "--operator-agent-lane", "cli-operator",
        "--route", "local-cli",
        "--risk-level", "Low",
        "--requested-capability", "read_only",
        # missing --allowed-file
        "--forbidden-area", ".triagecore/ledger.jsonl",
        "--non-scope", "file writes",
        "--approval-gates", "human review",
        "--validation-plan", "pytest",
        "--evidence", "stdout markdown",
        "--current-status", "proposed",
        "--operator-decision", "Pending",
        "--next-allowed-action", "review markdown"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "the following arguments are required" in result.stderr

def test_task_envelope_wizard_command_success():
    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "wizard"]

    wizard_input = "\n".join([
        "CR-057",                  # Task ID
        "Wizard Test",             # Title
        "Test wizard",             # Objective
        "TriageCore",              # Repository
        "cli-operator",            # Operator/Agent Lane
        "local-cli",               # Route
        "Low",                     # Risk Level
        "read_only",               # Requested Capability
        "file1", "done",           # Allowed Files
        "file2", "done",           # Forbidden Files or Areas
        "scope1", "done",          # Explicit Non-Scope
        "gate1",                   # Approval Gates
        "plan1",                   # Validation Plan
        "evidence1", "done",       # Evidence to Produce
        "status1",                 # Current Status
        "decision1",               # Operator Decision
        "action1",                 # Next Allowed Action
        "",                        # Failure Modes / Blocked Reasons
        "",                        # Approval Evidence
        ""                         # Admission Evidence
    ]) + "\n"

    result = subprocess.run(cmd, input=wizard_input, capture_output=True, text=True, timeout=5)

    assert result.returncode == 0
    assert "# CR-057 Task Envelope" in result.stdout
    assert "Wizard Test" in result.stdout
    assert "- file1" in result.stdout
    assert "- file2" in result.stdout
    assert "- scope1" in result.stdout
    assert "- evidence1" in result.stdout

def test_task_envelope_wizard_requires_list_entry():
    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "wizard"]

    wizard_input = "\n".join([
        "CR-057", "Title", "Objective", "Repo", "Lane", "Route", "Risk", "Cap",
        "", "done", "file1", "done", # Allowed Files fails then succeeds
        "file2", "done",
        "scope1", "done",
        "gate1", "plan1",
        "evidence1", "done",
        "status1", "decision1", "action1",
        "", "", ""
    ]) + "\n"

    result = subprocess.run(cmd, input=wizard_input, capture_output=True, text=True, timeout=5)

    assert result.returncode == 0
    assert "At least one entry is required." in result.stdout
    assert "- file1" in result.stdout

def test_task_envelope_draft_from_json_success(tmp_path):
    import json
    fixture_path = tmp_path / "fixture.json"
    payload = {
        "task_id": "CR-058", "title": "Test JSON", "objective": "Obj", "repo": "TriageCore",
        "operator_agent_lane": "cli-operator", "route": "local-cli", "risk_level": "Low",
        "requested_capability": "read_only", "approval_gates": "gates", "validation_plan": "plan",
        "current_status": "proposed", "operator_decision": "Pending", "next_allowed_action": "action",
        "allowed_files": ["file1"], "forbidden_files_or_areas": ["file2"],
        "explicit_non_scope": ["scope1"], "evidence_to_produce": ["evidence1"]
    }
    fixture_path.write_text(json.dumps(payload))

    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft", "--from-json", str(fixture_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert "# CR-058 Task Envelope" in result.stdout
    assert "Test JSON" in result.stdout

def test_task_envelope_draft_from_json_invalid_json(tmp_path):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text("{ invalid json")

    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft", "--from-json", str(fixture_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Error parsing JSON" in result.stderr

def test_task_envelope_draft_from_json_missing_field(tmp_path):
    import json
    fixture_path = tmp_path / "fixture.json"
    payload = {"task_id": "CR-058"}
    fixture_path.write_text(json.dumps(payload))

    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft", "--from-json", str(fixture_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Error validating Task Envelope JSON" in result.stderr

def test_task_envelope_draft_from_json_rejects_ledger():
    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft", "--from-json", ".triagecore/ledger.jsonl"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "ledger.jsonl is not allowed" in result.stderr

def test_task_envelope_draft_from_json_rejects_mixed_flags(tmp_path):
    import json
    fixture_path = tmp_path / "fixture.json"
    payload = {
        "task_id": "CR-058", "title": "Test JSON", "objective": "Obj", "repo": "TriageCore",
        "operator_agent_lane": "cli-operator", "route": "local-cli", "risk_level": "Low",
        "requested_capability": "read_only", "approval_gates": "gates", "validation_plan": "plan",
        "current_status": "proposed", "operator_decision": "Pending", "next_allowed_action": "action",
        "allowed_files": ["file1"], "forbidden_files_or_areas": ["file2"],
        "explicit_non_scope": ["scope1"], "evidence_to_produce": ["evidence1"]
    }
    fixture_path.write_text(json.dumps(payload))

    cmd = [
        sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft",
        "--from-json", str(fixture_path),
        "--task-id", "CR-058"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "--from-json cannot be mixed with explicit field flags" in result.stderr

def test_task_envelope_draft_from_json_empty_list(tmp_path):
    import json
    fixture_path = tmp_path / "fixture.json"
    payload = {
        "task_id": "CR-058", "title": "Test JSON", "objective": "Obj", "repo": "TriageCore",
        "operator_agent_lane": "cli-operator", "route": "local-cli", "risk_level": "Low",
        "requested_capability": "read_only", "approval_gates": "gates", "validation_plan": "plan",
        "current_status": "proposed", "operator_decision": "Pending", "next_allowed_action": "action",
        "allowed_files": [], "forbidden_files_or_areas": ["file2"],
        "explicit_non_scope": ["scope1"], "evidence_to_produce": ["evidence1"]
    }
    fixture_path.write_text(json.dumps(payload))

    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft", "--from-json", str(fixture_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Error validating Task Envelope JSON: Missing or empty required list field" in result.stderr

def test_task_envelope_draft_from_json_missing_list(tmp_path):
    import json
    fixture_path = tmp_path / "fixture.json"
    payload = {
        "task_id": "CR-058", "title": "Test JSON", "objective": "Obj", "repo": "TriageCore",
        "operator_agent_lane": "cli-operator", "route": "local-cli", "risk_level": "Low",
        "requested_capability": "read_only", "approval_gates": "gates", "validation_plan": "plan",
        "current_status": "proposed", "operator_decision": "Pending", "next_allowed_action": "action",
        "forbidden_files_or_areas": ["file2"],
        "explicit_non_scope": ["scope1"], "evidence_to_produce": ["evidence1"]
    }
    fixture_path.write_text(json.dumps(payload))

    cmd = [sys.executable, "-m", "triage_core.tc_cli", "task-envelope", "draft", "--from-json", str(fixture_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Error validating Task Envelope JSON: Missing or empty required list field" in result.stderr
