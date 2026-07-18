"""Pure, privacy-safe governed-decision construction.

This module is an internal CR-DD-012A foundation.  It deliberately has no
integration with the CLI, planning, execution, routing, ledgers, or artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any
import unicodedata

from triage_core.governed_run_snapshot import GovernedRunInputSnapshot


IDENTITY_DOMAIN = "triagecore.governed_decision.identity.v1"
CONTRACT_VERSION = "governed_decision.v1"
CANONICALIZATION_VERSION = "governed_decision_canonical_json.v1"
SNAPSHOT_CONTRACT_VERSION = "governed_run_input_snapshot.v1"
ASSEMBLY_CONTRACT_VERSION = "tc_run_worker_user_message.v1"
DECODE_NEWLINE_CONTRACT_VERSION = "tc_run_utf8_universal_newline.v1"
PROFILE_RESOLUTION_VERSION = "governed_run_profile_resolution.v1"
CONFIGURATION_VERSION = "governed_decision_configuration.v1"
POLICY_VERSION = "governed_decision_policy.v1"
CLASSIFICATION_POLICY_VERSION = "deterministic_task_classification.v1"
ROUTE_POLICY_VERSION = "governed_logical_route_policy.v1"
VERIFICATION_POLICY_VERSION = "governed_verification_requirements.v1"
MAX_CANONICAL_DECISION_BYTES = 1_000_000
MAX_BOUNDED_INTEGER = (1 << 63) - 1

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}\Z")

DECLARED_PRIVACY_VALUES = frozenset({"local_only", "external_safe", "public"})
CLOUD_INTENT_VALUES = frozenset({"not_requested", "requested"})
PRIVACY_PREFLIGHT_VALUES = frozenset({"passed", "failed"})
EGRESS_ELIGIBILITY_VALUES = frozenset({"prohibited", "eligible"})
BUDGET_POSTURE_VALUES = frozenset({"within_budget", "over_budget"})
CLASSIFICATION_VALUES = frozenset(
    {
        "docs_update",
        "bugfix",
        "test_addition",
        "refactor",
        "packaging",
        "security_review",
        "architecture_planning",
        "blocked_or_high_risk",
    }
)
RISK_POSTURE_VALUES = frozenset({"low", "medium", "high"})
LOGICAL_ROUTE_VALUES = frozenset(
    {
        "cloud_primary",
        "cloud_secondary",
        "local_heavy",
        "local_fast",
        "deterministic",
        "human_handoff",
    }
)
CLASSIFICATION_REASON_CODES = frozenset(
    {
        "deterministic_classifier_match",
        "deterministic_classifier_default",
        "privacy_preflight_failed",
        "operator_declaration",
        "ethical_firewall_triggered",
    }
)
ROUTE_REASON_CODES = frozenset(
    {
        "deterministic_tool_available_for_task_class",
        "cloud_primary_healthy_for_high_complexity_task",
        "cloud_primary_degraded_using_secondary",
        "local_heavy_available_for_medium_or_complex_task",
        "local_fast_available_for_small_or_repetitive_task",
        "local_heavy_available_after_preferred_route_unavailable",
        "local_fast_available_after_preferred_route_unavailable",
        "cloud_primary_available_after_local_routes_unavailable",
        "cloud_secondary_available_after_local_routes_unavailable",
        "deterministic_tool_available_as_last_automated_route",
        "no_reliable_automated_route_available",
        "ethical_firewall_requires_human_review",
        "policy_selected",
    }
)
ESCALATION_CONDITION_CODES = frozenset(
    {
        "route_unavailable_at_execution",
        "sensitivity_requires_governed_handoff",
        "egress_requires_explicit_authorization",
        "ethical_firewall_requires_human_review",
        "context_budget_overrun_requires_review",
    }
)
TERMINAL_ESCALATION_VALUES = frozenset(
    {"none", "human_only", "configured_human_review"}
)
ETHICAL_FIREWALL_VALUES = frozenset({"clear", "triggered"})
HUMAN_REVIEW_VALUES = frozenset({"not_required", "required"})
REQUIRED_CHECK_CODES = frozenset(
    {
        "packet_verification",
        "privacy_preflight",
        "route_policy_conformance",
        "decision_identity_verification",
        "artifact_digest_verification",
        "output_validation",
        "human_review",
    }
)


class GovernedDecisionError(ValueError):
    """A bounded governed-decision validation failure."""

    def __init__(self, code: str, path: str = "$") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}")


@dataclass(frozen=True, slots=True)
class DigestLengthBinding:
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class SourceDecisionBinding:
    position: int
    locator_sha256: str
    source_sha256: str | None
    source_byte_length: int | None
    normalized_sha256: str
    normalized_byte_length: int
    component_sha256: str
    component_byte_length: int
    decode_newline_contract_version: str


@dataclass(frozen=True, slots=True)
class SnapshotDecisionBinding:
    snapshot_contract_version: str
    assembly_contract_version: str
    instruction: DigestLengthBinding
    inline_input_posture: str
    inline_input: DigestLengthBinding
    sources: tuple[SourceDecisionBinding, ...]
    task_data: DigestLengthBinding
    assembled_execution: DigestLengthBinding
    task_id_posture: str
    task_id: str | None
    declared_privacy: str
    cloud_intent: str
    requested_profile: str
    resolved_profile_id: str
    profile_resolution_version: str
    construction_limits_sha256: str
    worker_system_message_version: str
    worker_system_message_sha256: str

    def __post_init__(self) -> None:
        if type(self.sources) not in {list, tuple}:
            raise GovernedDecisionError(
                "ordered_collection_invalid", "$.snapshot.sources"
            )
        if len(self.sources) > 4096:
            raise GovernedDecisionError("array_too_large", "$.snapshot.sources")
        owned_sources = tuple(self.sources)
        object.__setattr__(self, "sources", owned_sources)


@dataclass(frozen=True, slots=True)
class DecisionPolicyConfiguration:
    """All policy facts consumed by the pure decision builder."""

    configuration_version: str
    configuration_sha256: str
    policy_version: str
    classification_policy_version: str
    route_policy_version: str
    verification_policy_version: str
    estimated_input_tokens: int
    usable_input_tokens: int
    privacy_preflight: str
    classification: str
    risk_posture: str
    classification_reason_codes: tuple[str, ...]
    preferred_logical_route: str
    permitted_fallback_envelope: tuple[str, ...]
    route_reason_codes: tuple[str, ...]
    terminal_escalation: str
    ethical_firewall: str
    human_review: str
    escalation_conditions: tuple[str, ...]
    required_checks: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name, expected in (
            ("configuration_version", CONFIGURATION_VERSION),
            ("policy_version", POLICY_VERSION),
            ("classification_policy_version", CLASSIFICATION_POLICY_VERSION),
            ("route_policy_version", ROUTE_POLICY_VERSION),
            ("verification_policy_version", VERIFICATION_POLICY_VERSION),
        ):
            _require_exact_string(
                getattr(self, field_name),
                expected,
                f"$.{field_name}",
                "version_unsupported",
            )
        _require_digest(self.configuration_sha256, "$.configuration_sha256")
        _require_bounded_int(
            self.estimated_input_tokens,
            "$.estimated_input_tokens",
            minimum=0,
        )
        _require_bounded_int(
            self.usable_input_tokens,
            "$.usable_input_tokens",
            minimum=1,
        )
        _require_enum(
            self.privacy_preflight,
            PRIVACY_PREFLIGHT_VALUES,
            "$.privacy_preflight",
        )
        _require_enum(
            self.classification,
            CLASSIFICATION_VALUES,
            "$.classification",
        )
        _require_enum(self.risk_posture, RISK_POSTURE_VALUES, "$.risk_posture")
        _require_enum(
            self.preferred_logical_route,
            LOGICAL_ROUTE_VALUES,
            "$.preferred_logical_route",
        )
        _require_enum(
            self.terminal_escalation,
            TERMINAL_ESCALATION_VALUES,
            "$.terminal_escalation",
        )
        _require_enum(
            self.ethical_firewall,
            ETHICAL_FIREWALL_VALUES,
            "$.ethical_firewall",
        )
        _require_enum(
            self.human_review,
            HUMAN_REVIEW_VALUES,
            "$.human_review",
        )
        _own_code_tuple(
            self,
            "classification_reason_codes",
            CLASSIFICATION_REASON_CODES,
        )
        _own_code_tuple(
            self,
            "permitted_fallback_envelope",
            LOGICAL_ROUTE_VALUES,
        )
        _own_code_tuple(self, "route_reason_codes", ROUTE_REASON_CODES)
        _own_code_tuple(
            self,
            "escalation_conditions",
            ESCALATION_CONDITION_CODES,
        )
        _own_code_tuple(self, "required_checks", REQUIRED_CHECK_CODES)


@dataclass(frozen=True, slots=True)
class GovernedDecision:
    """One recursively immutable governed decision."""

    decision_id: str
    snapshot_binding: SnapshotDecisionBinding
    policy: DecisionPolicyConfiguration


def build_governed_decision(
    snapshot: GovernedRunInputSnapshot,
    configuration: DecisionPolicyConfiguration,
) -> GovernedDecision:
    """Build a decision using only an immutable snapshot and explicit facts."""

    if type(configuration) is not DecisionPolicyConfiguration:
        raise GovernedDecisionError("invalid_configuration_type", "$.configuration")
    binding = _snapshot_decision_binding(snapshot)
    _validate_policy_consistency(binding, configuration)
    provisional = GovernedDecision(
        decision_id="sha256:" + ("0" * 64),
        snapshot_binding=binding,
        policy=configuration,
    )
    decision_id = _decision_id_for_body(_decision_body(provisional))
    return GovernedDecision(
        decision_id=decision_id,
        snapshot_binding=binding,
        policy=configuration,
    )


def serialize_governed_decision(decision: GovernedDecision) -> bytes:
    """Return the pinned canonical UTF-8 representation."""

    if type(decision) is not GovernedDecision:
        raise GovernedDecisionError("invalid_decision_type")
    body = _decision_body(decision)
    expected_id = _decision_id_for_body(body)
    if decision.decision_id != expected_id:
        raise GovernedDecisionError("decision_id_mismatch", "$.decision_id")
    return _canonical_json_bytes(
        {
            "identity_domain": IDENTITY_DOMAIN,
            "contract_version": CONTRACT_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "decision_id": decision.decision_id,
            "decision_body": body,
        }
    )


def parse_governed_decision(canonical_bytes: bytes) -> GovernedDecision:
    """Parse, structurally validate, canonicality-check, and verify a decision."""

    if type(canonical_bytes) is not bytes:
        raise GovernedDecisionError("canonical_bytes_required")
    if not canonical_bytes or len(canonical_bytes) > MAX_CANONICAL_DECISION_BYTES:
        raise GovernedDecisionError("canonical_size_invalid")
    if canonical_bytes.startswith(b"\xef\xbb\xbf"):
        raise GovernedDecisionError("canonical_bom_forbidden")
    try:
        text = canonical_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GovernedDecisionError("canonical_utf8_invalid") from exc
    try:
        raw = json.loads(
            text,
            object_pairs_hook=_closed_object,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except GovernedDecisionError:
        raise
    except (json.JSONDecodeError, UnicodeError, ValueError, TypeError) as exc:
        raise GovernedDecisionError("canonical_json_invalid") from exc

    validated = _validate_top_level(raw)
    try:
        normalized = _canonical_json_bytes(validated)
    except (UnicodeError, TypeError, ValueError) as exc:
        raise GovernedDecisionError("canonical_json_invalid") from exc
    if normalized != canonical_bytes:
        raise GovernedDecisionError("noncanonical_bytes")

    body = validated["decision_body"]
    expected_id = _decision_id_for_body(body)
    if validated["decision_id"] != expected_id:
        raise GovernedDecisionError("decision_id_mismatch", "$.decision_id")
    decision = _decision_from_body(expected_id, body)
    if serialize_governed_decision(decision) != canonical_bytes:
        raise GovernedDecisionError("round_trip_mismatch")
    return decision


def verify_governed_decision_id(decision: GovernedDecision) -> bool:
    """Return whether the content-linkage ID matches the complete identity body."""

    if type(decision) is not GovernedDecision:
        return False
    try:
        return decision.decision_id == _decision_id_for_body(_decision_body(decision))
    except GovernedDecisionError:
        return False


def _snapshot_decision_binding(
    snapshot: GovernedRunInputSnapshot,
) -> SnapshotDecisionBinding:
    """Copy the snapshot's privacy-safe binding without retaining aliases."""

    if type(snapshot) is not GovernedRunInputSnapshot:
        raise GovernedDecisionError("invalid_snapshot_type", "$.snapshot")
    raw = snapshot.to_decision_binding()
    try:
        sources = tuple(
            SourceDecisionBinding(
                position=source.position,
                locator_sha256=source.locator_sha256,
                source_sha256=source.source_sha256,
                source_byte_length=source.source_byte_length,
                normalized_sha256=source.normalized_sha256,
                normalized_byte_length=source.normalized_byte_length,
                component_sha256=source.component_sha256,
                component_byte_length=source.component_byte_length,
                decode_newline_contract_version=(
                    source.decode_newline_contract_version
                ),
            )
            for source in raw.sources
        )
        binding = SnapshotDecisionBinding(
            snapshot_contract_version=raw.snapshot_contract_version,
            assembly_contract_version=raw.assembly_contract_version,
            instruction=DigestLengthBinding(
                raw.instruction.sha256,
                raw.instruction.byte_length,
            ),
            inline_input_posture=raw.inline_input_posture,
            inline_input=DigestLengthBinding(
                raw.inline_input.sha256,
                raw.inline_input.byte_length,
            ),
            sources=sources,
            task_data=DigestLengthBinding(
                raw.task_data.sha256,
                raw.task_data.byte_length,
            ),
            assembled_execution=DigestLengthBinding(
                raw.assembled_execution.sha256,
                raw.assembled_execution.byte_length,
            ),
            task_id_posture=raw.task_id_posture,
            task_id=raw.task_id,
            declared_privacy=raw.declared_privacy,
            cloud_intent=raw.cloud_intent,
            requested_profile=raw.requested_profile,
            resolved_profile_id=raw.resolved_profile_id,
            profile_resolution_version=raw.profile_resolution_version,
            construction_limits_sha256=raw.construction_limits_sha256,
            worker_system_message_version=raw.worker_system_message_version,
            worker_system_message_sha256=raw.worker_system_message_sha256,
        )
    except (AttributeError, TypeError) as exc:
        raise GovernedDecisionError(
            "invalid_snapshot_binding", "$.snapshot"
        ) from exc
    _validate_snapshot_binding(binding)
    return binding


