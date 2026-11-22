"""Grant A regressions for offline public-export eligibility."""

import builtins
import hashlib
import io
import json
import os
import socket
import subprocess
from collections import Counter
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from triage_core.privacy_scanner import PrivacyReport
from triage_core.project_steward import ProjectSteward
from triage_core.public_export import AccessAttestation, evaluate_export
from triage_core.task_packet import PrivacyMetadata

CORPUS_BYTES = (Path(__file__).parent / "fixtures" / "public_export_v0.json").read_bytes()
CORPUS = json.loads(CORPUS_BYTES)
FROZEN_CORPUS_SHA256 = "4c6f7abdb96137eb7cd36fed5d1fbf7a1fb29af687a1027839029ec89b6af3af"
FROZEN_POLICY_SHA256 = "fa17bbf7ea149fa23f8ea41c6cd274ff3e97d06c03d7252ad31bed68e7063dbe"
ELIGIBLE = "eligible_for_operator_reviewed_export"
REVIEW = "review_required"
REFUSE = "ineligible"
TICK = timedelta(microseconds=1)


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def frozen_inputs(case):
    def document(name):
        raw = case.get(name + "_json")
        if raw is not None:
            return raw.encode()
        return encode({**CORPUS[name], **case.get(name + "_patch", {})})

    attestation = case.get("attestation", CORPUS["attestation"])
    if attestation is None:
        answers = ()
    else:
        observed = {**attestation, **case.get("attestation_patch", {})}
        answers = (AccessAttestation(provider=observed["provider"], surface=observed["surface"],
                                     program=observed["program"], scope=observed["credential_scope"],
                                     state=observed["value"], observed_at=timestamp(observed["observed_at"])),)
    return {
        "proposal": document("proposal"),
        "parent": document("parent"),
        "payload": bytes.fromhex(case["payload_hex"]) if "payload_hex" in case else case["payload"].encode(),
        "policy": case.get("policy_json", CORPUS["policy_json"]).encode(),
        "attestations": answers,
        "payload_locator": case.get("payload_locator", CORPUS["payload_locator"]),
        "parent_locator": case.get("parent_locator", CORPUS["parent_locator"]),
        "evaluation_time": timestamp(CORPUS["evaluation_time"]),
        "triagecore_commit": CORPUS["triagecore_commit"],
    }


def patch_document(inputs, name, **changes):
    return {**inputs, name: encode({**json.loads(inputs[name]), **changes})}


@pytest.fixture
def ordinary():
    case = next(case for case in CORPUS["benign"] if case["expected_outcome"] == ELIGIBLE)
    return frozen_inputs(case)


@pytest.fixture
def evaluate_offline(monkeypatch):
    """Count attempted effects even if a dependency catches their exception."""
    def evaluate(inputs):
        effects = []

        def guard(label):
            def attempted(*args, **kwargs):
                effects.append(label)
                raise AssertionError(f"offline evaluation attempted {label}")
            return attempted

        with monkeypatch.context() as m:
            for owner, names in (
                (builtins, ("input", "open")),
                (io, ("open",)),
                (os, ("open", "mkdir", "rename", "replace", "unlink", "remove", "write", "system")),
                (socket, ("getaddrinfo", "create_connection")),
                (socket.socket, ("connect", "connect_ex", "send", "sendto", "sendall")),
                (subprocess, ("Popen",)),
            ):
                for name in names:
                    m.setattr(owner, name, guard(f"{owner.__name__}.{name}"))
            decision = evaluate_export(**inputs)
        assert effects == []
        return decision
    return evaluate


