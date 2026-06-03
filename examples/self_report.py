import os
import glob
from dotenv import load_dotenv
from triage_core.client import TriageClient

load_dotenv()

LOCAL_URL = os.getenv("LOCAL_URL", "http://127.0.0.1:1234")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gemini/gemini-1.5-pro")

def generate_self_report():
    client = TriageClient(local_url=LOCAL_URL, cloud_model=CLOUD_MODEL, timeout_seconds=120)
    
    # We grab one of the patched files as context to spark the narrative
    sample_file = "../pitlens-table-games/src/pitlens/database.py"
    if os.path.exists(sample_file):
        with open(sample_file, 'r', encoding='utf-8') as f:
            code_context = f.read()
    else:
        code_context = "No code context available."

    print("--- Initiating Offline Model Self-Report ---")
    
    narrative_prompt = """You are a brilliant offline AI engineer. You have just completed a massive security and stability pass over a complex Python codebase (a sample of your work is provided in the data). 
    
Your context window is filling up, and you need to generate a handoff report for your future self. 

Please write a narrative self-reflection detailing:
1. What vulnerabilities or code smells you suspect you encountered during the pass.
2. How you perceived the difficulty of the work.
3. Any lingering concerns or recommendations you want to leave for your future self to pick up on the next pass.

Write this in a conversational, scholarly, yet narrative tone. Do not write any code."""

    print("Asking the local model for a narrative self-reflection...")
    
    result = client.run_task(
        prompt=narrative_prompt,
        data=code_context,
        validator=None  # No syntax validation needed for a prose report
    )
    
    if result.get("status") == "success":
        print("\n=== NARRATIVE HANDOFF REPORT ===")
        print(f"Generated via: {result.get('source')} in {result.get('elapsed_seconds'):.2f}s\n")
        print(result.get('output'))
        print("===================================")
    else:
        print(f"\n[x] Failed to generate report: {result.get('error', result.get('escalation_reason'))}")

if __name__ == "__main__":
    generate_self_report()
