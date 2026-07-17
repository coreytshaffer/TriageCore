from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from triage_core.eval_fixture_validator import (
    EvalFixtureValidationError,
    load_eval_fixture_jsonl,
)
from triage_core.privacy_invariants import (
    PersistentPrivacyInvariantError,
    assert_persistent_privacy_safe,
)


MANIFEST_SCHEMA_VERSION = "evaluation_handoff_manifest.v0"
BUNDLE_TYPE = "evaluation_handoff"
HANDOFF_CONTRACT = "evaluation_handoff_contract.v0"
FIXTURE_CONTRACT = "eval_case_v0"
ACTUAL_CONTRACT = "actual_outcome_export.v0"
FIXTURE_BUNDLE_PATH = "fixtures/safety_boundaries_v0.jsonl"
MANIFEST_BUNDLE_PATH = "manifest/evaluation_handoff_manifest.json"
SAFE_CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_ACTUAL_REQUIRED_FIELDS = (
    "case_id",
    "decision",
    "boundary_family",
    "reasons",
    "audit_required",
    "human_approval_required",
)


class EvaluationHandoffBundleError(ValueError):
    """Fail-closed bundle construction error with a stable public reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class EvaluationHandoffBundleResult:
    output_dir: Path
    fixture_count: int
    actual_count: int


@dataclass(frozen=True)
class _ActualInput:
    case_id: str
    content: bytes
    sha256: str


def build_evaluation_handoff_bundle(
    fixture: str | Path,
    actuals_dir: str | Path,
    out_dir: str | Path,
) -> EvaluationHandoffBundleResult:
    """Build a deterministic, unscored evaluation handoff bundle."""

    fixture_path = Path(fixture)
    actuals_path = Path(actuals_dir)
    output_path = Path(out_dir)

    _validate_fixture_path(fixture_path)
    _validate_actuals_directory(actuals_path)
    _validate_output_path(output_path)
    _validate_no_path_conflict(fixture_path, actuals_path, output_path)

    try:
        fixture_cases = load_eval_fixture_jsonl(fixture_path)
    except EvalFixtureValidationError as exc:
        raise EvaluationHandoffBundleError("fixture_invalid") from exc
    except UnicodeError as exc:
        raise EvaluationHandoffBundleError("fixture_invalid") from exc
    except OSError as exc:
        raise EvaluationHandoffBundleError("input_unreadable") from exc

    try:
        for case in fixture_cases:
            assert_persistent_privacy_safe(case, artifact_name="eval fixture")
    except PersistentPrivacyInvariantError as exc:
        raise EvaluationHandoffBundleError("privacy_invariant_failed") from exc

    if any(
        not is_safe_case_id(str(case["case_id"]))
        for case in fixture_cases
    ):
        raise EvaluationHandoffBundleError("unsafe_case_id")

    try:
        fixture_content = fixture_path.read_bytes()
    except OSError as exc:
        raise EvaluationHandoffBundleError("input_unreadable") from exc

    fixture_case_ids = {str(case["case_id"]) for case in fixture_cases}
    actuals = _load_actuals(actuals_path, fixture_case_ids)
    manifest = _build_manifest(fixture_content, len(fixture_cases), actuals)

    stage_path: Path | None = None
    try:
        stage_path = Path(
            tempfile.mkdtemp(
                prefix=f".{output_path.name}.",
                dir=output_path.parent,
            )
        )
        fixture_output = stage_path / FIXTURE_BUNDLE_PATH
        fixture_output.parent.mkdir()
        fixture_output.write_bytes(fixture_content)

        actuals_output = stage_path / "actuals"
        actuals_output.mkdir()
        for actual in actuals:
            (actuals_output / f"{actual.case_id}.json").write_bytes(actual.content)

        manifest_output = stage_path / MANIFEST_BUNDLE_PATH
        manifest_output.parent.mkdir()
        manifest_output.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        stage_path.rename(output_path)
        stage_path = None
    except OSError as exc:
        raise EvaluationHandoffBundleError("write_failed") from exc
    finally:
        if stage_path is not None:
            shutil.rmtree(stage_path, ignore_errors=True)

    return EvaluationHandoffBundleResult(
        output_dir=output_path,
        fixture_count=len(fixture_cases),
        actual_count=len(actuals),
    )


def _validate_fixture_path(path: Path) -> None:
    try:
        if not path.exists():
            raise EvaluationHandoffBundleError("input_missing")
        if path.is_symlink() or not path.is_file():
            raise EvaluationHandoffBundleError("input_not_regular_file")
    except OSError as exc:
        raise EvaluationHandoffBundleError("input_unreadable") from exc


def _validate_actuals_directory(path: Path) -> None:
    try:
        if not path.exists() or path.is_symlink() or not path.is_dir():
            raise EvaluationHandoffBundleError("actuals_directory_missing")
    except OSError as exc:
        raise EvaluationHandoffBundleError("actuals_directory_missing") from exc


def _validate_output_path(path: Path) -> None:
    try:
        if path.exists() or path.is_symlink():
            raise EvaluationHandoffBundleError("output_exists")
        if (
            not path.parent.exists()
            or path.parent.is_symlink()
            or not path.parent.is_dir()
        ):
            raise EvaluationHandoffBundleError("output_parent_missing")
    except OSError as exc:
        raise EvaluationHandoffBundleError("output_parent_missing") from exc


def _validate_no_path_conflict(
    fixture_path: Path,
    actuals_path: Path,
    output_path: Path,
) -> None:
    try:
        fixture_resolved = fixture_path.resolve(strict=True)
        actuals_resolved = actuals_path.resolve(strict=True)
        output_resolved = output_path.resolve(strict=False)
    except OSError as exc:
        raise EvaluationHandoffBundleError("path_conflict") from exc

    if _paths_overlap(fixture_resolved, output_resolved) or _paths_overlap(
        actuals_resolved,
        output_resolved,
    ):
        raise EvaluationHandoffBundleError("path_conflict")


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _load_actuals(
    actuals_path: Path,
    fixture_case_ids: set[str],
) -> tuple[_ActualInput, ...]:
    try:
        entries = list(actuals_path.iterdir())
    except OSError as exc:
        raise EvaluationHandoffBundleError("input_unreadable") from exc

    if not entries:
        raise EvaluationHandoffBundleError("actuals_empty")

    loaded: list[_ActualInput] = []
    seen_case_ids: set[str] = set()
    for path in sorted(entries, key=lambda entry: entry.name):
        try:
            if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
                raise EvaluationHandoffBundleError("unexpected_actuals_entry")
            content = path.read_bytes()
        except EvaluationHandoffBundleError:
            raise
        except OSError as exc:
            raise EvaluationHandoffBundleError("input_unreadable") from exc

        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise EvaluationHandoffBundleError("actual_invalid_json") from exc

        validate_actual_outcome_contract(payload)
        case_id = payload["case_id"]
        if not is_safe_case_id(case_id):
            raise EvaluationHandoffBundleError("unsafe_case_id")
        if case_id in seen_case_ids:
            raise EvaluationHandoffBundleError("duplicate_case_id")
        if path.name != f"{case_id}.json":
            raise EvaluationHandoffBundleError("actual_filename_mismatch")
        if case_id not in fixture_case_ids:
            raise EvaluationHandoffBundleError("unknown_case_id")
        try:
            assert_persistent_privacy_safe(payload, artifact_name="actual outcome")
        except PersistentPrivacyInvariantError as exc:
            raise EvaluationHandoffBundleError("privacy_invariant_failed") from exc

        seen_case_ids.add(case_id)
        loaded.append(
            _ActualInput(
                case_id=case_id,
                content=content,
                sha256=hashlib.sha256(content).hexdigest(),
            )
        )

    return tuple(sorted(loaded, key=lambda actual: actual.case_id))


def is_safe_case_id(case_id: str) -> bool:
    return bool(SAFE_CASE_ID_PATTERN.fullmatch(case_id))


def validate_actual_outcome_contract(payload: Any) -> None:
    """Validate the CR-127 broad actual-outcome shape without adding enums."""

    if not isinstance(payload, Mapping):
        raise EvaluationHandoffBundleError("actual_invalid_contract")
    if any(field not in payload for field in _ACTUAL_REQUIRED_FIELDS):
        raise EvaluationHandoffBundleError("actual_invalid_contract")
    if not isinstance(payload["case_id"], str) or not payload["case_id"]:
        raise EvaluationHandoffBundleError("actual_invalid_contract")
    if not isinstance(payload["decision"], str) or not payload["decision"]:
        raise EvaluationHandoffBundleError("actual_invalid_contract")
    if (
        not isinstance(payload["boundary_family"], str)
        or not payload["boundary_family"]
    ):
        raise EvaluationHandoffBundleError("actual_invalid_contract")
    reasons = payload["reasons"]
    if not isinstance(reasons, list) or any(
        not isinstance(reason, str) for reason in reasons
    ):
        raise EvaluationHandoffBundleError("actual_invalid_contract")
    if not isinstance(payload["audit_required"], bool):
        raise EvaluationHandoffBundleError("actual_invalid_contract")
    if not isinstance(payload["human_approval_required"], bool):
        raise EvaluationHandoffBundleError("actual_invalid_contract")


def _build_manifest(
    fixture_content: bytes,
    fixture_count: int,
    actuals: tuple[_ActualInput, ...],
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "bundle_type": BUNDLE_TYPE,
        "handoff_contract": HANDOFF_CONTRACT,
        "scoring_owner": "external_evaluator",
        "triagecore_scored": False,
        "fixture": {
            "contract_identifier": FIXTURE_CONTRACT,
            "path": FIXTURE_BUNDLE_PATH,
            "sha256": hashlib.sha256(fixture_content).hexdigest(),
            "case_count": fixture_count,
        },
        "actuals": {
            "contract_identifier": ACTUAL_CONTRACT,
            "count": len(actuals),
            "entries": [
                {
                    "case_id": actual.case_id,
                    "path": f"actuals/{actual.case_id}.json",
                    "sha256": actual.sha256,
                }
                for actual in actuals
            ],
        },
    }