def _validate_snapshot_binding(binding: SnapshotDecisionBinding) -> None:
    for name, expected in (
        ("snapshot_contract_version", SNAPSHOT_CONTRACT_VERSION),
        ("assembly_contract_version", ASSEMBLY_CONTRACT_VERSION),
        ("profile_resolution_version", PROFILE_RESOLUTION_VERSION),
    ):
        _require_exact_string(
            getattr(binding, name),
            expected,
            f"$.snapshot.{name}",
            "version_unsupported",
        )
    for name in (
        "requested_profile",
        "resolved_profile_id",
        "worker_system_message_version",
    ):
        _require_identifier(getattr(binding, name), f"$.snapshot.{name}")
    _require_enum(
        binding.inline_input_posture,
        frozenset({"absent", "present"}),
        "$.snapshot.inline_input_posture",
    )
    _require_enum(
        binding.task_id_posture,
        frozenset({"implicit_unassigned", "explicit"}),
        "$.snapshot.task_id_posture",
    )
    if binding.task_id_posture == "implicit_unassigned":
        if binding.task_id is not None:
            raise GovernedDecisionError("task_id_posture_mismatch", "$.snapshot")
    else:
        _require_task_id(binding.task_id, "$.snapshot.task_id")
    _require_enum(
        binding.declared_privacy,
        DECLARED_PRIVACY_VALUES,
        "$.snapshot.declared_privacy",
    )
    _require_enum(
        binding.cloud_intent,
        CLOUD_INTENT_VALUES,
        "$.snapshot.cloud_intent",
    )
    for name in (
        "construction_limits_sha256",
        "worker_system_message_sha256",
    ):
        _require_digest(getattr(binding, name), f"$.snapshot.{name}")
    for name in ("instruction", "inline_input", "task_data", "assembled_execution"):
        _validate_digest_length(getattr(binding, name), f"$.snapshot.{name}")
    if (
        binding.inline_input_posture == "absent"
        and binding.inline_input.byte_length != 0
    ):
        raise GovernedDecisionError(
            "inline_posture_mismatch", "$.snapshot.inline_input"
        )
    for expected_position, source in enumerate(binding.sources):
        path = f"$.snapshot.sources[{expected_position}]"
        if not isinstance(source, SourceDecisionBinding):
            raise GovernedDecisionError("source_binding_invalid", path)
        if source.position != expected_position:
            raise GovernedDecisionError("source_position_invalid", path)
        _require_digest(source.locator_sha256, f"{path}.locator_sha256")
        if (source.source_sha256 is None) != (source.source_byte_length is None):
            raise GovernedDecisionError("source_provenance_mismatch", path)
        if source.source_sha256 is not None:
            _require_digest(source.source_sha256, f"{path}.source_sha256")
            _require_bounded_int(
                source.source_byte_length,
                f"{path}.source_byte_length",
                minimum=0,
            )
        _require_digest(source.normalized_sha256, f"{path}.normalized_sha256")
        _require_bounded_int(
            source.normalized_byte_length,
            f"{path}.normalized_byte_length",
            minimum=0,
        )
        _require_digest(source.component_sha256, f"{path}.component_sha256")
        _require_bounded_int(
            source.component_byte_length,
            f"{path}.component_byte_length",
            minimum=0,
        )
        _require_identifier(
            source.decode_newline_contract_version,
            f"{path}.decode_newline_contract_version",
        )
        if source.decode_newline_contract_version != DECODE_NEWLINE_CONTRACT_VERSION:
            raise GovernedDecisionError(
                "version_unsupported",
                f"{path}.decode_newline_contract_version",
            )


