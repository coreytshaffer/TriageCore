"""Independent, no-write verification for build-review packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from triage_core.build_review_integrity import (
    DECISION_STATUSES,
    REQUIRED_PACKET_FILES,
    decision_id,
    diff_summary,
    display_payload,
    evidence_sha256,
    validation_results,
)
from triage_core.build_review_report import render_html, render_markdown


class VerificationError(ValueError):
    """Raised when a packet is incomplete, malformed, or altered."""


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value}")


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise VerificationError(f"{label} is not valid UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(
            f"{label} contains malformed JSON at line {exc.lineno}, "
            f"column {exc.colno}: {path}"
        ) from exc
    except ValueError as exc:
        raise VerificationError(f"{label} contains malformed JSON: {exc}") from exc
    except OSError as exc:
        raise VerificationError(f"could not read {label}: {path}: {exc}") from exc


def _require_mapping(value: Any, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise VerificationError(f"{label} must contain a JSON object")
    return value


def _review_path(packet_path: Union[str, Path]) -> Path:
    supplied = Path(packet_path)
    if supplied.is_dir():
        return supplied / "review.json"
    if supplied.name != "review.json":
        raise VerificationError(
            "packet path must be a review directory or its review.json file"
        )
    return supplied


def _reject_link(path: Path, label: str) -> None:
    if path.is_symlink():
        raise VerificationError(f"{label} must not be a symbolic link")


def _required_review_fields(review: Dict[str, Any]) -> None:
    required = (
        "schema_version",
        "packet_id",
        "created_at",
        "repository",
        "request",
        "comparison",
        "expected_scope",
        "change_summary",
        "changed_files",
        "validations",
        "findings",
        "recommendation",
        "working_tree_clean",
        "decision",
        "evidence_sha256",
    )
    missing = [key for key in required if key not in review]
    if missing:
        raise VerificationError(
            "review.json is missing required field(s): " + ", ".join(missing)
        )
    if not isinstance(review["packet_id"], str) or not review["packet_id"].strip():
        raise VerificationError("review.json packet_id must be a nonempty string")
    if not isinstance(review["evidence_sha256"], str):
        raise VerificationError("review.json evidence_sha256 must be a string")
    if not isinstance(review["request"], dict):
        raise VerificationError("review.json request must be an object")
    if not isinstance(review["comparison"], dict):
        raise VerificationError("review.json comparison must be an object")
    for key in ("expected_scope", "changed_files", "validations", "findings"):
        if not isinstance(review[key], list):
            raise VerificationError(f"review.json {key} must be an array")
    decision = _require_mapping(review["decision"], "review.json decision")
    if decision.get("status") != "pending":
        raise VerificationError(
            "review.json decision must remain pending; decisions belong in "
            "decision.json"
        )


def _verify_decision(
    decision_path: Path,
    review: Dict[str, Any],
) -> Union[Dict[str, Any], None]:
    if not decision_path.exists():
        return None
    _reject_link(decision_path, "decision.json")
    decision = _require_mapping(
        _read_json(decision_path, "decision.json"),
        "decision.json",
    )
    required = (
        "schema_version",
        "decision_id",
        "review_packet_id",
        "evidence_sha256",
        "status",
        "reviewer",
        "note",
        "decided_at",
    )
    missing = [key for key in required if key not in decision]
    if missing:
        raise VerificationError(
            "decision.json is missing required field(s): " + ", ".join(missing)
        )
    if decision["status"] not in DECISION_STATUSES:
        raise VerificationError(
            "decision.json status must be approved, rejected, or needs_revision"
        )
    if decision["review_packet_id"] != review["packet_id"]:
        raise VerificationError(
            "decision.json references a different review packet ID"
        )
    if decision["evidence_sha256"] != review["evidence_sha256"]:
        raise VerificationError(
            "decision.json does not reference the verified evidence hash"
        )
    if decision["decision_id"] != decision_id(decision):
        raise VerificationError("decision.json decision ID is invalid")
    if not isinstance(decision["reviewer"], str) or not decision["reviewer"].strip():
        raise VerificationError("decision.json reviewer must be a nonempty string")
    return decision


def verify_packet(packet_path: Union[str, Path]) -> Dict[str, str]:
    """Verify the complete packet without modifying any artifact."""
    review_path = _review_path(packet_path)
    packet_dir = review_path.parent
    if packet_dir.is_symlink():
        raise VerificationError("packet directory must not be a symbolic link")
    missing = [
        name for name in REQUIRED_PACKET_FILES if not (packet_dir / name).is_file()
    ]
    if missing:
        raise VerificationError(
            "packet is missing required artifact(s): " + ", ".join(missing)
        )
    for name in REQUIRED_PACKET_FILES:
        _reject_link(packet_dir / name, name)

    review = _require_mapping(
        _read_json(review_path, "review.json"),
        "review.json",
    )
    _required_review_fields(review)
    actual_hash = evidence_sha256(review)
    if review["evidence_sha256"] != actual_hash:
        raise VerificationError(
            "review.json evidence hash mismatch; authoritative evidence was "
            "altered"
        )

    expected_derived: Tuple[Tuple[str, Dict[str, Any]], ...] = (
        ("diff-summary.json", diff_summary(review)),
        ("validation-results.json", validation_results(review)),
    )
    for filename, expected in expected_derived:
        actual = _read_json(packet_dir / filename, filename)
        if actual != expected:
            raise VerificationError(
                f"{filename} does not match authoritative review evidence"
            )

    decision = _verify_decision(packet_dir / "decision.json", review)
    rendered = display_payload(review, decision)
    expected_markdown = render_markdown(rendered, Path("review.json"))
    expected_html = render_html(rendered, Path("review.json"))
    try:
        actual_markdown = (packet_dir / "review.md").read_text(encoding="utf-8")
        actual_html = (packet_dir / "review.html").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VerificationError(
            f"could not read rendered packet artifact: {exc}"
        ) from exc
    if actual_markdown != expected_markdown:
        raise VerificationError(
            "review.md does not match authoritative review evidence"
        )
    if actual_html != expected_html:
        raise VerificationError(
            "review.html does not match authoritative review evidence"
        )

    return {
        "review_id": review["packet_id"],
        "evidence_sha256": actual_hash,
        "decision": decision["status"] if decision else "pending",
        "recommendation": review["recommendation"],
    }
