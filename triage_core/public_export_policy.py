"""Parse frozen operator-policy bytes for the offline public-export evaluator."""

import hashlib
import json
from dataclasses import dataclass
from typing import NoReturn


class InputError(ValueError):
    """Closed diagnostic for an input that cannot be used as authority."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    decoded = {}
    for key, value in pairs:
        if key in decoded:
            raise InputError("duplicate_key")
        decoded[key] = value
    return decoded


def _invalid_constant(_text: str) -> NoReturn:
    raise ValueError("nonfinite number")


def decode_object(raw: bytes, invalid_code: str = "invalid_structure") -> dict:
    """Decode one UTF-8 JSON object, preserving duplicate-key errors at every level."""
    if not isinstance(raw, bytes):
        raise InputError(invalid_code)
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant
        )
        # Ensure escaped strings have valid Unicode scalars and exponents stayed finite.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except InputError:
        raise
    except (ValueError, RecursionError) as exc:
        raise InputError(invalid_code) from exc
    if not isinstance(value, dict):
        raise InputError(invalid_code)
    return value


FORBIDDEN_FIELDS = frozenset({
    "basis", "attestation", "attestations", "approval", "operator_decision",
    "admitted", "outcome", "eligibility", "eligibility_id", "review_resolution",
})


def _policy_object(value: object, *fields: str) -> dict:
    if not isinstance(value, dict):
        raise InputError("policy_invalid")
    extra = value.keys() - fields
    if extra & FORBIDDEN_FIELDS:
        raise InputError("forbidden_field")
    if extra:
        raise InputError("unknown_field")
    if len(value) != len(fields):
        raise InputError("policy_invalid")
    return value


def _require_revision_one(value: object) -> None:
    if type(value) is not int or value != 1:
        raise InputError("policy_invalid")


def _limit(value: object, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise InputError("policy_invalid")
    return value


@dataclass(frozen=True, slots=True)
class Recipient:
    provider: str
    surface: str
    programs: tuple[str, ...]
    models: tuple[str, ...]
    review_always: bool


@dataclass(frozen=True, slots=True)
class ExportPolicy:
    version: int
    digest: str
    recipients: tuple[Recipient, ...]
    operations: tuple[str, ...]
    data_class_ceiling: str
    max_payload_bytes: int
    attestation_freshness_seconds: int
    eligibility_duration_seconds: int
    approval_ttl_seconds: int

    def recipient(self, provider: str, surface: str) -> Recipient | None:
        for recipient in self.recipients:
            if (recipient.provider, recipient.surface) == (provider, surface):
                return recipient
        return None


def _recipient(value: object) -> Recipient:
    entry = _policy_object(value, "provider", "surface", "programs", "models", "review_always")
    provider, surface = entry["provider"], entry["surface"]
    if provider == "anthropic" and surface == "claude_ai_web":
        required_program = "anthropic_cvp"
    elif provider == "openai" and surface in ("chatgpt_web", "chatgpt_android"):
        required_program = "openai_daybreak"
    else:
        raise InputError("policy_invalid")
    if entry["programs"] != [required_program] or entry["models"] != []:
        raise InputError("policy_invalid")
    if type(entry["review_always"]) is not bool:
        raise InputError("policy_invalid")
    return Recipient(provider, surface, (required_program,), (), entry["review_always"])


EXPORT_OPERATIONS = frozenset({
    "read_provided_text", "write_critique", "summarize_provided_text", "draft_test_plan",
})


def parse_policy(raw: bytes) -> ExportPolicy:
    """Read the closed recipient and staging sections without any ambient settings or I/O."""
    doc = _policy_object(
        decode_object(raw, "policy_invalid"),
        "schema", "version", "profile", "external_recipient", "local_staging",
    )
    if doc["schema"] != "triagecore.destination_policy" or doc["profile"] != "public_export_v0":
        raise InputError("policy_invalid")
    external = _policy_object(
        doc["external_recipient"], "version", "recipients", "operations", "data_class_ceiling",
        "max_payload_bytes", "attestation_freshness_seconds",
        "eligibility_duration_seconds", "approval_ttl_seconds",
    )
    staging = _policy_object(doc["local_staging"], "version", "roots", "clipboard")
    for section in (doc, external, staging):
        _require_revision_one(section["version"])
    if staging["roots"] != [] or staging["clipboard"] is not False:
        raise InputError("policy_invalid")
    if external["data_class_ceiling"] != "public" or not isinstance(external["recipients"], list):
        raise InputError("policy_invalid")

    recipients = tuple(_recipient(item) for item in external["recipients"])
    if len({(r.provider, r.surface) for r in recipients}) != len(recipients):
        raise InputError("policy_invalid")
    operations = external["operations"]
    if not isinstance(operations, list) or any(
        not isinstance(op, str) or op not in EXPORT_OPERATIONS for op in operations
    ):
        raise InputError("policy_invalid")
    if len(set(operations)) != len(operations):
        raise InputError("policy_invalid")
    return ExportPolicy(
        version=doc["version"],
        digest="sha256:" + hashlib.sha256(raw).hexdigest(),
        recipients=recipients,
        operations=tuple(operations),
        data_class_ceiling=external["data_class_ceiling"],
        max_payload_bytes=_limit(external["max_payload_bytes"], 16384),
        attestation_freshness_seconds=_limit(external["attestation_freshness_seconds"], 900),
        eligibility_duration_seconds=_limit(external["eligibility_duration_seconds"], 600),
        approval_ttl_seconds=_limit(external["approval_ttl_seconds"], 120),
    )
