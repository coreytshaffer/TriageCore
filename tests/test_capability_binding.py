"""Focused tests for observed local capability binding (CR-DD-013).

Every test is fully offline: capability is injected as an in-memory record or a
validated projection, so no network, subprocess, real runtime, or model call
occurs. Freshness-boundary cases use ``operator_recorded`` records, because the
probe contract forbids ``synthetic_fixture`` records from carrying
``observed_at`` and therefore they can never establish freshness.
"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from triage_core import capability_evidence as cap
from triage_core import tc_cli
from triage_core.backends import BackendResponse
from triage_core.client import TriageClient
from triage_core.local_backend_probe import LocalBackendProbeRecord
from triage_core.routing.resilience_router import (
    ResilienceRouteInput,
    choose_resilience_route,
)

NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)
FRESHNESS = 300


def _record(**overrides):
    base = dict(
        source_type="lm_studio",
        base_url="http://localhost:1234",
        reachable=True,
        evidence_tier="operator_recorded",
        observed_at=NOW.isoformat(),
    )
    base.update(overrides)
    return LocalBackendProbeRecord(**base)


def _resolve(record=None, *, fast=False, heavy=False, now=NOW, invalid=False):
    return cap.resolve_capability(
        record=record,
        declare_local_fast=fast,
        declare_local_heavy=heavy,
        config_reference="triagecore.toml:[capability]",
        now=now,
        freshness_seconds=FRESHNESS,
        record_invalid=invalid,
    )


class RecordingBackend:
    name = "fake"
    base_url = "http://localhost"
    model = "fake-model"

    def __init__(self):
        self.called = False

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        return BackendResponse(
            text="LOCAL_RAN", raw={}, usage={}, backend_name=self.name
        )


def _args(prompt="Summarize this text", **overrides):
    base = dict(
        prompt=prompt,
        files=[],
        data=None,
        privacy="local_only",
        allow_cloud=False,
        ledger_dir=None,
        task_id=None,
        output=None,
        print_output=False,
        no_ledger=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- 1. no record and no declarations -------------------------------------


def test_no_record_and_no_declaration_is_unknown_not_healthy():
    resolution = _resolve(None)
    assert resolution.evidence.state == cap.STATE_UNKNOWN
    assert resolution.evidence.reason == cap.UNKNOWN_MISSING
    assert resolution.lm_studio_ok is False
    assert resolution.local_fast_available is False
    assert resolution.local_heavy_available is False


def test_local_only_fails_closed_without_evidence_and_runs_no_worker(monkeypatch):
    backend = RecordingBackend()
    client = TriageClient(backend=backend)
    monkeypatch.setattr(cap, "resolve_from_config", lambda *a, **k: _resolve(None))

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(), client=client)

    assert exc.value.code == 2
    assert backend.called is False


# --- 2/3. observed unavailable and observed available ----------------------


def test_fresh_observed_unavailable_suppresses_all_local_routes():
    resolution = _resolve(
        _record(reachable=False, error_category="endpoint_unreachable"),
        fast=True,
        heavy=True,
    )
    assert resolution.evidence.state == cap.STATE_OBSERVED_UNAVAILABLE
    assert resolution.evidence.error_category == "endpoint_unreachable"
    assert resolution.lm_studio_ok is False
    assert resolution.local_fast_available is False
    assert resolution.local_heavy_available is False


def test_observed_unavailable_is_not_overridden_by_declarations():
    """Precedence 8: a fresh negative observation beats a declaration."""
    resolution = _resolve(
        _record(reachable=False, error_category="timeout"), fast=True, heavy=True
    )
    assert resolution.declared_route_classes == ("local_fast", "local_heavy")
    assert resolution.local_fast_available is False
    assert resolution.local_heavy_available is False


def test_reachable_alone_does_not_make_any_route_class_available():
    resolution = _resolve(_record())
    assert resolution.evidence.state == cap.STATE_OBSERVED_AVAILABLE
    assert resolution.evidence.supported_route_classes == ()
    assert resolution.lm_studio_ok is True
    assert resolution.local_fast_available is False
    assert resolution.local_heavy_available is False


def test_reachable_with_one_declared_class_enables_only_that_class():
    resolution = _resolve(_record(), heavy=True)
    assert resolution.local_heavy_available is True
    assert resolution.local_fast_available is False


def test_model_count_and_observed_models_do_not_imply_class_availability():
    resolution = _resolve(_record(model_count=7, observed_models=["a", "b", "c"]))
    assert resolution.local_fast_available is False
    assert resolution.local_heavy_available is False


# --- 4/5/6. disabled, stale, invalid --------------------------------------


def test_probe_disabled_is_unknown_not_unavailable():
    resolution = _resolve(_record(reachable=False, error_category="probe_disabled"))
    assert resolution.evidence.state == cap.STATE_UNKNOWN
    assert resolution.evidence.reason == cap.UNKNOWN_PROBE_DISABLED
    assert resolution.lm_studio_ok is False


def test_stale_boundary_just_inside_and_at_expiry():
    fresh = _record(observed_at=(NOW - timedelta(seconds=FRESHNESS)).isoformat())
    assert _resolve(fresh).evidence.state == cap.STATE_OBSERVED_AVAILABLE

    expired = _record(observed_at=(NOW - timedelta(seconds=FRESHNESS + 1)).isoformat())
    resolution = _resolve(expired)
    assert resolution.evidence.state == cap.STATE_UNKNOWN
    assert resolution.evidence.reason == cap.UNKNOWN_STALE
    assert resolution.lm_studio_ok is False


def test_applied_freshness_threshold_appears_in_evidence():
    payload = _resolve(_record()).to_evidence_payload()
    assert payload["capability_freshness_seconds"] == FRESHNESS


def test_invalid_record_resolves_to_unknown_and_does_not_execute():
    resolution = _resolve(None, invalid=True)
    assert resolution.evidence.reason == cap.UNKNOWN_INVALID_RECORD
    assert resolution.lm_studio_ok is False


def test_malformed_observed_at_is_invalid_record():
    resolution = _resolve(_record(observed_at="not-a-timestamp"))
    assert resolution.evidence.reason == cap.UNKNOWN_INVALID_RECORD


def test_synthetic_fixture_record_cannot_establish_freshness():
    """Fixture-tier records are forbidden from carrying observed_at."""
    resolution = _resolve(
        _record(evidence_tier="synthetic_fixture", observed_at=None)
    )
    assert resolution.evidence.state == cap.STATE_UNKNOWN
    assert resolution.evidence.reason == cap.UNKNOWN_STALE


def test_malformed_record_file_loads_as_invalid(tmp_path):
    path = tmp_path / "probe.json"
    path.write_text("{not json", encoding="utf-8")
    record, invalid = cap.load_probe_record(str(path))
    assert record is None and invalid is True


def test_missing_record_file_is_not_invalid(tmp_path):
    record, invalid = cap.load_probe_record(str(tmp_path / "absent.json"))
    assert record is None and invalid is False


def test_valid_record_file_round_trips(tmp_path):
    path = tmp_path / "probe.json"
    path.write_text(json.dumps(_record().to_dict()), encoding="utf-8")
    record, invalid = cap.load_probe_record(str(path))
    assert invalid is False
    assert record.reachable is True


# --- 7. configured variant -------------------------------------------------


def test_declaration_without_observation_is_configured_not_observed():
    resolution = _resolve(None, fast=True)
    assert resolution.evidence.state == cap.STATE_CONFIGURED
    assert resolution.evidence.source_type == cap.OPERATOR_CONFIG_SOURCE
    assert resolution.local_fast_available is True
    assert resolution.local_heavy_available is False


def test_configured_evidence_carries_no_probe_provenance():
    payload = _resolve(None, fast=True).to_evidence_payload()
    assert payload["capability_source_type"] == "operator_config"
    assert "capability_observed_at" not in payload
    assert "capability_evidence_tier" not in payload
    assert payload["capability_config_reference"] == "triagecore.toml:[capability]"


def test_ordinary_backend_configuration_is_not_a_declaration():
    """A configured backend type/model/endpoint must not imply capability."""
    config = SimpleNamespace(
        get_capability_probe_record_path=lambda: "",
        get_capability_freshness_seconds=lambda: FRESHNESS,
        # Ordinary backend settings exist, but no capability declaration.
        get_capability_declare_local_fast=lambda: False,
        get_capability_declare_local_heavy=lambda: False,
        get_backend_type=lambda: "ollama",
        get_backend_model=lambda: "llama3",
        get_backend_base_url=lambda: "http://localhost:11434",
    )
    resolution = cap.resolve_from_config(config, now=NOW)
    assert resolution.evidence.state == cap.STATE_UNKNOWN
    assert resolution.lm_studio_ok is False


def test_config_defaults_declare_nothing():
    from triage_core.config import default_config

    assert default_config.get_capability_declare_local_fast() is False
    assert default_config.get_capability_declare_local_heavy() is False
    assert default_config.get_capability_freshness_seconds() == 300
    assert default_config.get_capability_probe_record_path() == ""


# --- 8. discriminated-union validation ------------------------------------


def test_configured_cannot_carry_observed_at():
    with pytest.raises(TypeError):
        cap.Configured(
            config_reference="ref",
            declared_route_classes=("local_fast",),
            observed_at=NOW.isoformat(),
        )


def test_configured_cannot_carry_probe_evidence_tier():
    with pytest.raises(TypeError):
        cap.Configured(
            config_reference="ref",
            declared_route_classes=("local_fast",),
            evidence_tier="local_metadata_probe",
        )


def test_configured_requires_operator_config_source():
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.Configured(
            config_reference="ref",
            declared_route_classes=("local_fast",),
            source_type="lm_studio",
        )


def test_unknown_cannot_carry_a_positive_availability_claim():
    with pytest.raises(TypeError):
        cap.Unknown(reason="missing", supported_route_classes=("local_fast",))


def test_unknown_rejects_unlisted_reason_codes():
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.Unknown(reason="looks_fine")


def test_observed_variants_require_provenance_and_freshness():
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.ObservedAvailable(
            source_type="lm_studio",
            evidence_tier="operator_recorded",
            observed_at="",
            freshness_seconds=FRESHNESS,
        )
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.ObservedAvailable(
            source_type="lm_studio",
            evidence_tier="operator_recorded",
            observed_at=NOW.isoformat(),
            freshness_seconds=0,
        )


def test_observed_variants_reject_configured_marker():
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.ObservedAvailable(
            source_type=cap.OPERATOR_CONFIG_SOURCE,
            evidence_tier="operator_recorded",
            observed_at=NOW.isoformat(),
            freshness_seconds=FRESHNESS,
        )


def test_observed_available_rejects_unknown_route_class():
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.ObservedAvailable(
            source_type="lm_studio",
            evidence_tier="operator_recorded",
            observed_at=NOW.isoformat(),
            freshness_seconds=FRESHNESS,
            supported_route_classes=("cloud_primary",),
        )


def test_observed_unavailable_requires_affected_route_classes():
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.ObservedUnavailable(
            source_type="lm_studio",
            evidence_tier="operator_recorded",
            observed_at=NOW.isoformat(),
            freshness_seconds=FRESHNESS,
            error_category="timeout",
            affected_route_classes=(),
        )


# --- 9. cloud-permitted unknown -------------------------------------------


def test_cloud_permitted_unknown_may_consider_remote_and_states_unknown():
    resolution = _resolve(None)
    route_input = ResilienceRouteInput(
        task_class="security_review",
        complexity="high",
        privacy_level="external_safe",
        lm_studio_ok=resolution.lm_studio_ok,
        local_heavy_available=resolution.local_heavy_available,
        local_fast_available=resolution.local_fast_available,
        internet_ok=True,
        cloud_primary_available=True,
        capability_evidence=resolution,
    )
    decision = choose_resilience_route(route_input)
    assert decision.selected_route.startswith("cloud_")

    payload = resolution.to_evidence_payload()
    assert payload["capability_state"] == cap.STATE_UNKNOWN
    # The escalation must not be described as an observed local failure.
    assert payload.get("capability_error_category") is None
    summary = cap.describe_for_operator(resolution)
    assert "unknown" in summary
    assert "unavailable" not in summary


def test_operator_summary_never_claims_unobserved_failure():
    assert "unavailable" not in cap.describe_for_operator(_resolve(None))
    assert "unavailable" not in cap.describe_for_operator(_resolve(None, fast=True))
    unavailable = _resolve(_record(reachable=False, error_category="timeout"))
    assert "unavailable" in cap.describe_for_operator(unavailable)


# --- 10. direct caller compatibility --------------------------------------


def test_direct_resilience_route_input_callers_are_unchanged():
    """A caller supplying booleans directly sees identical behavior."""
    for privacy in ("local_ok", "local_only"):
        supplied = ResilienceRouteInput(
            task_class="general", complexity="medium", privacy_level=privacy
        )
        assert supplied.capability_evidence is None
        assert choose_resilience_route(supplied).selected_route == "local_heavy"


def test_run_task_without_capability_preserves_previous_route_input():
    """run_task callers that pass no capability keep the old literals."""
    route_input = TriageClient._build_resilience_route_input(
        category="docs_update", validator=None
    )
    assert route_input.lm_studio_ok is True
    assert route_input.local_heavy_available is True
    assert route_input.local_fast_available is True
    assert route_input.capability_evidence is None


# --- 11. evidence distinguishes all four states ---------------------------


@pytest.mark.parametrize(
    ("resolution_factory", "expected_state"),
    [
        (lambda: _resolve(_record()), cap.STATE_OBSERVED_AVAILABLE),
        (
            lambda: _resolve(_record(reachable=False, error_category="timeout")),
            cap.STATE_OBSERVED_UNAVAILABLE,
        ),
        (lambda: _resolve(None, fast=True), cap.STATE_CONFIGURED),
        (lambda: _resolve(None), cap.STATE_UNKNOWN),
    ],
)
def test_evidence_payload_distinguishes_every_state(resolution_factory, expected_state):
    payload = resolution_factory().to_evidence_payload()
    assert payload["capability_state"] == expected_state


def test_evidence_payload_carries_no_secrets_or_raw_endpoint():
    payload = _resolve(_record(base_url="http://localhost:1234")).to_evidence_payload()
    serialized = json.dumps(payload)
    assert "localhost:1234" not in serialized
    assert "http://" not in serialized


def test_mixed_observation_and_declaration_keeps_provenance_separate():
    """Fresh reachable + declare_local_heavy must not attribute the class to the probe.

    The runtime state may be observed_available, but the route class came from
    operator configuration, so it must appear under the declared list and never
    under the supported (observation-backed) list.
    """
    from triage_core.routing.route_events import build_route_decision_payload

    resolution = _resolve(_record(), heavy=True)
    assert resolution.evidence.state == cap.STATE_OBSERVED_AVAILABLE
    # The observation itself supports no route class.
    assert resolution.evidence.supported_route_classes == ()
    assert resolution.declared_route_classes == ("local_heavy",)

    route_input = ResilienceRouteInput(
        lm_studio_ok=resolution.lm_studio_ok,
        local_heavy_available=resolution.local_heavy_available,
        local_fast_available=resolution.local_fast_available,
        capability_evidence=resolution,
    )
    payload = build_route_decision_payload(
        route_input, choose_resilience_route(route_input)
    )

    assert payload["capability_state"] == cap.STATE_OBSERVED_AVAILABLE
    assert payload["capability_supported_route_classes"] == []
    assert payload["capability_declared_route_classes"] == ["local_heavy"]
    # local_heavy must never be presented as observation-backed.
    assert "local_heavy" not in payload["capability_supported_route_classes"]


def test_configured_variant_requires_declared_route_classes():
    """Configured carries its declared classes; it does not omit them."""
    evidence = cap.Configured(
        config_reference="triagecore.toml:[capability]",
        declared_route_classes=("local_fast",),
    )
    assert evidence.declared_route_classes == ("local_fast",)
    with pytest.raises(cap.CapabilityEvidenceError):
        cap.Configured(
            config_reference="triagecore.toml:[capability]",
            declared_route_classes=(),
        )


def test_unknown_forbids_every_route_class_field():
    for keyword in (
        "declared_route_classes",
        "supported_route_classes",
        "affected_route_classes",
    ):
        with pytest.raises(TypeError):
            cap.Unknown(reason="missing", **{keyword: ("local_fast",)})


def test_route_decision_payload_includes_capability_provenance():
    from triage_core.routing.route_events import build_route_decision_payload

    resolution = _resolve(_record(), heavy=True)
    route_input = ResilienceRouteInput(
        lm_studio_ok=resolution.lm_studio_ok,
        local_heavy_available=resolution.local_heavy_available,
        local_fast_available=resolution.local_fast_available,
        capability_evidence=resolution,
    )
    decision = choose_resilience_route(route_input)
    payload = build_route_decision_payload(route_input, decision)
    assert payload["capability_state"] == cap.STATE_OBSERVED_AVAILABLE
    assert payload["capability_evidence_tier"] == "operator_recorded"
    assert payload["capability_freshness_seconds"] == FRESHNESS


# --- no probe side effects -------------------------------------------------


def test_resolution_performs_no_network_subprocess_or_model_call():
    import socket
    import subprocess

    def _fail(*args, **kwargs):  # pragma: no cover - trap
        raise AssertionError("capability resolution must not reach the network")

    with patch.object(socket.socket, "connect", _fail):
        with patch.object(subprocess, "Popen", _fail):
            with patch("requests.get", _fail), patch("requests.post", _fail):
                resolution = _resolve(_record(), heavy=True)
    assert resolution.lm_studio_ok is True