def test_frozen_thresholds_and_case_coverage():
    # Git can check out JSON formatting with CRLF. Embedded payload and policy bytes
    # use JSON escapes and are decoded exactly, including their own line endings.
    assert hashlib.sha256(CORPUS_BYTES.replace(b"\r\n", b"\n")).hexdigest() == FROZEN_CORPUS_SHA256
    assert hashlib.sha256(CORPUS["policy_json"].encode()).hexdigest() == FROZEN_POLICY_SHA256
    assert CORPUS["policy_sha256"].removeprefix("sha256:") == FROZEN_POLICY_SHA256
    benign = CORPUS["benign"]
    assert len(benign) == 12
    counts = Counter(case["family"] for case in benign)
    assert len(counts) == 4 and set(counts.values()) == {3}
    assert Counter(case["expected_outcome"] for case in benign) == {ELIGIBLE: 9, REVIEW: 3}
    assert Counter(trigger for case in benign for trigger in case["expected_triggers"]) == {
        "steward_match": 2, "elevated_task_risk": 1,
    }
    assert {tuple(sorted(json.loads(frozen_inputs(case)["proposal"])["recipient"].items()))
            for case in benign} == {
        (("provider", "openai"), ("surface", "chatgpt_web")),
        (("provider", "openai"), ("surface", "chatgpt_android")),
        (("provider", "anthropic"), ("surface", "claude_ai_web")),
    }
    all_cases = [*benign, *CORPUS["hard_stops"], *CORPUS["policy_controls"]]
    assert len({case["id"] for case in all_cases}) == len(all_cases)
    assert CORPUS["hard_stops"]
    assert all(case["expected_outcome"] == REFUSE and case["expected_reasons"]
               for case in CORPUS["hard_stops"])


@pytest.mark.parametrize(("group", "case"), [
    pytest.param(group, case, id=case["id"])
    for group in ("benign", "hard_stops", "policy_controls") for case in CORPUS[group]
])
def test_frozen_case(group, case, evaluate_offline, record_property):
    inputs = frozen_inputs(case)
    result = evaluate_offline(inputs)
    repeat = evaluate_offline(inputs)
    expected_triggers = case.get("expected_triggers", [])
    expected_reasons = case.get("expected_reasons", [])
    record_property("case_result", json.dumps({
        "case_id": case["id"], "group": group, "family": case["family"],
        "expected_outcome": case["expected_outcome"], "actual_outcome": result.outcome,
        "expected_triggers": expected_triggers, "actual_triggers": list(result.review_triggers),
        "expected_reasons": expected_reasons, "actual_reasons": list(result.reason_codes),
        "eligibility_id": result.eligibility_id, "repeat_id": repeat.eligibility_id,
        "effect_attempts": 0,
    }, sort_keys=True))
    assert result.outcome == case["expected_outcome"]
    assert tuple(sorted(set(expected_triggers))) == result.review_triggers
    assert result.reason_codes == tuple(sorted(set(result.reason_codes)))
    if group == "hard_stops":
        assert set(expected_reasons) <= set(result.reason_codes)
    else:
        assert not result.reason_codes
    assert repeat.body == result.body
    assert repeat.eligibility_id == result.eligibility_id


