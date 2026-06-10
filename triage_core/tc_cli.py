import argparse
import os
import sys
import glob
import subprocess
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

    args = parser.parse_args()

    if args.command == "preflight":
        tc_preflight(args.cr_id, args.files)
    elif args.command == "handoff":
        tc_handoff(args.target == "latest", args.print)
    elif args.command == "status":
        print("TriageCore Operator Workflow active.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
