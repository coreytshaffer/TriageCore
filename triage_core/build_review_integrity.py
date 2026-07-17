"""Canonical hashing and derived artifact helpers for build-review packets."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Optional

DECISION_STATUSES = frozenset({"approved", "rejected", "needs_revision"})
REQUIRED_PACKET_FILES = (
    "review.json",
    "review.md",
    "review.html",
    "diff-summary.json",
    "validation-results.json",
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def evidence_payload(review: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(review)
    payload.pop("decision", None)
    payload.pop("evidence_sha256", None)
    return payload


def evidence_sha256(review: Dict[str, Any]) -> str:
    return sha256_json(evidence_payload(review))


def decision_id(decision: Dict[str, Any]) -> str:
    payload = deepcopy(decision)
    payload.pop("decision_id", None)
    return sha256_json(payload)[:16]


def diff_summary(review: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "review_id": review["packet_id"],
        "comparison": review["comparison"],
        "expected_scope": review["expected_scope"],
        "summary": review["change_summary"],
        "changed_files": review["changed_files"],
    }


def validation_results(review: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "review_id": review["packet_id"],
        "declared_validations": review["request"].get(
            "declared_validations", []
        ),
        "results": review["validations"],
    }


def display_payload(
    review: Dict[str, Any],
    decision: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = deepcopy(review)
    if decision is not None:
        payload["decision"] = {
            key: decision[key]
            for key in ("status", "reviewer", "note", "decided_at")
        }
    return payload
