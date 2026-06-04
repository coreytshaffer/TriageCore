import uuid
from typing import List, Dict, Any, Optional
from .work_orders import TaskBoard, WorkOrder
from .worker_registry import WorkerRegistry
from .union_rep import UnionRep
from .config import default_config

class ProjectManager:
    def __init__(self):
        self.board = TaskBoard()
        self.registry = WorkerRegistry()
        self.budgets = default_config.get_global("budgets", {}, {})
        self.union_rep = UnionRep(budgets=self.budgets)
        
    def dispatch_task(self, prompt: str, target_files: List[str], required_roles: List[str]) -> Dict[str, Any]:
        """
        Takes a raw prompt and targets, splits it into WorkOrders, dispatches to workers, and evaluates.
        """
        task_id = str(uuid.uuid4())
        
        # 1. Create work orders
        for role in required_roles:
            order = WorkOrder(
                task_id=task_id,
                assigned_role=role,
                input_artifacts=target_files + [prompt],
                output_required="Draft code or validate the previous steps.",
                max_tokens=self.budgets.get("max_tokens", 800)
            )
            self.board.add_order(order)
            
        # 2. Execute sequentially
        completed = []
        for order in self.board.get_pending():
            worker = self.registry.get_worker(order.assigned_role)
            if not worker:
                self.board.update_status(order.work_order_id, "failed", {"error": f"Worker role {order.assigned_role} not found"})
                continue
                
            result = worker.process(order)
            self.board.update_status(order.work_order_id, "completed", result)
            completed.append(self.board.orders[order.work_order_id])
            
        # 3. Audit results using UnionRep
        evaluation = self.union_rep.evaluate(prompt, target_files, completed)
        
        # 4. Generate escalation packet if needed
        packet_path = None
        if evaluation.get("local_result_status") == "insufficient":
            import os
            packet = self.union_rep.generate_escalation_packet(evaluation, prompt, target_files)
            os.makedirs(".agent_tasks", exist_ok=True)
            packet_path = f".agent_tasks/escalation_{task_id[:8]}.md"
            with open(packet_path, "w", encoding="utf-8") as f:
                f.write(packet.to_markdown())
                
        return {
            "task_id": task_id,
            "evaluation": evaluation,
            "escalation_packet": packet_path,
            "work_orders": [o.work_order_id for o in completed]
        }
