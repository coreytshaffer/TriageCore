"""Offline checks for the closed, operator-supplied public export policy."""

import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from triage_core.public_export_policy import InputError, decode_object, parse_policy


def policy_document():
    return {
        "schema": "triagecore.destination_policy",
        "version": 1,
        "profile": "public_export_v0",
        "external_recipient": {
            "version": 1,
            "recipients": [
                {
                    "provider": "openai",
                    "surface": "chatgpt_android",
                    "programs": ["openai_daybreak"],
                    "models": [],
                    "review_always": True,
                },
            ],
            "operations": ["write_critique"],
            "data_class_ceiling": "public",
            "max_payload_bytes": 8192,
            "attestation_freshness_seconds": 600,
            "eligibility_duration_seconds": 300,
            "approval_ttl_seconds": 60,
        },
        "local_staging": {"version": 1, "roots": [], "clipboard": False},
    }


def encode(policy):
    return json.dumps(policy, separators=(",", ":")).encode()


def test_policy_digest_binds_all_original_bytes_and_returns_immutable_values():
    raw = encode(policy_document())
    policy = parse_policy(raw)
    assert policy.version == 1
    assert policy.digest == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert parse_policy(raw + b"\n").digest != policy.digest
    recipient = policy.recipient("openai", "chatgpt_android")
    assert recipient == policy.recipients[0]
    assert recipient.programs == ("openai_daybreak",)
    assert recipient.models == ()
    assert recipient.review_always
    assert policy.recipient("openai", "chatgpt_web") is None
    assert policy.operations == ("write_critique",)
    assert policy.max_payload_bytes == 8192
    assert policy.attestation_freshness_seconds == 600
    assert policy.eligibility_duration_seconds == 300
    assert policy.approval_ttl_seconds == 60
    with pytest.raises(FrozenInstanceError):
        recipient.programs = ()
    with pytest.raises(FrozenInstanceError):
        policy.max_payload_bytes = 16384


@pytest.mark.parametrize("raw, code", [
    (b'{"v":1,"v":1}', "duplicate_key"),
    (b'{"recipients":[{"a":0,"\\u0061":1}]}', "duplicate_key"),
    (b"[]", "invalid_structure"),
    (b'{"x":NaN}', "invalid_structure"),
    (b'{"x":1e1000}', "invalid_structure"),
    (b'{"x":"\\ud800"}', "invalid_structure"),
    (b'{"x":"\xff"}', "invalid_structure"),
    (b'{} {}', "invalid_structure"),
    ("{}", "invalid_structure"),
])
def test_json_decoder_fails_closed(raw, code):
    with pytest.raises(InputError) as exc:
        decode_object(raw)
    assert exc.value.code == code


@pytest.mark.parametrize("raw", [None, b"", b"{", b"[]", b"{}", b'{"schema":1}'])
def test_missing_or_malformed_policy(raw):
    with pytest.raises(InputError) as exc:
        parse_policy(raw)
    assert exc.value.code == "policy_invalid"


def test_all_approved_surfaces_and_inclusive_ceilings():
    doc = policy_document()
    external = doc["external_recipient"]
    for provider, surface, program in [
        ("openai", "chatgpt_web", "openai_daybreak"),
        ("anthropic", "claude_ai_web", "anthropic_cvp"),
    ]:
        external["recipients"].append({
            "provider": provider, "surface": surface, "programs": [program],
            "models": [], "review_always": False,
        })
    external.update(
        operations=["read_provided_text", "write_critique", "summarize_provided_text", "draft_test_plan"],
        max_payload_bytes=16384, attestation_freshness_seconds=900,
        eligibility_duration_seconds=600, approval_ttl_seconds=120,
    )
    policy = parse_policy(encode(doc))
    assert len(policy.recipients) == 3
    assert len(policy.operations) == 4
    assert policy.recipient("anthropic", "claude_ai_web").programs == ("anthropic_cvp",)
    assert policy.recipient("openai", "chatgpt_web").programs == ("openai_daybreak",)
    assert policy.max_payload_bytes == 16384
    assert policy.attestation_freshness_seconds == 900
    assert policy.eligibility_duration_seconds == 600
    assert policy.approval_ttl_seconds == 120


