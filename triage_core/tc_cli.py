import argparse
import os
import sys
import glob
import subprocess
import json
import uuid
from pathlib import Path
from typing import List, Optional

from triage_core.agent_identity import AgentIdentityError, AgentIdentityRegistry, UnknownAgentError
from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.compression import compress_context
from triage_core.config import default_config
from triage_core.backends import LocalBackend
from triage_core.task_ledger import (
    TaskLedger,
    verify_ledger_event_signatures_in_ledger,
    verify_task_event_signatures,
)
from triage_core.demo_dry_run import format_demo_dry_run, run_demo_dry_run
from triage_core.agent_authority import (
    load_authority_manifest,
    summarize_authority_manifest_check,
    validate_authority_manifest,
)
from triage_core.model_manifest import (
    compare_route_to_manifest,
    load_json_payload,
    load_model_manifest,
    summarize_route_manifest_warning_report,
    summarize_model_manifest_check,
    validate_model_manifest,
)
from triage_core.privacy_invariants import find_forbidden_persistent_fields
from triage_core.runtime_strategy_evidence import (
    RecordedStrategyEvidenceError,
    build_fixture_strategy_delta_report,
    build_recorded_strategy_delta_report,
    export_strategy_delta_report,
    format_recorded_strategy_delta_report,
    format_strategy_delta_report,
    load_recorded_strategy_evidence_records,
    render_strategy_delta_report_json,
)
from triage_core.route_worker_ledger import (
    RouteWorkerLedgerValidationError,
    format_route_worker_ledger_inspection,
    inspect_route_worker_ledger,
)
from triage_core.token_efficiency import build_smoke_test_record
import triage_core.diagnostics as diagnostics
import triage_core.review_queue as review_queue
def _find_cr_file(cr_id: str) -> str:
    # search in docs/change/requests/
    pattern = f"docs/change/requests/{cr_id}-*.md"
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    # exact match just in case
    if os.path.exists(cr_id):
        return cr_id
    return ""

def _write_handoff(filename: str, content: str):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

def _copy_to_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            process = subprocess.Popen(["clip"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(input=text.encode("utf-16"))
        elif sys.platform == "darwin":
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(input=text.encode("utf-8"))
        else:
            process = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(input=text.encode("utf-8"))
        return process.returncode == 0
    except Exception:
        return False

def tc_preflight(cr_id: str, files: List[str]):
    cr_file = _find_cr_file(cr_id)
    if not cr_file:
        print(f"Error: Could not find documentation for {cr_id}")
        sys.exit(1)

    try:
        with open(cr_file, "r", encoding="utf-8") as f:
            cr_content = f.read()
    except Exception as e:
        print(f"Error reading {cr_file}: {e}")
        sys.exit(1)

    if not files:
        files = [cr_file, "docs/change/change_management.md"]

    packet = TaskPacket(
        prompt=f"Prepare preflight handoff for {cr_id}",
        data=cr_content,
        task_id=cr_id,
        privacy_metadata=PrivacyMetadata()
    )

    # Attempt local backend
    backend = None
    try:
        backend_type = default_config.get_backend_type()
        if backend_type == "ollama" or backend_type == "lmstudio":
            # Attempt to instantiate a naive backend or use TriageClient logic
            # For simplicity, we just won't instantiate one here if we don't have a reliable factory,
            # but we can try basic initialization.
            # However, since testing usually relies on mocking or the environment, we'll try to
            # instantiate LocalBackend if available.
            from triage_core.client import TriageClient
            client = TriageClient()
            if hasattr(client, "router") and hasattr(client.router, "get_backend"):
                backend = client.router.get_backend()
    except Exception:
        backend = None

    bundle = compress_context(packet, files, backend)

    # Build markdown
    md = f"# Handoff for {cr_id}\n\n"

    if any("Backend unavailable" in w for w in bundle.warnings) or not backend:
        md += "> [!WARNING]\n> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.\n\n"

    md += "## Task Scope\n"
    md += "Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation. Verify source files before editing and produce a plan before code changes.\n\n"

    md += "## Forbidden Scope\n"
    md += "Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.\n\n"

    md += "## Context\n"
    md += f"{bundle.summary_text}\n\n"

    md += "## Files Reference\n"
    for f_info in bundle.source_files:
        md += f"- `{f_info['path']}` (Size: {f_info['size_bytes']}, Hash: {f_info['fingerprint_sha256'][:8]})\n"

    if bundle.provenance:
        md += "\n## Provenance\n"
        md += f"- **Backend**: {bundle.provenance.get('backend_type')} ({bundle.provenance.get('backend_uri')})\n"
        md += f"- **Model**: {bundle.provenance.get('model')}\n"
        md += f"- **Generated**: {bundle.provenance.get('generated_at')}\n"

    md += f"\n<!-- Tokens: Raw={bundle.raw_tokens}, Compressed={bundle.compressed_tokens}, Ratio={bundle.reduction_ratio} -->\n"

    handoffs_dir = os.path.join(".triagecore", "handoffs")
    os.makedirs(handoffs_dir, exist_ok=True)

    specific_path = os.path.join(handoffs_dir, f"{cr_id}-preflight.md")
    latest_path = os.path.join(handoffs_dir, "latest.md")

    _write_handoff(specific_path, md)
    _write_handoff(latest_path, md)

    print(f"Success: Wrote preflight handoff to {specific_path} and updated {latest_path}")


def tc_handoff(latest: bool, print_only: bool):
    if not latest:
        print("Only 'tc handoff latest' is currently supported.")
        sys.exit(1)

    latest_path = os.path.join(".triagecore", "handoffs", "latest.md")
    if not os.path.exists(latest_path):
        print(f"Error: {latest_path} not found.")
        sys.exit(1)

    try:
        with open(latest_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {latest_path}: {e}")
        sys.exit(1)

    if print_only:
        print(content)
    else:
        success = _copy_to_clipboard(content)
        if success:
            print(f"Success: Copied {latest_path} to clipboard.")
        else:
            print(f"[!] Clipboard access failed. Handoff is available at: {os.path.abspath(latest_path)}")


def _repo_root_or_cwd() -> Path:
    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        if repo_root:
            return Path(repo_root)
    except Exception:
        pass

    return Path.cwd()


def _repo_root_without_subprocess() -> Path:
    """Locate an enclosing worktree for no-probe planning operations."""
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".git").exists():
            return candidate
    return cwd


def _ledger_path() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / ".triagecore").is_dir():
        return cwd / ".triagecore" / "ledger.jsonl"
    repo_root = _repo_root_without_subprocess()
    if repo_root != cwd or (cwd / ".git").exists():
        return repo_root / ".triagecore" / "ledger.jsonl"
    return _repo_root_or_cwd() / ".triagecore" / "ledger.jsonl"


def _identity_registry() -> AgentIdentityRegistry:
    return AgentIdentityRegistry(ledger_dir=_repo_root_or_cwd() / ".triagecore")

def tc_audit(kind: str, last: int):
    ledger_path = _ledger_path()
    if not ledger_path.exists():
        print(f"Error: {ledger_path} not found.")
        sys.exit(1)

    records = []
    try:
        with ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if kind and record.get("event_type") != kind:
                        continue
                    records.append(record)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"Error reading {ledger_path}: {e}")
        sys.exit(1)

    if last > 0:
        records = records[-last:]

    if not records:
        print(f"No records found" + (f" for kind '{kind}'" if kind else "") + ".")
        return

    for r in records:
        print(f"[{r.get('timestamp', 'unknown')}] Task: {r.get('task_id', 'unknown')} | Type: {r.get('event_type')}")
        payload = r.get("payload", {})
        if r.get("event_type") == "route_audit":
            reason = payload.get("reason_code", payload.get("reason"))
            privacy_passed = payload.get("privacy_scan_passed", payload.get("privacy_passed"))
            local_only = payload.get("is_local_only", payload.get("local_only"))
            route = payload.get("recommended_route", payload.get("requested_backend"))
            print(f"  Decision: {payload.get('decision')} | Reason: {reason}")
            print(f"  Privacy: {payload.get('privacy_level')} (Scan Passed: {privacy_passed})")
            print(f"  Local Only: {local_only} | Route: {route} | Backend: {payload.get('selected_backend')}")
        elif r.get("event_type") == "identity_rotation":
            agent_id = payload.get("agent_id")
            old_fp = payload.get("old_fingerprint")
            new_fp = payload.get("new_fingerprint")
            rotated_at = payload.get("rotated_at")
            status = payload.get("result_status")
            print(f"  identity_rotation agent={agent_id} old={old_fp} new={new_fp} rotated_at={rotated_at} status={status}")
        else:
            # General safe metadata fallback
            for k, v in payload.items():
                if k in ["prompt", "data", "content", "raw_data", "raw_prompt"]:
                    continue # Do not log raw prompt, raw data, or file contents
                if isinstance(v, str) and len(v) > 200:
                    v = v[:200] + "..."
                print(f"  {k}: {v}")
        print("-" * 60)


def tc_audit_self_test() -> None:
    payload = {
        "decision": "allowed",
        "reason": "audit_self_test",
        "reason_code": "audit_self_test",
        "privacy_level": "public",
        "privacy_passed": True,
        "privacy_scan_passed": True,
        "local_only": False,
        "is_local_only": False,
        "requested_backend": "self_test",
        "recommended_route": "self_test",
        "selected_backend": "self_test",
    }
    ledger_path = _ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = TaskLedger(str(ledger_path.parent))
    ledger.append_event("audit-self-test", "route_audit", payload)
    print(f"Success: Wrote privacy-safe route_audit self-test event to {ledger_path}.")


def tc_audit_signed_smoke_test(agent_id: str) -> None:
    payload = {
        "decision": "allowed",
        "reason_code": "signed_smoke_test",
        "privacy_level": "public",
        "privacy_scan_passed": True,
        "is_local_only": True,
        "recommended_route": "local",
        "selected_backend": "local",
        "smoke_test": True,
    }
    ledger_path = _ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = TaskLedger(str(ledger_path.parent))
    registry = _identity_registry()
    try:
        registry.load()
        ledger.append_signed_route_audit_event(
            "audit-signed-smoke-test",
            payload,
            signing_registry=registry,
            signing_agent_id=agent_id,
        )
    except AgentIdentityError as e:
        if _handle_registry_load_failure(registry.registry_path, e):
            return
        print(f"Error: {e}")
        sys.exit(1)

    print(
        "Success: Wrote metadata-only signed route_audit smoke test event "
        f"to {ledger_path} using agent_id={agent_id}."
    )


def tc_audit_signed_route_decision_smoke_test(agent_id: str) -> None:
    payload = {
        "selected_route": "local_fast",
        "reason": "signed_route_decision_smoke_test",
        "route_source": "smoke_test",
        "fallback_depth": 0,
        "selected_backend": "local",
        "selected_model": "smoke-test-model",
        "human_review_required": False,
        "required_checks": [],
        "smoke_test": True,
    }
    ledger_path = _ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger = TaskLedger(str(ledger_path.parent))
    registry = _identity_registry()
    try:
        registry.load()
        ledger.append_signed_route_decision_event(
            "audit-signed-route-decision-smoke-test",
            payload,
            signing_registry=registry,
            signing_agent_id=agent_id,
        )
    except AgentIdentityError as e:
        if _handle_registry_load_failure(registry.registry_path, e):
            return
        print(f"Error: {e}")
        sys.exit(1)

    print(
        "Success: Wrote metadata-only signed route_decision smoke test event "
        f"to {ledger_path} using agent_id={agent_id}."
    )


def _exit_missing_route_decision_smoke_agent_id(
    audit_parser: argparse.ArgumentParser,
) -> None:
    audit_parser.exit(
        2,
        "--agent-id is required for signed route-decision smoke tests.\n"
        "Run `tc identity list` to view available signer identities.\n",
    )


def tc_audit_privacy_invariants() -> None:
    ledger_path = _ledger_path()
    if not ledger_path.exists():
        print(f"Error: {ledger_path} not found.")
        sys.exit(1)

    checked_records = 0
    malformed_lines = 0
    violation_count = 0

    try:
        with ledger_path.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines += 1
                    print(f"FAIL line {line_number}: malformed JSON")
                    continue

                checked_records += 1
                violations = find_forbidden_persistent_fields(record)
                for violation in violations:
                    violation_count += 1
                    print(
                        "FAIL "
                        f"line {line_number}: "
                        f"task={record.get('task_id', 'unknown')} "
                        f"event_type={record.get('event_type', 'unknown')} "
                        f"path={violation.path} "
                        f"key={violation.key} "
                        f"reason={violation.reason}"
                    )
    except Exception as e:
        print(f"Error reading {ledger_path}: {e}")
        sys.exit(1)

    if violation_count or malformed_lines:
        print(
            "Privacy invariant audit failed: "
            f"{violation_count} violation(s), "
            f"{malformed_lines} malformed line(s), "
            f"{checked_records} record(s) checked."
        )
        sys.exit(1)

    print(
        "Privacy invariant audit passed: "
        f"{checked_records} record(s) checked in {ledger_path}."
    )


def tc_audit_verify_signatures(kind: str = "route_audit", strict: bool = False) -> None:
    supported_event_types = {
        "route_audit": "Route audit",
        "validation_result": "Validation result",
        "route_decision": "Route decision",
    }
    if kind not in supported_event_types:
        print(
            "Error: --verify-signatures supports only "
            "'route_audit', 'validation_result', or 'route_decision'."
        )
        sys.exit(1)

    ledger_path = _ledger_path()
    if not ledger_path.exists():
        print(f"Error: {ledger_path} not found.")
        sys.exit(1)

    try:
        summary = verify_ledger_event_signatures_in_ledger(ledger_path, event_type=kind)
    except AgentIdentityError as e:
        if _handle_registry_load_failure(_identity_registry().registry_path, e):
            return
        raise
    status = "failed" if summary.should_fail(strict=strict) else "passed"
    strict_mode = "on" if strict else "off"
    label = supported_event_types[kind]
    print(
        f"{label} signature verification "
        f"{status}: "
        f"event_type={kind} "
        f"valid_signed={summary.valid_signed} "
        f"invalid_signed={summary.invalid_signed} "
        f"unsigned={summary.unsigned} "
        f"malformed={summary.malformed} "
        f"skipped_non_target={summary.skipped_non_target} "
        f"strict={strict_mode}"
    )
    for finding in summary.findings:
        line = (
            f"{finding.status} event_type={finding.event_type} "
            f"task_id={finding.task_id} agent_id={finding.agent_id or 'unknown'}"
        )
        if finding.failure_reason:
            line += f" reason={finding.failure_reason}"
        print(line)
    if summary.should_fail(strict=strict):
        sys.exit(1)


