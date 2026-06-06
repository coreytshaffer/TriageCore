import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .task_ledger import TaskRecord


LEARNING_SEED_FILES = {
    "preflights": "triagecore-assignment-preflights.safetask.jsonl",
    "context_packs": "triagecore-context-packs.safetask.jsonl",
    "outcomes": "triagecore-assignment-outcomes.safetask.jsonl",
}

LEARNING_SEED_OUTPUT_FILES = {
    "preflights": "assignment_preflights.jsonl",
    "context_packs": "context_packs.jsonl",
    "outcomes": "assignment_outcomes.jsonl",
}

LEARNING_SEED_ID_FIELDS = {
    "preflights": "preflight_id",
    "context_packs": "context_pack_id",
    "outcomes": "task_id",
}

PREFLIGHT_REQUIRED_FIELDS = [
    "preflight_id",
    "created_at",
    "source_project",
    "assignment_goal",
    "task_class",
    "complexity",
    "sensitivity",
    "required_context",
    "context_pack_type",
    "candidate_combo",
    "required_checks",
    "stop_conditions",
    "human_review_required",
    "confidence_before_assignment",
    "rationale",
]

CONTEXT_PACK_REQUIRED_FIELDS = [
    "context_pack_id",
    "pack_type",
    "source_project",
    "task_goal",
    "source_artifacts",
    "constraints",
    "required_checks",
    "budget_note",
]

OUTCOME_REQUIRED_FIELDS = [
    "task_id",
    "preflight_id",
    "context_pack_id",
    "observed_at",
    "source_project",
    "source_artifacts",
    "task_class",
    "complexity",
    "sensitivity",
    "assignment_goal",
    "model_combo",
    "tool_path",
    "result_status",
    "verification",
    "correction_burden",
    "waste_signal",
    "confidence_after_review",
    "lesson",
    "human_review_required",
]


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


@dataclass
class LearningSeedImportResult:
    preflight_count: int = 0
    context_pack_count: int = 0
    outcome_count: int = 0
    preflight_imported: int = 0
    context_pack_imported: int = 0
    outcome_imported: int = 0
    errors: List[str] = field(default_factory=list)
    output_paths: Dict[str, str] = field(default_factory=dict)
    dry_run: bool = True

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def total_count(self) -> int:
        return self.preflight_count + self.context_pack_count + self.outcome_count

    @property
    def total_imported(self) -> int:
        return self.preflight_imported + self.context_pack_imported + self.outcome_imported


def import_learning_seed_records(
    source_dir: str,
    ledger_dir: str = ".triagecore",
    dry_run: bool = True,
) -> LearningSeedImportResult:
    source_path = Path(source_dir)
    output_dir = Path(ledger_dir) / "learning_seeds"
    output_paths = {
        label: str(output_dir / output_filename)
        for label, output_filename in LEARNING_SEED_OUTPUT_FILES.items()
    }
    result = LearningSeedImportResult(dry_run=dry_run, output_paths=output_paths)

    preflights, preflight_errors = _load_learning_seed_jsonl(
        source_path / LEARNING_SEED_FILES["preflights"],
        label="preflights",
    )
    context_packs, context_pack_errors = _load_learning_seed_jsonl(
        source_path / LEARNING_SEED_FILES["context_packs"],
        label="context_packs",
    )
    outcomes, outcome_errors = _load_learning_seed_jsonl(
        source_path / LEARNING_SEED_FILES["outcomes"],
        label="outcomes",
    )

    result.preflight_count = len(preflights)
    result.context_pack_count = len(context_packs)
    result.outcome_count = len(outcomes)
    result.errors.extend(preflight_errors + context_pack_errors + outcome_errors)
    result.errors.extend(validate_learning_seed_records(preflights, context_packs, outcomes))

    if result.errors or dry_run:
        return result

    output_dir.mkdir(parents=True, exist_ok=True)
    result.preflight_imported = _append_new_seed_records(
        Path(output_paths["preflights"]),
        preflights,
        id_field=LEARNING_SEED_ID_FIELDS["preflights"],
    )
    result.context_pack_imported = _append_new_seed_records(
        Path(output_paths["context_packs"]),
        context_packs,
        id_field=LEARNING_SEED_ID_FIELDS["context_packs"],
    )
    result.outcome_imported = _append_new_seed_records(
        Path(output_paths["outcomes"]),
        outcomes,
        id_field=LEARNING_SEED_ID_FIELDS["outcomes"],
    )
    return result