@pytest.mark.parametrize("path, value, code", [
    (("backend_endpoint",), {}, "unknown_field"),
    (("external_recipient", "endpoint"), "https://example.invalid", "unknown_field"),
    (("external_recipient", "recipients", 0, "endpoint"), 1, "unknown_field"),
    (("external_recipient", "recipients", 0, "basis"), "operator_policy", "forbidden_field"),
    (("local_staging", "command"), "copy", "unknown_field"),
    (("schema",), "triagecore.backend", "policy_invalid"),
    (("profile",), "backend_endpoint_v0", "policy_invalid"),
    (("version",), True, "policy_invalid"),
    (("local_staging", "version"), 1.0, "policy_invalid"),
    (("local_staging", "roots"), ["/tmp"], "policy_invalid"),
    (("local_staging", "clipboard"), 0, "policy_invalid"),
    (("local_staging", "clipboard"), True, "policy_invalid"),
    (("external_recipient", "recipients", 0, "provider"), "anthropic", "policy_invalid"),
    (("external_recipient", "recipients", 0, "surface"), "https://example.invalid", "policy_invalid"),
    (("external_recipient", "recipients", 0, "programs"), [], "policy_invalid"),
    (("external_recipient", "recipients", 0, "programs"), ["anthropic_cvp"], "policy_invalid"),
    (("external_recipient", "recipients", 0, "models"), ["*"], "policy_invalid"),
    (("external_recipient", "recipients", 0, "review_always"), "true", "policy_invalid"),
    (("external_recipient", "data_class_ceiling"), "nonpublic", "policy_invalid"),
    (("external_recipient", "operations"), ["send_message"], "policy_invalid"),
    (("external_recipient", "operations"), [["write_critique"]], "policy_invalid"),
    (("external_recipient", "operations"), ["write_critique"] * 2, "policy_invalid"),
    (("external_recipient", "max_payload_bytes"), 16385, "policy_invalid"),
    (("external_recipient", "attestation_freshness_seconds"), 901, "policy_invalid"),
    (("external_recipient", "eligibility_duration_seconds"), 601, "policy_invalid"),
    (("external_recipient", "approval_ttl_seconds"), 121, "policy_invalid"),
    (("external_recipient", "max_payload_bytes"), True, "policy_invalid"),
    (("external_recipient", "max_payload_bytes"), 0, "policy_invalid"),
    (("external_recipient", "recipients"), {}, "policy_invalid"),
])
def test_policy_is_closed_at_every_level_and_cannot_increase_authority(path, value, code):
    doc = policy_document()
    node = doc
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    with pytest.raises(InputError) as exc:
        parse_policy(encode(doc))
    assert exc.value.code == code


def test_repeated_recipient_refuses_instead_of_shadowing_the_stricter_review_flag():
    doc = policy_document()
    recipients = doc["external_recipient"]["recipients"]
    recipients.append(dict(recipients[0], review_always=False))
    with pytest.raises(InputError) as exc:
        parse_policy(encode(doc))
    assert exc.value.code == "policy_invalid"


def test_duplicate_policy_key_has_specific_diagnostic():
    with pytest.raises(InputError) as exc:
        parse_policy(b'{"version":1,"version":1}')
    assert exc.value.code == "duplicate_key"


def staging_document(base):
    document = policy_document()
    document["version"] = 2
    document["local_staging"] = {
        "version": 2,
        "roots": [str(base / "stage")],
        "evidence_root": str(base / "evidence"),
        "denied_sync_roots": [str(base / "sync")],
        "clipboard": False,
    }
    return document


def test_staging_settings_bind_exact_policy_bytes(tmp_path):
    doc = staging_document(tmp_path)
    raw = encode(doc)
    policy = parse_policy(raw)
    assert policy.version == 2
    assert policy.roots == (str(tmp_path / "stage"),)
    assert policy.evidence_root == str(tmp_path / "evidence")
    assert policy.denied_sync_roots == (str(tmp_path / "sync"),)
    assert policy.digest == "sha256:" + hashlib.sha256(raw).hexdigest()
    for key, value in (("roots", [str(tmp_path / "other")]),
                       ("evidence_root", str(tmp_path / "other")),
                       ("denied_sync_roots", [])):
        variant = staging_document(tmp_path)
        variant["local_staging"][key] = value
        assert parse_policy(encode(variant)).digest != policy.digest
    v1 = parse_policy(encode(policy_document()))
    assert (v1.roots, v1.evidence_root, v1.denied_sync_roots) == ((), None, ())


@pytest.mark.parametrize("field,value", [
    ("version", 1), ("version", 2.0), ("clipboard", True), ("roots", []),
    ("roots", ["relative"]), ("roots", [None]), ("evidence_root", "."),
    ("denied_sync_roots", {}), ("denied_sync_roots", ["../relative"]),
])
def test_invalid_staging_settings(tmp_path, field, value):
    doc = staging_document(tmp_path)
    doc["local_staging"][field] = value
    with pytest.raises(InputError, match="policy_invalid"):
        parse_policy(encode(doc))


def test_staging_authority_rejects_ambiguous_and_overlapping_directories(tmp_path):
    for key, value in (
        ("roots", [str(tmp_path / "stage"), str(tmp_path / "other")]),
        ("roots", [str(tmp_path / "evidence" / "nested")]),
        ("evidence_root", str(tmp_path / "stage")),
        ("evidence_root", str(tmp_path / "stage" / "nested")),
        ("evidence_root", str(tmp_path / "stage" / ".." / "alternate")),
        ("denied_sync_roots", [str(tmp_path)]),
    ):
        doc = staging_document(tmp_path)
        doc["local_staging"][key] = value
        with pytest.raises(InputError, match="policy_invalid"):
            parse_policy(encode(doc))


def test_policy_families_select_exact_section_revisions(tmp_path):
    for field, revision in (("version", 1), ("external_recipient", 2), ("version", 3)):
        doc = staging_document(tmp_path)
        if field == "version":
            doc[field] = revision
        else:
            doc[field]["version"] = revision
        with pytest.raises(InputError):
            parse_policy(encode(doc))
    doc = staging_document(tmp_path)
    doc["local_staging"]["operator_decision"] = "allow"
    with pytest.raises(InputError, match="forbidden_field"):
        parse_policy(encode(doc))