def tc_tokens_smoke_test() -> None:
    try:
        record = build_smoke_test_record()
    except (OSError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Token efficiency smoke test passed")
    print(f"baseline_estimated_total={record.baseline.estimated_total_tokens}")
    print(f"candidate_estimated_total={record.candidate.estimated_total_tokens}")
    print(f"estimated_tokens_saved={record.savings.estimated_tokens_saved}")
    print(f"estimated_percent_saved={record.savings.estimated_percent_saved:.1f}")


def tc_demo_dry_run(decision: str = "pending") -> None:
    ledger_path = _ledger_path()
    result = run_demo_dry_run(
        ledger_dir=ledger_path.parent,
        decision=decision,
    )
    print(format_demo_dry_run(result))


def tc_model_check(manifest_path: str) -> None:
    try:
        manifest = load_model_manifest(manifest_path)
    except FileNotFoundError:
        print(f"Error: {manifest_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: {manifest_path} is not valid JSON ({e.msg}).")
        sys.exit(1)
    except OSError as e:
        print(f"Error reading {manifest_path}: {e}")
        sys.exit(1)

    result = validate_model_manifest(manifest)
    print(summarize_model_manifest_check(manifest_path, manifest, result))
    if not result.is_valid:
        sys.exit(1)


def tc_model_warn(manifest_path: str, route_path: str) -> None:
    try:
        manifest = load_model_manifest(manifest_path)
    except FileNotFoundError:
        print(f"Error: {manifest_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: {manifest_path} is not valid JSON ({e.msg}).")
        sys.exit(1)
    except OSError as e:
        print(f"Error reading {manifest_path}: {e}")
        sys.exit(1)

    try:
        route_payload = load_json_payload(route_path)
    except FileNotFoundError:
        print(f"Error: {route_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: {route_path} is not valid JSON ({e.msg}).")
        sys.exit(1)
    except OSError as e:
        print(f"Error reading {route_path}: {e}")
        sys.exit(1)

    report = compare_route_to_manifest(route_payload, manifest)
    print(summarize_route_manifest_warning_report(manifest_path, route_path, report))


def tc_authority_check(manifest_path: str) -> None:
    try:
        manifest = load_authority_manifest(manifest_path)
    except FileNotFoundError:
        print(f"Error: {manifest_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: {manifest_path} is not valid JSON ({e.msg}).")
        sys.exit(1)
    except OSError as e:
        print(f"Error reading {manifest_path}: {e}")
        sys.exit(1)

    result = validate_authority_manifest(manifest)
    print(summarize_authority_manifest_check(manifest_path, manifest, result))
    if not result.is_valid:
        sys.exit(1)


def tc_identity_init(agent_id: str, role: str, capabilities: List[str]) -> None:
    registry = _identity_registry()
    try:
        identity = registry.generate_identity(
            agent_id=agent_id,
            role=role,
            capabilities=capabilities,
        )
    except AgentIdentityError as e:
        print(f"Error: {e}")
        sys.exit(1)

    key_path = registry.keys_dir / f"{identity.agent_id}.key"
    print(
        "Success: Initialized local identity "
        f"agent_id={identity.agent_id} "
        f"role={identity.role} "
        f"key_algorithm={identity.key_algorithm} "
        f"capabilities={','.join(identity.capabilities)}"
    )
    print(f"Registry: {registry.registry_path}")
    print(f"Private key path: {key_path}")


def _handle_registry_load_failure(registry_path: str | Path, e: AgentIdentityError) -> bool:
    from triage_core.agent_identity import (
        IdentityRegistryUnreadableError,
        IdentityRegistryMalformedError,
        InvalidIdentityRecordError,
    )
    category = None
    if isinstance(e, IdentityRegistryUnreadableError):
        category = "unreadable_registry"
    elif isinstance(e, IdentityRegistryMalformedError):
        category = "malformed_registry"
    elif isinstance(e, InvalidIdentityRecordError):
        category = "invalid_identity_record"
    if category:
        print("Error: identity registry load failed")
        print("reason=registry_load_failed")
        print(f"registry={registry_path}")
        print(f"category={category}")
        sys.exit(1)

    return False


def tc_identity_list() -> None:
    registry = _identity_registry()
    try:
        identities = registry.load()
    except AgentIdentityError as e:
        if not _handle_registry_load_failure(registry.registry_path, e):
            raise
    if not identities:
        print(f"No identities found in {registry.registry_path}.")
        return

    flat_identities = [identity for lst in identities.values() for identity in lst]
    print(f"Identities: {len(flat_identities)}")
    for identity in sorted(flat_identities, key=lambda item: (item.agent_id, item.created_at)):
        capabilities = ",".join(identity.capabilities)
        print(
            f"- agent_id={identity.agent_id} "
            f"role={identity.role} "
            f"status={identity.status} "
            f"key_algorithm={identity.key_algorithm} "
            f"fingerprint={identity.public_key_fingerprint} "
            f"capabilities={capabilities}"
        )


def tc_identity_revoke(agent_id: str) -> None:
    registry = _identity_registry()
    try:
            identities = registry.load()
            if agent_id not in identities or not identities[agent_id]:
                raise UnknownAgentError(f"Unknown agent identity: {agent_id}")

            already_revoked = all(k.status != "active" for k in identities[agent_id])
            revoked_identity = registry.revoke_identity(agent_id)
    except AgentIdentityError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if already_revoked:
        print(
            "Notice: Identity already revoked "
            f"agent_id={revoked_identity.agent_id} "
            f"status={revoked_identity.status}"
        )
    else:
        print(
            "Success: Revoked local identity "
            f"agent_id={revoked_identity.agent_id} "
            f"status={revoked_identity.status}"
        )
    print(f"Registry: {registry.registry_path}")


def tc_identity_check() -> None:
    registry = _identity_registry()
    report = registry.check_consistency()
    if report.has_errors:
        status = "failed"
    elif report.permission_warnings:
        status = "warnings"
    else:
        status = "passed"

    print(
        "Identity check "
        f"{status}: "
        f"identities={report.identity_count} "
        f"keys={report.key_count} "
        f"missing_keys={len(report.missing_key_agent_ids)} "
        f"orphaned_keys={len(report.orphaned_key_agent_ids)} "
        f"malformed_registry={int(report.malformed_registry)} "
        f"permission_warnings={len(report.permission_warnings)}"
    )
    if report.malformed_registry:
        print("ERROR malformed_registry")
    for agent_id in report.missing_key_agent_ids:
        print(f"ERROR missing_private_key agent_id={agent_id}")
    for agent_id in report.orphaned_key_agent_ids:
        print(f"ERROR orphaned_private_key agent_id={agent_id}")
    for warning in report.permission_warnings:
        print(f"WARNING private_key_permissions {warning}")

    if report.has_errors:
        sys.exit(1)


def tc_identity_doctor(agent_id: Optional[str], for_capability: Optional[str] = None) -> None:
    registry = _identity_registry()
    report = registry.check_health(agent_id)
    capability_ready_agents = []

    try:
        import json
        ledger_path = _ledger_path()
        audit_lookup = set()
        if ledger_path.exists():
            with open(ledger_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        e = json.loads(line)
                        if e.get("event_type") == "identity_rotation" and "payload" in e:
                            audit_lookup.add((e["payload"].get("agent_id"), e["payload"].get("rotated_at")))
                    except Exception:
                        pass
    except Exception as e:
        print(f"Warning: Failed to load ledger for audit cross-check: {e}")
        audit_lookup = None

    loaded_identities = None
    try:
        loaded_identities = registry.load()
    except Exception:
        loaded_identities = None

    if agent_id and agent_id not in report.checked_agent_ids:
        from triage_core.agent_identity import IdentityDoctorIssue
        report.errors.append(IdentityDoctorIssue(
            severity="error",
            code="unknown_agent",
            agent_id=agent_id,
            message="Unknown agent identity",
        ))

    if audit_lookup is not None and loaded_identities is not None:
        try:
            from triage_core.agent_identity import ROTATED_STATUS, IdentityDoctorIssue
            for a_id, agent_list in loaded_identities.items():
                if agent_id and a_id != agent_id:
                    continue
                for rot_id in agent_list:
                    if rot_id.status == ROTATED_STATUS and rot_id.rotated_at:
                        if (a_id, rot_id.rotated_at) not in audit_lookup:
                            report.warnings.append(IdentityDoctorIssue(
                                severity="warning",
                                code="missing_audit_event",
                                agent_id=a_id,
                                fingerprint=rot_id.public_key_fingerprint,
                                message=f"No identity_rotation audit event found for rotated_at={rot_id.rotated_at}"
                            ))
        except Exception:
            pass

    if for_capability and loaded_identities is not None:
        from triage_core.agent_identity import ACTIVE_STATUS, IdentityDoctorIssue
        for a_id, agent_list in loaded_identities.items():
            if agent_id and a_id != agent_id:
                continue
            active_identities = [item for item in agent_list if item.status == ACTIVE_STATUS]
            if len(active_identities) != 1:
                continue
            active_identity = active_identities[0]
            if for_capability not in active_identity.capabilities:
                report.errors.append(IdentityDoctorIssue(
                    severity="error",
                    code="missing_requested_capability",
                    agent_id=a_id,
                    fingerprint=active_identity.public_key_fingerprint,
                    message=f"Active identity is not authorized for capability '{for_capability}'",
                ))
            else:
                capability_ready_agents.append((a_id, for_capability, active_identity.public_key_fingerprint))

    if report.has_errors:
        status = "failed"
    elif report.warnings:
        status = "warnings"
    else:
        status = "passed"

    print(
        f"Identity doctor {status}: "
        f"checked_agents={len(report.checked_agent_ids)} "
        f"errors={len(report.errors)} "
        f"warnings={len(report.warnings)}"
    )

    for err in report.errors:
        fp_str = f" fingerprint={err.fingerprint}" if err.fingerprint else ""
        print(f"ERROR {err.code} agent_id={err.agent_id}{fp_str} ({err.message})")

    for warn in report.warnings:
        fp_str = f" fingerprint={warn.fingerprint}" if warn.fingerprint else ""
        print(f"WARNING {warn.code} agent_id={warn.agent_id}{fp_str} ({warn.message})")

    for ready_agent_id, capability, fingerprint in capability_ready_agents:
        print(
            f"OK capability_ready agent_id={ready_agent_id} "
            f"capability={capability} fingerprint={fingerprint}"
        )

    if report.has_errors:
        sys.exit(1)


def tc_workspace_export_eval(
    items_path: str,
    item_id: str,
    output_path: str,
    *,
    today_path: Optional[str] = None,
    case_id: Optional[str] = None,
    stale_after_days: int = 14,
    force: bool = False,
) -> None:
    from triage_core.workspace_board import load_work_items
    from triage_core.workspace_eval_packet import (
        build_workspace_evaluator_packet,
        write_workspace_evaluator_packet,
    )
    from triage_core.workspace_now import load_today_file

    items = load_work_items(items_path)
    target_item = None
    for item in items:
        if item.id == item_id:
            target_item = item
            break

    if target_item is None:
        raise ValueError(f"Work item {item_id} not found in {items_path}")

    today = load_today_file(today_path) if today_path else None
    packet = build_workspace_evaluator_packet(
        target_item,
        today=today,
        case_id=case_id,
        stale_after_days=stale_after_days,
    )
    written_path = write_workspace_evaluator_packet(packet, output_path, force=force)
    print(f"Workspace evaluator packet written to {written_path}")


def tc_identity_rotate(agent_id: str, dry_run: bool) -> None:
    from datetime import datetime, timezone

    registry = _identity_registry()

    if dry_run:
        try:
            identities = registry.load()
            if agent_id not in identities or not identities[agent_id]:
                print(f"Error: Unknown agent identity: {agent_id}")
                sys.exit(1)

            current_identity = None
            for identity in identities[agent_id]:
                if identity.status == "active":
                    current_identity = identity
                    break

            if not current_identity:
                print("Error: Cannot rotate non-active identity")
                sys.exit(1)

            print("Identity rotation dry run\n")
            print(f"agent_id: {agent_id}")
            print(f"current_status: {current_identity.status}")
            print("would_mark_current_key: rotated")

            dummy_ts = datetime.now(timezone.utc).isoformat()
            print(f"would_set_rotated_at: {dummy_ts}")

            print("would_generate_new_key: yes")
            print("would_write_registry: no")
            print("would_write_private_key: no\n")
            print("No files were modified.")
        except AgentIdentityError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        try:
            result = registry.rotate_identity(agent_id)
            print("Identity rotated successfully\n")
            print(f"agent_id: {result.agent_id}")
            print(f"old_fingerprint: {result.old_fingerprint}")
            print(f"new_fingerprint: {result.new_fingerprint}")
            print(f"rotated_at: {result.rotated_at}")
            print(f"active_key: {result.active_key_path}")
            print(f"archived_key: {result.archived_key_path}")

            from triage_core.task_ledger import TaskLedger
            try:
                ledger_path = _ledger_path()
                ledger_path.parent.mkdir(parents=True, exist_ok=True)
                ledger = TaskLedger(str(ledger_path.parent))
                audit_payload = {
                    "agent_id": result.agent_id,
                    "old_fingerprint": result.old_fingerprint,
                    "new_fingerprint": result.new_fingerprint,
                    "rotated_at": result.rotated_at,
                    "archived_key_path": str(result.archived_key_path),
                    "active_key_path": str(result.active_key_path),
                    "result_status": "success",
                    "source": "tc identity rotate",
                }
                # Use a deterministic-ish prefix task ID
                task_id = f"identity-rotation-{result.agent_id}-{result.rotated_at}"
                ledger.append_event(task_id, "identity_rotation", audit_payload)
            except Exception as e:
                print(f"\nWarning: Identity rotation completed, but audit event emission failed: {e}")
                print("Do not retry rotation blindly. Inspect the registry and ledger state.")

        except AgentIdentityError as e:
            print(f"Rotation failed: {e}")
            sys.exit(1)

import re

def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def tc_propose(cr_id: str, title: str, add_to_changelog: bool):
    if not re.match(r"^CR-\d{3}[A-Z]?$", cr_id):
        print(f"Error: Invalid CR ID format '{cr_id}'. Expected format like CR-003 or CR-004B.")
        sys.exit(1)

    slug = _slugify(title)
    if not slug:
        print("Error: Invalid title for slugification.")
        sys.exit(1)

    filename = f"docs/change/requests/{cr_id}-{slug}.md"
    if os.path.exists(filename):
        print(f"Error: File '{filename}' already exists. Refusing to overwrite.")
        sys.exit(1)

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    content = f"# {cr_id}: {title.replace('-', ' ').title()}\n\n## Status\nProposed\n\n## Scope\n\n\n## Implementation Authority\nNot authorized for implementation. This CR must be approved prior to any code changes.\n\n## Description\n\n\n## Acceptance Criteria\n- [ ] \n"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Success: Created proposal template at '{filename}'")
    except Exception as e:
        print(f"Error writing to '{filename}': {e}")
        sys.exit(1)

    if add_to_changelog:
        cl_path = "docs/change/change_log.md"
        if os.path.exists(cl_path):
            try:
                with open(cl_path, "r", encoding="utf-8") as f:
                    cl_content = f.read()

                entry = f"- Proposed {cr_id} ({title.replace('-', ' ').title()}): \n"
                if cr_id in cl_content:
                    print(f"Notice: Changelog entry for {cr_id} already exists.")
                elif "## [Unreleased]" in cl_content:
                    # Insert after ## [Unreleased]
                    new_cl = cl_content.replace("## [Unreleased]\n", f"## [Unreleased]\n{entry}")
                    with open(cl_path, "w", encoding="utf-8") as f:
                        f.write(new_cl)
                    print(f"Success: Added '{cr_id}' to [Unreleased] in changelog.")
                else:
                    print("Error: Could not find '## [Unreleased]' section in changelog.")
            except Exception as e:
                print(f"Error modifying changelog: {e}")

def tc_review_list():
    ledger_path = _ledger_path()
    ledger = TaskLedger(str(ledger_path.parent))
    pending = review_queue.get_pending_reviews(ledger)
    print(review_queue.format_review_queue(pending))


def tc_run(args, client=None) -> None:
    """Run a task through the governed local-first loop.

    Wraps ``TriageClient.run_task`` so the operator gets the full governed path
    (privacy scan, external-safe gate, resilience routing, local execution, and
    evidence) from one command, unlike ``triagecore run-pipeline`` which calls
    the engine directly and bypasses routing.

    This slice adds no new backends, no live capability probe, no budget
    enforcement, and no autonomous execution. Cloud escalation is reachable only
    through the existing bounded Qwen path already inside ``run_task`` (off by
    default), so ``tc run`` makes no new cloud calls.

    Exit codes:
      0  local execution succeeded
      1  input / IO / argument error
      2  privacy or safety fail-closed (blocked before any external egress)
      3  governed handoff_required (valid outcome, not executed locally)

    ``client`` is injectable for offline testing; when ``None`` it is built from
    the configured local backend.
    """
    from triage_core.privacy_scanner import PrivacyViolationError
    from triage_core.safe_task_packet import (
        LocalRouteUnavailableError,
        UnsafePacketError,
        verify_packet,
    )

    from triage_core.run_plan import (
        ContextSource,
        RunPlanPrivacyError,
        build_run_plan,
        privacy_metadata_for_run,
        render_run_plan,
    )

    planning = bool(getattr(args, "plan", False))
    plan_output = getattr(args, "plan_output", None)
    if plan_output and not planning:
        print("Error: --plan-output requires --plan.")
        sys.exit(1)
    if planning:
        ambiguous = [
            flag
            for flag, active in (
                ("--output", bool(getattr(args, "output", None))),
                ("--print", bool(getattr(args, "print_output", False))),
                ("--ledger-dir", bool(getattr(args, "ledger_dir", None))),
                ("--no-ledger", bool(getattr(args, "no_ledger", False))),
            )
            if active
        ]
        if ambiguous:
            print(f"Error: --plan cannot be combined with {', '.join(ambiguous)}.")
            sys.exit(1)
        if not getattr(args, "model", None):
            print("Error: --model is required with --plan.")
            sys.exit(1)
        if plan_output and not getattr(args, "task_id", None):
            print("Error: --task-id is required with --plan-output.")
            sys.exit(1)

    # 1. Assemble task data from --files (repeatable), then --data.
    data_parts: List[str] = []
    context_sources = []
    source_values = []
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"Error: input file not found: {file_path}")
            sys.exit(1)
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                content = handle.read()
                context_sources.append(
                    ContextSource(path=file_path, characters=len(content))
                )
                source_values.append((file_path, content))
                data_parts.append(f"\n--- {file_path} ---\n{content}")
        except OSError as exc:
            print(f"Error reading {file_path}: {exc}")
            sys.exit(1)
    if args.data:
        data_parts.append(args.data)
    data = "".join(data_parts)

    # 2. Map --privacy to packet metadata. Privacy class alone does not
    # authorize cloud execution; that requires explicit operator intent.
    if args.privacy == "local_only" and args.allow_cloud:
        print("Error: --allow-cloud cannot be used with --privacy local_only.")
        sys.exit(1)

    if planning:
        try:
            plan = build_run_plan(
                prompt=args.prompt,
                data=data,
                sources=context_sources,
                inline_data_characters=len(args.data or ""),
                privacy=args.privacy,
                allow_cloud=args.allow_cloud,
                model_profile=args.model,
                task_id=args.task_id,
            )
        except KeyError:
            print(f"Error: Unknown model profile: {args.model}")
            sys.exit(1)
        except RunPlanPrivacyError as exc:
            print("Blocked (privacy fail-closed).")
            print(f"finding_codes={','.join(exc.finding_codes)}")
            sys.exit(2)
        if plan_output:
            from triage_core.run_plan_artifact import (
                RunPlanArtifactError,
                build_artifact,
                publish_artifact,
            )

            try:
                _, artifact_bytes, body_digest, artifact_digest = build_artifact(
                    plan=plan,
                    prompt=args.prompt,
                    assembled_input=f"{args.prompt}\n{data}",
                    inline_input=args.data or "",
                    source_values=source_values,
                )
                written_path = publish_artifact(
                    plan_output,
                    artifact_bytes,
                    protected_directories=(
                        default_config.get_ledger_dir(),
                        _repo_root_without_subprocess() / ".triagecore",
                        default_config.get_tasks_dir(),
                        default_config.get_codex_tasks_dir(),
                    ),
                )
            except RunPlanArtifactError as exc:
                print(f"Error: {exc}")
                sys.exit(1)
            print(render_run_plan(plan, artifact_written=True), end="")
            print(f"Plan artifact: {written_path}")
            print(f"plan_body_digest: {body_digest}")
            print(f"artifact_byte_digest: {artifact_digest}")
        else:
            print(render_run_plan(plan), end="")
        return

    privacy_metadata = privacy_metadata_for_run(args.privacy, args.allow_cloud)

    # 3. Build and preflight the packet before any evidence is persisted.
    task_id = args.task_id or str(uuid.uuid4())
    packet = TaskPacket(
        prompt=args.prompt,
        data=data,
        task_id=task_id,
        privacy_metadata=privacy_metadata,
    )
    try:
        verify_packet(packet)
    except PrivacyViolationError as exc:
        print(f"Blocked (privacy fail-closed): {exc}")
        sys.exit(2)

    # 4. Ledger wiring (enabled by default; --no-ledger warns).
    ledger = None
    if args.no_ledger:
        print(
            "Warning: --no-ledger set; no evidence record will be written to the "
            "ledger for this run."
        )
    else:
        ledger_dir = args.ledger_dir or default_config.get_ledger_dir()
        try:
            ledger = TaskLedger(ledger_dir=ledger_dir)
        except Exception as exc:
            print(f"Error: could not open ledger at '{ledger_dir}': {exc}")
            sys.exit(1)

    # 5. Task identity + evidence scaffolding (mirrors the pipeline runner).
    if ledger is not None:
        if not args.task_id or not ledger.get_task(task_id):
            ledger.append_event(
                task_id,
                "task_created",
                {
                    "title": "tc run task",
                    "description": "Prompt content withheld from ledger.",
                    "prompt_length": len(args.prompt),
                    "data_length": len(data),
                    "target_files": args.files,
                },
            )
        ledger.append_event(task_id, "runner_selected", {"runner": "tc_run"})

    # 6. Build the client from config unless one was injected (tests inject).
    if client is None:
        from triage_core.client import TriageClient

        try:
            client = TriageClient(
                backend_type=default_config.get_backend_type(),
                model=default_config.get_backend_model(),
                base_url=default_config.get_backend_base_url(),
            )
        except Exception as exc:
            print(f"Error: could not initialize backend: {exc}")
            sys.exit(1)

    # 7. Governed loop. Privacy/safety failures fail closed (exit 2).
    try:
        result = client.run_task(task_packet=packet, ledger=ledger, task_id=task_id)
    except PrivacyViolationError as exc:
        print(f"Blocked (privacy fail-closed): {exc}")
        sys.exit(2)
    except LocalRouteUnavailableError as exc:
        print(f"Blocked (local route unavailable, failing closed): {exc}")
        sys.exit(2)
    except UnsafePacketError as exc:
        print(f"Blocked (unsafe packet, failing closed): {exc}")
        sys.exit(2)

    # 8. Interpret outcome.
    route = result.get("selected_route")
    if result.get("status") == "success":
        output = result.get("output", "")
        if args.output:
            out_dir = os.path.dirname(args.output)
            try:
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                with open(args.output, "w", encoding="utf-8") as handle:
                    handle.write(output)
            except OSError as exc:
                print(f"Error writing output to {args.output}: {exc}")
                sys.exit(1)
        print(f"Success: task ran locally (route={route}, task_id={task_id}).")
        if ledger is not None:
            print(f"Evidence written to {ledger.ledger_path}.")
        if args.print_output:
            print(output)
        return  # exit 0

    reason = result.get("handoff_reason") or result.get("reason") or "handoff required"
    print(f"Handoff required (route={route}, task_id={task_id}): {reason}")
    if ledger is not None:
        print(f"Evidence written to {ledger.ledger_path}.")
    sys.exit(3)


def tc_probe(args) -> None:
    """Read-only local backend metadata probe (CR-114).

    Probes a metadata-only endpoint of a local backend and renders a
    privacy-safe record. Never invokes a model; writes no ledger evidence and
    creates no artifact unless ``--output`` names one.

    Exit codes:
      0  the probe produced a valid metadata record (including reachable=false
         and probe_disabled records)
      1  argument / input / validation error (e.g. a secret-bearing base_url)
    """
    from triage_core.local_backend_probe import (
        ProbeInputError,
        probe_local_backend,
        render_probe_record,
    )

    timeout = args.timeout if args.timeout is not None else 3.0
    try:
        record = probe_local_backend(
            source_type=args.source_type,
            base_url=args.base_url,
            timeout=timeout,
            include_model_names=args.include_model_names,
            enabled=not args.disabled,
        )
        rendered = render_probe_record(record)
    except ProbeInputError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print(rendered)

    if args.output:
        out_dir = os.path.dirname(args.output)
        try:
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as handle:
                json.dump(record.to_dict(), handle, indent=2)
        except OSError as exc:
            print(f"Error writing output to {args.output}: {exc}")
            sys.exit(1)
        print(f"Record written to {args.output}.")


def tc_status():
    print("TriageCore Status\n")

    # 1. Repo cleanliness
    git_status = diagnostics.get_git_status()
    print(f"Repo: {git_status}")

    # 2. Ledger path and writability
    ledger_path = _ledger_path()
    try:
        rel_path = ledger_path.relative_to(Path.cwd())
    except ValueError:
        rel_path = ledger_path

    exists, readable, writable = diagnostics.get_ledger_status(str(ledger_path))
    ledger_str = f"{rel_path}"
    if not exists:
        ledger_str += " (does not exist)"
    elif not writable:
        ledger_str += " (read-only)"

    ledger_str = ledger_str.replace("\\", "/")
    print(f"Ledger: {ledger_str}")

    # 3. Last event
    last_event = diagnostics.get_ledger_last_event_timestamp(str(ledger_path))
    print(f"Last event: {last_event}")

    # 4. Pending reviews
    ledger = TaskLedger(str(ledger_path.parent))
    pending = review_queue.get_pending_reviews(ledger)
    print(f"Pending reviews: {len(pending)} detected")

    # 5. Failed validations
    print("Failed validations: not implemented")

    # 6. Configured backend
    backend = "unavailable"
    try:
        backend = default_config.get_backend_type()
    except Exception:
        pass
    print(f"Configured backend: {backend}")

    # 7. Default policy
    print("Default policy: human-review-required")

def tc_doctor():
    print("TriageCore Doctor")
    print("=" * 30)

    warnings = 0
    failures = 0

    cwd = os.getcwd()
    repo_root = diagnostics.get_git_repo_root()
    base_dir = diagnostics.get_base_dir()

    print("\nEnvironment")
    print(f"- CWD: {cwd}")
    if repo_root:
        print(f"- Git repo root: {repo_root}")
    else:
        print("- Git repo root: unavailable")
        warnings += 1

    print(f"- Python executable: {sys.executable}")
    print(f"- Python version: {sys.version.split()[0]}")

    try:
        import triage_core
        print(f"- triage_core import path: {triage_core.__file__}")
    except ImportError:
        print("- triage_core import path: unavailable")
        failures += 1

    tc_path = diagnostics.get_tc_executable_path()
    print(f"- tc executable path: {tc_path}")

    print("\nRepository")
    branch = diagnostics.get_git_branch()
    print(f"- Git branch: {branch}")

    status = diagnostics.get_git_status()
    print(f"- Git status: {status}")
    if status == "dirty":
        warnings += 1

    print("\nLedger")
    ledger_path = os.path.join(base_dir, ".triagecore", "ledger.jsonl")
    print(f"- Ledger path: {ledger_path}")

    exists, readable, writable = diagnostics.get_ledger_status(ledger_path)
    if exists:
        r_str = "yes" if readable else "no"
        w_str = "yes" if writable else "no"
        print(f"- Exists/readable/writable: exists (readable: {r_str}, writable: {w_str})")
        if not readable or not writable:
            failures += 1
    else:
        print("- Exists/readable/writable: unavailable (does not exist)")
        warnings += 1

    last_event = diagnostics.get_ledger_last_event_timestamp(ledger_path)
    print(f"- Last event timestamp: {last_event}")

    print("\nHandoff")
    handoff_path = os.path.join(base_dir, ".triagecore", "handoffs", "latest.md")
    if os.path.exists(handoff_path):
        print(f"- Latest handoff path: {handoff_path}")
    else:
        print("- Latest handoff path: unavailable")

    print("\nConfig/Test")
    pyproject_path = os.path.join(base_dir, "pyproject.toml")
    if os.path.exists(pyproject_path):
        print(f"- pyproject/pytest config path: {pyproject_path}")
    else:
        print("- pyproject/pytest config path: unavailable")
        warnings += 1

    print("\nRuntime Safety")
    print("- External execution posture: blocked")
    print("- Human approval posture: human-review-required")
    print("- Network/tool execution posture: unavailable")

    print("\nResult")
    if failures > 0:
        overall = "FAIL"
    elif warnings > 0:
        overall = "WARN"
    else:
        overall = "OK"
    print(f"- Overall: {overall}")

def _prompt_required(prompt_text: str) -> str:
    while True:
        try:
            val = input(prompt_text).strip()
            if val:
                return val
            print("This field is required.")
        except EOFError:
            print("\nError: EOF received during input.")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)

