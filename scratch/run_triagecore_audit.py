import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from triage_core.orchestration import ProjectManager
import json

pm = ProjectManager()

print("Launching TriageCore Worker Council on triage_core/ui/app.py...")
try:
    result = pm.dispatch_task(
        prompt="Fix the PEP-8 formatting errors in triage_core/ui/app.py including expected blank lines, continuation line indentations, multiple colons, and unused imports.",
        target_files=["triage_core/ui/app.py"],
        required_roles=["repo_mapper", "code_repair", "validator"],
        stream_callback=lambda chunk: sys.stdout.write(chunk)
    )

    print("\n\n--- EXECUTION COMPLETE ---")
    print("Task ID:", result.get("task_id"))
    print("Evaluation Status:", result.get("evaluation", {}).get("local_result_status"))
    print("Reason:", result.get("evaluation", {}).get("reason"))
    print("Recommended Escalation:", result.get("evaluation", {}).get("recommended_escalation"))
    print("Escalation Packet Path:", result.get("escalation_packet"))
except Exception as e:
    print(f"\nExecution failed with error: {e}")
