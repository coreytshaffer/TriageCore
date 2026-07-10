from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "eval_case_v0"
BOUNDARY_FAMILIES = frozenset(
    {"privacy", "routing", "identity", "provenance", "audit", "human_approval"}
)
CONTROL_PLANE_DECISIONS = frozenset({"allow", "deny", "require_human_approval"})
EVAL_OUTCOMES = frozenset({"pass", "fail", "block"})

REQUIRED_TOP_LEVEL_FIELDS = (
    "schema_version",
    "case_id",
    "boundary_family",
    "title",
    "description",
    "task_packet",
    "policy_expectation",
    "simulated_behavior",
    "expected_control_plane_decision",
    "expected_audit_outcome",
    "expected_eval_outcome",
)


@dataclass(frozen=True)
class EvalFixtureDiagnostic:
    line_number: int
    message: str

    def format(self) -> str:
        return f"line {self.line_number}: {self.message}"


class EvalFixtureValidationError(ValueError):
    """Fail-closed error for invalid safety-boundary eval fixtures."""

    def __init__(self, diagnostics: list[EvalFixtureDiagnostic]) -> None:
        if not diagnostics:
            raise ValueError("diagnostics must be non-empty")
        self.diagnostics = tuple(diagnostics)
        super().__init__(
            "eval fixture validation failed: "
            + "; ".join(diagnostic.format() for diagnostic in self.diagnostics)
        )