def _prompt_optional(prompt_text: str) -> Optional[str]:
    try:
        val = input(prompt_text).strip()
        return val if val else None
    except EOFError:
        print("\nError: EOF received during input.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)

def _prompt_required_list(prompt_text: str) -> List[str]:
    print(f"{prompt_text} (Enter empty string or 'done' to finish)")
    items = []
    while True:
        try:
            val = input("  > ").strip()
            if val.lower() == "done" or not val:
                if items:
                    return items
                print("At least one entry is required.")
            else:
                items.append(val)
        except EOFError:
            print("\nError: EOF received during input.")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)

def tc_task_envelope_preview() -> None:
    from triage_core.task_envelope import TaskEnvelope, render_task_envelope_markdown
    envelope = TaskEnvelope(
        task_id="EXAMPLE-CR-001",
        title="Example CLI Preview Task",
        objective="Demonstrate the CLI preview rendering of a deterministic Task Envelope.",
        repo="TriageCore",
        operator_agent_lane="cli-operator",
        route="local-preview",
        risk_level="Low",
        requested_capability="read_only",
        allowed_files=("docs/", "tests/"),
        forbidden_files_or_areas=(".triagecore/ledger.jsonl",),
        explicit_non_scope=("Runtime execution", "Network requests"),
        approval_gates="None",
        validation_plan="Read stdout",
        evidence_to_produce=(),
        current_status="preview",
        operator_decision="Pending",
        next_allowed_action="Close preview",
    )
    # The renderer appends a trailing newline, so print(..., end='') to avoid double blank line
    print(render_task_envelope_markdown(envelope), end='')

