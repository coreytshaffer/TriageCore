import pytest

from triage_core.benchmarks import resolve_validator
from triage_core.validators import ErrorWarningMarkdownValidator, MonitoringJsonValidator


def test_monitoring_json_validator_accepts_expected_compact_json():
    output = (
        '{"site_id":"CLW-07","date":"2026-06-03",'
        '"temperature_c":21.4,"turbidity_ntu":8.7}'
    )

    assert MonitoringJsonValidator.validate(output) is True


def test_monitoring_json_validator_rejects_missing_expected_value():
    output = (
        '{"site_id":"CLW-99","date":"2026-06-03",'
        '"temperature_c":21.4,"turbidity_ntu":8.7}'
    )

    assert MonitoringJsonValidator.validate(output) is False


def test_error_warning_markdown_validator_accepts_warning_and_error_bullets():
    output = "- WARN: Latency spike detected.\n- ERROR: Connection timeout on database sync."

    assert ErrorWarningMarkdownValidator.validate(output) is True


def test_error_warning_markdown_validator_rejects_info_noise():
    output = (
        "- INFO: Service started.\n"
        "- WARN: Latency spike detected.\n"
        "- ERROR: Connection timeout on database sync."
    )

    assert ErrorWarningMarkdownValidator.validate(output) is False


@pytest.mark.parametrize(
    "name",
    [
        "python_syntax",
        "monitoring_json",
        "error_warning_markdown",
        "none",
        None,
    ],
)
def test_resolve_validator_accepts_known_validator_names(name):
    validator = resolve_validator(name)

    assert validator is None or callable(validator)