def _validate_policy_consistency(
    binding: SnapshotDecisionBinding,
    configuration: DecisionPolicyConfiguration,
) -> None:
    egress = _egress_eligibility(binding, configuration)
    cloud_routes = {"cloud_primary", "cloud_secondary"}
    all_routes = (
        configuration.preferred_logical_route,
        *configuration.permitted_fallback_envelope,
    )
    if egress == "prohibited" and any(route in cloud_routes for route in all_routes):
        raise GovernedDecisionError(
            "cloud_route_outside_egress_envelope",
            "$.configuration",
        )
    review_required = (
        configuration.risk_posture == "high"
        or configuration.privacy_preflight == "failed"
        or configuration.ethical_firewall == "triggered"
        or configuration.preferred_logical_route == "human_handoff"
        or configuration.terminal_escalation != "none"
    )
    if review_required and configuration.human_review != "required":
        raise GovernedDecisionError(
            "human_review_posture_inconsistent",
            "$.configuration.human_review",
        )


def _decision_body(decision: GovernedDecision) -> dict[str, Any]:
    binding = decision.snapshot_binding
    policy = decision.policy
    _validate_snapshot_binding(binding)
    _validate_policy_consistency(binding, policy)
    budget_posture = (
        "within_budget"
        if policy.estimated_input_tokens <= policy.usable_input_tokens
        else "over_budget"
    )
    return {
        "normalization": {
            "snapshot_contract_version": binding.snapshot_contract_version,
            "assembly_contract_version": binding.assembly_contract_version,
            "profile_resolution_version": binding.profile_resolution_version,
            "policy_version": policy.policy_version,
        },
        "snapshot_binding": {
            "instruction": _digest_length_primitive(binding.instruction),
            "inline_input": {
                "posture": binding.inline_input_posture,
                **_digest_length_primitive(binding.inline_input),
            },
            "sources": [
                {
                    "position": source.position,
                    "locator_sha256": source.locator_sha256,
                    "source_sha256": source.source_sha256,
                    "source_byte_length": source.source_byte_length,
                    "normalized_sha256": source.normalized_sha256,
                    "normalized_byte_length": source.normalized_byte_length,
                    "component_sha256": source.component_sha256,
                    "component_byte_length": source.component_byte_length,
                    "decode_newline_contract_version": (
                        source.decode_newline_contract_version
                    ),
                }
                for source in binding.sources
            ],
            "task_data": _digest_length_primitive(binding.task_data),
            "assembled_execution": _digest_length_primitive(
                binding.assembled_execution
            ),
        },
        "operator_intent": {
            "task_id_posture": binding.task_id_posture,
            "task_id": binding.task_id,
            "declared_privacy": binding.declared_privacy,
            "cloud_intent": binding.cloud_intent,
            "requested_profile": binding.requested_profile,
            "resolved_profile_id": binding.resolved_profile_id,
        },
        "configuration_binding": {
            "configuration_version": policy.configuration_version,
            "configuration_sha256": policy.configuration_sha256,
            "classification_policy_version": policy.classification_policy_version,
            "route_policy_version": policy.route_policy_version,
            "verification_policy_version": policy.verification_policy_version,
            "construction_limits_sha256": binding.construction_limits_sha256,
            "worker_system_message_version": (
                binding.worker_system_message_version
            ),
            "worker_system_message_sha256": binding.worker_system_message_sha256,
        },
        "privacy_and_egress": {
            "privacy_preflight": policy.privacy_preflight,
            "egress_eligibility": _egress_eligibility(binding, policy),
            "cloud_intent": binding.cloud_intent,
            "cloud_authorization": "not_granted",
        },
        "context_budget": {
            "estimated_input_tokens": policy.estimated_input_tokens,
            "usable_input_tokens": policy.usable_input_tokens,
            "posture": budget_posture,
        },
        "classification": {
            "category": policy.classification,
            "risk_posture": policy.risk_posture,
            "reason_codes": list(policy.classification_reason_codes),
        },
        "logical_route_policy": {
            "preferred_route": policy.preferred_logical_route,
            "permitted_fallback_envelope": list(
                policy.permitted_fallback_envelope
            ),
            "reason_codes": list(policy.route_reason_codes),
        },
        "escalation_and_review": {
            "terminal_escalation": policy.terminal_escalation,
            "ethical_firewall": policy.ethical_firewall,
            "human_review": policy.human_review,
            "conditions": list(policy.escalation_conditions),
        },
        "verification": {
            "required_checks": list(policy.required_checks),
        },
        "authority_boundary": {
            "decision_id_is_linkage_only": True,
            "execution_authority": "not_granted",
            "egress_authority": "not_granted",
            "confirmation_authority": "not_granted",
            "acceptance_authority": "not_granted",
        },
    }


