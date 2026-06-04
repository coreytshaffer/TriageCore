import os
from dotenv import load_dotenv
from triage_core.client import TriageClient

load_dotenv()

BACKEND_TYPE = os.getenv("TRIAGE_BACKEND_TYPE", "ollama")
MODEL = os.getenv("TRIAGE_MODEL", "qwen2.5-coder:7b")
BASE_URL = os.getenv("TRIAGE_BASE_URL")

def main():
    client = TriageClient(
        backend_type=BACKEND_TYPE,
        model=MODEL,
        base_url=BASE_URL,
        timeout_seconds=60,
    )
    
    prompt = """You are a rigid parsing worker. Output ONLY valid markdown.
Format the raw log data into a summary list of errors."""
    
    data = """
    [2026-06-03 10:00:01] INFO - Service started.
    [2026-06-03 10:00:15] WARN - Latency spike detected.
    [2026-06-03 10:01:44] ERROR - Connection timeout on database sync.
    [2026-06-03 10:05:10] INFO - Sync complete.
    """
    
    print("Dispatching bulk parsing task...")
    result = client.run_task(prompt=prompt, data=data)
    
    print(f"\nResult Source: {result.get('source')}")
    if result.get("status") == "success":
        print(f"Elapsed Time: {result.get('elapsed_seconds'):.2f}s")
        print("--- OUTPUT ---")
        print(result.get('output'))
    else:
        print(f"Reason: {result.get('reason', result.get('error'))}")

if __name__ == "__main__":
    main()
