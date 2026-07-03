from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from triage_core.agent_identity import AGENT_ID_PATTERN


SUPPORTED_SCHEMA_VERSION = "1.0.0"
ACTIVE_REVOCATION_STATUS = "active"
ALLOWED_REVOCATION_STATUSES = {
    ACTIVE_REVOCATION_STATUS,
    "revoked",
    "disabled",
    "expired",
}
HIGH_RISK_ACTIONS_REQUIRING_APPROVAL = {
    "access_secrets",
    "credential_rotation",
    "deploy_code",
    "execute_shell",
    "external_api_call",
    "modify_identity_registry",
    "network_access",
    "write_to_main_branch",
}
REQUIRED_FIELD_PATHS = (
    "$.schema_version",
    "$.agent_id",
    "$.owner",
    "$.purpose",
    "$.allowed_actions",
    "$.denied_actions",
    "$.allowed_resources",
    "$.requires_human_approval_for",
    "$.expires_at",
    "$.revocation_status",
)
REQUIRED_STRING_FIELD_PATHS = {
    "$.schema_version",
    "$.agent_id",
    "$.owner",
    "$.purpose",
    "$.expires_at",
    "$.revocation_status",
}
REQUIRED_LIST_FIELD_PATHS = {
    "$.allowed_actions",
    "$.denied_actions",
    "$.allowed_resources",
    "$.requires_human_approval_for",
}


@dataclass(frozen=True)
class AuthorityManifestIssue:
    reason: str
    path: str
    message: str