def _egress_eligibility(
    binding: SnapshotDecisionBinding,
    policy: DecisionPolicyConfiguration,
) -> str:
    if (
        policy.privacy_preflight != "passed"
        or binding.declared_privacy == "local_only"
    ):
        return "prohibited"
    return "eligible"


def _decision_id_for_body(body: dict[str, Any]) -> str:
    envelope = {
        "identity_domain": IDENTITY_DOMAIN,
        "contract_version": CONTRACT_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "decision_body": body,
    }
    return "sha256:" + sha256(_canonical_json_bytes(envelope)).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    _validate_canonical_primitive(value)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise GovernedDecisionError("canonicalization_failed") from exc
    if len(encoded) > MAX_CANONICAL_DECISION_BYTES:
        raise GovernedDecisionError("canonical_size_invalid")
    return encoded


def _validate_canonical_primitive(value: Any) -> None:
    seen_containers: set[int] = set()

    def visit(item: Any, path: str, depth: int) -> None:
        if depth > 64:
            raise GovernedDecisionError("canonical_depth_exceeded", path)
        item_type = type(item)
        if item is None or item_type is bool:
            return
        if item_type is int:
            if item < -MAX_BOUNDED_INTEGER or item > MAX_BOUNDED_INTEGER:
                raise GovernedDecisionError("integer_invalid", path)
            return
        if item_type is str:
            try:
                encoded = item.encode("utf-8", errors="strict")
            except UnicodeEncodeError as exc:
                raise GovernedDecisionError("canonical_string_invalid", path) from exc
            if len(encoded) > MAX_CANONICAL_DECISION_BYTES:
                raise GovernedDecisionError("canonical_string_too_large", path)
            return
        if item_type is list:
            container_id = id(item)
            if container_id in seen_containers:
                raise GovernedDecisionError(
                    "canonical_container_alias_forbidden",
                    path,
                )
            seen_containers.add(container_id)
            if len(item) > 4096:
                raise GovernedDecisionError("array_too_large", path)
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]", depth + 1)
            return
        if item_type is dict:
            container_id = id(item)
            if container_id in seen_containers:
                raise GovernedDecisionError(
                    "canonical_container_alias_forbidden",
                    path,
                )
            seen_containers.add(container_id)
            if len(item) > 4096:
                raise GovernedDecisionError("object_too_large", path)
            for index, (key, child) in enumerate(item.items()):
                if type(key) is not str:
                    raise GovernedDecisionError(
                        "canonical_key_invalid",
                        f"{path}.object_key[{index}]",
                    )
                try:
                    key.encode("ascii", errors="strict")
                except UnicodeEncodeError as exc:
                    raise GovernedDecisionError(
                        "canonical_key_invalid",
                        f"{path}.object_key[{index}]",
                    ) from exc
                visit(child, f"{path}.object_value[{index}]", depth + 1)
            return
        raise GovernedDecisionError("canonical_type_forbidden", path)

    visit(value, "$", 0)