def test_access_attestation_is_immutable():
    attestation = AccessAttestation(
        provider="openai",
        surface="chatgpt_web",
        program="openai_daybreak",
        scope="account:ordinary-1",
        state="none",
        observed_at=datetime(2026, 11, 22, tzinfo=timezone.utc),
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        attestation.state = "unknown"


def test_decision_binds_frozen_bytes_and_exposes_detached_metadata(ordinary, evaluate_offline):
    secret_instruction = "Finish within three turns and do not browse."
    inputs = patch_document(ordinary, "proposal", recipient_instructions=[secret_instruction])
    inputs["payload"] = b"Describe this public glossary.\r\n"
    result = evaluate_offline(inputs)
    body = result.body
    assert result.outcome == ELIGIBLE
    assert body["schema"] == "triagecore.export_eligibility.v0"
    assert body["profile"] == "public_export_v0"
    assert body["input_basis"] == {
        "proposal": "proposal_declared", "payload": "observed_local", "policy": "operator_policy",
        "evaluation_time": "observed_local", "parent": "parent_declared",
    }
    assert body["payload"]["digest"] == digest(inputs["payload"])
    assert body["payload"]["length"] == len(inputs["payload"])
    assert body["proposal_digest"] == digest(inputs["proposal"])
    assert body["parent"]["bytes_digest"] == digest(inputs["parent"])
    assert body["policy"]["digest"] == digest(inputs["policy"])
    assert body["restrictions"] == [
        {"class": "recipient_instruction", "text_digest": digest(secret_instruction.encode())},
    ]
    assert body["data_class"]["scanner"] == "no_configured_finding"
    assert {k: body["data_class"][k] for k in ("declared", "computed", "effective")} == {
        "declared": "public", "computed": "public", "effective": "public",
    }
    assert {k: body["task_risk"][k] for k in ("declared", "computed", "effective")} == {
        "declared": "low", "computed": "low", "effective": "low",
    }
    assert body["access"]["credential_scope"]["basis"] == "operator_attested"
    assert all(grant["basis"] == "operator_attested" for grant in body["access"]["grants"])
    assert body["parent"]["basis"] == "parent_declared"
    assert body["triagecore_commit"] == inputs["triagecore_commit"]
    for raw in (secret_instruction, "Describe this public glossary.", inputs["parent_locator"],
                inputs["payload_locator"]):
        assert raw not in json.dumps(body)
    assert result.eligibility_id.startswith("sha256:")
    assert result.eligibility_id == digest(b"triagecore.export_eligibility.v0\0" + encode(body))
    body["data_class"]["effective"] = "modified"
    assert result.body["data_class"]["effective"] == "public"


@pytest.mark.parametrize("field", [
    "payload", "policy", "proposal", "parent", "evaluation_time", "triagecore_commit",
    "attestations", "payload_locator", "parent_locator", "requested_operations",
    "recipient_instructions", "declared_data_class", "declared_task_risk", "requested_expiry",
    "recipient", "scope", "state",
])
def test_independent_bound_input_changes_identifier_or_refuses(ordinary, evaluate_offline, field):
    result = evaluate_offline(ordinary)
    assert result.outcome == ELIGIBLE
    inputs = dict(ordinary)
    proposal = json.loads(inputs["proposal"])
    attestation, = inputs["attestations"]
    if field in ("policy", "parent", "proposal"):
        inputs[field] += b"\n"
    elif field == "payload":
        inputs[field] += b"\r\n"
    elif field == "evaluation_time":
        inputs[field] += TICK
    elif field == "triagecore_commit":
        inputs[field] = ("0" if inputs[field][0] != "0" else "1") + inputs[field][1:]
    elif field in ("payload_locator", "parent_locator"):
        inputs[field] += ".other"
    elif field in ("attestations", "scope", "state"):
        changed = {"attestations": {"observed_at": attestation.observed_at - TICK},
                   "scope": {"scope": "account:other-2"}, "state": {"state": "unknown"}}[field]
        inputs["attestations"] = (replace(attestation, **changed),)
    else:
        operation = next(op for op in ("write_critique", "read_provided_text", "draft_test_plan",
                                       "summarize_provided_text") if [op] != proposal["requested_operations"])
        changed = {
            "requested_operations": [operation], "recipient_instructions": ["Answer in two paragraphs."],
            "declared_data_class": "nonpublic", "declared_task_risk": "elevated",
            "requested_expiry": (timestamp(proposal["requested_expiry"]) - TICK).isoformat(),
            "recipient": {"provider": "unlisted", "surface": "unlisted"},
        }
        inputs = patch_document(inputs, "proposal", **{field: changed[field]})
    mutated = evaluate_offline(inputs)
    assert mutated.eligibility_id != result.eligibility_id or mutated.outcome == REFUSE
    if field in ("payload_locator", "parent_locator", "scope", "state", "recipient"):
        assert mutated.outcome == REFUSE


@pytest.mark.parametrize(("where", "field", "reason"), [
    ("proposal", "unrecognized", "unknown_field"),
    ("recipient", "unrecognized", "unknown_field"),
    ("proposal", "approval", "forbidden_field"),
    ("recipient", "basis", "forbidden_field"),
    ("proposal", "max_turns", "unsupported_constraint"),
    ("recipient", "tool_prohibitions", "unsupported_constraint"),
    ("parent", "allowed_recipients", "unsupported_constraint"),
])
def test_untrusted_structured_fields_refuse(ordinary, evaluate_offline, where, field, reason):
    if where == "recipient":
        recipient = json.loads(ordinary["proposal"])["recipient"]
        inputs = patch_document(ordinary, "proposal", recipient={**recipient, field: True})
    else:
        inputs = patch_document(ordinary, where, **{field: True})
    result = evaluate_offline(inputs)
    assert result.outcome == REFUSE
    assert reason in result.reason_codes
    assert result.body["access"]["status"] == "not_collected"


@pytest.mark.parametrize("name", ["proposal", "parent"])
@pytest.mark.parametrize(("raw", "reason"), [
    (b'{"nested":{"x":1,"x":2}}', "duplicate_key"),
    (b'{"x":', "invalid_structure"),
])
def test_parse_failure_stops_before_operator_channel(ordinary, evaluate_offline, name, raw, reason):
    result = evaluate_offline({**ordinary, name: raw})
    assert result.outcome == REFUSE
    assert reason in result.reason_codes
    assert result.body["access"]["status"] == "not_collected"
    assert not set(result.reason_codes) & {"attestation_missing", "grant_not_none"}


@pytest.mark.parametrize("field", ["proposal", "parent", "policy", "payload"])
def test_evaluator_accepts_only_frozen_bytes(ordinary, evaluate_offline, field):
    result = evaluate_offline({**ordinary, field: bytearray(ordinary[field])})
    assert result.outcome == REFUSE


def test_computed_or_approved_record_cannot_be_reused_as_a_proposal(ordinary, evaluate_offline):
    first = evaluate_offline(ordinary)
    assert first.outcome == ELIGIBLE
    for document in (first.body, {"approval": True, "eligibility_id": first.eligibility_id}):
        forged = evaluate_offline({**ordinary, "proposal": encode(document)})
        assert forged.outcome == REFUSE
        assert "forbidden_field" in forged.reason_codes


@pytest.mark.parametrize("metadata", [
    PrivacyMetadata(contains_pii=True), PrivacyMetadata(contains_sensitive_content=True),
    PrivacyMetadata(contains_precise_location=True), PrivacyMetadata(redaction_required=True),
    PrivacyMetadata(external_model_allowed=False),
])
def test_external_use_metadata_lifts_public_floor(ordinary, evaluate_offline, metadata):
    result = evaluate_offline({**ordinary, "privacy_metadata": metadata})
    assert result.outcome == REFUSE
    assert "nonpublic_content" in result.reason_codes
    assert result.body["data_class"]["declared"] == "public"
    assert result.body["data_class"]["computed"] == result.body["data_class"]["effective"] == "nonpublic"


@pytest.mark.parametrize(("declared_class", "declared_risk", "outcome", "class_floor", "risk_floor"), [
    ("public", "elevated", REVIEW, "public", "elevated"),
    ("nonpublic", "low", REFUSE, "nonpublic", "low"),
    ("nonpublic", "elevated", REFUSE, "nonpublic", "elevated"),
    ("public", "consequential", REFUSE, "public", "consequential"),
])
def test_declarations_can_only_raise_computed_floors(ordinary, evaluate_offline, declared_class, declared_risk,
                                                    outcome, class_floor, risk_floor):
    inputs = patch_document(ordinary, "proposal", declared_data_class=declared_class,
                            declared_task_risk=declared_risk)
    result = evaluate_offline(inputs)
    assert result.outcome == outcome
    assert result.body["data_class"]["computed"] == "public"
    assert result.body["data_class"]["effective"] == class_floor
    assert result.body["task_risk"]["computed"] == "low"
    assert result.body["task_risk"]["effective"] == risk_floor
    if outcome == REFUSE:
        assert not result.review_triggers


@pytest.mark.parametrize(("scanner_report", "expected"), [
    (PrivacyReport(True, [], ["Email pattern"]), "nonpublic_content"),
    (PrivacyReport(True, [], ["Secret/API key pattern"]), "credential_pattern"),
    (PrivacyReport(True, [], ["unmapped detection"]), "classification_unavailable"),
    (PrivacyReport(True, ["scanner validation failed"], []), "classification_unavailable"),
])
def test_positive_scanner_status_cannot_override_detections(ordinary, evaluate_offline, monkeypatch,
                                                           scanner_report, expected):
    monkeypatch.setattr("triage_core.public_export.scan_task_packet", lambda packet: scanner_report)
    result = evaluate_offline(ordinary)
    assert result.outcome == REFUSE
    assert expected in result.reason_codes


def test_classification_failure_omits_private_exception_text(ordinary, evaluate_offline, monkeypatch):
    def unavailable(packet):
        raise RuntimeError("private scanner diagnostic")

    monkeypatch.setattr("triage_core.public_export.scan_task_packet", unavailable)
    result = evaluate_offline(ordinary)
    assert result.outcome == REFUSE
    assert "classification_unavailable" in result.reason_codes
    assert "private scanner diagnostic" not in json.dumps(result.body)


@pytest.mark.parametrize(("age", "reason"), [
    (-TICK, "future_dated_attestation"), (timedelta(0), None), (TICK, None),
    (timedelta(minutes=15) - TICK, None), (timedelta(minutes=15), None),
    (timedelta(minutes=15) + TICK, "attestation_stale"),
])
def test_attestation_freshness_uses_injected_clock(ordinary, evaluate_offline, age, reason):
    attestation, = ordinary["attestations"]
    inputs = {**ordinary, "attestations": (replace(attestation, observed_at=ordinary["evaluation_time"] - age),)}
    result = evaluate_offline(inputs)
    if reason:
        assert result.outcome == REFUSE
        assert reason in result.reason_codes
    else:
        assert result.outcome == ELIGIBLE
        assert timestamp(result.body["valid_until"]) <= inputs["attestations"][0].observed_at + timedelta(minutes=15)


@pytest.mark.parametrize(("field", "key", "reason"), [
    ("parent", "expires_at", "parent_expired"), ("proposal", "requested_expiry", "expiry_passed"),
])
@pytest.mark.parametrize("offset", [-TICK, timedelta(0), TICK])
def test_request_and_parent_expiry_boundaries(ordinary, evaluate_offline, field, key, reason, offset):
    expiry = ordinary["evaluation_time"] + offset
    inputs = patch_document(ordinary, field, **{key: expiry.isoformat()})
    result = evaluate_offline(inputs)
    if offset <= timedelta(0):
        assert result.outcome == REFUSE
        assert reason in result.reason_codes
    else:
        assert result.outcome == ELIGIBLE
        assert timestamp(result.body["valid_until"]) == expiry


@pytest.mark.parametrize("bound", ["request", "parent", "attestation"])
@pytest.mark.parametrize("offset", [-TICK, timedelta(0), TICK])
def test_valid_until_uses_earliest_ceiling(ordinary, evaluate_offline, bound, offset):
    now = ordinary["evaluation_time"]
    target = now + timedelta(minutes=10) + offset
    farther = (now + timedelta(minutes=30)).isoformat()
    inputs = patch_document(ordinary, "proposal", requested_expiry=target.isoformat() if bound == "request" else farther)
    inputs = patch_document(inputs, "parent", expires_at=target.isoformat() if bound == "parent" else farther)
    attestation, = ordinary["attestations"]
    observed = target - timedelta(minutes=15) if bound == "attestation" else now
    inputs["attestations"] = (replace(attestation, observed_at=observed),)
    result = evaluate_offline(inputs)
    assert result.outcome == ELIGIBLE
    assert timestamp(result.body["valid_until"]) == min(target, now + timedelta(minutes=10))


@pytest.mark.parametrize(("length", "outcome"), [(16_383, ELIGIBLE), (16_384, ELIGIBLE), (16_385, REFUSE)])
def test_utf8_size_ceiling_counts_raw_bytes(ordinary, evaluate_offline, length, outcome):
    text = ("é" * (length // 2)).encode() + b" " * (length % 2)
    result = evaluate_offline({**ordinary, "payload": text})
    assert result.outcome == outcome
    if outcome == REFUSE:
        assert "payload_too_large" in result.reason_codes
    assert result.body["payload"]["digest"] == digest(text)


@pytest.mark.parametrize("attribute", ["scope", "program", "surface", "provider"])
def test_attestation_must_cover_exact_recipient_program_and_scope(ordinary, evaluate_offline, attribute):
    attestation, = ordinary["attestations"]
    inputs = {**ordinary, "attestations": (replace(attestation, **{attribute: "unrelated"}),)}
    result = evaluate_offline(inputs)
    assert result.outcome == REFUSE
    assert "attestation_missing" in result.reason_codes


def test_conflicting_program_answers_fail_closed(ordinary, evaluate_offline):
    attestation, = ordinary["attestations"]
    granted = replace(attestation, state="granted")
    for answers in [(granted, attestation), (attestation, granted)]:
        assert evaluate_offline({**ordinary, "attestations": answers}).outcome == REFUSE


def test_componentwise_source_and_parent_locator_binding(ordinary, evaluate_offline):
    source = "public/examples/approved.txt"
    inputs = patch_document(ordinary, "parent", allowed_resources=["public/examples"])
    inputs = patch_document(inputs, "proposal", payload_path=source)
    inputs["payload_locator"] = source
    assert evaluate_offline(inputs).outcome == ELIGIBLE
    for actual_locator in ("public/examples-copy/approved.txt", "unlisted/approved.txt"):
        mismatch = {**inputs, "payload_locator": actual_locator}
        assert evaluate_offline(mismatch).outcome == REFUSE
        outside = evaluate_offline(patch_document(mismatch, "proposal", payload_path=actual_locator))
        assert outside.outcome == REFUSE
        assert "source_outside_allowed_resources" in outside.reason_codes
    assert evaluate_offline({**inputs, "parent_locator": "public/unrelated-parent.json"}).outcome == REFUSE


def test_hard_stops_take_precedence_over_review_triggers(ordinary, evaluate_offline):
    inputs = patch_document(ordinary, "proposal", declared_task_risk="elevated", declared_data_class="nonpublic")
    inputs["attestations"] = ()
    result = evaluate_offline(inputs)
    assert result.outcome == REFUSE
    assert result.reason_codes == tuple(sorted(set(result.reason_codes)))
    assert {"nonpublic_content", "attestation_missing"} <= set(result.reason_codes)
    assert result.review_triggers == ()


def test_applicable_parent_gates_are_carried_forward_for_local_confirmation(ordinary, evaluate_offline):
    gates = ["propose_external_export", "external_api_call", "network_access"]
    inputs = patch_document(ordinary, "parent", requires_human_approval_for=[*gates, "unrequested_action"])
    result = evaluate_offline(inputs)
    assert result.outcome == ELIGIBLE
    assert set(result.body["parent"]["local_confirmation_gates"]) == set(gates)
    assert all(op["approval_gate"] == "none" for op in result.body["operations"])


def test_instruction_text_cannot_lower_computed_task_risk(ordinary, evaluate_offline):
    inputs = patch_document(ordinary, "proposal", recipient_instructions=["Perform credential rotation."])
    result = evaluate_offline(inputs)
    assert result.outcome == REFUSE
    assert "consequential_task_risk" in result.reason_codes
    assert result.body["task_risk"]["declared"] == "low"
    assert result.body["task_risk"]["computed"] == result.body["task_risk"]["effective"] == "consequential"


@pytest.mark.parametrize("field", ["evaluation_time", "attestations"])
def test_clock_inputs_reject_naive_or_non_utc_times(ordinary, evaluate_offline, field):
    for tz in (None, timezone(timedelta(hours=2))):
        wrong_time = ordinary["evaluation_time"].replace(tzinfo=tz)
        if field == "attestations":
            attestation, = ordinary[field]
            value = (replace(attestation, observed_at=wrong_time),)
        else:
            value = wrong_time
        assert evaluate_offline({**ordinary, field: value}).outcome == REFUSE


@pytest.mark.parametrize("payload", [
    b"Rotate the API keys.",
    b"Use the OpenAI Daybreak program.",
    b"Test the security of the sample service.",
])
def test_independent_consequential_work_floor(ordinary, evaluate_offline, payload):
    result = evaluate_offline({**ordinary, "payload": payload})
    assert result.outcome == REFUSE
    assert "consequential_task_risk" in result.reason_codes
    assert result.body["task_risk"]["computed"] == "consequential"


def test_independent_precise_coordinate_pair_raises_data_floor(ordinary, evaluate_offline):
    pair = """38°12'34"N 122°35'50"W"""
    result = evaluate_offline({**ordinary, "payload": pair.encode()})
    assert result.outcome == REFUSE
    assert "nonpublic_content" in result.reason_codes
    assert result.body["data_class"]["computed"] == "nonpublic"


def test_independent_neutral_public_bylaws_stay_low_risk(ordinary, evaluate_offline):
    result = evaluate_offline({**ordinary, "payload": b"Review the county bylaws."})
    assert result.outcome == ELIGIBLE
    assert result.body["task_risk"]["computed"] == "low"


def test_independent_parent_permission_is_not_recipient_work(ordinary, evaluate_offline):
    inputs = patch_document(ordinary, "proposal", requested_operations=["propose_external_export"])
    result = evaluate_offline(inputs)
    assert result.outcome == REFUSE
    assert "operation_outside_vocabulary" in result.reason_codes


def test_independent_unknown_scanner_finding_code_refuses(ordinary, evaluate_offline, monkeypatch):
    report = PrivacyReport(True, [], [], finding_codes=["unmapped_finding"])
    monkeypatch.setattr("triage_core.public_export.scan_task_packet", lambda packet: report)
    result = evaluate_offline(ordinary)
    assert result.outcome == REFUSE
    assert "classification_unavailable" in result.reason_codes


def test_independent_unapproved_model_selection_reports_specific_code(ordinary, evaluate_offline):
    raw_name = "vendor/model:unapproved@v1"
    inputs = patch_document(ordinary, "proposal", model_selection=raw_name)
    result = evaluate_offline(inputs)
    assert result.outcome == REFUSE
    assert "model_not_allowlisted" in result.reason_codes
    assert raw_name not in json.dumps(result.body)
    assert digest(raw_name.encode()) in json.dumps(result.body["recipient"]["model_selection"])


@pytest.mark.parametrize("configured", [True, False], ids=["configured", "fallback"])
def test_independent_offline_steward_matches_configured_and_fallback_triggers(configured):
    from triage_core.public_export import _OfflineSteward

    rules_path = Path(__file__).resolve().parents[1] / "policies" / "cybernetic_ecology_boundary.yaml"
    configured_rules = yaml.safe_load(rules_path.read_bytes())["rules"]
    reference = ProjectSteward.__new__(ProjectSteward)
    reference.budgets = {}
    reference.rules = configured_rules if configured else []
    offline = _OfflineSteward()
    if not configured:
        offline.rules = []
    examples = {term for rule in configured_rules for term in rule["trigger"].get("terms", [])}
    examples.update(ProjectSteward.SENSITIVE_KEYWORDS)
    examples.update(("Published county records", """38°12'34"N""", """122°35'50"W"""))
    for phrase in sorted(examples):
        assert offline.evaluate(phrase, [], [])["firewall_triggered"] == reference.evaluate(phrase, [], [])[
            "firewall_triggered"
        ], phrase
