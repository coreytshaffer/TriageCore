import os
from dotenv import load_dotenv
from triage_core.client import TriageClient
from triage_core.validators import PythonSyntaxValidator

load_dotenv()

LOCAL_URL = os.getenv("LOCAL_URL", "http://127.0.0.1:1234")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gemini/gemini-1.5-pro")

def run_escalation_demo():
    print("--- TriageCore Escalation Demonstration ---")
    print("Initializing client with a forced 2-second local timeout to guarantee escalation...")
    
    # We set a 2-second timeout which is physically impossible for the local model to beat.
    client = TriageClient(local_url=LOCAL_URL, cloud_model=CLOUD_MODEL, timeout_seconds=2)
    
    # Let's use a simple piece of broken code as our payload
    broken_code = """
def authenticate_user(username, password):
    if username == "admin" and password == "password123": # VULNERABILITY
        return True
    return False
    """
    
    prompt = """You are a rigid code execution worker. Review the provided Python code for security vulnerabilities. Apply any necessary fixes. Output ONLY the complete, corrected Python file."""

    print("\nDispatching task to local worker (Nemotron)...")
    
    result = client.run_task(
        prompt=prompt,
        data=broken_code,
        validator=PythonSyntaxValidator.validate
    )
    
    print("\n--- Final Execution Result ---")
    if result.get("status") == "success":
        print(f"Status: SUCCESS")
        print(f"Executed via: {result.get('source').upper()}")
        print(f"Time Elapsed: {result.get('elapsed_seconds'):.2f}s")
        print("\nPatched Output:")
        print(result.get('output'))
    else:
        print(f"Status: FAILED")
        print(f"Error: {result.get('error', result.get('escalation_reason'))}")

if __name__ == "__main__":
    run_escalation_demo()