def _validate_top_level(raw: Any) -> dict[str, Any]:
    top = _require_object(
        raw,
        {
            "identity_domain",
            "contract_version",
            "canonicalization_version",
            "decision_id",
            "decision_body",
        },
        "$",
    )
    _require_exact_string(
        top["identity_domain"],
        IDENTITY_DOMAIN,
        "$.identity_domain",
        "identity_domain_unsupported",
    )
    _require_exact_string(
        top["contract_version"],
        CONTRACT_VERSION,
        "$.contract_version",
        "contract_version_unsupported",
    )
    _require_exact_string(
        top["canonicalization_version"],
        CANONICALIZATION_VERSION,
        "$.canonicalization_version",
        "canonicalization_version_unsupported",
    )
    _require_digest(top["decision_id"], "$.decision_id")
    _validate_body_primitive(top["decision_body"])
    return top


def _validate_body_primitive(raw: Any) -> None:
    body = _require_object(
        raw,
        {
            "normalization",
            "snapshot_binding",
            "operator_intent",
            "configuration_binding",
            "privacy_and_egress",
            "context_budget",
            "classification",
            "logical_route_policy",
            "escalation_and_review",
            "verification",
            "authority_boundary",
        },
        "$.decision_body",
    )
    normalization = _require_object(
        body["normalization"],
        {
            "snapshot_contract_version",
            "assembly_contract_version",
            "profile_resolution_version",
            "policy_version",
        },
        "$.decision_body.normalization",
    )
    for key, expected in (
        ("snapshot_contract_version", SNAPSHOT_CONTRACT_VERSION),
        ("assembly_contract_version", ASSEMBLY_CONTRACT_VERSION),
        ("profile_resolution_version", PROFILE_RESOLUTION_VERSION),
        ("policy_version", POLICY_VERSION),
    ):
        _require_exact_string(
            normalization[key],
            expected,
            f"$.decision_body.normalization.{key}",
            "version_unsupported",
        )

    snapshot = _require_object(
        body["snapshot_binding"],
        {
            "instruction",
            "inline_input",
            "sources",
            "task_data",
            "assembled_execution",
        },
        "$.decision_body.snapshot_binding",
    )
    _validate_digest_length_primitive(
        snapshot["instruction"],
        "$.decision_body.snapshot_binding.instruction",
    )
    inline = _require_object(
        snapshot["inline_input"],
        {"posture", "sha256", "byte_length"},
        "$.decision_body.snapshot_binding.inline_input",
    )
    _require_enum(
        inline["posture"],
        frozenset({"absent", "present"}),
        "$.decision_body.snapshot_binding.inline_input.posture",
    )
    _require_digest(
        inline["sha256"],
        "$.decision_body.snapshot_binding.inline_input.sha256",
    )
    _require_bounded_int(
        inline["byte_length"],
        "$.decision_body.snapshot_binding.inline_input.byte_length",
        minimum=0,
    )
    if inline["posture"] == "absent" and inline["byte_length"] != 0:
        raise GovernedDecisionError(
            "inline_posture_mismatch",
            "$.decision_body.snapshot_binding.inline_input",
        )
    sources = _require_array(
        snapshot["sources"],
        "$.decision_body.snapshot_binding.sources",
    )
    for index, source_raw in enumerate(sources):
        path = f"$.decision_body.snapshot_binding.sources[{index}]"
        source = _require_object(
            source_raw,
            {
                "position",
                "locator_sha256",
                "source_sha256",
                "source_byte_length",
                "normalized_sha256",
                "normalized_byte_length",
                "component_sha256",
                "component_byte_length",
                "decode_newline_contract_version",
            },
            path,
        )
        _require_bounded_int(source["position"], f"{path}.position", minimum=0)
        if source["position"] != index:
            raise GovernedDecisionError("source_position_invalid", path)
        _require_digest(source["locator_sha256"], f"{path}.locator_sha256")
        if (source["source_sha256"] is None) != (
            source["source_byte_length"] is None
        ):
            raise GovernedDecisionError("source_provenance_mismatch", path)
        if source["source_sha256"] is not None:
            _require_digest(source["source_sha256"], f"{path}.source_sha256")
            _require_bounded_int(
                source["source_byte_length"],
                f"{path}.source_byte_length",
                minimum=0,
            )
        _require_digest(source["normalized_sha256"], f"{path}.normalized_sha256")
        _require_bounded_int(
            source["normalized_byte_length"],
            f"{path}.normalized_byte_length",
            minimum=0,
        )
        _require_digest(source["component_sha256"], f"{path}.component_sha256")
        _require_bounded_int(
            source["component_byte_length"],
            f"{path}.component_byte_length",
            minimum=0,
        )
        _require_identifier(
            source["decode_newline_contract_version"],
            f"{path}.decode_newline_contract_version",
        )
        if (
            source["decode_newline_contract_version"]
            != DECODE_NEWLINE_CONTRACT_VERSION
        ):
            raise GovernedDecisionError(
                "version_unsupported",
                f"{path}.decode_newline_contract_version",
            )
    _validate_digest_length_primitive(
        snapshot["task_data"],
        "$.decision_body.snapshot_binding.task_data",
    )
    _validate_digest_length_primitive(
        snapshot["assembled_execution"],
        "$.decision_body.snapshot_binding.assembled_execution",
    )

    intent = _require_object(
        body["operator_intent"],
        {
            "task_id_posture",
            "task_id",
            "declared_privacy",
            "cloud_intent",
            "requested_profile",
            "resolved_profile_id",
        },
        "$.decision_body.operator_intent",
    )
    _require_enum(
        intent["task_id_posture"],
        frozenset({"implicit_unassigned", "explicit"}),
        "$.decision_body.operator_intent.task_id_posture",
    )
    if intent["task_id_posture"] == "implicit_unassigned":
        if intent["task_id"] is not None:
            raise GovernedDecisionError(
                "task_id_posture_mismatch",
                "$.decision_body.operator_intent.task_id",
            )
    else:
        _require_task_id(
            intent["task_id"],
            "$.decision_body.operator_intent.task_id",
        )
    _require_enum(
        intent["declared_privacy"],
        DECLARED_PRIVACY_VALUES,
        "$.decision_body.operator_intent.declared_privacy",
    )
    _require_enum(
        intent["cloud_intent"],
        CLOUD_INTENT_VALUES,
        "$.decision_body.operator_intent.cloud_intent",
    )
    _require_identifier(
        intent["requested_profile"],
        "$.decision_body.operator_intent.requested_profile",
    )
    _require_identifier(
        intent["resolved_profile_id"],
        "$.decision_body.operator_intent.resolved_profile_id",
    )

    config = _require_object(
        body["configuration_binding"],
        {
            "configuration_version",
            "configuration_sha256",
            "classification_policy_version",
            "route_policy_version",
            "verification_policy_version",
            "construction_limits_sha256",
            "worker_system_message_version",
            "worker_system_message_sha256",
        },
        "$.decision_body.configuration_binding",
    )
    for key, expected in (
        ("configuration_version", CONFIGURATION_VERSION),
        ("classification_policy_version", CLASSIFICATION_POLICY_VERSION),
        ("route_policy_version", ROUTE_POLICY_VERSION),
        ("verification_policy_version", VERIFICATION_POLICY_VERSION),
    ):
        _require_exact_string(
            config[key],
            expected,
            f"$.decision_body.configuration_binding.{key}",
            "version_unsupported",
        )
    _require_identifier(
        config["worker_system_message_version"],
        "$.decision_body.configuration_binding.worker_system_message_version",
    )
    for key in (
        "configuration_sha256",
        "construction_limits_sha256",
        "worker_system_message_sha256",
    ):
        _require_digest(
            config[key],
            f"$.decision_body.configuration_binding.{key}",
        )

    privacy = _require_object(
        body["privacy_and_egress"],
        {
            "privacy_preflight",
            "egress_eligibility",
            "cloud_intent",
            "cloud_authorization",
        },
        "$.decision_body.privacy_and_egress",
    )
    _require_enum(
        privacy["privacy_preflight"],
        PRIVACY_PREFLIGHT_VALUES,
        "$.decision_body.privacy_and_egress.privacy_preflight",
    )
    _require_enum(
        privacy["egress_eligibility"],
        EGRESS_ELIGIBILITY_VALUES,
        "$.decision_body.privacy_and_egress.egress_eligibility",
    )
    _require_enum(
        privacy["cloud_intent"],
        CLOUD_INTENT_VALUES,
        "$.decision_body.privacy_and_egress.cloud_intent",
    )
    _require_exact_string(
        privacy["cloud_authorization"],
        "not_granted",
        "$.decision_body.privacy_and_egress.cloud_authorization",
        "authority_boundary_invalid",
    )

    budget = _require_object(
        body["context_budget"],
        {"estimated_input_tokens", "usable_input_tokens", "posture"},
        "$.decision_body.context_budget",
    )
    _require_bounded_int(
        budget["estimated_input_tokens"],
        "$.decision_body.context_budget.estimated_input_tokens",
        minimum=0,
    )
    _require_bounded_int(
        budget["usable_input_tokens"],
        "$.decision_body.context_budget.usable_input_tokens",
        minimum=1,
    )
    _require_enum(
        budget["posture"],
        BUDGET_POSTURE_VALUES,
        "$.decision_body.context_budget.posture",
    )
    expected_budget = (
        "within_budget"
        if budget["estimated_input_tokens"] <= budget["usable_input_tokens"]
        else "over_budget"
    )
    if budget["posture"] != expected_budget:
        raise GovernedDecisionError(
            "budget_posture_mismatch",
            "$.decision_body.context_budget.posture",
        )

    classification = _require_object(
        body["classification"],
        {"category", "risk_posture", "reason_codes"},
        "$.decision_body.classification",
    )
    _require_enum(
        classification["category"],
        CLASSIFICATION_VALUES,
        "$.decision_body.classification.category",
    )
    _require_enum(
        classification["risk_posture"],
        RISK_POSTURE_VALUES,
        "$.decision_body.classification.risk_posture",
    )
    _validate_code_array(
        classification["reason_codes"],
        CLASSIFICATION_REASON_CODES,
        "$.decision_body.classification.reason_codes",
    )

    route = _require_object(
        body["logical_route_policy"],
        {"preferred_route", "permitted_fallback_envelope", "reason_codes"},
        "$.decision_body.logical_route_policy",
    )
    _require_enum(
        route["preferred_route"],
        LOGICAL_ROUTE_VALUES,
        "$.decision_body.logical_route_policy.preferred_route",
    )
    _validate_code_array(
        route["permitted_fallback_envelope"],
        LOGICAL_ROUTE_VALUES,
        "$.decision_body.logical_route_policy.permitted_fallback_envelope",
    )
    _validate_code_array(
        route["reason_codes"],
        ROUTE_REASON_CODES,
        "$.decision_body.logical_route_policy.reason_codes",
    )

    escalation = _require_object(
        body["escalation_and_review"],
        {
            "terminal_escalation",
            "ethical_firewall",
            "human_review",
            "conditions",
        },
        "$.decision_body.escalation_and_review",
    )
    _require_enum(
        escalation["terminal_escalation"],
        TERMINAL_ESCALATION_VALUES,
        "$.decision_body.escalation_and_review.terminal_escalation",
    )
    _require_enum(
        escalation["ethical_firewall"],
        ETHICAL_FIREWALL_VALUES,
        "$.decision_body.escalation_and_review.ethical_firewall",
    )
    _require_enum(
        escalation["human_review"],
        HUMAN_REVIEW_VALUES,
        "$.decision_body.escalation_and_review.human_review",
    )
    _validate_code_array(
        escalation["conditions"],
        ESCALATION_CONDITION_CODES,
        "$.decision_body.escalation_and_review.conditions",
    )

    verification = _require_object(
        body["verification"],
        {"required_checks"},
        "$.decision_body.verification",
    )
    _validate_code_array(
        verification["required_checks"],
        REQUIRED_CHECK_CODES,
        "$.decision_body.verification.required_checks",
    )

    authority = _require_object(
        body["authority_boundary"],
        {
            "decision_id_is_linkage_only",
            "execution_authority",
            "egress_authority",
            "confirmation_authority",
            "acceptance_authority",
        },
        "$.decision_body.authority_boundary",
    )
    if authority["decision_id_is_linkage_only"] is not True:
        raise GovernedDecisionError(
            "authority_boundary_invalid",
            "$.decision_body.authority_boundary.decision_id_is_linkage_only",
        )
    for key in (
        "execution_authority",
        "egress_authority",
        "confirmation_authority",
        "acceptance_authority",
    ):
        _require_exact_string(
            authority[key],
            "not_granted",
            f"$.decision_body.authority_boundary.{key}",
            "authority_boundary_invalid",
        )

    expected_egress = (
        "prohibited"
        if privacy["privacy_preflight"] != "passed"
        or intent["declared_privacy"] == "local_only"
        else "eligible"
    )
    if privacy["egress_eligibility"] != expected_egress:
        raise GovernedDecisionError(
            "egress_posture_mismatch",
            "$.decision_body.privacy_and_egress.egress_eligibility",
        )
    if privacy["cloud_intent"] != intent["cloud_intent"]:
        raise GovernedDecisionError(
            "cloud_intent_mismatch",
            "$.decision_body.privacy_and_egress.cloud_intent",
        )
    if expected_egress == "prohibited":
        routes = [route["preferred_route"], *route["permitted_fallback_envelope"]]
        if any(value in {"cloud_primary", "cloud_secondary"} for value in routes):
            raise GovernedDecisionError(
                "cloud_route_outside_egress_envelope",
                "$.decision_body.logical_route_policy",
            )
    review_required = (
        classification["risk_posture"] == "high"
        or privacy["privacy_preflight"] == "failed"
        or escalation["ethical_firewall"] == "triggered"
        or route["preferred_route"] == "human_handoff"
        or escalation["terminal_escalation"] != "none"
    )
    if review_required and escalation["human_review"] != "required":
        raise GovernedDecisionError(
            "human_review_posture_inconsistent",
            "$.decision_body.escalation_and_review.human_review",
        )


