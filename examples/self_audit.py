import os
from dotenv import load_dotenv
from triage_core.client import TriageClient
from triage_core.validators import PythonSyntaxValidator

load_dotenv()

BACKEND_TYPE = os.getenv("TRIAGE_BACKEND_TYPE", "ollama")
MODEL = os.getenv("TRIAGE_MODEL", "qwen2.5-coder:7b")
BASE_URL = os.getenv("TRIAGE_BASE_URL")

def audit_file(client: TriageClient, filepath: str, prompt: str):
    print(f"\n--- Auditing {filepath} ---")
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        raw_data = f.read()

    print("Dispatching task to TriageCore...")
    result = client.run_task(
        prompt=prompt,
        data=raw_data,
        validator=PythonSyntaxValidator.validate
    )

    if result.get("status") == "success":
        output = result.get("output")
        print(f"Task succeeded via: {result.get('source')} (Time: {result.get('elapsed_seconds'):.2f}s)")
        
        # Clean markdown wrappers if returned
        if output.startswith("```python"):
            output = output.split("```python", 1)[1]
        if output.endswith("```"):
            output = output.rsplit("```", 1)[0]
        output = output.strip() + "\n"
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Successfully hardened and updated {filepath}")
    else:
        print(f"Task failed: {result.get('reason', result.get('error'))}")

def main():
    client = TriageClient(
        backend_type=BACKEND_TYPE,
        model=MODEL,
        base_url=BASE_URL,
        timeout_seconds=60,
    )
    
    # 1. Hardening engine.py
    engine_prompt = """You are a rigid code execution worker. Review the provided python code for stability and security vulnerabilities.
Specifically:
1. Fix JSON parsing to safely use .get() and avoid unhandled KeyError/IndexError if the response schema is unexpected.
2. Confirm local backend calls use an explicit timeout so the worker cannot hang indefinitely.
Apply the fixes. Output ONLY the complete, corrected python file. No markdown blocks, no conversational filler."""
    
    audit_file(client, "triage_core/engine.py", engine_prompt)

    # 2. Hardening validators.py
    validators_prompt = """You are a rigid code execution worker. Review the provided python code for stability and security vulnerabilities.
Specifically:
1. Improve the markdown stripping logic to use a robust Regex (e.g. `re.sub(r'^```python\\s*', '', code)`) instead of naive `.startswith()`.
2. Ensure the temporary file descriptor `fd` is completely closed using `os.close(fd)` *before* py_compile is called to prevent Windows PermissionErrors.
Apply the fixes. Output ONLY the complete, corrected python file. No markdown blocks, no conversational filler."""
    
    audit_file(client, "triage_core/validators.py", validators_prompt)

if __name__ == "__main__":
    main()
