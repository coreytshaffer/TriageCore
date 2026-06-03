import os
from dotenv import load_dotenv
from triage_core.client import TriageClient

load_dotenv()

LOCAL_URL = os.getenv("LOCAL_URL", "http://127.0.0.1:1234")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gemini/gemini-1.5-pro")

def main():
    client = TriageClient(local_url=LOCAL_URL, cloud_model=CLOUD_MODEL, timeout_seconds=60)
    
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
    print(f"Elapsed Time: {result.get('elapsed_seconds'):.2f}s")
    print("--- OUTPUT ---")
    print(result.get('output'))

if __name__ == "__main__":
    main()
