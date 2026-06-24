import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from triage_core.privacy_scanner import PrivacyReport
from triage_core.privacy_findings import (
    SSN_PATTERN_DETECTED,
    METADATA_PRIVACY_CONFLICT,
    PRIVACY_CHECK_FAILED,
)

def build_actual_outcome(
    *,
    case_id: str,
    decision: str,
    boundary_family: str,
    reasons: Iterable[str],
    audit_required: bool,
    human_approval_required: bool,
    diagnostic_details: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Builds a dictionary representing an actual evaluation outcome that conforms
    to the contract expected by the independent agent-control-evals repository.
    """
    if not case_id or not isinstance(case_id, str):
        raise ValueError("case_id must be a non-empty string.")
    
    if not re.match(r"^[a-zA-Z0-9_-]+$", case_id):
        raise ValueError(f"case_id '{case_id}' is not path-safe.")

    if not decision or not isinstance(decision, str):
        raise ValueError("decision must be a non-empty string.")
        
    if not boundary_family or not isinstance(boundary_family, str):
        raise ValueError("boundary_family must be a non-empty string.")
        
    if not isinstance(reasons, Iterable) or isinstance(reasons, str):
        raise ValueError("reasons must be a non-string iterable of strings.")
    
    reasons_list = list(reasons)
    for r in reasons_list:
        if not isinstance(r, str):
            raise ValueError("All reasons must be strings.")

    if not isinstance(audit_required, bool):
        raise ValueError("audit_required must be a boolean.")
        
    if not isinstance(human_approval_required, bool):
        raise ValueError("human_approval_required must be a boolean.")

    outcome = {
        "case_id": case_id,
        "decision": decision,
        "boundary_family": boundary_family,
        "reasons": reasons_list,
        "audit_required": audit_required,
        "human_approval_required": human_approval_required
    }

    if diagnostic_details is not None:
        if not isinstance(diagnostic_details, Iterable) or isinstance(diagnostic_details, str):
            raise ValueError("diagnostic_details must be a non-string iterable of strings.")
        dd_list = list(diagnostic_details)
        for dd in dd_list:
            if not isinstance(dd, str):
                raise ValueError("All diagnostic_details must be strings.")
        if dd_list:
            outcome["diagnostic_details"] = dd_list

    return outcome

def write_actual_outcome(
    outcome: Mapping[str, Any],
    output_dir: Union[str, Path],
) -> Path:
    """
    Writes a single actual outcome dictionary to a JSON file in the specified
    output directory. The filename is <case_id>.json.
    """
    if "case_id" not in outcome:
        raise ValueError("Outcome must contain a 'case_id'.")
        
    case_id = outcome["case_id"]
    if not re.match(r"^[a-zA-Z0-9_-]+$", case_id):
        raise ValueError(f"case_id '{case_id}' is not path-safe.")

    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    
    file_path = dir_path / f"{case_id}.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(outcome, f, sort_keys=True, indent=2)
        f.write("\n")
        
    return file_path

def write_actual_outcomes(
    outcomes: Iterable[Mapping[str, Any]],
    output_dir: Union[str, Path],
) -> List[Path]:
    """
    Writes multiple actual outcomes to the specified output directory.
    Raises ValueError if there are duplicate case_ids in the provided outcomes.
    """
    seen_ids = set()
    for outcome in outcomes:
        case_id = outcome.get("case_id")
        if case_id in seen_ids:
            raise ValueError(f"Duplicate case_id '{case_id}' found in outcomes.")
        seen_ids.add(case_id)
        
    paths = []
    for outcome in outcomes:
        paths.append(write_actual_outcome(outcome, output_dir))
        
    return paths

def normalize_privacy_reasons(violations: Iterable[str]) -> List[str]:
    """
    Normalizes raw privacy scanner violations into stable eval-facing reason codes.
    This exact-string mapping is transitional until PrivacyReport exposes structured signals.
    """
    reasons_set = set()
    for v in violations:
        if v == "Detected possible SSN pattern in packet content; metadata contains_pii=False.":
            reasons_set.add(SSN_PATTERN_DETECTED)
            reasons_set.add(METADATA_PRIVACY_CONFLICT)
        else:
            reasons_set.add(PRIVACY_CHECK_FAILED)

    return sorted(list(reasons_set))

def project_privacy_report_to_actual_outcome(
    case_id: str,
    report: PrivacyReport,
) -> Dict[str, Any]:
    """
    Projects a TriageCore PrivacyReport into the standard actual outcome contract.
    For privacy report export, failed privacy checks are projected as audit_required=True.
    This does not define a new runtime policy; it only maps the existing PrivacyReport
    result into the external actual-outcome contract.
    """
    reasons = []
    diagnostic_details = []
    if not report.passed:
        diagnostic_details = list(report.violations)
        if report.finding_codes:
            reasons = sorted(list(set(report.finding_codes)))
        else:
            reasons = normalize_privacy_reasons(report.violations)

    return build_actual_outcome(
        case_id=case_id,
        decision="allow" if report.passed else "block",
        boundary_family="privacy",
        reasons=reasons,
        audit_required=not report.passed,
        human_approval_required=False,
        diagnostic_details=diagnostic_details if diagnostic_details else None,
    )