def validate_learning_seed_records(
    preflights: List[Dict[str, Any]],
    context_packs: List[Dict[str, Any]],
    outcomes: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    errors.extend(_validate_required_fields("preflights", preflights, PREFLIGHT_REQUIRED_FIELDS))
    errors.extend(_validate_required_fields("context_packs", context_packs, CONTEXT_PACK_REQUIRED_FIELDS))
    errors.extend(_validate_required_fields("outcomes", outcomes, OUTCOME_REQUIRED_FIELDS))

    preflight_ids = _collect_unique_seed_ids(
        "preflights",
        preflights,
        LEARNING_SEED_ID_FIELDS["preflights"],
        errors,
    )
    context_pack_ids = _collect_unique_seed_ids(
        "context_packs",
        context_packs,
        LEARNING_SEED_ID_FIELDS["context_packs"],
        errors,
    )
    _collect_unique_seed_ids(
        "outcomes",
        outcomes,
        LEARNING_SEED_ID_FIELDS["outcomes"],
        errors,
    )

    for index, outcome in enumerate(outcomes, start=1):
        preflight_id = str(outcome.get("preflight_id", "")).strip()
        context_pack_id = str(outcome.get("context_pack_id", "")).strip()
        if preflight_id and preflight_id not in preflight_ids:
            errors.append(
                f"outcomes record {index}: preflight_id '{preflight_id}' "
                "does not match an imported preflight"
            )
        if context_pack_id and context_pack_id not in context_pack_ids:
            errors.append(
                f"outcomes record {index}: context_pack_id '{context_pack_id}' "
                "does not match an imported context pack"
            )

    return errors


def _load_learning_seed_jsonl(
    path: Path,
    label: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not path.exists():
        return [], [f"{label}: missing seed file {path}"]

    records: List[Dict[str, Any]] = []
    errors: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{label} line {line_number}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(parsed, dict):
                errors.append(f"{label} line {line_number}: expected a JSON object")
                continue
            records.append(parsed)
    return records, errors


def _validate_required_fields(
    label: str,
    records: List[Dict[str, Any]],
    required_fields: List[str],
) -> List[str]:
    errors: List[str] = []
    for index, record in enumerate(records, start=1):
        missing = [
            field_name
            for field_name in required_fields
            if field_name not in record or _is_blank_required_value(record[field_name])
        ]
        if missing:
            errors.append(f"{label} record {index}: missing required field(s): {', '.join(missing)}")
    return errors


def _collect_unique_seed_ids(
    label: str,
    records: List[Dict[str, Any]],
    id_field: str,
    errors: List[str],
) -> set[str]:
    ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        value = record.get(id_field)
        if _is_blank_required_value(value):
            continue
        text_value = str(value).strip()
        if text_value in ids:
            errors.append(f"{label} record {index}: duplicate {id_field} '{text_value}'")
        ids.add(text_value)
    return ids


def _append_new_seed_records(
    path: Path,
    records: List[Dict[str, Any]],
    id_field: str,
) -> int:
    existing_ids = _load_existing_seed_ids(path, id_field)
    new_records = [
        record
        for record in records
        if str(record.get(id_field, "")).strip() not in existing_ids
    ]
    if not new_records:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for record in new_records:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    return len(new_records)


def _load_existing_seed_ids(path: Path, id_field: str) -> set[str]:
    if not path.exists():
        return set()

    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            value = parsed.get(id_field)
            if not _is_blank_required_value(value):
                ids.add(str(value).strip())
    return ids


def _is_blank_required_value(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def build_learning_proposals(
    records: Iterable[TaskRecord],
    min_evidence: int = 1,
) -> List[LearningProposal]:
    records_list = list(records)
    proposals: List[LearningProposal] = []

    proposals.extend(_propose_benchmark_mismatch_lessons(records_list, min_evidence))
    proposals.extend(_propose_unexpected_handoff_lessons(records_list, min_evidence))
    proposals.extend(_propose_validator_failure_lessons(records_list, min_evidence))

    # TODO: Add positive learning evidence proposals requiring:
    # review_decision in ['accepted', 'accepted_with_minor_edits'] AND task_outcome == 'resolved'
    # Currently, we only propose lessons from failures.

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
