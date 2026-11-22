"""Grant A. Evaluate frozen public-export inputs entirely in memory."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from .agent_authority import REQUIRED_FIELD_PATHS, validate_authority_manifest
from .classifier import DangerDetector
from .privacy_findings import KNOWN_PRIVACY_FINDING_CODES, PRIVACY_CHECK_FAILED
from .privacy_scanner import scan_task_packet
from .project_steward import ProjectSteward
from .public_export_policy import (
    FORBIDDEN_FIELDS,
    InputError,
    decode_object,
    parse_policy,
)
from .safe_task_packet import (
    UnsafePacketError,
    VerifiedTaskPacket,
    make_external_safe_packet,
)
from .task_packet import PrivacyMetadata, TaskPacket


@dataclass(frozen=True)
class AccessAttestation:
    """One answer from the simulated, trusted operator channel."""

    provider: str
    surface: str
    program: str
    scope: str
    state: str
    observed_at: datetime


@dataclass(frozen=True)
class ExportEligibility:
    eligibility_id: str
    outcome: str
    reason_codes: tuple[str, ...]
    review_triggers: tuple[str, ...]
    _canonical_body: bytes

    @property
    def body(self) -> dict:
        """Return a detached view so callers cannot modify the decision."""
        return json.loads(self._canonical_body)


_PROPOSAL = frozenset({
    "schema", "proposal_id", "payload_path", "parent_manifest_path", "recipient",
    "requested_operations", "recipient_instructions", "declared_data_class",
    "declared_task_risk", "requested_expiry",
})
_UNENFORCEABLE = {"max_turns", "tool_prohibitions"}
_PARENT = {path[2:] for path in REQUIRED_FIELD_PATHS}
_EXCLUDED = {
    "claude_console", "claude_api", "claude_console_api", "claude_api_workspace",
    "responses_api", "openai_responses_api", "codex", "codex_cli", "codex_app",
    "desktop_stdio_mcp", "desktop_local_stdio_mcp", "desktop_stdio_mcp_plugin",
}
_EGRESS = {"network_access", "external_api_call"}
_DATA = ("public", "nonpublic")
_RISK = ("low", "elevated", "consequential")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z")
_KNOWN_FINDINGS = {
    "SSN pattern", "Email pattern", "Phone pattern", "Credit Card pattern",
    "Sensitive marker", "Precise location pattern", "Secret/API key pattern",
}
_CONSEQUENTIAL = re.compile(
    r"\b(?:security[ -]+(?:test(?:s|ing)?|assessments?)|penetration[ -]+test(?:s|ing)?|"
    r"(?:test|assess|probe)\s+(?:the\s+)?security\b|"
    r"credentials?|deploy(?:s|ed|ing|ments?)?|"
    r"privileged[ -]+(?:programs?|access|operations?)|"
    r"(?:rotate|revoke|issue|create|use|copy|print|reset|retrieve|manage|exchange)\s+"
    r"(?:the\s+|a[n]?\s+)?(?:api|access|private|signing)[ -]+keys?|"
    r"(?:api|access|private|signing)[ -]+key[ -]+(?:rotation|management)|"
    r"(?:use|enable|invoke|activate|access)\s+(?:the\s+)?"
    r"(?:(?:openai\s+)?daybreak|(?:anthropic\s+)?(?:cvp|cyber verification program)))\b",
    re.IGNORECASE,
)


class _ExportDangerDetector(DangerDetector):
    # The router's bare "aws" also matches ordinary words such as "bylaws".
    DEPLOYMENT_CONFIG = (r"\bdeploy(?:s|ed|ing|ments?)?\b", r"\bdocker-compose\b",
                         r"\bk8s\b", r"\bterraform\b", r"\baws\b")


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _digest(raw: bytes, domain: bytes = b"") -> str:
    return "sha256:" + hashlib.sha256(domain + raw).hexdigest()


def _bytes_digest(value) -> str | None:
    return _digest(value) if type(value) is bytes else None


def _locator_digest(value) -> str | None:
    if type(value) is not str:
        return None
    return _digest(_canonical_string(value), b"triagecore.export_locator.v0\0")


def _canonical_string(value: str) -> bytes:
    # Escape lone surrogates in malformed trusted input so even the refusal is encodable.
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def _finish(body, reasons, triggers=()) -> ExportEligibility:
    reasons = tuple(sorted(set(reasons)))
    triggers = () if reasons else tuple(sorted(set(triggers)))
    outcome = ("ineligible" if reasons else "review_required" if triggers
               else "eligible_for_operator_reviewed_export")
    body.update(outcome=outcome, reason_codes=list(reasons), review_triggers=list(triggers))
    canonical = _canonical(body)
    return ExportEligibility(_digest(canonical, b"triagecore.export_eligibility.v0\0"),
                             outcome, reasons, triggers, canonical)


def _utc(value) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
        raise InputError("invalid_structure")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _timestamp(value, code="invalid_structure") -> datetime:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        raise InputError(code)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError(code) from exc


def _identifier(value) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.fullmatch(value))


def _closed(data, required, optional=()):
    if not isinstance(data, dict):
        raise InputError("invalid_structure")
    extra = set(data).difference(required, optional)
    if extra & _UNENFORCEABLE:
        raise InputError("unsupported_constraint")
    if extra & FORBIDDEN_FIELDS:
        raise InputError("forbidden_field")
    if extra:
        raise InputError("unknown_field")
    if not set(required) <= data.keys():
        raise InputError("invalid_structure")


def _proposal(raw):
    p = decode_object(raw)
    _closed(p, _PROPOSAL, {"model_selection"})
    _closed(p["recipient"], {"provider", "surface"})
    if p["schema"] != "triagecore.export_proposal.v0":
        raise InputError("invalid_structure")
    try:
        if not isinstance(p["proposal_id"], str) or str(UUID(p["proposal_id"])) != p["proposal_id"].lower():
            raise ValueError
    except ValueError as exc:
        raise InputError("invalid_structure") from exc
    if not all(_identifier(v) for v in p["recipient"].values()):
        raise InputError("invalid_structure")
    if "model_selection" in p and not (isinstance(p["model_selection"], str) and p["model_selection"].strip()):
        raise InputError("invalid_structure")
    ops, instructions = p["requested_operations"], p["recipient_instructions"]
    if (not isinstance(ops, list) or not ops or not all(_identifier(op) for op in ops)
            or len(set(ops)) != len(ops)):
        raise InputError("invalid_structure")
    if not isinstance(instructions, list) or not all(isinstance(t, str) for t in instructions):
        raise InputError("invalid_structure")
    if p["declared_data_class"] not in _DATA or p["declared_task_risk"] not in _RISK:
        raise InputError("invalid_structure")
    if not all(isinstance(p[k], str) and p[k] for k in ("payload_path", "parent_manifest_path")):
        raise InputError("invalid_structure")
    return p


def _parts(path, *, prefix=False):
    """Portable, component-based repository paths. Never resolve or open a file."""
    if not isinstance(path, str):
        return None
    if prefix:
        path = path.removesuffix("/")
    parts = path.split("/")
    for part in parts:
        if (not part or part in (".", "..") or part.endswith((" ", "."))
                or any(ord(c) < 32 or c in '<>:"\\|?*' for c in part)
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)):
            return None
    return parts


def _parent_permissions(manifest, p, policy, body, reasons):
    allowed, denied, gated = (set(manifest[k]) for k in
                              ("allowed_actions", "denied_actions", "requires_human_approval_for"))
    if denied & _EGRESS:
        reasons.add("egress_denied_by_parent")
    gates = sorted(gated & (_EGRESS | {"propose_external_export"}))
    body["parent"]["local_confirmation_gates"] = gates
    for position, op in enumerate(["propose_external_export", *p["requested_operations"]]):
        requested = position > 0
        permission = "allowed" if op in allowed else "not_permitted"
        if op in denied:
            permission = "denied"
        if requested and op not in policy.operations:
            reasons.add("operation_outside_vocabulary")
        elif permission != "allowed":
            reasons.add("operation_" + permission)
        if requested:
            if op in gated:
                reasons.add("approval_gate_unsupported")
            body["operations"].append({"name": op, "parent": permission,
                                       "approval_gate": "unsupported" if op in gated else "none"})


# Frozen projection of the checked-in steward boundary rules. ProjectSteward also
# applies its fallback keywords on a configured-rule miss. Bind both to the result.
_STEWARD_TERMS = (
    ("tribal_sovereignty_and_confidentiality", ("tribal", "bo-no-po-ti", "bloody island",
     "sacred", "archaeological", "burial", "cultural resource", "confidential infrastructure")),
    ("public_health_and_safety", ("water intake", "sewer lift", "unsafe", "toxic",
     "cyanobacteria bloom", "do not swim", "contamination")),
    ("regulatory_interpretation", ("violates regulation", "out of compliance",
     "illegal discharge", "violation")),
)
_COORDINATES = tuple(r"""\d{1,3}°\d{1,2}'\d{1,2}"\s*""" + side for side in ("[NS]", "[EW]"))
_DMS = r"""\b\d{1,3}\s*°\s*\d{1,2}\s*['′]\s*\d{1,2}(?:\.\d+)?\s*["″]\s*"""
_DMS_AXES = tuple(re.compile(_DMS + side + r"\b", re.IGNORECASE) for side in ("[NS]", "[EW]"))


