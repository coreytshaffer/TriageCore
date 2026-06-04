import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
import time

@dataclass
class WorkOrder:
    task_id: str
    assigned_role: str
    input_artifacts: List[str]
    output_required: str
    max_tokens: int = 500
    max_seconds: int = 60
    status: str = "pending"
    work_order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    result: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    # Chunk tracking for large-file dispatch
    chunk_start: int = 0          # First line index (0-based, inclusive)
    chunk_end: Optional[int] = None  # Last line index (exclusive); None = end of file

    
class TaskBoard:
    def __init__(self):
        self.orders: Dict[str, WorkOrder] = {}
        
    def add_order(self, order: WorkOrder):
        self.orders[order.work_order_id] = order
        
    def get_pending(self) -> List[WorkOrder]:
        return [o for o in self.orders.values() if o.status == "pending"]
        
    def update_status(self, order_id: str, status: str, result: Optional[Dict] = None):
        if order_id in self.orders:
            self.orders[order_id].status = status
            if result:
                self.orders[order_id].result = result
