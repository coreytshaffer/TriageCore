"""Deterministic, metadata-only artifacts for governed run-plan review."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from triage_core.privacy_invariants import (
    PersistentPrivacyInvariantError,
    assert_persistent_privacy_safe,
)


CONTRACT_VERSION = "governed_run_plan.v1"
CANONICALIZATION_VERSION = "triagecore_canonical_json.v1"
PLANNER_CONTRACT_VERSION = "governed_run_plan_preview.v1"
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
TASK_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")

_ARTIFACT_KEYS = frozenset(
    {
        "canonicalization_version",
        "contract_version",
        "plan_body",
        "plan_body_digest",
    }
)
_PLAN_BODY_KEYS = frozenset(
    {
        "assembled_input_binding",
        "classification_forecast",
        "cloud_intent",
        "configuration_binding",
        "context_budget",
        "declared_model_profile",
        "declared_privacy_class",
        "ethical_firewall",
        "execution_authority",
        "execution_evidence",
        "inline_input_binding",
        "planner_contract_version",
        "route_forecast",
        "source_bindings",
        "task_id",
        "task_instruction_binding",
        "verification_posture",
    }
)
_BINDING_KEYS = frozenset({"byte_length", "sha256"})
_SOURCE_KEYS = frozenset(
    {"byte_length", "content_sha256", "locator_sha256", "ordinal"}
)
_CLASSIFICATION_KEYS = frozenset(
    {"category", "recommended_profile", "risk_level"}
)
_CONFIGURATION_KEYS = frozenset(
    {
        "backend_binding",
        "cloud_backend_enabled",
        "cloud_model_binding",
        "local_backend_type",
        "specialist_model_forecast",
        "specialist_timeout_seconds",
    }
)
_CONTEXT_BUDGET_KEYS = frozenset(
    {"estimated_input_tokens", "status", "usable_input_budget"}
)
_ETHICAL_FIREWALL_KEYS = frozenset({"recommended_escalation", "status"})
_ROUTE_KEYS = frozenset(
    {"fallback_depth", "human_review_required", "reason_code", "route"}
)
_VERIFICATION_KEYS = frozenset(
    {
        "output_validation",
        "packet_verification",
        "privacy_preflight",
        "route_required_checks",
    }
)
_CONFIRMATION_KEYS = frozenset(
    {
        "artifact_accepted",
        "artifact_byte_digest",
        "cloud_authorization",
        "contract_version",
        "decision",
        "ethical_firewall_status",
        "execution_authority",
        "general_approval",
        "human_review_gate_satisfied",
        "plan_body_digest",
        "route_posture",
        "task_id",
    }
)
_CLASSIFICATIONS = frozenset(
    {
        "architecture_planning",
        "blocked_or_high_risk",
        "bugfix",
        "docs_update",
        "packaging",
        "refactor",
        "security_review",
        "test_addition",
    }
)
_PROFILES = frozenset(
    {
        "blocked",
        "read-only",
        "workspace-write",
        "workspace-write-with-approval",
    }
)
_ROUTES = frozenset(
    {
        "cloud_primary",
        "cloud_secondary",
        "deterministic",
        "human_handoff",
        "local_fast",
        "local_heavy",
    }
)
_ROUTE_REASONS = frozenset(
    {
        "cloud_primary_available_after_local_routes_unavailable",
        "cloud_primary_degraded_using_secondary",
        "cloud_primary_healthy_for_high_complexity_task",
        "cloud_secondary_available_after_local_routes_unavailable",
        "deterministic_tool_available_as_last_automated_route",
        "deterministic_tool_available_for_task_class",
        "ethical_firewall_requires_human_review",
        "local_fast_available_after_preferred_route_unavailable",
        "local_fast_available_for_small_or_repetitive_task",
        "local_heavy_available_after_preferred_route_unavailable",
        "local_heavy_available_for_medium_or_complex_task",
        "no_reliable_automated_route_available",
        "sensitivity_requires_human_review",
    }
)
_ESCALATIONS = frozenset(
    {"antigravity", "codex", "configured_human_review", "human_only", "none"}
)
_CONFIRMATION_FALSE_FIELDS = (
    "artifact_accepted",
    "cloud_authorization",
    "execution_authority",
    "general_approval",
    "human_review_gate_satisfied",
)


class RunPlanArtifactError(ValueError):
    """Fail-closed artifact validation or publication error."""


def _reject_float(_value: str) -> None:
    raise RunPlanArtifactError("floats are not supported")


def _reject_constant(_value: str) -> None:
    raise RunPlanArtifactError("non-finite numbers are not supported")


def _object_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise RunPlanArtifactError("duplicate object key")
        value[key] = child
    return value


def _validate_canonical_value(value: Any) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise RunPlanArtifactError("floats are not supported")
    if isinstance(value, list):
        for child in value:
            _validate_canonical_value(child)
        return
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise RunPlanArtifactError("object keys must be strings")
        for child in value.values():
            _validate_canonical_value(child)
        return
    raise RunPlanArtifactError(
        f"unsupported canonical JSON type: {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    _validate_canonical_value(value)
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def sha256_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _assert_privacy_safe(value: Any, *, artifact_name: str) -> None:
    try:
        assert_persistent_privacy_safe(value, artifact_name=artifact_name)
    except PersistentPrivacyInvariantError as exc:
        raise RunPlanArtifactError("persistent privacy invariant failed") from exc


def _binding(value: str) -> dict[str, Any]:
    encoded = value.encode("utf-8")
    return {"byte_length": len(encoded), "sha256": sha256_digest(encoded)}


def build_artifact(
    *,
    plan: Mapping[str, Any],
    prompt: str,
    assembled_input: str,
    inline_input: str,
    source_values: Sequence[tuple[str, str]],
) -> tuple[dict[str, Any], bytes, str, str]:
    task_id = str(plan["task_id"])
    if not TASK_ID_RE.fullmatch(task_id):
        raise RunPlanArtifactError("task ID is not artifact-safe")

    source_bindings = []
    for ordinal, (locator, content) in enumerate(source_values, 1):
        source_bindings.append(
            {
                "byte_length": len(content.encode("utf-8")),
                "content_sha256": sha256_digest(content.encode("utf-8")),
                "locator_sha256": sha256_digest(locator.encode("utf-8")),
                "ordinal": ordinal,
            }
        )

    plan_body = {
        "assembled_input_binding": _binding(assembled_input),
        "classification_forecast": {
            "category": str(plan["classification"]),
            "recommended_profile": str(plan["recommended_profile"]),
            "risk_level": str(plan["risk_level"]),
        },
        "cloud_intent": bool(plan["cloud_authorized"]),
        "configuration_binding": {
            "backend_binding": str(plan["backend_binding"]),
            "cloud_backend_enabled": bool(plan["cloud_backend_enabled"]),
            "cloud_model_binding": str(plan["cloud_model_binding"]),
            "local_backend_type": str(plan["local_backend_type"]),
            "specialist_model_forecast": str(plan["specialist_model"]),
            "specialist_timeout_seconds": int(plan["specialist_timeout"]),
        },
        "context_budget": {
            "estimated_input_tokens": int(plan["estimated_tokens"]),
            "status": str(plan["budget_status"]),
            "usable_input_budget": int(plan["usable_budget"]),
        },
        "declared_model_profile": str(plan["model_profile"]),
        "declared_privacy_class": str(plan["privacy"]),
        "ethical_firewall": {
            "recommended_escalation": str(
                plan["ethical_firewall_recommended_escalation"]
            ),
            "status": str(plan["ethical_firewall_status"]),
        },
        "execution_authority": False,
        "execution_evidence": False,
        "inline_input_binding": _binding(inline_input),
        "planner_contract_version": PLANNER_CONTRACT_VERSION,
        "route_forecast": {
            "fallback_depth": int(plan["fallback_depth"]),
            "human_review_required": bool(plan["human_review_required"]),
            "reason_code": str(plan["reason"]),
            "route": str(plan["route"]),
        },
        "source_bindings": source_bindings,
        "task_id": task_id,
        "task_instruction_binding": _binding(prompt),
        "verification_posture": {
            "output_validation": "not_configured",
            "packet_verification": "required",
            "privacy_preflight": "required",
            "route_required_checks": list(plan["required_checks"]),
        },
    }
    _validate_plan_body(plan_body)
    _assert_privacy_safe(plan_body, artifact_name="governed run plan body")
    body_digest = sha256_digest(canonical_json_bytes(plan_body))
    artifact = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "contract_version": CONTRACT_VERSION,
        "plan_body": plan_body,
        "plan_body_digest": body_digest,
    }
    _assert_privacy_safe(artifact, artifact_name="governed run plan artifact")
    artifact_bytes = canonical_json_bytes(artifact)
    artifact_digest = sha256_digest(artifact_bytes)
    return artifact, artifact_bytes, body_digest, artifact_digest


def _require_exact_keys(
    value: Any, keys: frozenset[str], label: str
) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise RunPlanArtifactError(f"invalid closed {label} schema")
    return value


def _validate_binding(value: Any, label: str) -> None:
    item = _require_exact_keys(value, _BINDING_KEYS, label)
    if (
        not isinstance(item["byte_length"], int)
        or isinstance(item["byte_length"], bool)
        or item["byte_length"] < 0
        or not isinstance(item["sha256"], str)
        or not DIGEST_RE.fullmatch(item["sha256"])
    ):
        raise RunPlanArtifactError(f"invalid {label}")


def _require_int(value: Any, label: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RunPlanArtifactError(f"invalid {label}")
    return value


def _require_string(
    value: Any,
    label: str,
    *,
    allowed: frozenset[str] | None = None,
    maximum_length: int = 256,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum_length
        or any(ord(character) < 32 for character in value)
    ):
        raise RunPlanArtifactError(f"invalid {label}")
    if allowed is not None and value not in allowed:
        raise RunPlanArtifactError(f"invalid {label}")
    return value


def _validate_plan_body(body: dict[str, Any]) -> None:
    task_id = body["task_id"]
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise RunPlanArtifactError("invalid task ID")
    if body["planner_contract_version"] != PLANNER_CONTRACT_VERSION:
        raise RunPlanArtifactError("unsupported planner contract version")
    if (
        body["execution_authority"] is not False
        or body["execution_evidence"] is not False
    ):
        raise RunPlanArtifactError("artifact cannot grant execution authority")

    for key in (
        "assembled_input_binding",
        "inline_input_binding",
        "task_instruction_binding",
    ):
        _validate_binding(body[key], key)

    if not isinstance(body["cloud_intent"], bool):
        raise RunPlanArtifactError("invalid cloud intent")
    _require_string(
        body["declared_model_profile"],
        "declared model profile",
        maximum_length=128,
    )
    _require_string(
        body["declared_privacy_class"],
        "declared privacy class",
        allowed=frozenset({"external_safe", "local_only", "public"}),
    )

    classification = _require_exact_keys(
        body["classification_forecast"],
        _CLASSIFICATION_KEYS,
        "classification forecast",
    )
    _require_string(
        classification["category"],
        "classification category",
        allowed=_CLASSIFICATIONS,
    )
    _require_string(
        classification["recommended_profile"],
        "recommended profile",
        allowed=_PROFILES,
    )
    _require_string(
        classification["risk_level"],
        "risk level",
        allowed=frozenset({"high", "low", "medium"}),
    )

    configuration = _require_exact_keys(
        body["configuration_binding"],
        _CONFIGURATION_KEYS,
        "configuration binding",
    )
    _require_string(
        configuration["backend_binding"], "backend binding", maximum_length=256
    )
    if not isinstance(configuration["cloud_backend_enabled"], bool):
        raise RunPlanArtifactError("invalid cloud backend posture")
    _require_string(
        configuration["cloud_model_binding"],
        "cloud model binding",
        maximum_length=256,
    )
    if configuration["cloud_backend_enabled"] == (
        configuration["cloud_model_binding"] == "not_enabled"
    ):
        raise RunPlanArtifactError("inconsistent cloud backend binding")
    _require_string(
        configuration["local_backend_type"],
        "local backend type",
        maximum_length=128,
    )
    _require_string(
        configuration["specialist_model_forecast"],
        "specialist model forecast",
        maximum_length=256,
    )
    _require_int(
        configuration["specialist_timeout_seconds"],
        "specialist timeout",
        minimum=1,
    )

    budget = _require_exact_keys(
        body["context_budget"], _CONTEXT_BUDGET_KEYS, "context budget"
    )
    _require_int(budget["estimated_input_tokens"], "estimated input tokens")
    _require_int(budget["usable_input_budget"], "usable input budget")
    _require_string(
        budget["status"],
        "context budget status",
        allowed=frozenset({"fits", "over_budget"}),
    )

    firewall = _require_exact_keys(
        body["ethical_firewall"],
        _ETHICAL_FIREWALL_KEYS,
        "ethical firewall",
    )
    _require_string(
        firewall["recommended_escalation"],
        "ethical firewall escalation",
        allowed=_ESCALATIONS,
    )
    _require_string(
        firewall["status"],
        "ethical firewall status",
        allowed=frozenset({"clear", "triggered"}),
    )

    route = _require_exact_keys(
        body["route_forecast"], _ROUTE_KEYS, "route forecast"
    )
    _require_int(route["fallback_depth"], "fallback depth")
    if not isinstance(route["human_review_required"], bool):
        raise RunPlanArtifactError("invalid human review posture")
    _require_string(route["reason_code"], "route reason", allowed=_ROUTE_REASONS)
    _require_string(route["route"], "route", allowed=_ROUTES)
    if route["route"].startswith("cloud_") and (
        not body["cloud_intent"] or not configuration["cloud_backend_enabled"]
    ):
        raise RunPlanArtifactError("cloud route lacks declared posture")
    if firewall["status"] == "triggered" and (
        route["route"] != "human_handoff"
        or route["human_review_required"] is not True
        or route["reason_code"] != "ethical_firewall_requires_human_review"
    ):
        raise RunPlanArtifactError("ethical firewall posture is inconsistent")

    verification = _require_exact_keys(
        body["verification_posture"],
        _VERIFICATION_KEYS,
        "verification posture",
    )
    for key, expected in (
        ("output_validation", "not_configured"),
        ("packet_verification", "required"),
        ("privacy_preflight", "required"),
    ):
        if verification[key] != expected:
            raise RunPlanArtifactError(f"invalid {key}")
    checks = verification["route_required_checks"]
    if (
        not isinstance(checks, list)
        or len(checks) > 32
        or any(
            not isinstance(check, str)
            or not check
            or len(check) > 128
            or not re.fullmatch(r"[a-z0-9][a-z0-9._:-]*", check)
            for check in checks
        )
    ):
        raise RunPlanArtifactError("invalid route required checks")

    if not isinstance(body["source_bindings"], list):
        raise RunPlanArtifactError("invalid source bindings")
    for ordinal, source in enumerate(body["source_bindings"], 1):
        item = _require_exact_keys(source, _SOURCE_KEYS, "source binding")
        if item["ordinal"] != ordinal:
            raise RunPlanArtifactError("source bindings are not ordered")
        _require_int(item["byte_length"], "source byte length")
        for digest_key in ("content_sha256", "locator_sha256"):
            if not isinstance(item[digest_key], str) or not DIGEST_RE.fullmatch(
                item[digest_key]
            ):
                raise RunPlanArtifactError("invalid source digest")


def validate_artifact_bytes(
    artifact_bytes: bytes,
) -> tuple[dict[str, Any], str, str]:
    if artifact_bytes.startswith(b"\xef\xbb\xbf") or artifact_bytes.endswith(b"\n"):
        raise RunPlanArtifactError("artifact has a BOM or trailing newline")
    try:
        text = artifact_bytes.decode("ascii")
        artifact = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunPlanArtifactError("artifact is not canonical JSON") from exc
    if canonical_json_bytes(artifact) != artifact_bytes:
        raise RunPlanArtifactError("artifact bytes are noncanonical")

    root = _require_exact_keys(artifact, _ARTIFACT_KEYS, "artifact")
    if root["contract_version"] != CONTRACT_VERSION:
        raise RunPlanArtifactError("unsupported artifact contract version")
    if root["canonicalization_version"] != CANONICALIZATION_VERSION:
        raise RunPlanArtifactError("unsupported canonicalization version")
    body = _require_exact_keys(root["plan_body"], _PLAN_BODY_KEYS, "plan body")
    _validate_plan_body(body)
    embedded = root["plan_body_digest"]
    if not isinstance(embedded, str) or not DIGEST_RE.fullmatch(embedded):
        raise RunPlanArtifactError("invalid plan body digest")
    expected_body = sha256_digest(canonical_json_bytes(body))
    if embedded != expected_body:
        raise RunPlanArtifactError("plan body digest mismatch")
    _assert_privacy_safe(artifact, artifact_name="governed run plan artifact")
    return artifact, embedded, sha256_digest(artifact_bytes)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_unlinked_input_chain(path: Path) -> None:
    supplied = path if path.is_absolute() else Path.cwd() / path
    current = Path(supplied.anchor)
    for part in supplied.parts[1:]:
        if part in ("", "."):
            continue
        if part == "..":
            current = current.parent
            continue
        current = current / part
        if (current.exists() or current.is_symlink()) and _is_link_or_reparse(
            current
        ):
            raise RunPlanArtifactError("plan output parent chain is linked")


def validate_output_path(
    output: str | Path,
    *,
    protected_directories: Iterable[str | Path],
) -> Path:
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise RunPlanArtifactError("plan output already exists")
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        raise RunPlanArtifactError("plan output parent does not exist")
    _assert_unlinked_input_chain(parent)
    absolute_parent = parent.resolve(strict=True)
    resolved_target = absolute_parent / target.name
    for protected in protected_directories:
        protected_path = Path(protected).resolve(strict=False)
        if _is_relative_to(resolved_target, protected_path):
            raise RunPlanArtifactError("plan output is inside protected state")
    return resolved_target


def publish_artifact(
    output: str | Path,
    artifact_bytes: bytes,
    *,
    protected_directories: Iterable[str | Path],
) -> Path:
    target = validate_output_path(
        output, protected_directories=protected_directories
    )
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
        )
    except OSError as exc:
        raise RunPlanArtifactError(
            f"could not create plan artifact staging file: {exc}"
        ) from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(artifact_bytes)
            handle.flush()
            if hasattr(os, "fsync"):
                os.fsync(handle.fileno())
        os.link(temporary_name, target)
        if hasattr(os, "fsync"):
            try:
                directory_fd = os.open(target.parent, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                finally:
                    os.close(directory_fd)
    except FileExistsError as exc:
        raise RunPlanArtifactError("plan output already exists") from exc
    except OSError as exc:
        raise RunPlanArtifactError(f"could not publish plan artifact: {exc}") from exc
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return target


def confirmation_payload(
    artifact: Mapping[str, Any],
    *,
    artifact_digest: str,
    plan_body_digest: str,
) -> dict[str, Any]:
    body = artifact["plan_body"]
    return {
        "artifact_accepted": False,
        "artifact_byte_digest": artifact_digest,
        "cloud_authorization": False,
        "contract_version": CONTRACT_VERSION,
        "decision": "exact_plan_reviewed",
        "ethical_firewall_status": body["ethical_firewall"]["status"],
        "execution_authority": False,
        "general_approval": False,
        "human_review_gate_satisfied": False,
        "plan_body_digest": plan_body_digest,
        "route_posture": body["route_forecast"]["route"],
        "task_id": body["task_id"],
    }


def validate_confirmation_payload(
    payload: Any, *, expected_task_id: str | None = None
) -> dict[str, Any]:
    item = _require_exact_keys(
        payload, _CONFIRMATION_KEYS, "run plan confirmation"
    )
    if item["contract_version"] != CONTRACT_VERSION:
        raise RunPlanArtifactError("unsupported confirmation contract version")
    if item["decision"] != "exact_plan_reviewed":
        raise RunPlanArtifactError("invalid confirmation decision")
    for key in _CONFIRMATION_FALSE_FIELDS:
        if item[key] is not False:
            raise RunPlanArtifactError("confirmation cannot grant authority")
    task_id = item["task_id"]
    if (
        not isinstance(task_id, str)
        or not TASK_ID_RE.fullmatch(task_id)
        or (expected_task_id is not None and task_id != expected_task_id)
    ):
        raise RunPlanArtifactError("invalid confirmation task ID")
    for key in ("artifact_byte_digest", "plan_body_digest"):
        if not isinstance(item[key], str) or not DIGEST_RE.fullmatch(item[key]):
            raise RunPlanArtifactError("invalid confirmation digest")
    _require_string(
        item["ethical_firewall_status"],
        "confirmation ethical firewall status",
        allowed=frozenset({"clear", "triggered"}),
    )
    _require_string(
        item["route_posture"], "confirmation route posture", allowed=_ROUTES
    )
    _assert_privacy_safe(item, artifact_name="run plan review confirmation")
    return item


def validate_ledger_file(ledger_path: str | Path) -> None:
    """Reject malformed JSONL before confirmation or linkage inspection."""
    path = Path(ledger_path)
    if not path.exists():
        return
    if not path.is_file() or _is_link_or_reparse(path):
        raise RunPlanArtifactError("ledger path is not a regular file")
    try:
        with path.open("rb") as handle:
            for raw_line in handle:
                if not raw_line.endswith(b"\n"):
                    raise RunPlanArtifactError(
                        "ledger contains an incomplete event"
                    )
                if not raw_line.strip():
                    continue
                try:
                    event = json.loads(
                        raw_line.decode("utf-8"),
                        object_pairs_hook=_object_without_duplicates,
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise RunPlanArtifactError(
                        "ledger contains malformed JSON"
                    ) from exc
                if (
                    not isinstance(event, dict)
                    or not isinstance(event.get("task_id"), str)
                    or not event["task_id"]
                    or not isinstance(event.get("event_type"), str)
                    or not event["event_type"]
                    or not isinstance(event.get("payload"), dict)
                ):
                    raise RunPlanArtifactError(
                        "ledger contains a malformed event"
                    )
    except OSError as exc:
        raise RunPlanArtifactError(f"could not validate ledger: {exc}") from exc


def prepare_confirmation(
    *,
    plan_path: str | Path,
    expected_artifact_digest: str,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(expected_artifact_digest, str) or not DIGEST_RE.fullmatch(
        expected_artifact_digest
    ):
        raise RunPlanArtifactError("artifact digest must be exact lower-case sha256")
    try:
        artifact_bytes = Path(plan_path).read_bytes()
    except OSError as exc:
        raise RunPlanArtifactError(f"could not read plan artifact: {exc}") from exc
    artifact, body_digest, actual_digest = validate_artifact_bytes(artifact_bytes)
    if expected_artifact_digest != actual_digest:
        raise RunPlanArtifactError("artifact byte digest mismatch")
    payload = confirmation_payload(
        artifact,
        artifact_digest=actual_digest,
        plan_body_digest=body_digest,
    )
    _assert_privacy_safe(payload, artifact_name="run plan review confirmation")
    return artifact["plan_body"]["task_id"], payload


def record_confirmation(
    *, task_id: str, payload: dict[str, Any], ledger: Any
) -> str:
    validate_confirmation_payload(payload, expected_task_id=task_id)
    existing = [
        validate_confirmation_payload(
            event.get("payload"), expected_task_id=task_id
        )
        for event in ledger.get_events(task_id)
        if event.get("event_type") == "run_plan_review_confirmed"
    ]
    if existing:
        if all(existing_payload == payload for existing_payload in existing):
            return "already_confirmed"
        raise RunPlanArtifactError("conflicting plan confirmation for task ID")
    if ledger.get_task(task_id) is None:
        ledger.append_event(
            task_id,
            "task_created",
            {
                "description": "Raw task details withheld from ledger.",
                "title": "Governed run plan review",
            },
        )
    ledger.append_event(task_id, "run_plan_review_confirmed", payload)
    return "confirmed"
