from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ALLOWED_EXECUTION_CLASSES = {"local", "cloud", "hybrid", "unknown"}
ALLOWED_INTEGRITY_STATUSES = {"complete", "partial", "invalid"}
ALIASED_MODEL_IDENTITIES = {"latest", "default", "unknown"}
REQUIRED_FIELD_PATHS = (
    "$.schema_version",
    "$.route_id",
    "$.display_name",
    "$.boundary.execution_class",
    "$.boundary.network_dependency",
    "$.boundary.intended_privacy_class",
    "$.backend.backend_type",
    "$.backend.wrapper_identity",
    "$.model.exact_model_id",
    "$.model.mutable_reference",
    "$.model.source_channel",
    "$.artifact.digest_required",
    "$.template_behavior.template_source",
    "$.integrity.provenance_complete",
    "$.integrity.integrity_status",
)


@dataclass(frozen=True)
class ManifestIssue:
    reason: str
    path: str
    message: str


@dataclass
class ManifestCheckResult:
    issues: list[ManifestIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def add_issue(self, reason: str, path: str, message: str) -> None:
        issue = ManifestIssue(reason=reason, path=path, message=message)
        if issue not in self.issues:
            self.issues.append(issue)


def load_model_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_model_manifest(manifest: dict[str, Any]) -> ManifestCheckResult:
    result = ManifestCheckResult()
    if not isinstance(manifest, dict):
        result.add_issue(
            "invalid_manifest_root",
            "$",
            "Manifest root must be a JSON object.",
        )
        return result

    for required_path in REQUIRED_FIELD_PATHS:
        value, found = _get_path_value(manifest, required_path)
        if not found:
            result.add_issue(
                "missing_required_field",
                required_path,
                "Required manifest field is missing.",
            )
            continue
        if required_path == "$.boundary.execution_class":
            execution_class = str(value)
            if execution_class not in ALLOWED_EXECUTION_CLASSES:
                result.add_issue(
                    "invalid_execution_class",
                    required_path,
                    "execution_class must be local, cloud, hybrid, or unknown.",
                )
            elif execution_class == "unknown":
                result.add_issue(
                    "boundary_unknown",
                    required_path,
                    "execution_class must not be unknown for an integrity-valid route.",
                )
        elif required_path == "$.integrity.integrity_status":
            integrity_status = str(value)
            if integrity_status not in ALLOWED_INTEGRITY_STATUSES:
                result.add_issue(
                    "invalid_integrity_status",
                    required_path,
                    "integrity_status must be complete, partial, or invalid.",
                )

    exact_model_id = _string_at_path(manifest, "$.model.exact_model_id")
    mutable_reference = _bool_at_path(manifest, "$.model.mutable_reference")
    source_channel = _string_at_path(manifest, "$.model.source_channel")
    source_uri = _string_at_path(manifest, "$.model.source_uri")

    if mutable_reference and exact_model_id.lower() in ALIASED_MODEL_IDENTITIES:
        result.add_issue(
            "alias_only_model_identity",
            "$.model.exact_model_id",
            "Mutable alias values such as latest or default are not sufficient exact model identity.",
        )
    elif mutable_reference and not source_uri and source_channel.lower() == "unknown":
        result.add_issue(
            "alias_only_model_identity",
            "$.model",
            "Mutable model identity must include stronger provenance than an unknown source.",
        )

    digest_required = _bool_at_path(manifest, "$.artifact.digest_required")
    digest = _string_at_path(manifest, "$.artifact.digest")
    if digest_required and not digest:
        result.add_issue(
            "missing_required_digest",
            "$.artifact.digest",
            "digest is required for this manifest but is missing or blank.",
        )

    return result


def summarize_model_manifest_check(
    manifest_path: str | Path,
    manifest: dict[str, Any],
    result: ManifestCheckResult,
) -> str:
    manifest_name = str(manifest_path)
    if result.is_valid:
        return "\n".join(
            [
                "Model manifest check passed",
                f"manifest={manifest_name}",
                f"execution_class={_string_at_path(manifest, '$.boundary.execution_class')}",
                f"backend_type={_string_at_path(manifest, '$.backend.backend_type')}",
                f"exact_model_id={_string_at_path(manifest, '$.model.exact_model_id')}",
                f"integrity_status={_string_at_path(manifest, '$.integrity.integrity_status')}",
            ]
        )

    lines = [
        "Model manifest check failed",
        f"manifest={manifest_name}",
    ]
    for issue in result.issues:
        lines.append(f"reason={issue.reason} path={issue.path}")
    return "\n".join(lines)


def _get_path_value(payload: dict[str, Any], path: str) -> tuple[Any, bool]:
    current: Any = payload
    for segment in path.removeprefix("$.").split("."):
        if not isinstance(current, dict) or segment not in current:
            return None, False
        current = current[segment]
    return current, True


def _string_at_path(payload: dict[str, Any], path: str) -> str:
    value, found = _get_path_value(payload, path)
    if not found or value is None:
        return ""
    return str(value)


def _bool_at_path(payload: dict[str, Any], path: str) -> bool:
    value, found = _get_path_value(payload, path)
    if not found:
        return False
    return bool(value)