def _decision_from_body(
    decision_id: str,
    body: dict[str, Any],
) -> GovernedDecision:
    snapshot = body["snapshot_binding"]
    intent = body["operator_intent"]
    normalization = body["normalization"]
    config = body["configuration_binding"]
    privacy = body["privacy_and_egress"]
    budget = body["context_budget"]
    classification = body["classification"]
    route = body["logical_route_policy"]
    escalation = body["escalation_and_review"]
    verification = body["verification"]
    sources = tuple(
        SourceDecisionBinding(
            position=item["position"],
            locator_sha256=item["locator_sha256"],
            source_sha256=item["source_sha256"],
            source_byte_length=item["source_byte_length"],
            normalized_sha256=item["normalized_sha256"],
            normalized_byte_length=item["normalized_byte_length"],
            component_sha256=item["component_sha256"],
            component_byte_length=item["component_byte_length"],
            decode_newline_contract_version=item[
                "decode_newline_contract_version"
            ],
        )
        for item in snapshot["sources"]
    )
    binding = SnapshotDecisionBinding(
        snapshot_contract_version=normalization["snapshot_contract_version"],
        assembly_contract_version=normalization["assembly_contract_version"],
        instruction=DigestLengthBinding(**snapshot["instruction"]),
        inline_input_posture=snapshot["inline_input"]["posture"],
        inline_input=DigestLengthBinding(
            sha256=snapshot["inline_input"]["sha256"],
            byte_length=snapshot["inline_input"]["byte_length"],
        ),
        sources=sources,
        task_data=DigestLengthBinding(**snapshot["task_data"]),
        assembled_execution=DigestLengthBinding(
            **snapshot["assembled_execution"]
        ),
        task_id_posture=intent["task_id_posture"],
        task_id=intent["task_id"],
        declared_privacy=intent["declared_privacy"],
        cloud_intent=intent["cloud_intent"],
        requested_profile=intent["requested_profile"],
        resolved_profile_id=intent["resolved_profile_id"],
        profile_resolution_version=normalization["profile_resolution_version"],
        construction_limits_sha256=config["construction_limits_sha256"],
        worker_system_message_version=config["worker_system_message_version"],
        worker_system_message_sha256=config["worker_system_message_sha256"],
    )
    policy = DecisionPolicyConfiguration(
        configuration_version=config["configuration_version"],
        configuration_sha256=config["configuration_sha256"],
        policy_version=normalization["policy_version"],
        classification_policy_version=config["classification_policy_version"],
        route_policy_version=config["route_policy_version"],
        verification_policy_version=config["verification_policy_version"],
        estimated_input_tokens=budget["estimated_input_tokens"],
        usable_input_tokens=budget["usable_input_tokens"],
        privacy_preflight=privacy["privacy_preflight"],
        classification=classification["category"],
        risk_posture=classification["risk_posture"],
        classification_reason_codes=tuple(classification["reason_codes"]),
        preferred_logical_route=route["preferred_route"],
        permitted_fallback_envelope=tuple(
            route["permitted_fallback_envelope"]
        ),
        route_reason_codes=tuple(route["reason_codes"]),
        terminal_escalation=escalation["terminal_escalation"],
        ethical_firewall=escalation["ethical_firewall"],
        human_review=escalation["human_review"],
        escalation_conditions=tuple(escalation["conditions"]),
        required_checks=tuple(verification["required_checks"]),
    )
    decision = GovernedDecision(decision_id, binding, policy)
    _validate_policy_consistency(binding, policy)
    return decision


