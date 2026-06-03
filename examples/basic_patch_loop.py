import os
from dotenv import load_dotenv
from triage_core.client import TriageClient
from triage_core.validators import PythonSyntaxValidator

load_dotenv()

# Example configuration
LOCAL_URL = os.getenv("LOCAL_URL", "http://127.0.0.1:1234")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gemini/gemini-1.5-pro")

def main():
    client = TriageClient(local_url=LOCAL_URL, cloud_model=CLOUD_MODEL, timeout_seconds=45)
    
    prompt = "Output ONLY a python function named 'add' that takes two ints and returns an int. Raw python only."
    data = "Current codebase has no math functions."
    
    print("Dispatching task...")
    result = client.run_task(
        prompt=prompt, 
        data=data, 
        validator=PythonSyntaxValidator.validate
    )
    
    print(f"\nResult Source: {result.get('source')}")
    print(f"Elapsed Time: {result.get('elapsed_seconds'):.2f}s")
    print("--- OUTPUT ---")
    print(result.get('output'))

if __name__ == "__main__":
    main()
