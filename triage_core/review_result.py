"""Deterministic checker core for the evidence-bound review harness (CR-RH-002).

``build_review_result`` consumes an already-validated ``review_submission_v0``
(see :mod:`triage_core.review_submission`) plus an explicitly supplied context
packet string, and produces a ``review_result_v0`` dict. It performs only
mechanically-decidable checks:

- section-scoped citation resolution against the supplied packet,
- a grounding gate that fails on severe unsupported categories, unresolved
  context-supported citations, or (when ``changed_paths`` is supplied) a
  declared-scope violation,
- routing of human-review-required declared actions,
- selection of a next safe action only from authorized-next-action claims when
  the gate passes,
- surfacing of uncertain and non-severe unsupported claims as warnings.

It is deliberately **not an oracle**. It does not classify raw model prose,
decide whether any claim is true, execute the declared validation commands, call
a model, or approve real-world actions. A passing grounding gate verifies
structural grounding and routing only; it is not a correctness, safety,
certification, or production-readiness verdict.

Outputs are leak-safe: claims and actions are identified by id/index, never by
echoing claim or action text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

SCHEMA_VERSION = "review_result_v0"

BOUNDARY = (
    "This result verifies structural grounding and routing only. It is not a "
    "correctness, safety, certification, or production-readiness verdict."
)

# Unsupported categories severe enough to fail the grounding gate outright.
SEVERE_UNSUPPORTED_CATEGORIES = (
    "production-readiness-claim",
    "scope-overreach",
)

_FILE_MARKER_RE = re.compile(r"^FILE:\s*(.+?)\s*$")


def build_review_result(
    submission: Dict[str, Any],
    context_packet: str,
    changed_paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Build a ``review_result_v0`` from a validated submission and a packet.

    ``submission`` is assumed to already be structurally valid (validate it with
    :func:`triage_core.review_submission.validate_review_submission` first).
    ``context_packet`` is the raw bundle text the review was performed against.
    ``changed_paths`` is optional; when omitted, the scope check is reported as
    ``not_checked`` rather than guessed.
    """
    sections = _parse_packet_sections(context_packet)

    citation_map: List[Dict[str, Any]] = []
    gate_failures: List[Dict[str, str]] = []
    unsupported_claims: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    authorized_next_action_ids: List[str] = []

    for claim in submission.get("claims", []) or []:
        claim_id = claim.get("id")
        category = claim.get("category")

        if category == "context-supported":
            resolved, matched_file = _resolve_citation(
                claim.get("citation", ""), sections
            )
            entry: Dict[str, Any] = {"claim_id": claim_id, "resolved": resolved}
            if matched_file is not None:
                entry["matched_file"] = matched_file
            citation_map.append(entry)
            if not resolved:
                gate_failures.append(
                    {"claim_id": claim_id, "code": "unresolved_citation"}
                )

        elif category == "unsupported":
            unsupported_category = claim.get("unsupported_category")
            unsupported_claims.append(
                {"claim_id": claim_id, "unsupported_category": unsupported_category}
            )
            if unsupported_category in SEVERE_UNSUPPORTED_CATEGORIES:
                gate_failures.append(
                    {"claim_id": claim_id, "code": "severe_unsupported_category"}
                )
            else:
                warnings.append(
                    {"claim_id": claim_id, "code": "non_severe_unsupported"}
                )

        elif category == "uncertain-inference":
            warnings.append({"claim_id": claim_id, "code": "uncertain_inference"})

        elif category == "authorized-next-action":
            authorized_next_action_ids.append(claim_id)

    scope_check = _check_scope(
        submission.get("declared_scope"), changed_paths, gate_failures
    )

    grounding_gate = "fail" if gate_failures else "pass"

    human_review_required: List[Dict[str, int]] = []
    for index, action in enumerate(submission.get("declared_actions", []) or []):
        if action.get("requires_human_review") is True:
            human_review_required.append({"action_index": index})

    next_safe_action: Optional[Dict[str, str]] = None
    if grounding_gate == "pass" and authorized_next_action_ids:
        next_safe_action = {"claim_id": authorized_next_action_ids[0]}

    return {
        "schema_version": SCHEMA_VERSION,
        "boundary": BOUNDARY,
        "grounding_gate": grounding_gate,
        "gate_failures": gate_failures,
        "citation_map": citation_map,
        "unsupported_claims": unsupported_claims,
        "warnings": warnings,
        "scope_check": scope_check,
        "human_review_required": human_review_required,
        "next_safe_action": next_safe_action,
    }


