from dataclasses import dataclass, field
import json
from typing import Optional, Dict, Any

@dataclass(frozen=True)
class RouteDecisionAudit:
    task_id: Optional[str]
    privacy_level: str
    privacy_scan_passed: bool
    is_local_only: bool
    recommended_route: Optional[str]
    selected_backend: Optional[str]
    decision: str  # "allowed" or "blocked"
    reason_code: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "privacy_level": self.privacy_level,
            "privacy_scan_passed": self.privacy_scan_passed,
            "is_local_only": self.is_local_only,
            "recommended_route": self.recommended_route,
            "selected_backend": self.selected_backend,
            "decision": self.decision,
            "reason_code": self.reason_code,
        }