def tc_task_envelope_draft(args: argparse.Namespace) -> None:
    from triage_core.task_envelope import TaskEnvelope, render_task_envelope_markdown, task_envelope_from_mapping
    import json

    # Validation
    if args.from_json:
        # Reject mixed usage
        mixed_flags = [
            args.task_id, args.title, args.objective, args.repo, args.operator_agent_lane,
            args.route, args.risk_level, args.requested_capability, args.allowed_file,
            args.forbidden_area, args.non_scope, args.approval_gates, args.validation_plan,
            args.evidence, args.current_status, args.operator_decision, args.next_allowed_action,
            args.blocked_reason, args.approval_evidence, args.admission_evidence
        ]
        if any(f is not None for f in mixed_flags):
            sys.stderr.write("Error: --from-json cannot be mixed with explicit field flags.\n")
            sys.exit(1)

        json_path = os.path.normpath(args.from_json)
        if json_path.endswith(".triagecore/ledger.jsonl") or json_path.endswith(".triagecore\\ledger.jsonl"):
            sys.stderr.write("Error: ledger.jsonl is not allowed as a --from-json fixture source.\n")
            sys.exit(1)

        try:
            with open(args.from_json, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            envelope = task_envelope_from_mapping(payload)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Error parsing JSON: {e}\n")
            sys.exit(1)
        except ValueError as e:
            sys.stderr.write(f"Error validating Task Envelope JSON: {e}\n")
            sys.exit(1)
        except Exception as e:
            sys.stderr.write(f"Error reading JSON fixture: {e}\n")
            sys.exit(1)
    else:
        # Enforce required flags
        required_flags = {
            "--task-id": args.task_id, "--title": args.title, "--objective": args.objective,
            "--repo": args.repo, "--operator-agent-lane": args.operator_agent_lane,
            "--route": args.route, "--risk-level": args.risk_level,
            "--requested-capability": args.requested_capability, "--allowed-file": args.allowed_file,
            "--forbidden-area": args.forbidden_area, "--non-scope": args.non_scope,
            "--approval-gates": args.approval_gates, "--validation-plan": args.validation_plan,
            "--evidence": args.evidence, "--current-status": args.current_status,
            "--operator-decision": args.operator_decision, "--next-allowed-action": args.next_allowed_action
        }
        missing_flags = [name for name, val in required_flags.items() if val is None]
        if missing_flags:
            sys.stderr.write(f"Error: the following arguments are required: {', '.join(missing_flags)}\n")
            sys.exit(1)

        envelope = TaskEnvelope(
            task_id=args.task_id,
            title=args.title,
            objective=args.objective,
            repo=args.repo,
            operator_agent_lane=args.operator_agent_lane,
            route=args.route,
            risk_level=args.risk_level,
            requested_capability=args.requested_capability,
            allowed_files=tuple(args.allowed_file),
            forbidden_files_or_areas=tuple(args.forbidden_area),
            explicit_non_scope=tuple(args.non_scope),
            approval_gates=args.approval_gates,
            validation_plan=args.validation_plan,
            evidence_to_produce=tuple(args.evidence),
            current_status=args.current_status,
            operator_decision=args.operator_decision,
            next_allowed_action=args.next_allowed_action,
            failure_modes_or_blocked_reasons=args.blocked_reason,
            approval_evidence=args.approval_evidence,
            admission_evidence=args.admission_evidence,
        )

    print(render_task_envelope_markdown(envelope), end='')

def tc_task_envelope_validate(args: argparse.Namespace) -> None:
    from triage_core.task_envelope import task_envelope_from_mapping
    import json

    json_path = os.path.normpath(args.from_json)
    if json_path.endswith(".triagecore/ledger.jsonl") or json_path.endswith(".triagecore\\ledger.jsonl"):
        sys.stderr.write("Error: ledger.jsonl is not allowed as a --from-json fixture source.\n")
        sys.exit(1)

    try:
        with open(args.from_json, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        task_envelope_from_mapping(payload)
        print("Validation successful.")
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error parsing JSON: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error validating Task Envelope JSON: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error reading JSON fixture: {e}\n")
        sys.exit(1)

def _load_admission_evidence_fixture(from_json: str):
    from triage_core.admission import admission_evidence_from_mapping
    import json

    json_path = os.path.normpath(from_json)
    if json_path.endswith(".triagecore/ledger.jsonl") or json_path.endswith(".triagecore\\ledger.jsonl"):
        raise ValueError("ledger.jsonl is not allowed as a --from-json fixture source.")

    with open(from_json, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    evidence = admission_evidence_from_mapping(payload)
    return payload, evidence


def tc_admission_validate(args: argparse.Namespace) -> None:
    from triage_core.admission import admission_evidence_from_mapping
    import json

    json_path = os.path.normpath(args.from_json)
    if json_path.endswith(".triagecore/ledger.jsonl") or json_path.endswith(".triagecore\\ledger.jsonl"):
        sys.stderr.write("Error: ledger.jsonl is not allowed as a --from-json fixture source.\n")
        sys.exit(1)

    try:
        with open(args.from_json, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        admission_evidence_from_mapping(payload)
        print("Validation successful.")
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error parsing JSON: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error validating Admission Evidence JSON: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error reading JSON fixture: {e}\n")
        sys.exit(1)

def tc_admission_render(args: argparse.Namespace) -> None:
    from triage_core.admission import admission_evidence_from_mapping, render_admission_evidence_markdown
    import json

    json_path = os.path.normpath(args.from_json)
    if json_path.endswith(".triagecore/ledger.jsonl") or json_path.endswith(".triagecore\\ledger.jsonl"):
        sys.stderr.write("Error: ledger.jsonl is not allowed as a --from-json fixture source.\n")
        sys.exit(1)

    try:
        with open(args.from_json, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        evidence = admission_evidence_from_mapping(payload)
        print(render_admission_evidence_markdown(evidence), end='')
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error parsing JSON: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error validating Admission Evidence JSON: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error reading JSON fixture: {e}\n")
        sys.exit(1)

def tc_admission_bundle(args: argparse.Namespace) -> None:
    from triage_core.admission import render_admission_evidence_markdown
    import json

    try:
        payload, evidence = _load_admission_evidence_fixture(args.from_json)
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        review_path = out_dir / "admission_review.md"
        evidence_path = out_dir / "admission_evidence.json"
        manifest_path = out_dir / "bundle_manifest.json"

        review_markdown = (
            render_admission_evidence_markdown(evidence)
            + "\n\n> This review bundle is an operator review artifact. It does not grant execution authority.\n"
        )
        manifest = {
            "bundle_type": "admission_review",
            "execution_authority": False,
            "source_evidence": "admission_evidence.json",
            "rendered_review": "admission_review.md",
        }

        review_path.write_text(review_markdown, encoding='utf-8')
        evidence_path.write_text(json.dumps(payload, indent=2) + "\n", encoding='utf-8')
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding='utf-8')

        print(f"Success: Wrote admission review bundle to {out_dir}.")
    except json.JSONDecodeError as e:
        sys.stderr.write(f"Error parsing JSON: {e}\n")
        sys.exit(1)
    except ValueError as e:
        sys.stderr.write(f"Error validating Admission Evidence JSON: {e}\n")
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Error writing admission review bundle: {e}\n")
        sys.exit(1)

def tc_task_envelope_wizard() -> None:
    from triage_core.task_envelope import TaskEnvelope, render_task_envelope_markdown

    print("=== Task Envelope Wizard ===")

    task_id = _prompt_required("Task ID (e.g., CR-057): ")
    title = _prompt_required("Title: ")
    objective = _prompt_required("Objective: ")
    repo = _prompt_required("Repository: ")
    operator_agent_lane = _prompt_required("Operator/Agent Lane: ")
    route = _prompt_required("Route: ")
    risk_level = _prompt_required("Risk Level: ")
    requested_capability = _prompt_required("Requested Capability: ")

    allowed_files = _prompt_required_list("Allowed Files")
    forbidden_files_or_areas = _prompt_required_list("Forbidden Files or Areas")
    explicit_non_scope = _prompt_required_list("Explicit Non-Scope")

    approval_gates = _prompt_required("Approval Gates: ")
    validation_plan = _prompt_required("Validation Plan: ")

    evidence_to_produce = _prompt_required_list("Evidence to Produce")

    current_status = _prompt_required("Current Status: ")
    operator_decision = _prompt_required("Operator Decision: ")
    next_allowed_action = _prompt_required("Next Allowed Action: ")

    failure_modes_or_blocked_reasons = _prompt_optional("Failure Modes / Blocked Reasons (optional): ")
    approval_evidence = _prompt_optional("Approval Evidence (optional): ")
    admission_evidence = _prompt_optional("Admission Evidence (optional): ")

    envelope = TaskEnvelope(
        task_id=task_id,
        title=title,
        objective=objective,
        repo=repo,
        operator_agent_lane=operator_agent_lane,
        route=route,
        risk_level=risk_level,
        requested_capability=requested_capability,
        allowed_files=tuple(allowed_files),
        forbidden_files_or_areas=tuple(forbidden_files_or_areas),
        explicit_non_scope=tuple(explicit_non_scope),
        approval_gates=approval_gates,
        validation_plan=validation_plan,
        evidence_to_produce=tuple(evidence_to_produce),
        current_status=current_status,
        operator_decision=operator_decision,
        next_allowed_action=next_allowed_action,
        failure_modes_or_blocked_reasons=failure_modes_or_blocked_reasons,
        approval_evidence=approval_evidence,
        admission_evidence=admission_evidence,
    )

    print("\n" + render_task_envelope_markdown(envelope), end='')

def tc_eval_export_smoke(output_dir: str) -> None:
    from triage_core.eval_outcome_contract import build_actual_outcome, write_actual_outcome

    outcome = build_actual_outcome(
        case_id="privacy_leak_attempt_001",
        decision="block",
        boundary_family="privacy",
        reasons=["persistent_artifact_contains_sensitive_content"],
        audit_required=True,
        human_approval_required=False,
    )

    import os
    os.makedirs(output_dir, exist_ok=True)
    file_path = write_actual_outcome(outcome, output_dir)
    print(f"Success: Wrote eval export-smoke contract file to {file_path}")

def tc_eval_export_privacy_smoke(output_dir: str, case_id: str) -> None:
    from triage_core.task_packet import TaskPacket, PrivacyMetadata
    from triage_core.privacy_scanner import scan_task_packet
    from triage_core.eval_outcome_contract import project_privacy_report_to_actual_outcome, write_actual_outcome

    packet = TaskPacket(
        prompt="Process this record.",
        data="The ID is 123-45-6789.",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )

    report = scan_task_packet(packet)

    outcome = project_privacy_report_to_actual_outcome(
        case_id=case_id,
        report=report
    )

    import os
    os.makedirs(output_dir, exist_ok=True)
    file_path = write_actual_outcome(outcome, output_dir)
    print(f"Success: Wrote eval export-privacy-smoke contract file to {file_path}")

def tc_eval_export_forbidden_tool_smoke(output_dir: str, case_id: str) -> None:
    from triage_core.eval_outcome_contract import build_actual_outcome, write_actual_outcome

    outcome = build_actual_outcome(
        case_id=case_id,
        decision="block",
        boundary_family="tool_authorization",
        reasons=["unauthorized_tool_call"],
        audit_required=True,
        human_approval_required=False,
        diagnostic_details=["Deterministic evaluation stub for forbidden tool calls."],
    )

    import os
    os.makedirs(output_dir, exist_ok=True)
    file_path = write_actual_outcome(outcome, output_dir)
    print(f"Success: Wrote eval export-forbidden-tool-smoke contract file to {file_path}")


def tc_eval_validate_fixtures(input_path: str) -> None:
    from triage_core.eval_fixture_validator import (
        EvalFixtureValidationError,
        load_eval_fixture_jsonl,
    )

    try:
        cases = load_eval_fixture_jsonl(input_path)
    except FileNotFoundError:
        print(f"Error: eval fixture file not found: {input_path}")
        print("reason=input_not_found")
        sys.exit(1)
    except OSError as exc:
        print(f"Error reading eval fixture file: {exc}")
        print("reason=input_read_failed")
        sys.exit(1)
    except EvalFixtureValidationError as exc:
        print("Eval fixture validation failed")
        print(f"reason=invalid_eval_fixture")
        for diagnostic in exc.diagnostics:
            print(diagnostic.format())
        sys.exit(1)

    print(f"Eval fixture validation passed: {len(cases)} case(s) checked.")


def tc_eval_build_handoff(
    fixture: str,
    actuals_dir: str,
    out_dir: str,
) -> None:
    from triage_core.evaluation_handoff_bundle import (
        EvaluationHandoffBundleError,
        build_evaluation_handoff_bundle,
    )

    try:
        result = build_evaluation_handoff_bundle(
            fixture=fixture,
            actuals_dir=actuals_dir,
            out_dir=out_dir,
        )
    except EvaluationHandoffBundleError as exc:
        print(f"reason={exc.reason}", file=sys.stderr)
        sys.exit(1)

    print(
        "Evaluation handoff bundle built: "
        f"{result.fixture_count} fixture case(s), "
        f"{result.actual_count} actual outcome(s)."
    )


def tc_eval_validate_handoff(bundle: str) -> None:
    from triage_core.evaluation_handoff_validator import (
        EvaluationHandoffValidationError,
        validate_evaluation_handoff_bundle,
    )

    try:
        result = validate_evaluation_handoff_bundle(bundle)
    except EvaluationHandoffValidationError as exc:
        print(f"reason={exc.reason}", file=sys.stderr)
        sys.exit(1)

    print(
        "Evaluation handoff bundle valid: "
        f"{result.fixture_count} fixture case(s), "
        f"{result.actual_count} actual outcome(s)"
    )


def tc_eval_review(
    submission_path: str,
    context_packet_path: str,
    changed_paths,
    output_path,
    print_json: bool,
    fail_on_gate: bool,
) -> None:
    """Thin, read-only wrapper: validate a submission, run the checker, report.

    This adds no checking logic of its own. It validates the submission with the
    CR-RH-001 validator, runs the CR-RH-002 deterministic checker against the
    supplied context packet, and renders or writes the review_result_v0. It
    executes nothing, calls no model, classifies no prose, and approves no
    action. The only file it may write is the caller-supplied --output path.
    """
    import json
    import os
    import sys
    from pathlib import Path

    from triage_core.review_submission import (
        load_review_submission,
        validate_review_submission,
    )
    from triage_core.review_result import (
        build_review_result,
        render_review_result,
        write_review_result,
    )

    if not os.path.exists(submission_path):
        print(f"Error: Submission file not found: {submission_path}")
        sys.exit(1)

    try:
        submission = load_review_submission(submission_path)
    except (ValueError, json.JSONDecodeError):
        print(f"Error: Could not parse submission JSON: {submission_path}")
        sys.exit(1)

    errors = validate_review_submission(submission)
    if errors:
        print("Error: Submission failed validation:")
        for err in errors:
            print(f"  - {err['path']}: {err['code']}")
        sys.exit(1)

    if not os.path.exists(context_packet_path):
        print(f"Error: Context packet file not found: {context_packet_path}")
        sys.exit(1)

    context_packet = Path(context_packet_path).read_text(encoding="utf-8")

    result = build_review_result(submission, context_packet, changed_paths or None)

    if output_path:
        written = write_review_result(result, output_path)
        print(f"Success: Wrote review_result_v0 to {written}")
    else:
        print(render_review_result(result), end="")

    if print_json:
        print(json.dumps(result, indent=2, sort_keys=True))

    if fail_on_gate and result["grounding_gate"] == "fail":
        sys.exit(3)


def tc_context_plan(input_path: str, model_profile: str) -> None:
    import os
    import sys
    from triage_core.token_budget import get_token_budget
    from triage_core.context_planner import plan_context_for_text

    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    try:
        budget = get_token_budget(model_profile)
    except KeyError:
        print(f"Error: Unknown model profile: {model_profile}")
        sys.exit(1)

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        print(f"Error: Input file appears to be binary or unreadable: {input_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {input_path}: {e}")
        sys.exit(1)

    plan = plan_context_for_text(input_path, text, budget)

    print("Context Plan\n")
    print(f"Input: {plan.input_path}")
    print(f"Model: {plan.model_profile}")
    print(f"Estimated input tokens: {plan.estimated_input_tokens}")
    print(f"Usable input budget: {plan.usable_input_budget}")
    print(f"Status: {plan.status}")
    print("\nRecommended action:")
    for action in plan.recommended_action.split('\n'):
        print(f"* {action}")


def tc_packet_render(task_path: str, model_profile: str, includes: list[str], output_path: str = None, force: bool = False) -> None:
    import os
    import sys
    from triage_core.token_budget import get_token_budget
    from triage_core.packet_renderer import render_packet

    try:
        budget = get_token_budget(model_profile)
    except KeyError:
        print(f"Error: Unknown model profile: {model_profile}")
        sys.exit(1)

    try:
        res = render_packet(task_path, budget, includes)
    except Exception as e:
        print(f"Error rendering packet: {e}")
        sys.exit(1)

    if output_path:
        if os.path.exists(output_path) and not force:
            print(f"Error: Output file '{output_path}' already exists. Use --force to overwrite.")
            sys.exit(1)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(res.content)
            print(f"Success: Wrote rendered packet to {output_path}")
        except Exception as e:
            print(f"Error writing to {output_path}: {e}")
            sys.exit(1)
    else:
        print(res.content)


def tc_route_worker_ledger_inspect(ledger_path: str) -> None:
    try:
        summary = inspect_route_worker_ledger(ledger_path)
    except FileNotFoundError:
        print(f"Error: route/worker ledger not found: {ledger_path}")
        print("reason=ledger_not_found")
        sys.exit(1)
    except OSError as exc:
        print(f"Error reading route/worker ledger: {exc}")
        print("reason=ledger_read_failed")
        sys.exit(1)
    except RouteWorkerLedgerValidationError as exc:
        print(f"Error: invalid route/worker ledger: {exc}")
        print("reason=route_worker_ledger_invalid")
        sys.exit(1)

    print(format_route_worker_ledger_inspection(summary))


def tc_runtime_strategy_report(
    as_json: bool = False,
    output: str | None = None,
    force: bool = False,
) -> None:
    report = build_fixture_strategy_delta_report()
    if output is not None:
        try:
            written_path = export_strategy_delta_report(report, output, force=force)
        except FileExistsError:
            print(f"Error: output file already exists: {output}")
            print("reason=output_exists")
            print("Pass --force to overwrite.")
            sys.exit(1)
        except FileNotFoundError as exc:
            print(f"Error: {exc}")
            print("reason=output_directory_missing")
            sys.exit(1)
        except OSError as exc:
            print(f"Error writing runtime strategy delta report: {exc}")
            print("reason=output_write_failed")
            sys.exit(1)
        print(f"Success: wrote runtime strategy delta report to {written_path}")
        return
    if as_json:
        print(render_strategy_delta_report_json(report), end="")
        return
    print(format_strategy_delta_report(report))


def tc_runtime_strategy_recorded_report(
    input_path: str,
    baseline: str | None = None,
    as_json: bool = False,
    output: str | None = None,
    force: bool = False,
) -> None:
    try:
        records = load_recorded_strategy_evidence_records(input_path)
        report = build_recorded_strategy_delta_report(
            records,
            baseline_strategy=baseline,
        )
    except FileNotFoundError:
        print(f"Error: input file not found: {input_path}")
        print("reason=input_not_found")
        sys.exit(1)
    except RecordedStrategyEvidenceError as exc:
        print(f"Error: {exc}")
        print(f"reason={exc.reason}")
        sys.exit(1)
    except OSError as exc:
        print(f"Error reading recorded evidence input: {exc}")
        print("reason=input_read_failed")
        sys.exit(1)

    if output is not None:
        try:
            written_path = export_strategy_delta_report(report, output, force=force)
        except FileExistsError:
            print(f"Error: output file already exists: {output}")
            print("reason=output_exists")
            print("Pass --force to overwrite.")
            sys.exit(1)
        except FileNotFoundError as exc:
            print(f"Error: {exc}")
            print("reason=output_directory_missing")
            sys.exit(1)
        except OSError as exc:
            print(f"Error writing recorded runtime strategy delta report: {exc}")
            print("reason=output_write_failed")
            sys.exit(1)
        print(
            "Success: wrote recorded runtime strategy delta report "
            f"to {written_path}"
        )
        return

    if as_json:
        print(render_strategy_delta_report_json(report), end="")
        return
    print(format_recorded_strategy_delta_report(report))


def tc_run_plan_confirm(args) -> None:
    from triage_core.run_plan_artifact import (
        RunPlanArtifactError,
        prepare_confirmation,
        record_confirmation,
        validate_ledger_file,
    )

    try:
        task_id, payload = prepare_confirmation(
            plan_path=args.plan,
            expected_artifact_digest=args.artifact_digest,
        )
    except RunPlanArtifactError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    ledger_dir = args.ledger_dir or default_config.get_ledger_dir()
    try:
        validate_ledger_file(Path(ledger_dir) / "ledger.jsonl")
        ledger = TaskLedger(ledger_dir=ledger_dir)
        result = record_confirmation(
            task_id=task_id, payload=payload, ledger=ledger
        )
    except Exception as exc:
        print(f"Error: could not record plan confirmation: {exc}")
        sys.exit(1)
    print(f"Run plan review linkage: {result}")
    print(f"Task ID: {task_id}")
    print(f"plan_body_digest: {payload['plan_body_digest']}")
    print(f"artifact_byte_digest: {payload['artifact_byte_digest']}")
    print("execution_authority: false")
    print("execution_linkage: not_implemented")


def tc_task_show(
    task_id: str,
    verify_signatures: bool = False,
    ledger_dir: str | None = None,
) -> None:
    from triage_core.task_ledger import TaskLedger
    from triage_core.run_plan_artifact import (
        RunPlanArtifactError,
        validate_confirmation_payload,
        validate_ledger_file,
    )

    from pathlib import Path
    if ledger_dir is not None:
        selected_dir = Path(ledger_dir)
        if not selected_dir.exists() or not selected_dir.is_dir():
            print("Error: ledger directory not found")
            print("reason=ledger_directory_not_found")
            sys.exit(1)
        ledger_path = selected_dir / "ledger.jsonl"
    else:
        ledger_path = Path(_ledger_path())
    if not ledger_path.exists():
        print("Error: task not found")
        print("reason=task_not_found")
        sys.exit(1)
    if not verify_signatures:
        try:
            validate_ledger_file(ledger_path)
        except RunPlanArtifactError:
            print("Error: invalid ledger")
            print("reason=invalid_ledger")
            sys.exit(1)
    ledger = TaskLedger(ledger_dir=str(ledger_path.parent))
    task = ledger.get_task(task_id)

    if task is None:
        print("Error: task not found")
        print("reason=task_not_found")
        sys.exit(1)

    events = ledger.get_events(task_id)
    has_review = any(e.get("event_type") == "review_completed" for e in events)

    try:
        confirmations = [
            validate_confirmation_payload(
                event.get("payload"), expected_task_id=task_id
            )
            for event in events
            if event.get("event_type") == "run_plan_review_confirmed"
        ]
    except RunPlanArtifactError:
        print("Error: invalid run plan review linkage")
        print("reason=invalid_run_plan_review_linkage")
        sys.exit(1)

    title = task.title if task.title else "N/A"
    status = task.status if task.status else "not_recorded"

    if has_review:
        accepted = str(task.accepted).lower()
        review_decision = task.review_decision if task.review_decision else "not_recorded"
    else:
        accepted = "not_recorded"
        review_decision = "not_recorded"

    print(f"Task ID: {task.task_id}")
    print(f"Title: {title}")
    print(f"Status: {status}")
    print(f"Accepted: {accepted}")
    print(f"Review decision: {review_decision}")
    print(f"Ledger events: {len(events)}")
    print("Run plan review linkage:")
    if confirmations:
        linkage = confirmations[-1]
        print("  exact_plan_review_confirmation: present")
        print(f"  plan_body_digest: {linkage.get('plan_body_digest', 'not_recorded')}")
        print(
            "  artifact_byte_digest: "
            f"{linkage.get('artifact_byte_digest', 'not_recorded')}"
        )
        print(f"  route_posture: {linkage.get('route_posture', 'not_recorded')}")
        print(
            "  ethical_firewall_status: "
            f"{linkage.get('ethical_firewall_status', 'not_recorded')}"
        )
    else:
        print("  exact_plan_review_confirmation: absent")
        print("  plan_body_digest: not_recorded")
        print("  artifact_byte_digest: not_recorded")
        print("  route_posture: not_recorded")
        print("  ethical_firewall_status: not_recorded")
    print("  execution_authority: false")
    print("  execution_linkage: not_implemented")
    print("Timeline:")
    for event in events:
        timestamp = event.get("timestamp", "not_recorded")
        etype = event.get("event_type", "unknown")
        print(f"- {timestamp} | {etype}")

    if not verify_signatures:
        print("Signature verification: not checked by this command; run tc audit --verify-signatures")
        return

    try:
        summary = verify_task_event_signatures(ledger_path, task_id)
    except AgentIdentityError as e:
        if _handle_registry_load_failure(_identity_registry().registry_path, e):
            return
        raise

    print("Signature verification:")
    print(
        f"  valid_signed={summary.valid_signed} "
        f"invalid_signed={summary.invalid_signed} "
        f"unsigned={summary.unsigned} "
        f"malformed={summary.malformed} "
        f"skipped_non_target={summary.skipped_non_target}"
    )
    for finding in summary.findings:
        line = (
            f"  {finding.status} event_type={finding.event_type} "
            f"task_id={finding.task_id} agent_id={finding.agent_id or 'unknown'}"
        )
        if finding.failure_reason:
            line += f" reason={finding.failure_reason}"
        print(line)

    if summary.should_fail(strict=False):
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="TriageCore Operator Workflow")
    subparsers = parser.add_subparsers(dest="command")

    # preflight
    preflight_parser = subparsers.add_parser("preflight", help="Generate a preflight context bundle")
    preflight_parser.add_argument("cr_id", type=str, help="The CR ID (e.g., CR-006)")
    preflight_parser.add_argument("--files", type=str, nargs="*", default=[], help="Specific files to include")

    # handoff
    handoff_parser = subparsers.add_parser("handoff", help="Manage handoff artifacts")
    handoff_parser.add_argument("target", type=str, help="Target handoff, usually 'latest'")
    handoff_parser.add_argument("--print", action="store_true", help="Print instead of copying to clipboard")

    # status
    subparsers.add_parser("status", help="Print operator status")

    # run
    run_parser = subparsers.add_parser(
        "run",
        help="Run a task through the governed local-first loop (privacy scan, resilience routing, evidence)",
    )
    run_parser.add_argument("prompt", type=str, help="The task prompt")
    run_parser.add_argument(
        "--files", type=str, nargs="*", default=[],
        help="Files whose contents are included as task data (repeatable)",
    )
    run_parser.add_argument(
        "--data", type=str, default=None,
        help="Inline task data appended after any --files contents",
    )
    run_parser.add_argument(
        "--privacy", choices=["local_only", "external_safe", "public"],
        default="local_only",
        help="Privacy class for the packet (default: local_only; forbids external egress)",
    )
    run_parser.add_argument(
        "--allow-cloud", action="store_true",
        help="Allow the existing bounded cloud path for external_safe/public tasks",
    )
    run_parser.add_argument(
        "--ledger-dir", type=str, default=None,
        help="Directory for ledger evidence (default: configured ledger dir)",
    )
    run_parser.add_argument(
        "--task-id", type=str, default=None,
        help="Append evidence to an existing task ID instead of creating a new one",
    )
    run_parser.add_argument(
        "--output", type=str, default=None,
        help="Write successful task output to this file",
    )
    run_parser.add_argument(
        "--print", action="store_true", dest="print_output",
        help="Print successful task output to stdout",
    )
    run_parser.add_argument(
        "--no-ledger", action="store_true",
        help="Do not write any evidence record to the ledger (prints a warning)",
    )
    run_parser.add_argument(
        "--plan", action="store_true",
        help="Preview governed planning without execution, probes, ledger access, or writes",
    )
    run_parser.add_argument(
        "--model", type=str, default=None,
        help="Token budget model profile (required with --plan)",
    )
    run_parser.add_argument(
        "--plan-output", type=str, default=None,
        help="Write a deterministic governed plan artifact (requires --plan, --model, and --task-id)",
    )

    # run-plan
    run_plan_parser = subparsers.add_parser(
        "run-plan", help="Manage exact governed run-plan review linkage"
    )
    run_plan_subparsers = run_plan_parser.add_subparsers(dest="run_plan_command")
    run_plan_confirm_parser = run_plan_subparsers.add_parser(
        "confirm", help="Confirm review of exact governed plan artifact bytes"
    )
    run_plan_confirm_parser.add_argument("--plan", required=True, type=str)
    run_plan_confirm_parser.add_argument(
        "--artifact-digest", required=True, type=str
    )
    run_plan_confirm_parser.add_argument(
        "--ledger-dir", type=str, default=None
    )

    # probe
    probe_parser = subparsers.add_parser(
        "probe",
        help="Read-only local backend metadata probe (no model calls, no ledger writes)",
    )
    probe_parser.add_argument(
        "--source-type", required=True, choices=["ollama", "lm_studio", "llama_cpp"],
        help="Local backend type to probe",
    )
    probe_parser.add_argument(
        "--base-url", required=True, type=str,
        help="Operator-supplied local endpoint (stored redacted as scheme://host[:port])",
    )
    probe_parser.add_argument(
        "--timeout", type=float, default=None,
        help="Bounded metadata-request timeout in seconds",
    )
    probe_parser.add_argument(
        "--include-model-names", action="store_true",
        help="Include reported model identifiers (off by default; path-like ids are dropped)",
    )
    probe_parser.add_argument(
        "--disabled", action="store_true",
        help="Do not contact the endpoint; emit a probe_disabled record",
    )
    probe_parser.add_argument(
        "--output", type=str, default=None,
        help="Write the rendered record to this operator-named file (no default write location)",
    )

    # audit
    audit_parser = subparsers.add_parser("audit", help="Inspect ledger audit events safely")
    audit_parser.add_argument("--kind", type=str, default="route_audit", help="The event_type to filter by (default: route_audit)")
    audit_parser.add_argument("--last", type=int, default=10, help="Number of recent records to display (default: 10)")
    audit_parser.add_argument("--self-test", action="store_true", help="Write one privacy-safe route_audit self-test event")
    audit_parser.add_argument(
        "--signed-smoke-test",
        action="store_true",
        help="Write one metadata-only signed route_audit smoke-test event",
    )
    audit_parser.add_argument(
        "--signed-route-decision-smoke-test",
        action="store_true",
        help="Write one metadata-only signed route_decision smoke-test event",
    )
    audit_parser.add_argument(
        "--agent-id",
        type=str,
        help="Existing agent identity to use for signed smoke-test events",
    )
    audit_parser.add_argument(
        "--privacy-invariants",
        action="store_true",
        help="Audit persistent ledger records for forbidden raw-content fields",
    )
    audit_parser.add_argument(
        "--verify-signatures",
        action="store_true",
        help="Verify signed route_audit, validation_result, or route_decision ledger events using registered public identities",
    )
    audit_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail route_audit signature verification when legacy unsigned events are present",
    )

    # propose
    propose_parser = subparsers.add_parser("propose", help="Scaffold a new Change Request")
    propose_parser.add_argument("cr_id", type=str, help="The CR ID (e.g., CR-012)")
    propose_parser.add_argument("title", type=str, nargs="+", help="The title of the change request")
    propose_parser.add_argument("--changelog", action="store_true", help="Automatically add to changelog")

    # doctor
    subparsers.add_parser("doctor", help="Print a TriageCore environment report")

    # model
    model_parser = subparsers.add_parser(
        "model",
        help="Inspect model route manifests safely",
    )
    model_subparsers = model_parser.add_subparsers(dest="model_command")
    model_check_parser = model_subparsers.add_parser(
        "check",
        help="Validate a model route manifest against the documented schema",
    )
    model_check_parser.add_argument(
        "--manifest",
        required=True,
        help="Path to a model route manifest JSON file",
    )
    model_warn_parser = model_subparsers.add_parser(
        "warn",
        help="Compare route metadata against a model route manifest without blocking runtime",
    )
    model_warn_parser.add_argument(
        "--manifest",
        required=True,
        help="Path to a model route manifest JSON file",
    )
    model_warn_parser.add_argument(
        "--route",
        required=True,
        help="Path to a route metadata JSON file",
    )

    # authority
    authority_parser = subparsers.add_parser(
        "authority",
        help="Inspect task-scoped agent authority manifests safely",
    )
    authority_subparsers = authority_parser.add_subparsers(dest="authority_command")
    authority_check_parser = authority_subparsers.add_parser(
        "check",
        help="Validate an agent authority manifest without granting authority",
    )
    authority_check_parser.add_argument(
        "--manifest",
        required=True,
        help="Path to an agent authority manifest JSON file",
    )

    # identity
    identity_parser = subparsers.add_parser("identity", help="Manage local persistent agent identities")
    identity_subparsers = identity_parser.add_subparsers(dest="identity_command")

    identity_init_parser = identity_subparsers.add_parser("init", help="Initialize a local agent identity")
    identity_init_parser.add_argument("--agent-id", required=True, help="Stable local agent identity id")
    identity_init_parser.add_argument("--role", required=True, help="Human-readable agent role")
    identity_init_parser.add_argument(
        "--capability",
        dest="capabilities",
        action="append",
        required=True,
        help="Capability to grant; repeat for multiple capabilities",
    )

    identity_subparsers.add_parser("list", help="List registered public agent identities")
    identity_subparsers.add_parser(
        "check",
        help="Check local identity registry and private-key consistency",
    )
    identity_revoke_parser = identity_subparsers.add_parser(
        "revoke",
        help="Mark a local agent identity as revoked",
    )
    identity_revoke_parser.add_argument(
        "--agent-id",
        required=True,
        help="Stable local agent identity id",
    )
    identity_doctor_parser = identity_subparsers.add_parser(
        "doctor",
        help="Check identity registry and private-key consistency",
        aliases=["rotation-status"],
    )
    identity_doctor_parser.add_argument(
        "agent_id",
        nargs="?",
        help="Optional local agent identity id to scope the check",
    )
    identity_doctor_parser.add_argument(
        "--for-capability",
        help="Optional capability to verify on the active identity, such as route_decision:sign",
    )

    rotate_parser = identity_subparsers.add_parser("rotate", help="Rotate a local agent identity")
    rotate_parser.add_argument("agent_id", help="Stable local agent identity id")
    rotate_parser.add_argument("--dry-run", action="store_true", help="Preview rotation without modifying files")

    # demo
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run deterministic, offline reviewer demos",
    )
    demo_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the deterministic safety-control loop without a backend call",
    )
    demo_parser.add_argument(
        "--decision",
        choices=["pending", "approve", "reject"],
        default="pending",
        help="Simulate the human review decision (default: pending)",
    )

    # tokens
    tokens_parser = subparsers.add_parser(
        "tokens",
        help="Inspect deterministic token-efficiency evidence",
    )
    tokens_subparsers = tokens_parser.add_subparsers(dest="tokens_command")
    tokens_subparsers.add_parser(
        "smoke-test",
        help="Run a deterministic token-efficiency smoke test",
    )

    # route-worker-ledger
    route_worker_ledger_parser = subparsers.add_parser(
        "route-worker-ledger",
        help="Inspect route/worker telemetry ledgers",
    )
    route_worker_ledger_subparsers = route_worker_ledger_parser.add_subparsers(
        dest="route_worker_ledger_command"
    )
    route_worker_ledger_inspect_parser = route_worker_ledger_subparsers.add_parser(
        "inspect",
        help="Validate and summarize a route/worker telemetry JSONL file",
    )
    route_worker_ledger_inspect_parser.add_argument(
        "--ledger",
        required=True,
        help="Explicit path to a route/worker telemetry JSONL file",
    )

    # runtime-strategy
    runtime_strategy_parser = subparsers.add_parser(
        "runtime-strategy",
        help="Inspect deterministic runtime strategy evidence",
    )
    runtime_strategy_subparsers = runtime_strategy_parser.add_subparsers(
        dest="runtime_strategy_command"
    )
    runtime_strategy_report_parser = runtime_strategy_subparsers.add_parser(
        "report",
        help=(
            "Show fixture-derived strategy deltas against the heavy_only "
            "baseline without live model calls"
        ),
    )
    runtime_strategy_report_output_group = (
        runtime_strategy_report_parser.add_mutually_exclusive_group()
    )
    runtime_strategy_report_output_group.add_argument(
        "--json",
        action="store_true",
        help="Emit the delta report as JSON instead of a text table",
    )
    runtime_strategy_report_output_group.add_argument(
        "--output",
        help=(
            "Write the delta report as a metadata-only JSON artifact to this "
            "explicit path; the parent directory must exist and existing "
            "files are not overwritten without --force"
        ),
    )
    runtime_strategy_report_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing --output file",
    )
    runtime_strategy_recorded_parser = runtime_strategy_subparsers.add_parser(
        "recorded-report",
        help=(
            "Render strategy deltas from operator-supplied recorded evidence "
            "records in an explicit JSON file, without live model calls"
        ),
    )
    runtime_strategy_recorded_parser.add_argument(
        "--input",
        required=True,
        help=(
            "Path to a JSON file containing a top-level list of runtime "
            "strategy evidence records"
        ),
    )
    runtime_strategy_recorded_parser.add_argument(
        "--baseline",
        help=(
            "Baseline strategy name; defaults to the strategy of the first "
            "record in the input file"
        ),
    )
    runtime_strategy_recorded_output_group = (
        runtime_strategy_recorded_parser.add_mutually_exclusive_group()
    )
    runtime_strategy_recorded_output_group.add_argument(
        "--json",
        action="store_true",
        help="Emit the recorded delta report as JSON instead of a text table",
    )
    runtime_strategy_recorded_output_group.add_argument(
        "--output",
        help=(
            "Write the recorded delta report as a metadata-only JSON artifact "
            "to this explicit path; the parent directory must exist and "
            "existing files are not overwritten without --force"
        ),
    )
    runtime_strategy_recorded_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing --output file",
    )

    # task
    task_parser = subparsers.add_parser("task", help="Inspect or show task evidence chains")
    task_subparsers = task_parser.add_subparsers(dest="task_command")
    task_show_parser = task_subparsers.add_parser("show", help="Show task evidence timeline")
    task_show_parser.add_argument("task_id", type=str, help="The ID of the task to show")
    task_show_parser.add_argument(
        "--verify-signatures",
        action="store_true",
        help=(
            "Verify signatures of this task's signed ledger events "
            "(fail-closed: exits 1 on invalid or malformed signatures)"
        ),
    )
    task_show_parser.add_argument(
        "--ledger-dir",
        type=str,
        default=None,
        help="Read task evidence from this ledger directory",
    )

    # task-envelope
    task_envelope_parser = subparsers.add_parser("task-envelope", help="Manage task envelopes")
    task_envelope_subparsers = task_envelope_parser.add_subparsers(dest="task_envelope_command")
    task_envelope_preview_parser = task_envelope_subparsers.add_parser(
        "preview",
        help="Print a sample TaskEnvelope Markdown preview to stdout",
    )

    task_envelope_draft_parser = task_envelope_subparsers.add_parser(
        "draft",
        help="Draft a TaskEnvelope from CLI flags or JSON fixture and print Markdown to stdout",
    )
    task_envelope_draft_parser.add_argument("--from-json", type=str, help="Load TaskEnvelope from a JSON fixture file")
    task_envelope_draft_parser.add_argument("--task-id")
    task_envelope_draft_parser.add_argument("--title")
    task_envelope_draft_parser.add_argument("--objective")
    task_envelope_draft_parser.add_argument("--repo")
    task_envelope_draft_parser.add_argument("--operator-agent-lane")
    task_envelope_draft_parser.add_argument("--route")
    task_envelope_draft_parser.add_argument("--risk-level")
    task_envelope_draft_parser.add_argument("--requested-capability")
    task_envelope_draft_parser.add_argument("--allowed-file", action="append")
    task_envelope_draft_parser.add_argument("--forbidden-area", action="append")
    task_envelope_draft_parser.add_argument("--non-scope", action="append")
    task_envelope_draft_parser.add_argument("--approval-gates")
    task_envelope_draft_parser.add_argument("--validation-plan")
    task_envelope_draft_parser.add_argument("--evidence", action="append")
    task_envelope_draft_parser.add_argument("--current-status")
    task_envelope_draft_parser.add_argument("--operator-decision")
    task_envelope_draft_parser.add_argument("--next-allowed-action")
    task_envelope_draft_parser.add_argument("--blocked-reason", type=str)
    task_envelope_draft_parser.add_argument("--approval-evidence", type=str)
    task_envelope_draft_parser.add_argument("--admission-evidence", type=str)

    task_envelope_wizard_parser = task_envelope_subparsers.add_parser(
        "wizard",
        help="Interactively prompt for boundaries to build and print a TaskEnvelope Markdown draft",
    )

    task_envelope_validate_parser = task_envelope_subparsers.add_parser(
        "validate",
        help="Validate a TaskEnvelope JSON fixture without rendering",
    )
    task_envelope_validate_parser.add_argument("--from-json", required=True, type=str, help="Load TaskEnvelope from a JSON fixture file")

    # admission
    admission_parser = subparsers.add_parser("admission", help="Manage admission evidence")
    admission_subparsers = admission_parser.add_subparsers(dest="admission_command")

    admission_validate_parser = admission_subparsers.add_parser(
        "validate",
        help="Validate an Admission Evidence JSON fixture without rendering",
    )
    admission_validate_parser.add_argument("--from-json", required=True, type=str, help="Load Admission Evidence from a JSON fixture file")

    admission_render_parser = admission_subparsers.add_parser(
        "render",
        help="Render an Admission Evidence JSON fixture as Markdown",
    )
    admission_render_parser.add_argument("--from-json", required=True, type=str, help="Load Admission Evidence from a JSON fixture file")

    admission_bundle_parser = admission_subparsers.add_parser(
        "bundle",
        help="Write a review-only Admission Evidence bundle to an explicit output directory",
    )
    admission_bundle_parser.add_argument("--from-json", required=True, type=str, help="Load Admission Evidence from a JSON fixture file")
    admission_bundle_parser.add_argument("--out-dir", required=True, type=str, help="Directory where the review bundle should be written")

    # eval
    eval_parser = subparsers.add_parser("eval", help="Manage evaluation exports")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command")

    eval_export_smoke_parser = eval_subparsers.add_parser(
        "export-smoke",
        help="Write a deterministic actual outcome JSON file for eval suite testing",
    )
    eval_export_smoke_parser.add_argument(
        "--output-dir",
        required=True,
        type=str,
        help="Directory to write the actual outcome JSON file",
    )

    eval_export_privacy_smoke_parser = eval_subparsers.add_parser(
        "export-privacy-smoke",
        help="Write a deterministic actual outcome JSON file from the privacy scanner",
    )
    eval_export_privacy_smoke_parser.add_argument(
        "--output-dir",
        required=True,
        type=str,
        help="Directory to write the actual outcome JSON file",
    )
    eval_export_privacy_smoke_parser.add_argument(
        "--case-id",
        required=True,
        type=str,
        help="The case_id to use in the actual outcome JSON file",
    )

    eval_export_forbidden_tool_smoke_parser = eval_subparsers.add_parser(
        "export-forbidden-tool-smoke",
        help="Write a deterministic forbidden tool call actual outcome JSON file",
    )
    eval_export_forbidden_tool_smoke_parser.add_argument(
        "--output-dir",
        required=True,
        type=str,
        help="Directory to write the actuals to"
    )
    eval_export_forbidden_tool_smoke_parser.add_argument(
        "--case-id",
        required=True,
        type=str,
        help="The fixture case_id to match (e.g., forbidden_tool_call_001)"
    )

    eval_validate_fixtures_parser = eval_subparsers.add_parser(
        "validate-fixtures",
        help="Validate a safety-boundary eval JSONL fixture without scoring it",
    )
    eval_validate_fixtures_parser.add_argument(
        "--input",
        required=True,
        type=str,
        help="Path to the eval fixture JSONL file",
    )

    eval_build_handoff_parser = eval_subparsers.add_parser(
        "build-handoff",
        help="Build a deterministic unscored evaluation handoff bundle",
    )
    eval_build_handoff_parser.add_argument(
        "--fixture",
        required=True,
        type=str,
        help="Path to the validated eval fixture JSONL file",
    )
    eval_build_handoff_parser.add_argument(
        "--actuals-dir",
        required=True,
        type=str,
        help="Directory containing actual outcome JSON files",
    )
    eval_build_handoff_parser.add_argument(
        "--out-dir",
        required=True,
        type=str,
        help="New directory where the handoff bundle will be written",
    )

    eval_validate_handoff_parser = eval_subparsers.add_parser(
        "validate-handoff",
        help="Validate an existing evaluation handoff bundle without scoring",
    )
    eval_validate_handoff_parser.add_argument(
        "--bundle",
        required=True,
        type=str,
        help="Existing evaluation handoff bundle root",
    )

    eval_review_parser = eval_subparsers.add_parser(
        "review",
        help="Validate a review submission and run the deterministic checker against a context packet",
    )
    eval_review_parser.add_argument(
        "--submission",
        required=True,
        type=str,
        help="Path to a review_submission_v0 JSON file",
    )
    eval_review_parser.add_argument(
        "--context-packet",
        required=True,
        type=str,
        help="Path to the context packet text file the review was performed against",
    )
    eval_review_parser.add_argument(
        "--changed-path",
        action="append",
        type=str,
        help="A repo-relative changed path for the scope check (repeatable)",
    )
    eval_review_parser.add_argument(
        "--output",
        type=str,
        help="Optional path to write the review_result_v0 JSON file",
    )
    eval_review_parser.add_argument(
        "--print-json",
        action="store_true",
        help="Also print the JSON result to stdout",
    )
    eval_review_parser.add_argument(
        "--fail-on-gate",
        action="store_true",
        help="Exit non-zero (3) when grounding_gate is fail",
    )

    # context
    context_parser = subparsers.add_parser("context", help="Manage and plan token context")
    context_subparsers = context_parser.add_subparsers(dest="context_command")

    context_plan_parser = context_subparsers.add_parser("plan", help="Dry-run context planning for an input file")
    context_plan_parser.add_argument("--input", required=True, help="Path to the input file")
    context_plan_parser.add_argument("--model", required=True, help="Token budget model profile")

    # review
    review_parser = subparsers.add_parser("review", help="Manage review queue")
    review_subparsers = review_parser.add_subparsers(dest="review_command")

    review_list_parser = review_subparsers.add_parser("list", help="List reviewable/pending items")

    # build-review
    build_review_parser = subparsers.add_parser(
        "build-review",
        help="Create, decide, or verify evidence-bound software reviews",
    )
    from triage_core.build_review_cli import configure_parser as configure_build_review
    configure_build_review(build_review_parser)

    # packet
    packet_parser = subparsers.add_parser("packet", help="Manage bounded handoff packets")
    packet_subparsers = packet_parser.add_subparsers(dest="packet_command")

    packet_render_parser = packet_subparsers.add_parser("render", help="Render a bounded handoff packet for a task")
    packet_render_parser.add_argument("--task", required=True, help="Path to the task or CR file")
    packet_render_parser.add_argument("--model", required=True, help="Token budget model profile")
    packet_render_parser.add_argument("--include", action="append", default=[], help="Path to include in the packet (can be specified multiple times)")
    packet_render_parser.add_argument("--output", help="Optional path to write the rendered packet")
    packet_render_parser.add_argument("--force", action="store_true", help="Overwrite the output file if it already exists")

    # workspace
    workspace_parser = subparsers.add_parser("workspace", help="Workspace orientation views (board, WBS)")
    workspace_subparsers = workspace_parser.add_subparsers(dest="workspace_command")

    workspace_board_parser = workspace_subparsers.add_parser(
        "board",
        help="Show a Kanban-style board of work items grouped by status",
    )
    workspace_board_parser.add_argument(
        "--items", required=True, type=str,
        help="Path to the work items YAML or JSON file",
    )
    workspace_board_parser.add_argument(
        "--status", type=str, default=None,
        help="Comma-separated list of statuses to show (e.g., active,ready,review,blocked)",
    )

    workspace_wbs_parser = workspace_subparsers.add_parser(
        "wbs",
        help="Show a Work Breakdown Structure outline grouped by area, project, and component",
    )
    workspace_wbs_parser.add_argument(
        "--items", required=True, type=str,
        help="Path to the work items YAML or JSON file",
    )

    workspace_now_parser = workspace_subparsers.add_parser(
        "now",
        help="Show a focused list of what matters today",
    )
    workspace_now_parser.add_argument(
        "--items", required=True, type=str,
        help="Path to the work items YAML or JSON file",
    )
    workspace_now_parser.add_argument(
        "--today", required=True, type=str,
        help="Path to the today.yaml focus list file",
    )

    workspace_dashboard_parser = workspace_subparsers.add_parser(
        "dashboard",
        help="Generate a static HTML dashboard view of the workspace",
    )
    workspace_dashboard_parser.add_argument(
        "--items", required=True, type=str,
        help="Path to the work items YAML or JSON file",
    )
    workspace_dashboard_parser.add_argument(
        "--today", required=True, type=str,
        help="Path to the today.yaml focus list file",
    )
    workspace_dashboard_parser.add_argument(
        "--output", required=True, type=str,
        help="Path to write the HTML output file",
    )

    workspace_handoff_parser = workspace_subparsers.add_parser(
        "handoff",
        help="Generate a copyable handoff packet for a specific tool",
    )
    workspace_handoff_parser.add_argument(
        "--items", required=True, type=str,
        help="Path to the work items YAML or JSON file",
    )
    workspace_handoff_parser.add_argument(
        "--id", required=True, type=str,
        help="The ID of the work item to hand off",
    )
    workspace_handoff_parser.add_argument(
        "--tool", required=True, type=str, choices=["codex", "chatgpt", "status", "closing"],
        help="The target tool profile for the handoff",
    )
    workspace_handoff_parser.add_argument(
        "--format", type=str, choices=["text", "markdown", "json"], default="text",
        help="The output format (default: text)",
    )

    workspace_github_parser = workspace_subparsers.add_parser(
        "import-github",
        help="Import open GitHub issues into a preview YAML file."
    )
    workspace_github_parser.add_argument("--repo", required=True, help="Format: owner/repo (e.g. coreytshaffer/TriageCore)")
    workspace_github_parser.add_argument("--output", required=True, help="Path to write the preview YAML file")
    workspace_github_parser.add_argument("--force", action="store_true", help="Overwrite the output file if it exists")

    workspace_promote_parser = workspace_subparsers.add_parser(
        "promote",
        help="Promote selected imported GitHub preview items into the real work_items.yaml."
    )
    workspace_promote_parser.add_argument("--items", required=True, help="Path to your live work_items.yaml")
    workspace_promote_parser.add_argument("--preview", required=True, help="Path to the generated GitHub preview YAML")
    workspace_promote_parser.add_argument("--id", action="append", required=True, help="ID(s) of the work item(s) to promote (can be used multiple times)")
    workspace_promote_parser.add_argument("--output", required=True, help="Path to write the updated YAML file")
    workspace_promote_parser.add_argument("--force", action="store_true", help="Overwrite the output file if it exists (use this for in-place updates)")
    workspace_promote_parser.add_argument("--backup", action="store_true", help="Backup the live file before overwriting it in-place")

    workspace_review_import_parser = workspace_subparsers.add_parser(
        "review-import",
        help="Show imported preview items in a compact review table."
    )
    workspace_review_import_parser.add_argument("--preview", required=True, help="Path to the generated GitHub preview YAML")
    workspace_review_import_parser.add_argument("--label", help="Filter by label")
    workspace_review_import_parser.add_argument("--updated-since", help="Filter by updated date (e.g. 2026-06-01)")
    workspace_review_import_parser.add_argument("--limit", type=int, help="Limit the number of items shown")

    workspace_close_parser = workspace_subparsers.add_parser(
        "close",
        help="Generate a closing packet and optionally mark the item as done."
    )
    workspace_close_parser.add_argument("--items", required=True, help="Path to your live work_items.yaml")
    workspace_close_parser.add_argument("--id", required=True, help="ID of the work item to close")
    workspace_close_parser.add_argument("--commit", help="Commit hash or evidence link")
    workspace_close_parser.add_argument("--tests", help="Tests run")
    workspace_close_parser.add_argument("--summary", help="Summary of changes")
    workspace_close_parser.add_argument("--output", help="Optional path to write the updated YAML file")
    workspace_close_parser.add_argument("--force", action="store_true", help="Overwrite the output file if it exists (use this for in-place updates)")
    workspace_close_parser.add_argument("--backup", action="store_true", help="Backup the live file before overwriting it in-place")

    workspace_touch_parser = workspace_subparsers.add_parser(
        "touch",
        help="Update an item's review.last_touched timestamp."
    )
    workspace_touch_parser.add_argument("--items", required=True, help="Path to your live work_items.yaml")
    workspace_touch_parser.add_argument("--id", required=True, help="ID of the work item to touch")
    workspace_touch_parser.add_argument("--note", help="Optional note to set as review_note")
    workspace_touch_parser.add_argument("--output", help="Optional path to write the updated YAML file")
    workspace_touch_parser.add_argument("--force", action="store_true", help="Overwrite the output file if it exists (use this for in-place updates)")
    workspace_touch_parser.add_argument("--backup", action="store_true", help="Backup the live file before overwriting it in-place")

    workspace_review_parser = workspace_subparsers.add_parser(
        "review",
        help="Show a Weekly Review of the workspace items."
    )
    workspace_review_parser.add_argument("--items", required=True, help="Path to your live work_items.yaml")
    workspace_review_parser.add_argument("--stale-after-days", type=int, default=14, help="Days of inactivity before an item is considered stale (default: 14)")

    workspace_export_eval_parser = workspace_subparsers.add_parser(
        "export-eval",
        help="Write a static evaluator-input packet for a selected workspace item.",
    )
    workspace_export_eval_parser.add_argument("--items", required=True, help="Path to the work items YAML or JSON file")
    workspace_export_eval_parser.add_argument("--id", required=True, help="ID of the work item to export")
    workspace_export_eval_parser.add_argument("--output", required=True, help="Path to write the evaluator packet JSON file")
    workspace_export_eval_parser.add_argument("--today", help="Optional today.yaml focus list file")
    workspace_export_eval_parser.add_argument("--case-id", help="Optional evaluator-facing case ID override")
    workspace_export_eval_parser.add_argument("--stale-after-days", type=int, default=14, help="Days of inactivity before an item is considered stale (default: 14)")
    workspace_export_eval_parser.add_argument("--force", action="store_true", help="Overwrite the output file if it exists")

    args = parser.parse_args()

    if args.command == "propose":
        title_str = " ".join(args.title)
        tc_propose(args.cr_id, title_str, args.changelog)
    elif args.command == "preflight":
        tc_preflight(args.cr_id, args.files)
    elif args.command == "handoff":
        tc_handoff(args.target == "latest", args.print)
    elif args.command == "audit":
        active_audit_modes = sum(
            bool(flag)
            for flag in (
                args.self_test,
                args.signed_smoke_test,
                args.signed_route_decision_smoke_test,
                args.privacy_invariants,
                args.verify_signatures,
            )
        )
        if active_audit_modes > 1:
            audit_parser.error(
                "--self-test, --signed-smoke-test, --signed-route-decision-smoke-test, --privacy-invariants, and --verify-signatures cannot be used together"
            )
        if args.strict and not args.verify_signatures:
            audit_parser.error("--strict requires --verify-signatures")
        if args.signed_smoke_test and not args.agent_id:
            audit_parser.error("--signed-smoke-test requires --agent-id")
        if args.signed_route_decision_smoke_test and not args.agent_id:
            _exit_missing_route_decision_smoke_agent_id(audit_parser)
        if args.privacy_invariants:
            tc_audit_privacy_invariants()
        elif args.verify_signatures:
            tc_audit_verify_signatures(kind=args.kind, strict=args.strict)
        elif args.signed_smoke_test:
            tc_audit_signed_smoke_test(args.agent_id)
        elif args.signed_route_decision_smoke_test:
            tc_audit_signed_route_decision_smoke_test(args.agent_id)
        elif args.self_test:
            tc_audit_self_test()
        else:
            tc_audit(args.kind, args.last)
    elif args.command == "status":
        tc_status()
    elif args.command == "run":
        tc_run(args)
    elif args.command == "run-plan":
        if args.run_plan_command == "confirm":
            tc_run_plan_confirm(args)
        else:
            run_plan_parser.error("run-plan requires a subcommand: confirm")
    elif args.command == "probe":
        tc_probe(args)
    elif args.command == "doctor":
        tc_doctor()
    elif args.command == "identity":
        if args.identity_command == "init":
            tc_identity_init(args.agent_id, args.role, args.capabilities)
        elif args.identity_command == "list":
            tc_identity_list()
        elif args.identity_command == "revoke":
            tc_identity_revoke(args.agent_id)
        elif args.identity_command == "check":
            tc_identity_check()
        elif args.identity_command in ("doctor", "rotation-status"):
            tc_identity_doctor(args.agent_id, for_capability=args.for_capability)
        elif args.identity_command == "rotate":
            tc_identity_rotate(args.agent_id, args.dry_run)
        else:
            identity_parser.error("identity requires a subcommand: init, list, revoke, check, doctor, rotation-status, or rotate")
    elif args.command == "model":
        if args.model_command == "check":
            tc_model_check(args.manifest)
        elif args.model_command == "warn":
            tc_model_warn(args.manifest, args.route)
        else:
            model_parser.error("model requires a subcommand: check or warn")
    elif args.command == "authority":
        if args.authority_command == "check":
            tc_authority_check(args.manifest)
        else:
            authority_parser.error("authority requires a subcommand: check")
    elif args.command == "demo":
        if not args.dry_run:
            demo_parser.error("the demo command currently requires --dry-run")
        tc_demo_dry_run(args.decision)
    elif args.command == "tokens":
        if args.tokens_command == "smoke-test":
            tc_tokens_smoke_test()
        else:
            tokens_parser.error("tokens requires a subcommand: smoke-test")
    elif args.command == "runtime-strategy":
        if args.runtime_strategy_command == "report":
            if args.force and not args.output:
                runtime_strategy_parser.error("--force requires --output")
            tc_runtime_strategy_report(
                as_json=args.json,
                output=args.output,
                force=args.force,
            )
        elif args.runtime_strategy_command == "recorded-report":
            if args.force and not args.output:
                runtime_strategy_parser.error("--force requires --output")
            tc_runtime_strategy_recorded_report(
                input_path=args.input,
                baseline=args.baseline,
                as_json=args.json,
                output=args.output,
                force=args.force,
            )
        else:
            runtime_strategy_parser.error(
                "runtime-strategy requires a subcommand: report or recorded-report"
            )
    elif args.command == "route-worker-ledger":
        if args.route_worker_ledger_command == "inspect":
            tc_route_worker_ledger_inspect(args.ledger)
        else:
            route_worker_ledger_parser.error(
                "route-worker-ledger requires a subcommand: inspect"
            )
    elif args.command == "task":
        if args.task_command == "show":
            tc_task_show(
                args.task_id,
                verify_signatures=args.verify_signatures,
                ledger_dir=args.ledger_dir,
            )
        else:
            task_parser.error("task requires a subcommand: show")
    elif args.command == "task-envelope":
        if args.task_envelope_command == "preview":
            tc_task_envelope_preview()
        elif args.task_envelope_command == "draft":
            tc_task_envelope_draft(args)
        elif args.task_envelope_command == "wizard":
            tc_task_envelope_wizard()
        elif args.task_envelope_command == "validate":
            tc_task_envelope_validate(args)
        else:
            task_envelope_parser.error("task-envelope requires a subcommand: preview, draft, wizard, or validate")
    elif args.command == "admission":
        if args.admission_command == "validate":
            tc_admission_validate(args)
        elif args.admission_command == "render":
            tc_admission_render(args)
        elif args.admission_command == "bundle":
            tc_admission_bundle(args)
        else:
            admission_parser.error("admission requires a subcommand: validate, render, or bundle")
    elif args.command == "eval":
        if args.eval_command == "export-smoke":
            tc_eval_export_smoke(args.output_dir)
        elif args.eval_command == "export-privacy-smoke":
            tc_eval_export_privacy_smoke(args.output_dir, args.case_id)
        elif args.eval_command == "export-forbidden-tool-smoke":
            tc_eval_export_forbidden_tool_smoke(args.output_dir, args.case_id)
        elif args.eval_command == "validate-fixtures":
            tc_eval_validate_fixtures(args.input)
        elif args.eval_command == "build-handoff":
            tc_eval_build_handoff(args.fixture, args.actuals_dir, args.out_dir)
        elif args.eval_command == "validate-handoff":
            tc_eval_validate_handoff(args.bundle)
        elif args.eval_command == "review":
            tc_eval_review(
                args.submission,
                args.context_packet,
                args.changed_path,
                args.output,
                args.print_json,
                args.fail_on_gate,
            )
        else:
            eval_parser.error("eval requires a subcommand: export-smoke, export-privacy-smoke, export-forbidden-tool-smoke, validate-fixtures, build-handoff, validate-handoff, or review")
    elif args.command == "context":
        if args.context_command == "plan":
            tc_context_plan(args.input, args.model)
        else:
            context_parser.error("context requires a subcommand: plan")
    elif args.command == "build-review":
        from triage_core.build_review_cli import run as run_build_review
        exit_code = run_build_review(args)
        if exit_code:
            sys.exit(exit_code)
    elif args.command == "packet":
        if args.packet_command == "render":
            tc_packet_render(args.task, args.model, args.include, args.output, args.force)
        else:
            packet_parser.error("packet requires a subcommand: render")
    elif args.command == "review":
        if args.review_command == "list":
            tc_review_list()
        else:
            review_parser.error("review requires a subcommand: list")
    elif args.command == "workspace":
        from triage_core.workspace_board import load_work_items, render_board, render_wbs
        if args.workspace_command == "board":
            try:
                items = load_work_items(args.items)
            except (FileNotFoundError, ValueError, ImportError) as e:
                print(f"Error: {e}")
                sys.exit(1)
            statuses = None
            if args.status:
                statuses = [s.strip() for s in args.status.split(",") if s.strip()]
            try:
                print(render_board(items, statuses=statuses))
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.workspace_command == "wbs":
            try:
                items = load_work_items(args.items)
            except (FileNotFoundError, ValueError, ImportError) as e:
                print(f"Error: {e}")
                sys.exit(1)
            print(render_wbs(items))
        elif args.workspace_command == "now":
            from triage_core.workspace_now import load_today_file, render_now
            try:
                items = load_work_items(args.items)
                today = load_today_file(args.today)
                print(render_now(items, today))
            except (FileNotFoundError, ValueError, ImportError) as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.workspace_command == "dashboard":
            from triage_core.workspace_now import load_today_file
            from triage_core.workspace_dashboard import render_html
            try:
                items = load_work_items(args.items)
                today = load_today_file(args.today)
                html_out = render_html(items, today, items_path=args.items, today_path=args.today)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(html_out)
                print(f"Dashboard generated at {args.output}")
            except (FileNotFoundError, ValueError, ImportError) as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.workspace_command == "handoff":
            from triage_core.workspace_handoff import generate_handoff
            try:
                items = load_work_items(args.items)
                
                # Resolve exactly one work item by ID
                target_item = None
                for it in items:
                    if it.id == args.id:
                        target_item = it
                        break
                
                if not target_item:
                    raise ValueError(f"Work item {args.id} not found in {args.items}")
                    
                output = generate_handoff(target_item, args.tool, args.format)
                print(output)
            except (FileNotFoundError, ValueError, ImportError) as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.workspace_command == "import-github":
            try:
                from triage_core.workspace_github_import import generate_preview_yaml
                generate_preview_yaml(args.repo, args.output, force=args.force)
                print(f"Generated GitHub issues preview at {args.output}")
            except Exception as e:
                print(f"Error importing GitHub issues: {e}")
                sys.exit(1)
        elif args.workspace_command == "promote":
            try:
                from triage_core.workspace_promote import promote_items
                promote_items(args.items, args.preview, args.output, args.id, force=args.force, backup=args.backup)
                print(f"Promoted {len(args.id)} item(s) to {args.output}")
            except Exception as e:
                print(f"Error promoting items: {e}")
                sys.exit(1)
        elif args.workspace_command == "review-import":
            try:
                from triage_core.workspace_review_import import render_import_review
                print(render_import_review(args.preview, label=args.label, updated_since=args.updated_since, limit=args.limit))
            except Exception as e:
                print(f"Error reviewing imports: {e}")
                sys.exit(1)
        elif args.workspace_command == "close":
            try:
                from triage_core.workspace_close import generate_closing_packet, close_work_item
                items = load_work_items(args.items)
                target_item = None
                for it in items:
                    if it.id == args.id:
                        target_item = it
                        break
                
                if not target_item:
                    raise ValueError(f"Work item {args.id} not found in {args.items}")
                    
                packet = generate_closing_packet(target_item, args.commit, args.tests, args.summary)
                print(packet)
                
                if args.output or args.force:
                    output_path = args.output if args.output else args.items
                    close_work_item(args.items, args.id, output_path, force=args.force, backup=args.backup)
                    print(f"\n[System] Work item {args.id} marked as done in {output_path}")
            except Exception as e:
                print(f"Error closing item: {e}")
                sys.exit(1)
        elif args.workspace_command == "touch":
            try:
                from triage_core.workspace_touch import touch_work_item
                output_path = args.output if args.output else args.items
                touch_work_item(args.items, args.id, output_path, note=args.note, force=args.force, backup=args.backup)
                print(f"[System] Work item {args.id} touched in {output_path}")
            except Exception as e:
                print(f"Error touching item: {e}")
                sys.exit(1)
        elif args.workspace_command == "review":
            try:
                from triage_core.workspace_review import render_weekly_review
                items = load_work_items(args.items)
                print(render_weekly_review(items, stale_after_days=args.stale_after_days))
            except Exception as e:
                print(f"Error generating review: {e}")
                sys.exit(1)
        elif args.workspace_command == "export-eval":
            try:
                tc_workspace_export_eval(
                    args.items,
                    args.id,
                    args.output,
                    today_path=args.today,
                    case_id=args.case_id,
                    stale_after_days=args.stale_after_days,
                    force=args.force,
                )
            except Exception as e:
                print(f"Error exporting evaluator packet: {e}")
                sys.exit(1)
        else:
            workspace_parser.error("workspace requires a subcommand: board, wbs, now, dashboard, handoff, import-github, promote, review-import, close, touch, review, or export-eval")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