@dataclass
class AuthorityManifestCheckResult:
    issues: list[AuthorityManifestIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def add_issue(self, reason: str, path: str, message: str) -> None:
        issue = AuthorityManifestIssue(reason=reason, path=path, message=message)
        if issue not in self.issues:
            self.issues.append(issue)


def load_authority_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    return json.loads(path.read_text(encoding="utf-8"))


def validate_authority_manifest(
    manifest: dict[str, Any],
    *,
    now: datetime | None = None,
) -> AuthorityManifestCheckResult:
    result = AuthorityManifestCheckResult()
    if not isinstance(manifest, dict):
        result.add_issue(
            "invalid_manifest_root",
            "$",
            "Authority manifest root must be a JSON object.",
        )
        return result

    for required_path in REQUIRED_FIELD_PATHS:
        value, found = _get_path_value(manifest, required_path)
        if not found:
            result.add_issue(
                "missing_required_field",
                required_path,
                "Required authority manifest field is missing.",
            )
            continue
        if required_path in REQUIRED_STRING_FIELD_PATHS:
            if not isinstance(value, str) or not value.strip():
                result.add_issue(
                    "empty_required_string",
                    required_path,
                    "Required authority manifest string field is empty.",
                )
        elif required_path in REQUIRED_LIST_FIELD_PATHS:
            _validate_string_list(result, value, required_path)

    schema_version = _string_at_path(manifest, "$.schema_version")
    if schema_version and schema_version != SUPPORTED_SCHEMA_VERSION:
        result.add_issue(
            "unsupported_schema_version",
            "$.schema_version",
            f"schema_version must be {SUPPORTED_SCHEMA_VERSION}.",
        )

    agent_id = _string_at_path(manifest, "$.agent_id")
    if agent_id and not AGENT_ID_PATTERN.fullmatch(agent_id):
        result.add_issue(
            "invalid_agent_id",
            "$.agent_id",
            "agent_id must use only letters, numbers, dots, underscores, and hyphens.",
        )

    revocation_status = _string_at_path(manifest, "$.revocation_status")
    if revocation_status:
        if revocation_status not in ALLOWED_REVOCATION_STATUSES:
            result.add_issue(
                "invalid_revocation_status",
                "$.revocation_status",
                "revocation_status must be active, revoked, disabled, or expired.",
            )
        elif revocation_status != ACTIVE_REVOCATION_STATUS:
            result.add_issue(
                "inactive_authority_manifest",
                "$.revocation_status",
                "Only active authority manifests can pass validation.",
            )

    expires_at = _string_at_path(manifest, "$.expires_at")
    if expires_at:
        _validate_expiration(result, expires_at, now=now)

    allowed_actions = set(_list_at_path(manifest, "$.allowed_actions"))
    denied_actions = set(_list_at_path(manifest, "$.denied_actions"))
    approval_gates = set(_list_at_path(manifest, "$.requires_human_approval_for"))
    allowed_resources = set(_list_at_path(manifest, "$.allowed_resources"))

    for action in sorted(allowed_actions & denied_actions):
        result.add_issue(
            "contradictory_action_scope",
            "$.allowed_actions",
            f"Action '{action}' cannot be both allowed and denied.",
        )

    for path, values in (
        ("$.allowed_actions", allowed_actions),
        ("$.allowed_resources", allowed_resources),
    ):
        if "*" in values:
            result.add_issue(
                "wildcard_authority_scope",
                path,
                "Wildcard authority is not allowed in this manifest contract.",
            )

    for action in sorted(allowed_actions & HIGH_RISK_ACTIONS_REQUIRING_APPROVAL):
        if action not in approval_gates:
            result.add_issue(
                "missing_human_approval_gate",
                "$.requires_human_approval_for",
                f"High-risk allowed action '{action}' must require human approval.",
            )

    return result


def summarize_authority_manifest_check(
    manifest_path: str | Path,
    manifest: dict[str, Any],
    result: AuthorityManifestCheckResult,
) -> str:
    manifest_name = str(manifest_path)
    if result.is_valid:
        return "\n".join(
            [
                "Agent authority manifest check passed",
                f"manifest={manifest_name}",
                f"agent_id={_string_at_path(manifest, '$.agent_id')}",
                f"owner={_string_at_path(manifest, '$.owner')}",
                f"revocation_status={_string_at_path(manifest, '$.revocation_status')}",
                f"allowed_actions={len(_list_at_path(manifest, '$.allowed_actions'))}",
                f"denied_actions={len(_list_at_path(manifest, '$.denied_actions'))}",
                f"approval_gates={len(_list_at_path(manifest, '$.requires_human_approval_for'))}",
                (
                    "boundary=structural review evidence only; not approval, "
                    "permission, authorization, a capability grant, or a "
                    "substitute for human approval of one exact canonicalized "
                    "action packet"
                ),
            ]
        )

    lines = [
        "Agent authority manifest check failed",
        f"manifest={manifest_name}",
    ]
    for issue in result.issues:
        lines.append(f"reason={issue.reason} path={issue.path}")
    return "\n".join(lines)


def _validate_string_list(
    result: AuthorityManifestCheckResult,
    value: Any,
    path: str,
) -> None:
    if not isinstance(value, list):
        result.add_issue(
            "invalid_list_field",
            path,
            "Required authority manifest list field must be a list.",
        )
        return

    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            result.add_issue(
                "invalid_list_item",
                f"{path}[{index}]",
                "Authority manifest list items must be non-empty strings.",
            )


def _validate_expiration(
    result: AuthorityManifestCheckResult,
    expires_at: str,
    *,
    now: datetime | None,
) -> None:
    try:
        parsed = _parse_datetime(expires_at)
    except ValueError:
        result.add_issue(
            "invalid_expires_at",
            "$.expires_at",
            "expires_at must be an ISO-8601 timestamp with timezone.",
        )
        return

    if parsed.tzinfo is None:
        result.add_issue(
            "invalid_expires_at",
            "$.expires_at",
            "expires_at must include timezone information.",
        )
        return

    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    if parsed <= reference_time.astimezone(parsed.tzinfo):
        result.add_issue(
            "expired_authority_manifest",
            "$.expires_at",
            "Authority manifest has expired.",
        )


def _parse_datetime(value: str) -> datetime:
    normalized = value
    if value.endswith("Z"):
        normalized = value[:-1] + "+00:00"
    return datetime.fromisoformat(normalized)


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


def _list_at_path(payload: dict[str, Any], path: str) -> list[str]:
    value, found = _get_path_value(payload, path)
    if not found or not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