def render_review_result(result: Dict[str, Any]) -> str:
    """Render a ``review_result_v0`` as deterministic, ASCII, leak-safe text.

    Only ids, codes, counts, and the boundary line are emitted — never claim or
    action text.
    """
    lines: List[str] = []
    lines.append(f"grounding_gate: {result['grounding_gate']}")
    lines.append(f"boundary: {result['boundary']}")

    gate_failures = result["gate_failures"]
    lines.append(f"gate_failures: {len(gate_failures)}")
    for failure in gate_failures:
        claim_id = failure.get("claim_id", "-")
        lines.append(f"  - {failure['code']} (claim {claim_id})")

    citation_map = result["citation_map"]
    resolved_count = sum(1 for c in citation_map if c["resolved"])
    lines.append(f"citations_resolved: {resolved_count}/{len(citation_map)}")

    lines.append(f"unsupported_claims: {len(result['unsupported_claims'])}")
    lines.append(f"warnings: {len(result['warnings'])}")

    scope_check = result["scope_check"]
    lines.append(f"scope_check: {scope_check['status']}")
    for path in scope_check["out_of_scope"]:
        lines.append(f"  - out_of_scope: {path}")

    lines.append(f"human_review_required: {len(result['human_review_required'])}")

    next_safe_action = result["next_safe_action"]
    if next_safe_action is None:
        lines.append("next_safe_action: none")
    else:
        lines.append(f"next_safe_action: claim {next_safe_action['claim_id']}")

    return "\n".join(lines) + "\n"


def _parse_packet_sections(context_packet: str) -> Dict[str, str]:
    """Split a context packet into ``path -> section text`` using FILE markers.

    Multiple blocks for the same path are concatenated. Content before the first
    FILE marker is ignored.
    """
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    buffer: List[str] = []

    for line in context_packet.splitlines():
        marker = _FILE_MARKER_RE.match(line)
        if marker:
            if current is not None:
                sections.setdefault(current, []).append("\n".join(buffer))
            current = marker.group(1).strip()
            buffer = []
        else:
            buffer.append(line)

    if current is not None:
        sections.setdefault(current, []).append("\n".join(buffer))

    return {path: "\n".join(blocks) for path, blocks in sections.items()}


def _resolve_citation(
    citation: Any, sections: Dict[str, str]
) -> Tuple[bool, Optional[str]]:
    """Resolve a citation against parsed packet sections (section-scoped).

    Returns ``(resolved, matched_file)``. ``matched_file`` is the file path when
    the file marker is present in the packet (even if an anchor fails to
    resolve), else ``None``. An anchor, when present, must appear within that
    file's section — not merely somewhere in the packet.
    """
    if not isinstance(citation, str):
        return (False, None)

    ref = citation.strip()
    if ref.startswith("FILE:"):
        ref = ref[len("FILE:"):].strip()

    if "#" in ref:
        path, _, anchor = ref.partition("#")
        path = path.strip()
        anchor = anchor.strip()
    else:
        path = ref
        anchor = ""

    if path not in sections:
        return (False, None)

    if anchor:
        if anchor in sections[path]:
            return (True, path)
        return (False, path)

    return (True, path)


def _check_scope(
    declared_scope: Any,
    changed_paths: Optional[Sequence[str]],
    gate_failures: List[Dict[str, str]],
) -> Dict[str, Any]:
    if changed_paths is None:
        return {"status": "not_checked", "out_of_scope": []}

    scope = declared_scope if isinstance(declared_scope, list) else []
    out_of_scope = [p for p in changed_paths if not _path_in_scope(p, scope)]

    if out_of_scope:
        gate_failures.append({"code": "scope_violation"})
        return {"status": "fail", "out_of_scope": sorted(out_of_scope)}

    return {"status": "pass", "out_of_scope": []}


def _path_in_scope(path: str, scope: Sequence[str]) -> bool:
    normalized = str(path).replace("\\", "/")
    for entry in scope:
        candidate = str(entry).replace("\\", "/")
        if candidate.endswith("/"):
            if normalized == candidate.rstrip("/") or normalized.startswith(candidate):
                return True
        else:
            if normalized == candidate or normalized.startswith(candidate + "/"):
                return True
    return False


def write_review_result(
    result: Dict[str, Any], output_path: Union[str, Path]
) -> Path:
    """Write a ``review_result_v0`` to a JSON file (deterministic, sorted keys).

    Pure I/O helper mirroring ``eval_outcome_contract.write_actual_outcome``. It
    only writes the caller-supplied path; it touches no ledger, identity, or
    other runtime state.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path
