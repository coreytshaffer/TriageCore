import argparse
import os
import sys
import glob
import subprocess
import json
from typing import List

from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.compression import compress_context
from triage_core.config import default_config
from triage_core.backends import LocalBackend

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

def tc_audit(kind: str, last: int):
    ledger_path = os.path.join(".triagecore", "ledger.jsonl")
    if not os.path.exists(ledger_path):
        print(f"Error: {ledger_path} not found.")
        sys.exit(1)
        
    records = []
    try:
        with open(ledger_path, "r", encoding="utf-8") as f:
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
            print(f"  Decision: {payload.get('decision')} | Reason: {payload.get('reason_code')}")
            print(f"  Privacy: {payload.get('privacy_level')} (Scan Passed: {payload.get('privacy_scan_passed')})")
            print(f"  Local Only: {payload.get('is_local_only')} | Route: {payload.get('recommended_route')} | Backend: {payload.get('selected_backend')}")
        else:
            # General safe metadata fallback
            for k, v in payload.items():
                if k in ["prompt", "data", "content", "raw_data", "raw_prompt"]:
                    continue # Do not log raw prompt, raw data, or file contents
                if isinstance(v, str) and len(v) > 200:
                    v = v[:200] + "..."
                print(f"  {k}: {v}")
        print("-" * 60)

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

def tc_doctor():
    print("TriageCore Doctor")
    print("-" * 30)
    
    cwd = os.getcwd()
    print(f"CWD: {cwd}")
    
    repo_root = ""
    try:
        repo_root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL).decode('utf-8').strip()
        print(f"Git Repo Root: {repo_root}")
    except Exception:
        print("Git Repo Root: unavailable")
        
    print(f"Python Executable: {sys.executable}")
    print(f"Python Version: {sys.version.split()[0]}")
    
    try:
        import triage_core
        print(f"triage_core path: {triage_core.__file__}")
    except ImportError:
        print("triage_core path: unavailable")
        
    try:
        cmd = "where" if sys.platform == "win32" else "which"
        tc_path = subprocess.check_output([cmd, "tc"], stderr=subprocess.DEVNULL).decode('utf-8').strip().split('\n')[0]
        if tc_path:
            print(f"tc path: {tc_path}")
        else:
            print("tc path: unavailable")
    except Exception:
        print("tc path: unavailable")
        
    try:
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL).decode('utf-8').strip()
        print(f"Git Branch: {branch}")
    except Exception:
        print("Git Branch: unavailable")
        
    try:
        status_out = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.DEVNULL).decode('utf-8')
        status = "dirty" if status_out.strip() else "clean"
        print(f"Git Status: {status}")
    except Exception:
        print("Git Status: unavailable")
        
    base_dir = repo_root if repo_root else cwd
    
    ledger_path = os.path.join(base_dir, ".triagecore", "ledger.jsonl")
    if os.path.exists(ledger_path):
        print(f"Ledger Path: {ledger_path}")
    else:
        print("Ledger Path: unavailable")
        
    handoff_path = os.path.join(base_dir, ".triagecore", "handoffs", "latest.md")
    if os.path.exists(handoff_path):
        print(f"Handoff Latest: {handoff_path}")
    else:
        print("Handoff Latest: unavailable")
        
    pyproject_path = os.path.join(base_dir, "pyproject.toml")
    if os.path.exists(pyproject_path):
        print(f"pytest config: {pyproject_path}")
        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read()
                if 'norecursedirs = ["scratch"]' in content or "norecursedirs = ['scratch']" in content:
                    print("Scratch Excluded: yes")
                else:
                    print("Scratch Excluded: no")
        except Exception:
            print("Scratch Excluded: unavailable")
    else:
        print("pytest config: unavailable")
        print("Scratch Excluded: unavailable")

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

    # audit
    audit_parser = subparsers.add_parser("audit", help="Inspect ledger audit events safely")
    audit_parser.add_argument("--kind", type=str, default="route_audit", help="The event_type to filter by (default: route_audit)")
    audit_parser.add_argument("--last", type=int, default=10, help="Number of recent records to display (default: 10)")

    # propose
    propose_parser = subparsers.add_parser("propose", help="Scaffold a new Change Request")
    propose_parser.add_argument("cr_id", type=str, help="The CR ID (e.g., CR-012)")
    propose_parser.add_argument("title", type=str, nargs="+", help="The title of the change request")
    propose_parser.add_argument("--changelog", action="store_true", help="Automatically add to changelog")

    # doctor
    subparsers.add_parser("doctor", help="Print a TriageCore environment report")

    args = parser.parse_args()

    if args.command == "propose":
        title_str = " ".join(args.title)
        tc_propose(args.cr_id, title_str, args.changelog)
    elif args.command == "preflight":
        tc_preflight(args.cr_id, args.files)
    elif args.command == "handoff":
        tc_handoff(args.target == "latest", args.print)
    elif args.command == "audit":
        tc_audit(args.kind, args.last)
    elif args.command == "status":
        print("TriageCore Operator Workflow active.")
    elif args.command == "doctor":
        tc_doctor()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
