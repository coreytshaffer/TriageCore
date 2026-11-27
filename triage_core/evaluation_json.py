from __future__ import annotations

import json
from typing import Any


class EvaluationJSONDecodeError(ValueError):
    """A JSON decode error whose message is safe to report."""


def decode_evaluation_json(content: str | bytes) -> Any:
    """Decode evaluation JSON with unique object keys and standard constants."""
    try:
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except EvaluationJSONDecodeError:
        raise
    except json.JSONDecodeError as exc:
        raise EvaluationJSONDecodeError(f"malformed JSON ({exc.msg})") from None
    except (ValueError, RecursionError):
        raise EvaluationJSONDecodeError("malformed JSON") from None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationJSONDecodeError("malformed JSON (duplicate object key)")
        result[key] = value
    return result


def _reject_constant(_token: str) -> None:
    raise EvaluationJSONDecodeError("malformed JSON (non-standard numeric constant)")
