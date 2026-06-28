import os
import glob
from dataclasses import dataclass
from typing import List, Optional
from .evaluator_result import EvaluatorResult, load_evaluator_result, EvaluatorResultValidationError

@dataclass(frozen=True)
class EvaluatorResultSummary:
    filepath: str
    status_label: str
    item_id: str
    decision: str
    generated_at: str
    warnings_count: int
    is_valid: bool
    original_result: Optional[EvaluatorResult] = None
    error_message: Optional[str] = None

def _summarize_file(filepath: str) -> EvaluatorResultSummary:
    try:
        res = load_evaluator_result(filepath)
        d_lower = res.decision.lower()
        if d_lower in ["pass", "observe"]:
            status = "PASS"
        elif d_lower == "fail":
            status = "FAIL"
        elif d_lower == "ambiguous":
            status = "AMBIG"
        else:
            status = "NOT EVALUATED"
            
        return EvaluatorResultSummary(
            filepath=filepath,
            status_label=status,
            item_id=res.item_id,
            decision=res.decision,
            generated_at=res.generated_at or "",
            warnings_count=len(res.warnings),
            is_valid=True,
            original_result=res,
            error_message=None
        )
    except EvaluatorResultValidationError as e:
        msg = str(e)
        if "Malformed JSON" in msg or "Failed to read file" in msg or "JSON root must be an object" in msg:
            status = "MALFORMED"
        elif "evaluator output appears to claim approval authority" in msg or "claims execution capability" in msg:
            status = "UNSAFE"
        else:
            status = "INVALID"
            
        return EvaluatorResultSummary(
            filepath=filepath,
            status_label=status,
            item_id="—",
            decision="invalid",
            generated_at="",
            warnings_count=0,
            is_valid=False,
            original_result=None,
            error_message=msg
        )
    except Exception as e:
        return EvaluatorResultSummary(
            filepath=filepath,
            status_label="MALFORMED",
            item_id="—",
            decision="invalid",
            generated_at="",
            warnings_count=0,
            is_valid=False,
            original_result=None,
            error_message=str(e)
        )

def sort_results(results: List[EvaluatorResultSummary]) -> List[EvaluatorResultSummary]:
    # Pass 1: tie-breaker by filename ascending
    r1 = sorted(results, key=lambda x: os.path.basename(x.filepath))
    # Pass 2: generated_at descending
    r2 = sorted(r1, key=lambda x: x.generated_at or "", reverse=True)
    # Pass 3: valid files first
    r3 = sorted(r2, key=lambda x: 0 if x.is_valid else 1)
    return r3

def load_evaluator_result_files(paths: List[str]) -> List[EvaluatorResultSummary]:
    summaries = []
    for p in paths:
        summaries.append(_summarize_file(p))
    return sort_results(summaries)

def load_evaluator_result_folder(path: str) -> List[EvaluatorResultSummary]:
    if not os.path.isdir(path):
        return []
    
    # Non-recursive JSON scan
    json_files = glob.glob(os.path.join(path, "*.json"))
    return load_evaluator_result_files(json_files)