def _digest_length_primitive(binding: DigestLengthBinding) -> dict[str, Any]:
    _validate_digest_length(binding, "$.binding")
    return {"sha256": binding.sha256, "byte_length": binding.byte_length}


def _validate_digest_length(
    binding: DigestLengthBinding,
    path: str,
) -> None:
    if not isinstance(binding, DigestLengthBinding):
        raise GovernedDecisionError("digest_length_binding_invalid", path)
    _require_digest(binding.sha256, f"{path}.sha256")
    _require_bounded_int(binding.byte_length, f"{path}.byte_length", minimum=0)


def _validate_digest_length_primitive(raw: Any, path: str) -> None:
    value = _require_object(raw, {"sha256", "byte_length"}, path)
    _require_digest(value["sha256"], f"{path}.sha256")
    _require_bounded_int(value["byte_length"], f"{path}.byte_length", minimum=0)


def _closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GovernedDecisionError("duplicate_key")
        result[key] = value
    return result


def _reject_float(_: str) -> Any:
    raise GovernedDecisionError("float_forbidden")


def _require_object(
    value: Any,
    keys: set[str],
    path: str,
) -> dict[str, Any]:
    if type(value) is not dict:
        raise GovernedDecisionError("object_required", path)
    actual = set(value)
    if actual != keys:
        code = "unknown_field" if actual - keys else "missing_field"
        raise GovernedDecisionError(code, path)
    return value


