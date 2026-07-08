"""Structural validator for ``review_submission_v0`` packets (CR-RH-001, Slice 1).

This module validates the *structure* of an evidence-bound review submission:
required fields, types, taxonomy enums, citation/anchor *format*, and basic
legibility (non-empty text, unique claim ids).

It deliberately does not:

- resolve citations against a context packet,
- classify raw model prose,
- decide whether any claim is true,
- execute commands,
- approve actions, or
- make any correctness, safety, or production-readiness claim.

Passing validation means a submission is well-formed and readable, not that its
claims are correct. Errors are returned as stable ``{"path", "code"}`` dicts and
carry no claim text or file paths, so the validator is not a data-leak surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Union
import re

SCHEMA_VERSION = "review_submission_v0"

CLAIM_CATEGORIES = (
    "context-supported",
    "uncertain-inference",
    "unsupported",
    "authorized-next-action",
)

UNSUPPORTED_CATEGORIES = (
    "hallucinated-artifact",
    "invented-capability",
    "assumption-as-fact",
    "scope-overreach",
    "production-readiness-claim",
    "stale-context-claim",
)

# Citation *format* only (no resolution): either a bundle file marker
# ("FILE: <path>") or a "<ref>#<anchor>" pair. This checks shape, never whether
# the referenced artifact exists in any context packet.
_CITATION_RE = re.compile(r"^(FILE:\s*\S.*|\S.*#\S.*)$")

_MISSING = object()


def _check_nonempty_str(
    container: Dict[str, Any],
    key: str,
    path: str,
    err: Callable[[str, str], None],
) -> None:
    value = container.get(key, _MISSING)
    if value is _MISSING:
        err(path, "missing_field")
    elif not isinstance(value, str):
        err(path, "wrong_type")
    elif not value.strip():
        err(path, "empty_value")


def _check_citation_format(
    citation: Any,
    path: str,
    err: Callable[[str, str], None],
) -> None:
    if not isinstance(citation, str):
        err(path, "wrong_type")
    elif not _CITATION_RE.match(citation):
        err(path, "invalid_citation_format")


def _check_unsupported_category(
    value: Any,
    path: str,
    err: Callable[[str, str], None],
) -> None:
    if not isinstance(value, str):
        err(path, "wrong_type")
    elif value not in UNSUPPORTED_CATEGORIES:
        err(path, "invalid_unsupported_category")


def validate_review_submission(obj: Any) -> List[Dict[str, str]]:
    """Return a list of structural errors for a review submission.

    Each error is a stable ``{"path": ..., "code": ...}`` dict. An empty list
    means the submission is structurally valid (well-formed and readable) — not
    that its claims are correct, safe, or approved.
    """
    errors: List[Dict[str, str]] = []

    def err(path: str, code: str) -> None:
        errors.append({"path": path, "code": code})

    if not isinstance(obj, dict):
        err("$", "wrong_type")
        return errors

    schema_version = obj.get("schema_version", _MISSING)
    if schema_version is _MISSING:
        err("$.schema_version", "missing_field")
    elif not isinstance(schema_version, str):
        err("$.schema_version", "wrong_type")
    elif schema_version != SCHEMA_VERSION:
        err("$.schema_version", "invalid_schema_version")

    _check_nonempty_str(obj, "context_packet_ref", "$.context_packet_ref", err)

    _validate_claims(obj.get("claims", _MISSING), err)
    _validate_declared_actions(obj.get("declared_actions", _MISSING), err)
    _validate_validation(obj.get("validation", _MISSING), err)
    _validate_declared_scope(obj.get("declared_scope", _MISSING), err)

    repo_diff_ref = obj.get("repo_diff_ref", _MISSING)
    if (
        repo_diff_ref is not _MISSING
        and repo_diff_ref is not None
        and not isinstance(repo_diff_ref, str)
    ):
        err("$.repo_diff_ref", "wrong_type")

    return errors


def _validate_claims(claims: Any, err: Callable[[str, str], None]) -> None:
    if claims is _MISSING:
        err("$.claims", "missing_field")
        return
    if not isinstance(claims, list):
        err("$.claims", "wrong_type")
        return
    if not claims:
        err("$.claims", "empty_claims")
        return

    seen_ids: set = set()
    for i, claim in enumerate(claims):
        base = f"$.claims[{i}]"
        if not isinstance(claim, dict):
            err(base, "wrong_type")
            continue

        claim_id = claim.get("id", _MISSING)
        if claim_id is _MISSING:
            err(f"{base}.id", "missing_field")
        elif not isinstance(claim_id, str):
            err(f"{base}.id", "wrong_type")
        elif not claim_id.strip():
            err(f"{base}.id", "empty_value")
        else:
            if claim_id in seen_ids:
                err(f"{base}.id", "duplicate_claim_id")
            seen_ids.add(claim_id)

        _check_nonempty_str(claim, "text", f"{base}.text", err)

        category = claim.get("category", _MISSING)
        if category is _MISSING:
            err(f"{base}.category", "missing_field")
        elif not isinstance(category, str):
            err(f"{base}.category", "wrong_type")
        elif category not in CLAIM_CATEGORIES:
            err(f"{base}.category", "invalid_category")

        _validate_claim_citation(claim, category, base, err)
        _validate_claim_unsupported_category(claim, category, base, err)


def _validate_claim_citation(
    claim: Dict[str, Any],
    category: Any,
    base: str,
    err: Callable[[str, str], None],
) -> None:
    citation = claim.get("citation", _MISSING)
    path = f"{base}.citation"
    if category == "context-supported":
        if citation is _MISSING:
            err(path, "missing_citation")
        else:
            _check_citation_format(citation, path, err)
    elif citation is not _MISSING:
        # Citation is optional for other categories, but if present it must
        # still be well-formed.
        _check_citation_format(citation, path, err)


def _validate_claim_unsupported_category(
    claim: Dict[str, Any],
    category: Any,
    base: str,
    err: Callable[[str, str], None],
) -> None:
    value = claim.get("unsupported_category", _MISSING)
    path = f"{base}.unsupported_category"
    if category == "unsupported":
        if value is _MISSING:
            err(path, "missing_unsupported_category")
        else:
            _check_unsupported_category(value, path, err)
    elif value is not _MISSING:
        _check_unsupported_category(value, path, err)


def _validate_declared_actions(
    actions: Any, err: Callable[[str, str], None]
) -> None:
    if actions is _MISSING:
        return
    if not isinstance(actions, list):
        err("$.declared_actions", "wrong_type")
        return
    for i, action in enumerate(actions):
        base = f"$.declared_actions[{i}]"
        if not isinstance(action, dict):
            err(base, "wrong_type")
            continue
        _check_nonempty_str(action, "text", f"{base}.text", err)
        requires_human_review = action.get("requires_human_review", _MISSING)
        if requires_human_review is _MISSING:
            err(f"{base}.requires_human_review", "missing_field")
        elif not isinstance(requires_human_review, bool):
            err(f"{base}.requires_human_review", "wrong_type")


def _validate_validation(validation: Any, err: Callable[[str, str], None]) -> None:
    # Structural only. Declared commands are recorded, never executed here.
    if validation is _MISSING:
        return
    if not isinstance(validation, list):
        err("$.validation", "wrong_type")
        return
    for i, item in enumerate(validation):
        base = f"$.validation[{i}]"
        if not isinstance(item, dict):
            err(base, "wrong_type")
            continue
        _check_nonempty_str(item, "command", f"{base}.command", err)
        recorded_result = item.get("recorded_result", _MISSING)
        if recorded_result is not _MISSING and not isinstance(recorded_result, str):
            err(f"{base}.recorded_result", "wrong_type")


def _validate_declared_scope(scope: Any, err: Callable[[str, str], None]) -> None:
    if scope is _MISSING:
        return
    if not isinstance(scope, list):
        err("$.declared_scope", "wrong_type")
        return
    for i, entry in enumerate(scope):
        if not isinstance(entry, str):
            err(f"$.declared_scope[{i}]", "wrong_type")
        elif not entry.strip():
            err(f"$.declared_scope[{i}]", "empty_value")


def load_review_submission(path: Union[str, Path]) -> Any:
    """Parse a submission JSON file. Raises on malformed JSON.

    This only parses; call :func:`validate_review_submission` on the result to
    check structure.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))
