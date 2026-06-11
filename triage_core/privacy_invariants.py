from __future__ import annotations

from typing import Any


PROHIBITED_PERSISTENT_KEYS = {
    "prompt",
    "data",
    "content",
    "raw_prompt",
    "raw_data",
    "message_body",
    "body",
}


class PersistentArtifactPrivacyError(ValueError):
    """Raised when a persistent artifact contains prohibited raw-content keys."""


def validate_persistent_artifact_payload(
    payload: Any,
    *,
    root_path: str = "payload",
) -> None:
    """Reject prohibited raw-content keys without echoing sensitive values."""
    _validate_node(payload, root_path)


def _validate_node(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in PROHIBITED_PERSISTENT_KEYS:
                raise PersistentArtifactPrivacyError(
                    f"Persistent artifact contains prohibited key at '{child_path}'."
                )
            _validate_node(child, child_path)
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_node(item, f"{path}[{index}]")