def _require_array(value: Any, path: str) -> list[Any]:
    if type(value) is not list:
        raise GovernedDecisionError("array_required", path)
    if len(value) > 4096:
        raise GovernedDecisionError("array_too_large", path)
    return value


def _require_enum(value: Any, allowed: frozenset[str], path: str) -> None:
    if type(value) is not str or value not in allowed:
        raise GovernedDecisionError("enum_invalid", path)


def _require_identifier(value: Any, path: str) -> None:
    if type(value) is not str or _IDENTIFIER_RE.fullmatch(value) is None:
        raise GovernedDecisionError("identifier_invalid", path)


def _require_task_id(value: Any, path: str) -> None:
    if type(value) is not str or not value:
        raise GovernedDecisionError("identifier_invalid", path)
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise GovernedDecisionError("identifier_invalid", path) from exc
    if len(encoded) > 512:
        raise GovernedDecisionError("identifier_invalid", path)
    for index, character in enumerate(value):
        category = unicodedata.category(character)
        allowed = category[0] in {"L", "M", "N"} or character in "._:+-"
        if not allowed or (index == 0 and category[0] not in {"L", "N"}):
            raise GovernedDecisionError("identifier_invalid", path)


def _require_digest(value: Any, path: str) -> None:
    if type(value) is not str or _DIGEST_RE.fullmatch(value) is None:
        raise GovernedDecisionError("digest_invalid", path)


def _require_bounded_int(
    value: Any,
    path: str,
    *,
    minimum: int,
) -> None:
    if (
        type(value) is not int
        or value < minimum
        or value > MAX_BOUNDED_INTEGER
    ):
        raise GovernedDecisionError("integer_invalid", path)


def _require_exact_string(
    value: Any,
    expected: str,
    path: str,
    code: str,
) -> None:
    if type(value) is not str or value != expected:
        raise GovernedDecisionError(code, path)


def _validate_code_array(
    value: Any,
    allowed: frozenset[str],
    path: str,
) -> None:
    items = _require_array(value, path)
    for index, item in enumerate(items):
        _require_enum(item, allowed, f"{path}[{index}]")


def _own_code_tuple(
    instance: DecisionPolicyConfiguration,
    field_name: str,
    allowed: frozenset[str],
) -> None:
    raw = getattr(instance, field_name)
    if type(raw) not in {list, tuple}:
        raise GovernedDecisionError("ordered_collection_invalid", f"$.{field_name}")
    if len(raw) > 4096:
        raise GovernedDecisionError("array_too_large", f"$.{field_name}")
    owned = tuple(raw)
    for index, item in enumerate(owned):
        _require_enum(item, allowed, f"$.{field_name}[{index}]")
    object.__setattr__(instance, field_name, owned)
