from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from triage_core.privacy_scanner import (
    CC_CANDIDATE_REGEX,
    EMAIL_REGEX,
    LAT_LON_REGEX,
    PHONE_REGEX,
    SECRET_KEYS_REGEX,
    SSN_REGEX,
    is_valid_luhn,
)


FORBIDDEN_PERSISTENT_KEYS = frozenset(
    {
        "prompt",
        "data",
        "content",
        "raw_prompt",
        "raw_data",
        "raw_content",
        "raw_task",
        "raw_request",
        "raw_response",
        "messages",
        "conversation",
        "conversation_history",
        "user_prompt",
        "system_prompt",
        "developer_prompt",
        "api_key",
        "access_token",
        "authorization",
        "bearer",
        "client_secret",
        "private_key",
        "secret",
        "token",
    }
)


@dataclass(frozen=True)
class PrivacyInvariantViolation:
    path: str
    key: str
    reason: str = "forbidden_key"


class PersistentPrivacyInvariantError(ValueError):
    """Raised when a persistent artifact contains forbidden raw-content fields."""

    def __init__(
        self,
        artifact_name: str,
        violations: list[PrivacyInvariantViolation],
    ) -> None:
        self.artifact_name = artifact_name
        self.violations = violations
        paths = ", ".join(violation.path for violation in violations)
        super().__init__(
            f"{artifact_name} violates persistent privacy invariant: {paths}"
        )


def find_forbidden_persistent_fields(
    value: Any,
    *,
    path: str = "$",
) -> list[PrivacyInvariantViolation]:
    violations: list[PrivacyInvariantViolation] = []

    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_path = (
                f"{path}.{key_text}"
                if key_text.isidentifier()
                else f"{path}[{key_text!r}]"
            )

            if key_text in FORBIDDEN_PERSISTENT_KEYS:
                violations.append(
                    PrivacyInvariantViolation(path=child_path, key=key_text)
                )

            violations.extend(
                find_forbidden_persistent_fields(child, path=child_path)
            )
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for index, child in enumerate(value):
            violations.extend(
                find_forbidden_persistent_fields(child, path=f"{path}[{index}]")
            )
    elif isinstance(value, str):
        reason = _sensitive_persistent_value_reason(value)
        if reason:
            violations.append(
                PrivacyInvariantViolation(
                    path=path,
                    key="<sensitive_value>",
                    reason=reason,
                )
            )

    return violations


def _sensitive_persistent_value_reason(value: str) -> str | None:
    if SSN_REGEX.search(value):
        return "ssn_pattern"
    if EMAIL_REGEX.search(value):
        return "email_pattern"
    if PHONE_REGEX.search(value):
        return "phone_pattern"
    if SECRET_KEYS_REGEX.search(value):
        return "secret_pattern"
    if LAT_LON_REGEX.search(value):
        return "precise_location_pattern"
    if any(is_valid_luhn(match.group()) for match in CC_CANDIDATE_REGEX.finditer(value)):
        return "credit_card_pattern"
    return None


def assert_persistent_privacy_safe(
    payload: Any,
    *,
    artifact_name: str = "persistent artifact",
) -> None:
    violations = find_forbidden_persistent_fields(payload)
    if violations:
        raise PersistentPrivacyInvariantError(artifact_name, violations)
