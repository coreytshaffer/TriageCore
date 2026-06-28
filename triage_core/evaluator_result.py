import json
from dataclasses import dataclass, field
from typing import List, Optional

class EvaluatorResultValidationError(ValueError):
    """Raised when an evaluator result JSON violates safety or schema constraints."""
    pass

@dataclass
class EvaluatorResult:
    item_id: str
    packet_id: str
    decision: str
    approval_status: str
    target_invocation: str
    score: str
    reasons: List[str]
    warnings: List[str] = field(default_factory=list)
    generated_at: Optional[str] = None
    result_type: str = "workspace_packet_evaluation_result"

def validate_evaluator_result(data: dict) -> EvaluatorResult:
    """
    Validates the raw parsed JSON dict of an evaluator result and ensures
    it complies with the observation-only safety boundaries.
    """
    required_fields = [
        "item_id", "packet_id", "decision", "approval_status",
        "target_invocation", "score", "reasons"
    ]
    
    for field_name in required_fields:
        if field_name not in data:
            raise EvaluatorResultValidationError(f"Missing required field: {field_name}")
            
    # Observation-only boundary enforcement
    if data["approval_status"] != "not_approval":
        raise EvaluatorResultValidationError(
            "Invalid evaluator result: evaluator output appears to claim approval authority. (approval_status != not_approval)"
        )
        
    if data["target_invocation"] != "not_invoked":
        raise EvaluatorResultValidationError(
            "Invalid evaluator result: evaluator output appears to claim execution capability. (target_invocation != not_invoked)"
        )
        
    unsafe_decisions = {"approve", "approved", "execute", "invoke"}
    if data["decision"].lower() in unsafe_decisions:
        raise EvaluatorResultValidationError(
            f"Invalid evaluator result: evaluator output appears to claim approval authority. (decision='{data['decision']}')"
        )
        
    reasons = data["reasons"]
    if not isinstance(reasons, list):
        raise EvaluatorResultValidationError("Field 'reasons' must be a list of strings.")
        
    warnings = data.get("warnings", [])
    if not isinstance(warnings, list):
        raise EvaluatorResultValidationError("Field 'warnings' must be a list of strings.")

    return EvaluatorResult(
        item_id=str(data["item_id"]),
        packet_id=str(data["packet_id"]),
        decision=str(data["decision"]),
        approval_status=str(data["approval_status"]),
        target_invocation=str(data["target_invocation"]),
        score=str(data["score"]),
        reasons=[str(r) for r in reasons],
        warnings=[str(w) for w in warnings],
        generated_at=data.get("generated_at"),
        result_type=data.get("result_type", "workspace_packet_evaluation_result")
    )

def load_evaluator_result(path: str) -> EvaluatorResult:
    """
    Loads an evaluator result from a JSON file and returns a validated EvaluatorResult.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise EvaluatorResultValidationError(f"Malformed JSON: {str(e)}")
    except Exception as e:
        raise EvaluatorResultValidationError(f"Failed to read file: {str(e)}")
        
    if not isinstance(data, dict):
        raise EvaluatorResultValidationError("JSON root must be an object.")
        
    return validate_evaluator_result(data)
