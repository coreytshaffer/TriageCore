import os
import glob
import time
from dotenv import load_dotenv
from triage_core.client import TriageClient
from triage_core.validators import PythonSyntaxValidator

load_dotenv()

BACKEND_TYPE = os.getenv("TRIAGE_BACKEND_TYPE", "ollama")
MODEL = os.getenv("TRIAGE_MODEL", "qwen2.5-coder:7b")
BASE_URL = os.getenv("TRIAGE_BASE_URL")

def run_bulk_audit(target_dir: str):
    client = TriageClient(
        backend_type=BACKEND_TYPE,
        model=MODEL,
        base_url=BASE_URL,
        timeout_seconds=60,
    )
    
    # Find all Python files recursively
    search_pattern = os.path.join(target_dir, "**", "*.py")
    py_files = glob.glob(search_pattern, recursive=True)
    
    print(f"--- Starting Bulk Audit on: {target_dir} ---")
    print(f"Found {len(py_files)} Python files to audit.\n")
    
    stats = {
        "success_local": 0,
        "handoff_required": 0,
        "failed": 0,
        "syntax_errors_prevented": 0
    }
    
    prompt = """You are a rigid code execution worker. Review the provided Python code for credibility, stability, and security vulnerabilities (e.g., SQL injection, unhandled exceptions, resource leaks, hardcoded secrets, XSS). Apply any necessary fixes. Output ONLY the complete, corrected Python file. No markdown blocks, no conversational filler."""

    for file in py_files:
        # Skip virtual environments and hidden dirs
        if "venv" in file or "__pycache__" in file or ".git" in file:
            continue
            
        print(f"Auditing: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            raw_data = f.read()
            
        result = client.run_task(
            prompt=prompt,
            data=raw_data,
            validator=PythonSyntaxValidator.validate
        )
        
        if result.get("status") == "success":
            source = result.get('source')
            print(f"  [SUCCESS] Succeeded via: {source} (Time: {result.get('elapsed_seconds'):.2f}s)")
            if source == "local":
                stats["success_local"] += 1
            else:
                stats["handoff_required"] += 1
                
            # We are writing the hardened file back
            output = result.get('output')
            with open(file, 'w', encoding='utf-8') as f:
                f.write(output)
        else:
            print(f"  [x] Handoff required: {result.get('reason', result.get('error'))}")
            stats["failed"] += 1
            
        time.sleep(1) # Small delay to not overwhelm models
        
    print("\n--- Audit Summary ---")
    print(f"Files Fixed via Local MoE: {stats['success_local']}")
    print(f"Files Requiring Handoff:   {stats['handoff_required']}")
    print(f"Failed to Patch:           {stats['failed']}")

if __name__ == "__main__":
    # We will target pitlens-table-games first as a constrained test
    target_directory = "../pitlens-table-games"
    run_bulk_audit(target_directory)
