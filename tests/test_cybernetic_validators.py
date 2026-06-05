from triage_core.validators import CyberneticReportValidator, ModestToolsValidator


def test_modest_tools_validator_blocks_heavy_dependencies():
    assert ModestToolsValidator.validate("import sqlite3") is False
    assert ModestToolsValidator.validate("import csv") is True


def test_cybernetic_report_validator_requires_limits_or_uncertainty():
    assert (
        CyberneticReportValidator.validate(
            "# Report\n## Limitations\nThis is a simulated dataset."
        )
        is True
    )
    assert CyberneticReportValidator.validate("# Report\nThis is the data.") is False