class _OfflineSteward(ProjectSteward):
    def _load_boundary_rules(self):
        return [{"id": name, "trigger": {"terms": terms}} for name, terms in _STEWARD_TERMS] + [
            {"id": "sensitive_coordinates", "trigger": {"regex": _COORDINATES}}
        ]


def _classify(p, content, meta, body, reasons, triggers):
    if (type(meta) is not PrivacyMetadata or not isinstance(meta.data_class, str)
            or not isinstance(meta.retention_policy, str)
            or not all(type(getattr(meta, k)) is bool for k in
                       ("contains_pii", "contains_sensitive_content", "contains_precise_location",
                        "redaction_required", "external_model_allowed"))):
        raise InputError("classification_unavailable")
    meta = PrivacyMetadata(**asdict(meta))
    body["classification_inputs"]["metadata_digest"] = _digest(_canonical(asdict(meta)))
    packet = TaskPacket(prompt="", data=content, privacy_metadata=meta)
    report = scan_task_packet(packet)
    if (type(report.passed) is not bool or not isinstance(report.violations, list)
            or report.passed != (not report.violations) or not isinstance(report.detections, list)
            or any(d not in _KNOWN_FINDINGS for d in report.detections)):
        raise InputError("classification_unavailable")
    codes = [] if report.finding_codes is None else report.finding_codes
    if (not isinstance(codes, list) or set(codes) - KNOWN_PRIVACY_FINDING_CODES
            or PRIVACY_CHECK_FAILED in codes):
        raise InputError("classification_unavailable")
    findings = set(report.detections)
    if all(axis.search(content) for axis in _DMS_AXES):
        findings.add("Precise location pattern")
    computed = "nonpublic" if findings or codes else "public"
    verified = VerifiedTaskPacket(prompt="", data=content, privacy_metadata=meta, scan_report=report)
    try:
        make_external_safe_packet(verified)
    except UnsafePacketError:
        computed = "nonpublic"
    effective = max(p["declared_data_class"], computed, key=_DATA.index)
    scanner = "configured_finding" if findings or codes else "no_configured_finding"
    body["data_class"] = {"declared": p["declared_data_class"], "computed": computed,
                          "effective": effective, "scanner": scanner,
                          "detections": sorted(findings), "finding_codes": sorted(set(codes))}
    if "Secret/API key pattern" in findings:
        reasons.add("credential_pattern")
    if effective != "public":
        reasons.add("nonpublic_content")

    work = "\n".join([content, *p["requested_operations"], *p["recipient_instructions"]])
    danger = _ExportDangerDetector.analyze(work)
    computed = {"low": "low", "medium": "elevated", "high": "consequential"}[danger.risk_level]
    if _CONSEQUENTIAL.search(work):
        computed = "consequential"
    risk = max(p["declared_task_risk"], computed, key=_RISK.index)
    body["task_risk"] = {"declared": p["declared_task_risk"], "computed": computed, "effective": risk}
    if risk == "consequential":
        reasons.add("consequential_task_risk")
    elif risk == "elevated":
        triggers.add("elevated_task_risk")
    steward = _OfflineSteward()
    body["classification_inputs"]["steward_digest"] = _digest(_canonical(
        {"rules": steward.rules, "fallback": sorted(steward.SENSITIVE_KEYWORDS)}))
    if steward.evaluate(work, [], [])["firewall_triggered"]:
        triggers.add("steward_match")


