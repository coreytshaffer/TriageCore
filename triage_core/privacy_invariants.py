from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


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
    }
)


@dataclass(frozen=True)
class PrivacyInvariantViolation:
    path: str
    key: str


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

    return violations


def assert_persistent_privacy_safe(
    payload: Any,
    *,
    artifact_name: str = "persistent artifact",
) -> None:
    violations = find_forbidden_persistent_fields(payload)
    if violations:
        raise PersistentPrivacyInvariantError(artifact_name, violations)
