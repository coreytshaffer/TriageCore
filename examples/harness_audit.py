import os
import json
from dotenv import load_dotenv
from triage_core.orchestration import ProjectManager

load_dotenv()

def audit_file_via_harness(manager: ProjectManager, filepath: str, requirement: str):
    print(f"\n--- Harness Auditing {filepath} ---")
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        raw_data = f.read()

    print("Dispatching multi-agent task to ProjectManager...")
    
    # We will dispatch a task through the RepoMapper -> CodeRepair -> Validator pipeline.
    # We pass the raw code as the input prompt, or we can just send the file path.
    # Since ProjectManager.dispatch_task takes (prompt, target_files, required_roles), 
    # we'll frame the requirement as the prompt.
    
    result = manager.dispatch_task(
        prompt=requirement,
        target_files=[filepath],
        required_roles=["repo_mapper", "code_repair", "validator"]
    )
    
    evaluation = result.get("evaluation", {})
    if evaluation.get("local_result_status") == "accepted":
        print("Harness pipeline accepted the result!")
        # Find the repaired code from the work orders
        # work_orders is a list of work order IDs that completed
        # The completed orders themselves are not returned directly in the dict, 
        # but we can fetch them from manager.board
        
        repaired_code = None
        for order_id in result.get("work_orders", []):
            order = manager.board.orders.get(order_id)
            if order and order.assigned_role == "code_repair":
                # order.result contains the JSON from CodeRepairWorker
                order_result = order.result or {}
                repaired_code = order_result.get("repaired_code")
                break
                
        if repaired_code:
            # Write back to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(repaired_code)
            print(f"Successfully hardened and updated {filepath}")
        else:
            print("Error: CodeRepairWorker did not output 'repaired_code'.")
            
    else:
        print(f"Harness rejected the task. Escalation needed.")
        if result.get("escalation_packet"):
            print(f"Packet generated: {result['escalation_packet']}")


def main():
    manager = ProjectManager()
    
    # Override budgets if needed for larger files (repair can be heavy)
    manager.budgets["max_tokens"] = 2000
    
    # 1. Hardening orchestration.py
    orchestration_req = """Review orchestration.py for stability and bugs.
Specifically:
1. Ensure the JSON payloads handled in the evaluation step gracefully handle missing fields (use .get() with defaults).
2. Ensure file writes for escalation packets wrap in a try-except block to catch OSError.
Return ONLY the complete, corrected python file."""
    
    audit_file_via_harness(manager, "triage_core/orchestration.py", orchestration_req)

    # 2. Hardening task_ledger.py
    ledger_req = """Review task_ledger.py for stability and bugs.
Specifically:
1. Ensure all json.loads() calls are wrapped in a try-except JSONDecodeError block.
2. In get_all_tasks, if the file is empty, return an empty list safely without crashing.
Return ONLY the complete, corrected python file."""
    
    audit_file_via_harness(manager, "triage_core/task_ledger.py", ledger_req)


if __name__ == "__main__":
    main()