def _deadline(start, seconds):
    try:
        return start + timedelta(seconds=seconds)
    except OverflowError:
        return datetime.max.replace(tzinfo=timezone.utc)


def _access(recipient, attested, scope, now, policy, body, reasons):
    if type(attested) is not tuple:
        raise InputError("invalid_structure")
    answers = {}
    entries = []
    for answer in attested:
        if type(answer) is not AccessAttestation:
            raise InputError("invalid_structure")
        if (not all(_identifier(getattr(answer, key)) for key in ("provider", "surface", "program", "scope"))
                or answer.state not in ("none", "granted", "unknown")):
            raise InputError("invalid_structure")
        observed = _utc(answer.observed_at)
        entries.append({**asdict(answer), "observed_at": _stamp(observed)})
        if ((answer.provider, answer.surface, answer.scope) ==
                (recipient.provider, recipient.surface, scope) and answer.program in recipient.programs):
            if answer.program in answers:
                raise InputError("invalid_structure")
            answers[answer.program] = answer
        else:
            reasons.add("attestation_missing")
    grants = []
    deadlines = []
    body["access"] = {"status": "collected", "mode_mechanism": "none_documented",
                      "channel_digest": _digest(_canonical(entries)), "grants": grants}
    for program in recipient.programs:
        answer = answers.get(program)
        if answer is None:
            reasons.add("attestation_missing")
            continue
        observed = _utc(answer.observed_at)
        grant = {"program": program, "value": answer.state, "basis": "operator_attested",
                 "observed_at": _stamp(observed)}
        grants.append(grant)
        body["access"]["credential_scope"] = {"value": scope, "basis": "operator_attested",
                                              "observed_at": _stamp(observed)}
        end = _deadline(observed, policy.attestation_freshness_seconds)
        deadlines.append(end)
        if observed > now:
            reasons.add("future_dated_attestation")
        elif end < now:
            reasons.add("attestation_stale")
        if answer.state != "none":
            reasons.add("grant_not_none")
    return deadlines


