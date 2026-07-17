from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from triage_core.eval_fixture_validator import (
    EvalFixtureValidationError,
    load_eval_fixture_jsonl,
)
from triage_core.evaluation_handoff_bundle import (
    ACTUAL_CONTRACT,
    BUNDLE_TYPE,
    FIXTURE_BUNDLE_PATH,
    FIXTURE_CONTRACT,
    HANDOFF_CONTRACT,
    MANIFEST_BUNDLE_PATH,
    MANIFEST_SCHEMA_VERSION,
    EvaluationHandoffBundleError,
    is_safe_case_id,
    validate_actual_outcome_contract,
)
from triage_core.privacy_invariants import (
    PersistentPrivacyInvariantError,
    assert_persistent_privacy_safe,
)


_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_KEYS = {
    "schema_version",
    "bundle_type",
    "handoff_contract",
    "scoring_owner",
    "triagecore_scored",
    "fixture",
    "actuals",
}
_FIXTURE_KEYS = {"contract_identifier", "path", "sha256", "case_count"}
_ACTUALS_KEYS = {"contract_identifier", "count", "entries"}
_ACTUAL_ENTRY_KEYS = {"case_id", "path", "sha256"}


class EvaluationHandoffValidationError(ValueError):
    """Fail-closed validation error with one stable public reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class EvaluationHandoffValidationResult:
    fixture_count: int
    actual_count: int


class _DuplicateObjectKey(ValueError):
    pass


def validate_evaluation_handoff_bundle(
    bundle: str | Path,
) -> EvaluationHandoffValidationResult:
    """Validate an existing CR-127 bundle without mutating it."""

    root = Path(bundle)
    _validate_root(root)
    manifest_path = root / MANIFEST_BUNDLE_PATH
    _validate_manifest_file(manifest_path)
    manifest = _load_manifest(manifest_path)
    fixture_spec, actual_specs = _validate_manifest_schema(manifest)
    _validate_inventory(root, actual_specs)

    fixture_path = root / FIXTURE_BUNDLE_PATH
    fixture_bytes = _read_bytes(fixture_path)
    if _sha256(fixture_bytes) != fixture_spec["sha256"]:
        raise EvaluationHandoffValidationError("hash_mismatch")

    try:
        fixture_cases = load_eval_fixture_jsonl(fixture_path)
    except EvalFixtureValidationError as exc:
        raise EvaluationHandoffValidationError("fixture_invalid") from exc
    except UnicodeError as exc:
        raise EvaluationHandoffValidationError("fixture_invalid") from exc
    except OSError as exc:
        raise EvaluationHandoffValidationError("input_unreadable") from exc

    if len(fixture_cases) != fixture_spec["case_count"]:
        raise EvaluationHandoffValidationError("fixture_count_mismatch")
    try:
        for case in fixture_cases:
            assert_persistent_privacy_safe(case, artifact_name="eval fixture")
    except PersistentPrivacyInvariantError as exc:
        raise EvaluationHandoffValidationError("privacy_invariant_failed") from exc

    fixture_case_ids = {str(case["case_id"]) for case in fixture_cases}
    if any(not is_safe_case_id(case_id) for case_id in fixture_case_ids):
        raise EvaluationHandoffValidationError("unsafe_case_id")

    for spec in actual_specs:
        actual_path = root.joinpath(*spec["path"].split("/"))
        content = _read_bytes(actual_path)
        if _sha256(content) != spec["sha256"]:
            raise EvaluationHandoffValidationError("hash_mismatch")
        try:
            payload = json.loads(
                content.decode("utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise EvaluationHandoffValidationError("actual_invalid_json") from exc
        try:
            validate_actual_outcome_contract(payload)
        except EvaluationHandoffBundleError as exc:
            raise EvaluationHandoffValidationError("actual_invalid_contract") from exc
        case_id = payload["case_id"]
        if not is_safe_case_id(case_id):
            raise EvaluationHandoffValidationError("unsafe_case_id")
        if actual_path.name != f"{case_id}.json" or spec["case_id"] != case_id:
            raise EvaluationHandoffValidationError("actual_filename_mismatch")
        if case_id not in fixture_case_ids:
            raise EvaluationHandoffValidationError("unknown_case_id")
        try:
            assert_persistent_privacy_safe(payload, artifact_name="actual outcome")
        except PersistentPrivacyInvariantError as exc:
            raise EvaluationHandoffValidationError("privacy_invariant_failed") from exc

    if len(actual_specs) != manifest["actuals"]["count"]:
        raise EvaluationHandoffValidationError("actual_count_mismatch")
    return EvaluationHandoffValidationResult(
        fixture_count=len(fixture_cases),
        actual_count=len(actual_specs),
    )


def _validate_root(root: Path) -> None:
    try:
        if _has_link_or_reparse_ancestor(root):
            raise EvaluationHandoffValidationError("bundle_root_symlink")
        try:
            root.lstat()
        except FileNotFoundError:
            raise EvaluationHandoffValidationError("bundle_missing")
        if _is_link_or_reparse(root):
            raise EvaluationHandoffValidationError("bundle_root_symlink")
        if not root.is_dir():
            raise EvaluationHandoffValidationError("bundle_not_directory")
    except EvaluationHandoffValidationError:
        raise
    except OSError as exc:
        raise EvaluationHandoffValidationError("input_unreadable") from exc


def _validate_manifest_file(path: Path) -> None:
    try:
        try:
            path.parent.lstat()
        except FileNotFoundError:
            raise EvaluationHandoffValidationError("manifest_missing")
        if _is_link_or_reparse(path.parent):
            raise EvaluationHandoffValidationError("bundle_symlink")
        try:
            path.lstat()
        except FileNotFoundError:
            raise EvaluationHandoffValidationError("manifest_missing")
        if _is_link_or_reparse(path):
            raise EvaluationHandoffValidationError("bundle_symlink")
        if not path.is_file():
            raise EvaluationHandoffValidationError("manifest_missing")
    except EvaluationHandoffValidationError:
        raise
    except OSError as exc:
        raise EvaluationHandoffValidationError("manifest_unreadable") from exc


def _load_manifest(path: Path) -> Mapping[str, Any]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise EvaluationHandoffValidationError("manifest_unreadable") from exc
    try:
        payload = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, _DuplicateObjectKey, ValueError) as exc:
        raise EvaluationHandoffValidationError("manifest_invalid_json") from exc
    if not isinstance(payload, Mapping):
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    return payload


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateObjectKey(key)
        result[key] = value
    return result


def _reject_json_constant(value: str):
    raise ValueError(value)


def _validate_manifest_schema(
    manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...]]:
    if set(manifest) != _TOP_LEVEL_KEYS:
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    if (
        manifest["schema_version"] != MANIFEST_SCHEMA_VERSION
        or manifest["bundle_type"] != BUNDLE_TYPE
        or manifest["handoff_contract"] != HANDOFF_CONTRACT
        or manifest["scoring_owner"] != "external_evaluator"
        or manifest["triagecore_scored"] is not False
    ):
        raise EvaluationHandoffValidationError("manifest_contract_mismatch")

    fixture = manifest["fixture"]
    actuals = manifest["actuals"]
    if not isinstance(fixture, Mapping) or set(fixture) != _FIXTURE_KEYS:
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    if not isinstance(actuals, Mapping) or set(actuals) != _ACTUALS_KEYS:
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    if (
        fixture["contract_identifier"] != FIXTURE_CONTRACT
        or actuals["contract_identifier"] != ACTUAL_CONTRACT
    ):
        raise EvaluationHandoffValidationError("manifest_contract_mismatch")

    _validate_manifest_path(fixture["path"], expected=FIXTURE_BUNDLE_PATH)
    if not _is_sha256(fixture["sha256"]):
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    if not _is_count(fixture["case_count"]) or fixture["case_count"] < 1:
        raise EvaluationHandoffValidationError("manifest_invalid_schema")

    entries = actuals["entries"]
    if not _is_count(actuals["count"]):
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    if not isinstance(entries, list):
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    if actuals["count"] == 0 or not entries:
        raise EvaluationHandoffValidationError("actual_count_mismatch")
    if actuals["count"] != len(entries):
        raise EvaluationHandoffValidationError("actual_count_mismatch")

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    validated_entries: list[Mapping[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != _ACTUAL_ENTRY_KEYS:
            raise EvaluationHandoffValidationError("manifest_invalid_schema")
        case_id = entry["case_id"]
        if not isinstance(case_id, str) or not is_safe_case_id(case_id):
            raise EvaluationHandoffValidationError("unsafe_case_id")
        if case_id in seen_ids:
            raise EvaluationHandoffValidationError("duplicate_case_id")
        if not isinstance(entry["path"], str):
            raise EvaluationHandoffValidationError("manifest_path_invalid")
        if entry["path"] in seen_paths:
            raise EvaluationHandoffValidationError("duplicate_actual_path")
        expected_path = f"actuals/{case_id}.json"
        _validate_manifest_path(entry["path"], expected=expected_path)
        if not _is_sha256(entry["sha256"]):
            raise EvaluationHandoffValidationError("manifest_invalid_schema")
        seen_ids.add(case_id)
        seen_paths.add(entry["path"])
        validated_entries.append(entry)

    case_ids = [entry["case_id"] for entry in validated_entries]
    if case_ids != sorted(case_ids):
        raise EvaluationHandoffValidationError("manifest_invalid_schema")
    return fixture, tuple(validated_entries)


def _validate_manifest_path(value: Any, *, expected: str) -> None:
    if not isinstance(value, str) or not value:
        raise EvaluationHandoffValidationError("manifest_path_invalid")
    if (
        value != expected
        or "\\" in value
        or value.startswith("/")
        or re.match(r"^[A-Za-z]:", value)
    ):
        raise EvaluationHandoffValidationError("manifest_path_invalid")
    components = value.split("/")
    if any(component in {"", ".", ".."} for component in components):
        raise EvaluationHandoffValidationError("manifest_path_invalid")


def _validate_inventory(
    root: Path,
    actual_specs: tuple[Mapping[str, Any], ...],
) -> None:
    expected_root = {"fixtures", "actuals", "manifest"}
    _require_exact_directory_entries(root, expected_root)
    _require_real_directory(root / "fixtures")
    _require_real_directory(root / "actuals")
    _require_real_directory(root / "manifest")
    _require_exact_directory_entries(
        root / "fixtures",
        {"safety_boundaries_v0.jsonl"},
    )
    _require_exact_directory_entries(
        root / "manifest",
        {"evaluation_handoff_manifest.json"},
    )
    expected_actual_names = {
        f"{spec['case_id']}.json"
        for spec in actual_specs
    }
    _require_exact_directory_entries(root / "actuals", expected_actual_names)

    for path in (
        root / FIXTURE_BUNDLE_PATH,
        root / MANIFEST_BUNDLE_PATH,
        *(root.joinpath(*spec["path"].split("/")) for spec in actual_specs),
    ):
        _require_real_file(path)


def _require_exact_directory_entries(path: Path, expected: set[str]) -> None:
    try:
        entries = list(path.iterdir())
        if any(_is_link_or_reparse(entry) for entry in entries):
            raise EvaluationHandoffValidationError("bundle_symlink")
        actual = {entry.name for entry in entries}
    except EvaluationHandoffValidationError:
        raise
    except FileNotFoundError as exc:
        raise EvaluationHandoffValidationError("declared_file_missing") from exc
    except OSError as exc:
        raise EvaluationHandoffValidationError("input_unreadable") from exc
    if actual != expected:
        missing = expected - actual
        if missing:
            raise EvaluationHandoffValidationError("declared_file_missing")
        raise EvaluationHandoffValidationError("unexpected_bundle_entry")


def _require_real_directory(path: Path) -> None:
    try:
        if _is_link_or_reparse(path):
            raise EvaluationHandoffValidationError("bundle_symlink")
        if not path.is_dir():
            raise EvaluationHandoffValidationError("declared_file_missing")
    except EvaluationHandoffValidationError:
        raise
    except OSError as exc:
        raise EvaluationHandoffValidationError("input_unreadable") from exc


def _require_real_file(path: Path) -> None:
    try:
        if _is_link_or_reparse(path):
            raise EvaluationHandoffValidationError("bundle_symlink")
        if not path.is_file():
            raise EvaluationHandoffValidationError("declared_file_missing")
    except EvaluationHandoffValidationError:
        raise
    except OSError as exc:
        raise EvaluationHandoffValidationError("input_unreadable") from exc


def _is_link_or_reparse(path: Path) -> bool:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _has_link_or_reparse_ancestor(path: Path) -> bool:
    absolute = path.absolute()
    for parent in reversed(absolute.parents):
        if parent == Path(absolute.anchor):
            continue
        try:
            is_link = _is_link_or_reparse(parent)
        except FileNotFoundError:
            continue
        if is_link:
            return True
    return False


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise EvaluationHandoffValidationError("input_unreadable") from exc


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX_SHA256.fullmatch(value))


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
