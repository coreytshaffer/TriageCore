import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def _snapshot_workspace_state(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[f"{relative_path}/"] = "<dir>"
        else:
            snapshot[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def test_admission_cli_example_fixture_smoke():
    fixture_path = os.path.join("docs", "examples", "admission-evidence.example.json")

    validate_result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", fixture_path],
        capture_output=True,
        text=True,
    )
    assert validate_result.returncode == 0
    assert "Validation successful." in validate_result.stdout

    render_result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "render", "--from-json", fixture_path],
        capture_output=True,
        text=True,
    )
    assert render_result.returncode == 0
    assert "# External Runtime Admission Readout" in render_result.stdout
    assert "**Requested Runtime:** python-local" in render_result.stdout
    assert "**Approval Required:** true" in render_result.stdout
    assert "## Blocked Reasons" in render_result.stdout
    assert "explicit approval required before write-capable runtime use" in render_result.stdout
    assert "## Manifest / Source Evidence" in render_result.stdout



def test_admission_validate_and_render_from_json_do_not_mutate_runtime_state(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "docs" / "examples" / "admission-evidence.example.json"
    workspace = tmp_path / "isolated-workspace"
    workspace.mkdir()

    triagecore_dir = workspace / ".triagecore"
    triagecore_dir.mkdir()
    ledger_path = triagecore_dir / "ledger.jsonl"
    ledger_text = '{"seed": true}\n'
    ledger_path.write_text(ledger_text, encoding="utf-8")
    sentinel_path = triagecore_dir / "sentinel.txt"
    sentinel_path.write_text("preserve-me\n", encoding="utf-8")

    before_state = _snapshot_workspace_state(workspace)

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )

    validate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "admission",
            "validate",
            "--from-json",
            str(fixture_path),
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )
    assert validate_result.returncode == 0
    assert "Validation successful." in validate_result.stdout

    render_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "admission",
            "render",
            "--from-json",
            str(fixture_path),
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )
    assert render_result.returncode == 0
    assert "# External Runtime Admission Readout" in render_result.stdout

    after_state = _snapshot_workspace_state(workspace)
    assert after_state == before_state
    assert ledger_path.read_text(encoding="utf-8") == ledger_text
    assert sentinel_path.read_text(encoding="utf-8") == "preserve-me\n"