def load_eval_fixture_jsonl(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    text = Path(path).read_text(encoding="utf-8")
    return validate_eval_fixture_jsonl_text(text)


def validate_eval_fixture_jsonl_text(text: str) -> tuple[Mapping[str, Any], ...]:
    cases: list[Mapping[str, Any]] = []
    diagnostics: list[EvalFixtureDiagnostic] = []
    seen_case_ids: dict[str, int] = {}

    lines = text.splitlines()
    if not lines:
        diagnostics.append(EvalFixtureDiagnostic(1, "fixture must contain at least one case"))

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            diagnostics.append(
                EvalFixtureDiagnostic(line_number, "empty line is not a JSON object")
            )
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            diagnostics.append(
                EvalFixtureDiagnostic(
                    line_number,
                    f"malformed JSON ({exc.msg})",
                )
            )
            continue

        if not isinstance(payload, Mapping):
            diagnostics.append(
                EvalFixtureDiagnostic(line_number, "case must be a JSON object")
            )
            continue

        case_diagnostics = _validate_case_mapping(payload, line_number)
        diagnostics.extend(case_diagnostics)

        case_id = payload.get("case_id")
        if isinstance(case_id, str) and case_id.strip():
            previous_line = seen_case_ids.get(case_id)
            if previous_line is not None:
                diagnostics.append(
                    EvalFixtureDiagnostic(
                        line_number,
                        f"duplicate case_id: {case_id} (first seen on line {previous_line})",
                    )
                )
            else:
                seen_case_ids[case_id] = line_number

        if not case_diagnostics:
            cases.append(payload)

    if diagnostics:
        raise EvalFixtureValidationError(diagnostics)
    return tuple(cases)


def _validate_case_mapping(
    payload: Mapping[str, Any],
    line_number: int,
) -> list[EvalFixtureDiagnostic]:
    diagnostics: list[EvalFixtureDiagnostic] = []

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            diagnostics.append(EvalFixtureDiagnostic(line_number, f"missing field: {field}"))

    _require_exact_value(
        payload,
        line_number,
        "schema_version",
        SCHEMA_VERSION,
        diagnostics,
    )
    _require_non_empty_text(payload, line_number, "case_id", diagnostics)
    _require_value_in(
        payload,
        line_number,
        "boundary_family",
        BOUNDARY_FAMILIES,
        diagnostics,
    )
    _require_non_empty_text(payload, line_number, "title", diagnostics)
    _require_non_empty_text(payload, line_number, "description", diagnostics)
    _require_value_in(
        payload,
        line_number,
        "expected_control_plane_decision",
        CONTROL_PLANE_DECISIONS,
        diagnostics,
    )
    _require_value_in(
        payload,
        line_number,
        "expected_eval_outcome",
        EVAL_OUTCOMES,
        diagnostics,
    )

    task_packet = _require_object(payload, line_number, "task_packet", diagnostics)
    if task_packet is not None:
        _require_non_empty_text(task_packet, line_number, "task_packet.summary", diagnostics)
        _require_non_empty_text(
            task_packet,
            line_number,
            "task_packet.declared_risk",
            diagnostics,
        )
        _require_object(
            task_packet,
            line_number,
            "task_packet.relevant_metadata",
            diagnostics,
        )

    policy_expectation = _require_object(
        payload,
        line_number,
        "policy_expectation",
        diagnostics,
    )
    if policy_expectation is not None:
        _require_non_empty_text(
            policy_expectation,
            line_number,
            "policy_expectation.boundary_rule",
            diagnostics,
        )
        _require_non_empty_text(
            policy_expectation,
            line_number,
            "policy_expectation.reason",
            diagnostics,
        )

    simulated_behavior = _require_object(
        payload,
        line_number,
        "simulated_behavior",
        diagnostics,
    )
    if simulated_behavior is not None:
        _require_non_empty_text(
            simulated_behavior,
            line_number,
            "simulated_behavior.actor_type",
            diagnostics,
        )
        _require_non_empty_text(
            simulated_behavior,
            line_number,
            "simulated_behavior.proposed_action",
            diagnostics,
        )
        _require_string_list(
            simulated_behavior,
            line_number,
            "simulated_behavior.notable_conditions",
            diagnostics,
        )

    expected_audit_outcome = _require_object(
        payload,
        line_number,
        "expected_audit_outcome",
        diagnostics,
    )
    if expected_audit_outcome is not None:
        _require_string_list(
            expected_audit_outcome,
            line_number,
            "expected_audit_outcome.required_artifacts",
            diagnostics,
        )
        _require_string_list(
            expected_audit_outcome,
            line_number,
            "expected_audit_outcome.forbidden_artifacts",
            diagnostics,
        )
        _require_non_empty_text(
            expected_audit_outcome,
            line_number,
            "expected_audit_outcome.notes",
            diagnostics,
        )

    return diagnostics


def _require_exact_value(
    payload: Mapping[str, Any],
    line_number: int,
    field: str,
    expected: str,
    diagnostics: list[EvalFixtureDiagnostic],
) -> None:
    if field not in payload:
        if "." in field:
            diagnostics.append(EvalFixtureDiagnostic(line_number, f"missing field: {field}"))
        return
    value = payload[field]
    if value != expected:
        diagnostics.append(
            EvalFixtureDiagnostic(line_number, f"{field} must be {expected}")
        )


def _require_value_in(
    payload: Mapping[str, Any],
    line_number: int,
    field: str,
    allowed: frozenset[str],
    diagnostics: list[EvalFixtureDiagnostic],
) -> None:
    if field not in payload:
        if "." in field:
            diagnostics.append(EvalFixtureDiagnostic(line_number, f"missing field: {field}"))
        return
    value = payload[field]
    if not isinstance(value, str) or value not in allowed:
        diagnostics.append(
            EvalFixtureDiagnostic(line_number, f"invalid {field}: {value}")
        )


def _require_non_empty_text(
    payload: Mapping[str, Any],
    line_number: int,
    field: str,
    diagnostics: list[EvalFixtureDiagnostic],
) -> None:
    key = field.rsplit(".", 1)[-1]
    if key not in payload:
        if "." in field:
            diagnostics.append(EvalFixtureDiagnostic(line_number, f"missing field: {field}"))
        return
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        diagnostics.append(
            EvalFixtureDiagnostic(line_number, f"{field} must be a non-empty string")
        )


def _require_object(
    payload: Mapping[str, Any],
    line_number: int,
    field: str,
    diagnostics: list[EvalFixtureDiagnostic],
) -> Mapping[str, Any] | None:
    key = field.rsplit(".", 1)[-1]
    if key not in payload:
        if "." in field:
            diagnostics.append(EvalFixtureDiagnostic(line_number, f"missing field: {field}"))
        return None
    value = payload[key]
    if not isinstance(value, Mapping):
        diagnostics.append(EvalFixtureDiagnostic(line_number, f"{field} must be an object"))
        return None
    return value


def _require_string_list(
    payload: Mapping[str, Any],
    line_number: int,
    field: str,
    diagnostics: list[EvalFixtureDiagnostic],
) -> None:
    key = field.rsplit(".", 1)[-1]
    if key not in payload:
        if "." in field:
            diagnostics.append(EvalFixtureDiagnostic(line_number, f"missing field: {field}"))
        return
    value = payload[key]
    if not isinstance(value, list):
        diagnostics.append(
            EvalFixtureDiagnostic(line_number, f"{field} must be a list of strings")
        )
        return
    if any(not isinstance(item, str) or not item.strip() for item in value):
        diagnostics.append(
            EvalFixtureDiagnostic(line_number, f"{field} must be a list of strings")
        )
