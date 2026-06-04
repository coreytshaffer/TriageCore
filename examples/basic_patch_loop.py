import os
from dotenv import load_dotenv
from triage_core.client import TriageClient
from triage_core.validators import PythonSyntaxValidator

load_dotenv()

# Example configuration
BACKEND_TYPE = os.getenv("TRIAGE_BACKEND_TYPE", "ollama")
MODEL = os.getenv("TRIAGE_MODEL", "qwen2.5-coder:7b")
BASE_URL = os.getenv("TRIAGE_BASE_URL")

def main():
    client = TriageClient(
        backend_type=BACKEND_TYPE,
        model=MODEL,
        base_url=BASE_URL,
        timeout_seconds=45,
    )
    
    prompt = "Output ONLY a python function named 'add' that takes two ints and returns an int. Raw python only."
    data = "Current codebase has no math functions."
    
    print("Dispatching task...")
    result = client.run_task(
        prompt=prompt, 
        data=data, 
        validator=PythonSyntaxValidator.validate
    )
    
    print(f"\nResult Source: {result.get('source')}")
    if result.get("status") == "success":
        print(f"Elapsed Time: {result.get('elapsed_seconds'):.2f}s")
        print("--- OUTPUT ---")
        print(result.get('output'))
    else:
        print(f"Reason: {result.get('reason', result.get('error'))}")

if __name__ == "__main__":
    main()