def test_admission_validate_success(tmp_path):
    fixture_path = tmp_path / "valid.json"
    valid_data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test"
    }
    fixture_path.write_text(json.dumps(valid_data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Validation successful." in result.stdout

def test_admission_validate_missing_field(tmp_path):
    fixture_path = tmp_path / "missing.json"
    data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "local",
        "requested_capability": "read_only",
        "approval_required": False,
        # missing approval_used
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test"
    }
    fixture_path.write_text(json.dumps(data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error validating Admission Evidence JSON" in result.stderr

def test_admission_validate_invalid_json(tmp_path):
    fixture_path = tmp_path / "invalid.json"
    fixture_path.write_text("{ unquoted_key: true }", encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error parsing JSON" in result.stderr

def test_admission_validate_rejects_ledger(tmp_path):
    triagecore_dir = tmp_path / ".triagecore"
    triagecore_dir.mkdir()
    ledger_path = triagecore_dir / "ledger.jsonl"
    ledger_path.write_text("{}", encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(ledger_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "ledger.jsonl is not allowed as a --from-json fixture source." in result.stderr

def test_admission_validate_requires_from_json():
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate"],
        capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "the following arguments are required: --from-json" in result.stderr

def test_admission_validate_empty_required_string(tmp_path):
    fixture_path = tmp_path / "empty_string.json"
    data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "", # empty string should fail validation
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test"
    }
    fixture_path.write_text(json.dumps(data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "validate", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error validating Admission Evidence JSON" in result.stderr

def test_admission_render_success(tmp_path):
    fixture_path = tmp_path / "valid_render.json"
    valid_data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test evidence"
    }
    fixture_path.write_text(json.dumps(valid_data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "render", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "# External Runtime Admission Readout" in result.stdout
    assert "**Admitted:** true" in result.stdout

def test_admission_render_missing_field(tmp_path):
    fixture_path = tmp_path / "missing_render.json"
    data = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "local",
        "requested_capability": "read_only",
        "approval_required": False,
        # missing approval_used
        "blocked_reasons": [],
        "manifest_or_source_evidence": "test evidence"
    }
    fixture_path.write_text(json.dumps(data), encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "render", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error validating Admission Evidence JSON" in result.stderr

def test_admission_render_invalid_json(tmp_path):
    fixture_path = tmp_path / "invalid_render.json"
    fixture_path.write_text("{ unquoted_key: true }", encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "render", "--from-json", str(fixture_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "Error parsing JSON" in result.stderr

def test_admission_render_rejects_ledger(tmp_path):
    triagecore_dir = tmp_path / ".triagecore"
    triagecore_dir.mkdir()
    ledger_path = triagecore_dir / "ledger.jsonl"
    ledger_path.write_text("{}", encoding="utf-8")
    
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "render", "--from-json", str(ledger_path)],
        capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "ledger.jsonl is not allowed as a --from-json fixture source." in result.stderr

def test_admission_render_requires_from_json():
    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "render"],
        capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "the following arguments are required: --from-json" in result.stderr


def test_admission_render_example_fixture_missing_required_field(tmp_path):
    fixture_path = tmp_path / "missing_field.json"
    with open(os.path.join("docs", "examples", "admission-evidence.example.json"), "r", encoding="utf-8") as f:
        payload = json.load(f)
    payload.pop("requested_runtime")
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        ["python", "-m", "triage_core.tc_cli", "admission", "render", "--from-json", str(fixture_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Error validating Admission Evidence JSON" in result.stderr

def test_admission_bundle_from_json_writes_review_only_bundle(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    fixture_path = repo_root / "docs" / "examples" / "admission-evidence.example.json"
    workspace = tmp_path / "isolated-workspace"
    workspace.mkdir()

    triagecore_dir = workspace / ".triagecore"
    triagecore_dir.mkdir()
    ledger_path = triagecore_dir / "ledger.jsonl"
    ledger_text = '{"seed": true}\n'
    ledger_path.write_text(ledger_text, encoding="utf-8")

    out_dir = workspace / "review-bundle"
    before_state = _snapshot_workspace_state(workspace)

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "admission",
            "bundle",
            "--from-json",
            str(fixture_path),
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )
    assert result.returncode == 0
    assert "Success: Wrote admission review bundle" in result.stdout

    review_path = out_dir / "admission_review.md"
    evidence_path = out_dir / "admission_evidence.json"
    manifest_path = out_dir / "bundle_manifest.json"
    assert review_path.exists()
    assert evidence_path.exists()
    assert manifest_path.exists()

    review_text = review_path.read_text(encoding="utf-8")
    assert "# External Runtime Admission Readout" in review_text
    assert "This review bundle is an operator review artifact. It does not grant execution authority." in review_text

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest == {
        "bundle_type": "admission_review",
        "execution_authority": False,
        "source_evidence": "admission_evidence.json",
        "rendered_review": "admission_review.md",
    }

    with open(fixture_path, "r", encoding="utf-8") as f:
        expected_payload = json.load(f)
    actual_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert actual_payload == expected_payload

    after_state = _snapshot_workspace_state(workspace)
    non_bundle_after_state = {
        path: fingerprint
        for path, fingerprint in after_state.items()
        if not path.startswith("review-bundle/")
    }
    assert non_bundle_after_state == before_state
    assert ledger_path.read_text(encoding="utf-8") == ledger_text


def test_admission_bundle_from_invalid_json_fails_closed_without_bundle(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "isolated-workspace"
    workspace.mkdir()

    fixture_path = workspace / "invalid.json"
    fixture_path.write_text("{ unquoted_key: true }", encoding="utf-8")
    out_dir = workspace / "review-bundle"

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "admission",
            "bundle",
            "--from-json",
            str(fixture_path),
            "--out-dir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )
    assert result.returncode == 1
    assert "Error parsing JSON" in result.stderr
    assert not out_dir.exists()
