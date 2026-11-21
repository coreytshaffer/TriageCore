"""``tc checklist-review``: saved document-revision review (CR-138).

``save``, ``run``, and ``review`` are explicit mutations into the named
``--store``. ``show`` opens an existing store read-only. Errors print closed
reason codes only and never echo case text, model text, notes, or paths.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Iterable, Optional, Sequence

from triage_core import checklist_review as cr
from triage_core.checklist_review import ChecklistReviewError
from triage_core.checklist_review_local import ReviewModel, run_review
from triage_core.checklist_review_store import (
    EVIDENCE_ASSESSMENTS,
    HUMAN_DISPOSITIONS,
    HUMAN_REASON_CODES,
    LABEL_ASSESSMENTS,
    NOTE_LIMIT_BYTES,
    Event,
    ReviewStore,
    RunView,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ATTEMPT_STOPPED = 3
STORE_PLACEHOLDER = "<store>"
COMMAND = "tc checklist-review"


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store",
        required=True,
        dest="checklist_review_store",
        metavar="DIR",
        help="Private local review store directory, outside shared, synced, and version-controlled folders",
    )
    actions = parser.add_subparsers(dest="checklist_review_action", required=True, metavar="{save,run,show,review}")

    save = actions.add_parser("save", help="Freeze the workflow definition under a reference (creates the store if new)")
    save.add_argument("--workflow", required=True, help="Workflow reference, for example docrev-v1")
    save.add_argument("--model", required=True, help="Installed local Ollama model tag")
    save.add_argument("--model-digest", required=True, help="Expected 64-hex model digest reported by Ollama")

    run = actions.add_parser("run", help="Run the saved review on one case file")
    run.add_argument("--workflow", required=True, help="Saved workflow reference")
    run.add_argument("--case", required=True, help="Case file (UTF-8, LF line endings)")
    run.add_argument(
        "--confirm-local-runtime",
        action="store_true",
        help="Record that you verified the running Ollama has cloud features disabled and the pinned model is local",
    )

    show = actions.add_parser("show", help="Inspect a run read-only")
    show.add_argument("--run", required=True, dest="run_id", help="Run ID")
    show.add_argument("--item", help=f"Item ID (default {cr.ITEM_ID} with --evidence)")
    show.add_argument("--evidence", action="store_true", help="Show cited lines resolved against the recorded case")

    review = actions.add_parser("review", help="Record one human decision linked to an earlier result")
    review.add_argument("--run", required=True, dest="run_id", help="Run ID")
    review.add_argument("--item", required=True, help=f"Item ID, for example {cr.ITEM_ID}")
    review.add_argument("--target", required=True, help="Rule, model, or policy result event ID")
    review.add_argument("--finding", required=True, choices=cr.FINDINGS)
    review.add_argument("--disposition", required=True, choices=HUMAN_DISPOSITIONS)
    review.add_argument("--label-assessment", required=True, choices=LABEL_ASSESSMENTS)
    review.add_argument("--evidence-assessment", required=True, choices=EVIDENCE_ASSESSMENTS)
    review.add_argument("--cite", action="append", default=[], dest="cites", help="Case line label; repeat as needed")
    review.add_argument("--reason-code", required=True, choices=HUMAN_REASON_CODES)
    review.add_argument("--supersedes", help="Earlier human event ID of the same run and item")
    review.add_argument("--note-file", help="Private rationale note (UTF-8, at most 8 KiB)")
    review.add_argument("--active-seconds", type=float, help="Active operator seconds, if measured")


def run(args: argparse.Namespace) -> int:
    action = args.checklist_review_action
    try:
        if action == "save":
            return _save(args)
        if action == "run":
            return _run(args)
        if action == "show":
            return _show(args)
        if action == "review":
            return _review(args)
    except ChecklistReviewError as exc:
        _emit([f"tc: error: checklist-review {action}: {exc.reason_code}"], sys.stderr)
        return EXIT_ERROR
    return 2


# --- Actions ----------------------------------------------------------------


def _read_bounded(path: str, limit: int, code: str) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(limit)
    except OSError:
        raise ChecklistReviewError(code) from None


def _save(args: argparse.Namespace) -> int:
    with ReviewStore.create(args.checklist_review_store) as store:
        definition = store.save_definition(args.workflow, model_tag=args.model, model_digest=args.model_digest)
    record = definition.record
    profile = record["model_profile"]
    options = profile["request_settings"]["options"]
    _emit(
        [
            "Definition saved" if definition.created else "Definition already saved with identical content",
            f"  Workflow: {definition.ref}",
            f"  Definition ID: {definition.definition_id}",
            f"  Definition digest: {definition.digest}",
            f"  System text sha256: {record['system_text']['sha256']} (verified private artifact)",
            f"  User template sha256: {record['user_template']['sha256']} (verified private artifact)",
            f"  Rule: {record['rule_id']}  Parser: {record['parser_id']}  Policy: {record['policy_id']}",
            f"  Model: {profile['tag']}  expected digest {profile['expected_digest']}",
            "  Request settings: "
            + ", ".join(f"{key} {value}" for key, value in options.items())
            + ", think false, stream false",
            f"  Endpoint: {profile['endpoint']} (GET /api/tags, POST /api/chat only)",
        ]
    )
    return EXIT_OK


def _run(args: argparse.Namespace) -> int:
    case_bytes = _read_bounded(args.case, cr.CASE_LIMIT_BYTES + 1, "case_file_unreadable")
    with ReviewStore.open(args.checklist_review_store) as store:
        outcome = run_review(
            store,
            workflow_ref=args.workflow,
            case_bytes=case_bytes,
            model=ReviewModel(),
            confirm_local_runtime=args.confirm_local_runtime,
        )
        lines = render_run(store, store.project_run(outcome.run_id))
    _emit(lines)
    return EXIT_OK if outcome.status in ("returned_valid", "returned_invalid") else EXIT_ATTEMPT_STOPPED


def _show(args: argparse.Namespace) -> int:
    with ReviewStore.open_readonly(args.checklist_review_store) as store:
        view = store.project_run(args.run_id)
        item = args.item
        if item is not None and not any(event.item_id == item for event in view.events):
            raise ChecklistReviewError("item_unknown")
        if args.evidence:
            lines = render_evidence(store, view, item or cr.ITEM_ID)
        else:
            lines = render_run(store, view)
    _emit(lines)
    return EXIT_OK


def _review(args: argparse.Namespace) -> int:
    note = None
    if args.note_file:
        note = _read_bounded(args.note_file, NOTE_LIMIT_BYTES + 1, "note_file_unreadable")
    with ReviewStore.open(args.checklist_review_store) as store:
        event = store.record_human_assessment(
            args.run_id,
            item_id=args.item,
            target_event_id=args.target,
            finding=args.finding,
            disposition=args.disposition,
            label_assessment=args.label_assessment,
            evidence_assessment=args.evidence_assessment,
            cited_labels=args.cites,
            reason_code=args.reason_code,
            supersedes_event_id=args.supersedes,
            note_bytes=note,
            active_seconds=args.active_seconds,
        )
    record = event.record
    lines = [
        "Human decision recorded",
        f"  Event: {event.event_id}  (seq {event.seq})",
        f"  Run: {event.run_id}  Item: {event.item_id}",
        f"  Target: {event.target_event_id} ({record['target_step']} result)",
    ]
    if event.supersedes_event_id:
        lines.append(f"  Supersedes: {event.supersedes_event_id}")
    lines += [
        f"  {_human_summary(record)}",
        f"  Cited: {_labels(record['cited_labels'])}",
        f"  Reason code: {record['reason_code']}  Record: {record['record_kind']}",
        f"  Note: {'stored as a private artifact' if record['note']['stored'] else 'none'}",
        f"  Active operator s: {_number(record['measurements']['active_operator_s'])}",
        f"Run view: {COMMAND} --store {STORE_PLACEHOLDER} show --run {event.run_id}",
    ]
    _emit(lines)
    return EXIT_OK


# --- Rendering --------------------------------------------------------------


def _emit(lines: Iterable[str], stream: Any = None) -> None:
    stream = stream or sys.stdout
    text = "\n".join(lines) + "\n"
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        stream.write(text.encode(encoding, "backslashreplace").decode(encoding))
    stream.flush()


def _labels(labels: Sequence[str]) -> str:
    return " ".join(labels) if labels else "none"


def _number(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:g}"
    return str(value)


def _human_summary(record: dict) -> str:
    disposition = record["disposition"]
    if record["revision_of"] != "none":
        disposition = f"{disposition} ({record['revision_of']})"
    return (
        f"Finding: {record['finding']}  disposition {disposition}  "
        f"label {record['label_assessment']}  evidence {record['evidence_assessment']}"
    )


def _load_case(store: ReviewStore, view: RunView) -> tuple[Optional[cr.ReviewCase], str]:
    ref = view.started.artifacts.get("case")
    if ref is None:
        return None, "not_stored"
    read = store.read_artifact(ref)
    if read.status != "verified":
        return None, read.status
    try:
        return cr.parse_case(read.data), "verified"
    except cr.CaseInputError as exc:
        return None, f"verified, unparsed ({exc.reason_code})"


def _artifact_status(store: ReviewStore, event: Optional[Event], role: str) -> str:
    if event is None or role not in event.artifacts:
        return "none"
    return store.read_artifact(event.artifacts[role]).status


def _origin_text(record: dict) -> str:
    text = record["origin"]
    if record.get("origin_label"):
        text = record["origin_label"]
    if record.get("refers_to"):
        text += f" (refers to {record['refers_to']})"
    return text


def _overall_text(view: RunView) -> str:
    overall = view.overall
    if overall["source"] == "human":
        revision = overall["revision_of"]
        disposition = overall["disposition"] if revision == "none" else f"{overall['disposition']} {revision}"
        return (
            f"{overall['finding']} (from Human decision {overall['event_id']}: {disposition}, "
            f"label {overall['label_assessment']}, evidence {overall['evidence_assessment']})"
        )
    if overall["source"] == "policy":
        return f"{overall['finding']} (policy {cr.POLICY_ID}: {overall['agreement']}, evidence {overall['evidence_status']})"
    return f"none (attempt {overall['status']}, reason {overall['reason_code'] or 'none'}, stage {overall['stage']})"


def _agreement_text(record: dict) -> str:
    if record["agreement"] == "agreed":
        return f"agreed, evidence {record['evidence_status']}"
    return f"{record['agreement']}, review needed"


def render_run(store: ReviewStore, view: RunView) -> list[str]:
    started = view.started.record
    definition = store.load_definition(view.run.definition_ref)
    profile = definition.record["model_profile"]
    _, case_status = _load_case(store, view)
    case_id = (view.rule.record.get("case_id") if view.rule else None) or "unparsed"
    identity = "not reached"
    if view.preflight is not None:
        observed = view.preflight.record.get("observed_digest") or "none"
        identity = f"{view.preflight.record['identity_source']} {observed} ({view.preflight.status})"
    lines = [
        f"Checklist review run {view.run.run_id}",
        f"  Origin: {_origin_text(started)}",
        f"  Definition: {definition.ref}  digest {definition.digest}",
        f"  Model: {profile['tag']}  expected digest {profile['expected_digest']}  identity {identity}",
        f"  Runtime confirmation: {started['runtime_confirmation']}",
        f"  Case: {case_id}  sha256 {started['case']['sha256'] or 'not stored'}  [{case_status}]",
        f"  Attempt: {view.attempt_status}  reason {view.attempt_reason or 'none'}  stage {view.stage or 'none'}",
        f"  Stages reached: {', '.join(view.stages)}",
        f"Overall decision: {_overall_text(view)}",
        f"Item {cr.ITEM_ID}",
    ]
    for event in view.events:
        if event.item_id != cr.ITEM_ID:
            continue
        record = event.record
        prefix = f"  #{event.seq} {event.step:<6} {event.event_id}"
        if event.step == "rule":
            lines.append(f"{prefix}  {record['finding']}  {record['reason_code']}  cites {_labels(record['cited_labels'])}")
        elif event.step == "model":
            lines.append(
                f"{prefix}  {event.status}  {record['finding'] or 'no finding'}  parse {record['reason_code'] or 'ok'}"
                f"  citations {record['citation_resolution'] or 'n/a'}  cites {_labels(record['cited_labels'])}"
                f"  output [{_artifact_status(store, event, 'output')}]"
            )
        elif event.step == "policy":
            lines.append(f"{prefix}  {record['finding']}  {_agreement_text(record)}")
        elif event.step == "human":
            line = (
                f"{prefix}  {_human_summary(record)}  cites {_labels(record['cited_labels'])}"
                f"  reason {record['reason_code']}  {record['record_kind']}  target {event.target_event_id}"
            )
            if event.supersedes_event_id:
                line += f"  supersedes {event.supersedes_event_id}"
            lines.append(line)
    if not view.human:
        lines.append("  Human decision: none yet (review available)")
    generation = view.model.record["measurements"] if view.model else {}
    to_policy = view.policy.record["measurements"]["end_to_end_to_policy_s"] if view.policy else "inapplicable"
    latest = view.effective_human.record["measurements"] if view.effective_human else {}
    lines += [
        "Measurements",
        (
            f"  model generation s: {_number(generation.get('model_generation_s', 'inapplicable'))}"
            f"  (runtime total s {_number(generation.get('runtime_total_s', 'inapplicable'))},"
            f" load s {_number(generation.get('runtime_load_s', 'inapplicable'))})"
        ),
        f"  end to end to policy s: {_number(to_policy)}",
        f"  active operator s: {_number(latest.get('active_operator_s', 'unknown'))}",
        f"  end to end to decision s: {_number(latest.get('end_to_end_to_decision_s', 'inapplicable'))}",
        f"Evidence view: {COMMAND} --store {STORE_PLACEHOLDER} show --run {view.run.run_id} --item {cr.ITEM_ID} --evidence",
    ]
    return lines


def _case_lines(case: cr.ReviewCase, labels: Iterable[str], indent: str = "  ") -> list[str]:
    return [f"{indent}{label}  {case.line(label).text}" for label in labels if case.line(label) is not None]


def render_evidence(store: ReviewStore, view: RunView, item: str) -> list[str]:
    started = view.started.record
    case, case_status = _load_case(store, view)
    lines = [
        "Checklist review evidence",
        f"  Run: {view.run.run_id}",
        f"  Item: {item}",
        f"  Origin: {_origin_text(started)}",
        f"  Case: {case.case_id if case else 'unavailable'}  sha256 {started['case']['sha256'] or 'not stored'}  [{case_status}]",
    ]
    outline = cr.evidence_outline(case) if case else None
    if case is None:
        lines.append(f"Case lines unavailable: {case_status}")
    else:
        lines.append("Work-product header")
        lines += _case_lines(case, outline.target_lines) or ["  (no Document ID or Revision header line)"]
        if outline.controlling_file:
            lines.append(f"Controlling register {outline.controlling_prefix} ({outline.controlling_file})")
            lines += _case_lines(case, outline.register_lines)
            if outline.document_id is not None:
                matching = _labels(outline.matching_rows)
                lines.append(f"  Rows whose Document ID is {outline.document_id}: {matching}")
        else:
            lines.append("Controlling register: not supplied")

    if view.rule is not None:
        record = view.rule.record
        lines += [
            f"Rule {cr.RULE_ID}  event {view.rule.event_id}",
            f"  Finding: {record['finding']}  ({record['reason_code']})",
            f"  Cited: {_labels(record['cited_labels'])}",
        ]
        if record["gaps"]:
            lines.append(f"  Gaps: {', '.join(record['gaps'])}")

    if view.model is not None:
        record = view.model.record
        lines += [
            f"Model  event {view.model.event_id}  {view.model.status}",
            f"  Finding: {record['finding'] or 'none'}  parse {record['reason_code'] or 'ok'}",
        ]
        output = store.read_artifact(view.model.artifacts["output"]) if "output" in view.model.artifacts else None
        parsed = None
        if output is not None and output.status == "verified" and case is not None:
            parsed = cr.parse_model_result(case, output.data.decode("utf-8", "replace"))
        if parsed is not None and parsed.reason_text is not None:
            lines.append(f"  Reason (model text, not verified by the rule): {parsed.reason_text}")
        else:
            status = output.status if output is not None else "none"
            lines.append(f"  Reason: unavailable (output [{status}], case [{case_status}])")
        lines.append(f"  Cited: {_labels(record['cited_labels'])}  (resolution: {record['citation_resolution'] or 'n/a'})")
        if parsed is not None and parsed.unresolved_citations:
            lines.append(f"  Unresolved citations: {' | '.join(parsed.unresolved_citations)}")
        if outline is not None and outline.register_rows and record["finding"] is not None:
            uncited = [label for label in outline.register_rows if label not in record["cited_labels"]]
            lines.append(f"  Controlling-register rows not cited by the model: {_labels(uncited)}")
        lines.append(f"  Output: [{output.status if output is not None else 'none'}]")

    if view.policy is not None:
        record = view.policy.record
        lines += [
            f"Policy {cr.POLICY_ID}  event {view.policy.event_id}",
            f"  Finding: {record['finding']}  {_agreement_text(record)}",
            f"  Rule finding: {record['rule_finding']}  Model finding: {record['model_finding'] or 'none'}",
        ]

    if view.finished is not None and view.finished.status in ("stopped", "failed"):
        lines.append(f"Attempt {view.finished.status}: {view.finished.reason_code} at stage {view.finished.record['stage']}")

    superseded = {event.supersedes_event_id for event in view.human if event.supersedes_event_id}
    for event in view.human:
        if event.item_id != item:
            continue
        record = event.record
        status = "superseded" if event.event_id in superseded else "current"
        lines += [
            f"Human decision  event {event.event_id}  (seq {event.seq}, {status})",
            f"  {_human_summary(record)}",
            f"  Cited: {_labels(record['cited_labels'])}  reason {record['reason_code']}  record {record['record_kind']}",
            f"  Target: {event.target_event_id}",
        ]
        if case is not None:
            lines += _case_lines(case, record["cited_labels"], indent="    ")
        if "note" in event.artifacts:
            note = store.read_artifact(event.artifacts["note"])
            if note.status == "verified":
                lines.append(f"  Note: {note.data.decode('utf-8')}")
            else:
                lines.append(f"  Note: [{note.status}]")
    if not view.human:
        lines.append("Human decision: none yet (review available)")
    lines.append(f"Back to run view: {COMMAND} --store {STORE_PLACEHOLDER} show --run {view.run.run_id}")
    return lines