def evaluate_export(*, proposal: bytes, payload: bytes, parent: bytes, policy: bytes,
                    payload_locator: str, parent_locator: str, attestations: tuple[AccessAttestation, ...],
                    evaluation_time: datetime, triagecore_commit: str,
                    privacy_metadata: PrivacyMetadata | None = None) -> ExportEligibility:
    """Evaluate a caller-frozen snapshot. Locators describe those buffers; they are never opened.

    The Grant A operator channel is synthetic and scoped to account:ordinary-1.
    Authorization to confirm or stage any bytes is outside this interface.
    """
    body = {
        "schema": "triagecore.export_eligibility.v0", "profile": "public_export_v0",
        "input_basis": {"proposal": "proposal_declared", "payload": "observed_local",
                        "parent": "parent_declared", "policy": "operator_policy",
                        "evaluation_time": "observed_local"},
        "proposal_digest": _bytes_digest(proposal),
        "payload": {"digest": _bytes_digest(payload), "length": len(payload) if type(payload) is bytes else None,
                    "locator_digest": _locator_digest(payload_locator)},
        "parent": {"bytes_digest": _bytes_digest(parent), "locator_digest": _locator_digest(parent_locator)},
        "policy": {"digest": _bytes_digest(policy)}, "access": {"status": "not_collected"},
        "operations": [], "restrictions": [], "valid_until": None,
        "classification_inputs": {"version": "public_export_v0.m05.1",
                                  "steward_version": "cybernetic_ecology_boundary.v1"},
    }
    reasons, triggers = set(), set()
    try:
        now = _utc(evaluation_time)
        body["evaluation_time"] = _stamp(now)
        if not isinstance(triagecore_commit, str) or not re.fullmatch("[0-9a-f]{40}", triagecore_commit):
            raise InputError("invalid_structure")
        body["triagecore_commit"] = triagecore_commit
        parsed_policy = parse_policy(policy)
        body["policy"]["version"] = parsed_policy.version
        p = _proposal(proposal)
        expiry = _timestamp(p["requested_expiry"])
        manifest = decode_object(parent)
        if manifest.keys() - _PARENT:
            raise InputError("unsupported_constraint")
        parent_expiry = _timestamp(manifest.get("expires_at"), "parent_invalid")
        checked = validate_authority_manifest(manifest, now=now)
        for issue in checked.issues:
            reasons.add({"expired_authority_manifest": "parent_expired",
                         "inactive_authority_manifest": "parent_inactive"}.get(issue.reason, "parent_invalid"))
        if "parent_invalid" in reasons:
            return _finish(body, reasons)
        body["parent"].update(agent_id=manifest["agent_id"], expires_at=_stamp(parent_expiry),
                              revocation_status=manifest["revocation_status"], basis="parent_declared")
        if not _parts(parent_locator) or parent_locator != p["parent_manifest_path"]:
            raise InputError("parent_invalid")
        source = _parts(payload_locator)
        prefixes = [_parts(path, prefix=True) for path in manifest["allowed_resources"]]
        if (not source or payload_locator != p["payload_path"]
                or not any(prefix and source[:len(prefix)] == prefix for prefix in prefixes)):
            reasons.add("source_outside_allowed_resources")
        if type(payload) is not bytes:
            raise InputError("invalid_structure")
        if len(payload) > parsed_policy.max_payload_bytes:
            raise InputError("payload_too_large")
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InputError("payload_not_utf8") from exc
        _parent_permissions(manifest, p, parsed_policy, body, reasons)
        body["restrictions"] = [{"class": "recipient_instruction", "text_digest": _digest(t.encode("utf-8"))}
                                for t in p["recipient_instructions"]]
        provider, surface = p["recipient"]["provider"], p["recipient"]["surface"]
        body["recipient"] = {"provider": provider, "surface": surface}
        recipient = parsed_policy.recipient(provider, surface)
        if surface in _EXCLUDED:
            reasons.add("surface_excluded_from_v0")
        elif not recipient:
            reasons.add("recipient_not_allowlisted")
        if "model_selection" in p:
            model = p["model_selection"]
            body["recipient"]["model_selection"] = {"value_digest": _digest(model.encode("utf-8")),
                                                    "basis": "proposal_declared"}
            if not recipient or model not in recipient.models:
                reasons.add("model_not_allowlisted")
        if recipient and recipient.review_always:
            triggers.add("recipient_review_always")
        if expiry <= now:
            reasons.add("expiry_passed")
        try:
            _classify(p, content, PrivacyMetadata() if privacy_metadata is None else privacy_metadata,
                      body, reasons, triggers)
        except Exception:  # noqa: BLE001 - mandatory classifier boundary, including third-party failures
            # Classification is mandatory. Dependency diagnostics may contain private input.
            reasons.add("classification_unavailable")
        if recipient:
            windows = _access(recipient, attestations, "account:ordinary-1", now, parsed_policy, body, reasons)
            if not reasons:
                body["valid_until"] = _stamp(min(expiry, parent_expiry,
                                                 _deadline(now, parsed_policy.eligibility_duration_seconds),
                                                 *windows))
    except InputError as exc:
        reasons.add(exc.code)
    return _finish(body, reasons, triggers)
