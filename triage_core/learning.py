import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .task_ledger import TaskRecord


@dataclass
class LearningProposal:
    proposal_id: str
    trigger: str
    recommendation: str
    evidence_task_ids: List[str]
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewer_decision: Optional[str] = None
    reviewer_notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def build_learning_proposals(
    records: Iterable[TaskRecord],
    min_evidence: int = 1,
) -> List[LearningProposal]:
    records_list = list(records)
    proposals: List[LearningProposal] = []

    proposals.extend(_propose_benchmark_mismatch_lessons(records_list, min_evidence))
    proposals.extend(_propose_unexpected_handoff_lessons(records_list, min_evidence))
    proposals.extend(_propose_validator_failure_lessons(records_list, min_evidence))

    return proposals


def load_learning_proposals(path: str) -> List[LearningProposal]:
    proposal_path = Path(path)
    if not proposal_path.exists():
        return []

    proposals: List[LearningProposal] = []
    with proposal_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            proposals.append(LearningProposal(**json.loads(line)))
    return proposals


def append_learning_proposals(path: str, proposals: List[LearningProposal]) -> List[LearningProposal]:
    proposal_path = Path(path)
    proposal_path.parent.mkdir(parents=True, exist_ok=True)

    existing_ids = {proposal.proposal_id for proposal in load_learning_proposals(path)}
    new_proposals = [proposal for proposal in proposals if proposal.proposal_id not in existing_ids]

    with proposal_path.open("a", encoding="utf-8") as f:
        for proposal in new_proposals:
            f.write(json.dumps(proposal.to_dict()) + "\n")

    return new_proposals


def append_learning_review(
    path: str,
    proposal_id: str,
    decision: str,
    notes: str = "",
) -> Dict[str, str]:
    if decision not in {"accepted", "rejected"}:
        raise ValueError("decision must be 'accepted' or 'rejected'")

    review = {
        "proposal_id": proposal_id,
        "decision": decision,
        "notes": notes,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }

    review_path = Path(path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(review) + "\n")

    return review


def _propose_benchmark_mismatch_lessons(
    records: List[TaskRecord],
    min_evidence: int,
) -> List[LearningProposal]:
    grouped: Dict[str, List[TaskRecord]] = {}
    for record in records:
        if not record.expected_status or not record.observed_status:
            continue
        if record.expected_status == record.observed_status:
            continue
        key = record.benchmark_category or "uncategorized"
        grouped.setdefault(key, []).append(record)

    proposals = []
    for category, evidence in grouped.items():
        if len(evidence) < min_evidence:
            continue
        trigger = f"benchmark_status_mismatch:{category}"
        recommendation = (
            f"Review benchmark category '{category}' because observed statuses diverged "
            "from expected statuses. Check prompt wording, validator choice, routing rules, "
            "and local model suitability before changing behavior."
        )
        proposals.append(_make_proposal(trigger, recommendation, evidence))
    return proposals


def _propose_unexpected_handoff_lessons(
    records: List[TaskRecord],
    min_evidence: int,
) -> List[LearningProposal]:
    grouped: Dict[str, List[TaskRecord]] = {}
    for record in records:
        if not record.handoff_reason:
            continue
        if record.expected_status == "handoff_required":
            continue
        key = record.benchmark_category or record.risk_level or "uncategorized"
        grouped.setdefault(key, []).append(record)

    proposals = []
    for category, evidence in grouped.items():
        if len(evidence) < min_evidence:
            continue
        trigger = f"unexpected_handoff:{category}"
        recommendation = (
            f"Review unexpected handoffs for '{category}'. Consider whether the timeout, "
            "context size threshold, risk detector, or validator is too strict for this task class."
        )
        proposals.append(_make_proposal(trigger, recommendation, evidence))
    return proposals


def _propose_validator_failure_lessons(
    records: List[TaskRecord],
    min_evidence: int,
) -> List[LearningProposal]:
    grouped: Dict[str, List[TaskRecord]] = {}
    for record in records:
        if record.validator_passed is not False:
            continue
        key = record.benchmark_category or "uncategorized"
        grouped.setdefault(key, []).append(record)

    proposals = []
    for category, evidence in grouped.items():
        if len(evidence) < min_evidence:
            continue
        trigger = f"validator_failure:{category}"
        recommendation = (
            f"Review validator failures for '{category}'. Consider a stricter prompt template, "
            "a different local model, or a task-specific validator before accepting future outputs."
        )
        proposals.append(_make_proposal(trigger, recommendation, evidence))
    return proposals


def _make_proposal(
    trigger: str,
    recommendation: str,
    evidence: List[TaskRecord],
) -> LearningProposal:
    evidence_task_ids = sorted(record.task_id for record in evidence)
    proposal_key = f"{trigger}|{','.join(evidence_task_ids)}|{recommendation}"
    proposal_id = hashlib.sha256(proposal_key.encode("utf-8")).hexdigest()[:12]

    return LearningProposal(
        proposal_id=proposal_id,
        trigger=trigger,
        recommendation=recommendation,
        evidence_task_ids=evidence_task_ids,
    )
