import os
import glob
import time
from dotenv import load_dotenv
from triage_core.client import TriageClient

load_dotenv()

BACKEND_TYPE = os.getenv("TRIAGE_BACKEND_TYPE", "ollama")
MODEL = os.getenv("TRIAGE_MODEL", "qwen2.5-coder:7b")
BASE_URL = os.getenv("TRIAGE_BASE_URL")

def run_clearlake_audit(target_dir: str):
    # We aggressively drop the timeout to 30s because we expect the user is running Qwen2.5-Coder!
    client = TriageClient(
        backend_type=BACKEND_TYPE,
        model=MODEL,
        base_url=BASE_URL,
        timeout_seconds=30,
    )
    
    # Clear Lake Watch is built in JS and PowerShell, not Python!
    js_files = glob.glob(os.path.join(target_dir, "**", "*.js"), recursive=True)
    ps_files = glob.glob(os.path.join(target_dir, "**", "*.ps1"), recursive=True)
    target_files = js_files + ps_files
    
    print(f"--- Starting High-Speed Qwen2.5 Audit on: {target_dir} ---")
    print(f"Found {len(target_files)} script files to audit (JS/PS1).\n")
    
    stats = {
        "success_local": 0,
        "handoff_required": 0,
        "failed": 0
    }
    
    prompt = """You are a high-speed Qwen2.5 code execution worker. Review the provided JavaScript or PowerShell code for frontend bugs, logic errors, or performance issues. Apply any necessary fixes. Output ONLY the complete, corrected raw file. No markdown blocks, no conversational filler."""

    for file in target_files:
        if "node_modules" in file or ".git" in file:
            continue
            
        print(f"Auditing: {file}")
        with open(file, 'r', encoding='utf-8') as f:
            raw_data = f.read()
            
        # We pass None to validator since TriageCore's default validator is for Python only
        result = client.run_task(
            prompt=prompt,
            data=raw_data,
            validator=None 
        )
        
        if result.get("status") == "success":
            source = result.get('source')
            print(f"  [SUCCESS] Patched via: {source} (Time: {result.get('elapsed_seconds'):.2f}s)")
            if source == "local":
                stats["success_local"] += 1
            else:
                stats["handoff_required"] += 1
                
            output = result.get('output')
            # Dry run for this demonstration to protect the flagship project codebase
            # with open(file, 'w', encoding='utf-8') as f:
            #     f.write(output)
        else:
            print(f"  [HANDOFF]: {result.get('reason', result.get('error'))}")
            stats["failed"] += 1
            
        time.sleep(1) # Let the local GPU breathe
        
    print("\n--- Optimized Audit Summary ---")
    print(f"Files Fixed via Local Edge: {stats['success_local']}")
    print(f"Files Requiring Handoff:    {stats['handoff_required']}")
    print(f"Failed to Patch:            {stats['failed']}")

if __name__ == "__main__":
    target_directory = "../clear-lake-watch"
    run_clearlake_audit(target_directory)
