import pytest

from triage_core.classifier import TaskClassifier, DangerDetector

def test_task_classifier():
    assert TaskClassifier.classify("Please fix this error") == "bugfix"
    assert TaskClassifier.classify("Update the README") == "docs_update"
    assert TaskClassifier.classify("Add a pytest") == "test_addition"
    assert TaskClassifier.classify("Delete all files") == "blocked_or_high_risk"

def test_danger_detector_safe():
    res = DangerDetector.analyze("Add a new print statement to main.py", ["main.py"])
    assert res.risk_level == "low"
    assert res.recommended_profile == "workspace-write"
    assert not res.risk_categories

def test_danger_detector_read_only():
    res = DangerDetector.analyze("Read the config and explain it")
    assert res.risk_level == "low"
    assert res.recommended_profile == "read-only"

def test_danger_detector_high_risk_destructive():
    res = DangerDetector.analyze("Use sudo to rm -rf the secrets directory")
    assert res.risk_level == "high"
    assert res.recommended_profile == "blocked"
    assert "system_modifications" in res.risk_categories
    assert "destructive_ops" in res.risk_categories

def test_danger_detector_high_risk_secrets():
    res = DangerDetector.analyze("Update the credentials", ["secrets.json"])
    assert res.risk_level == "high"
    assert res.recommended_profile == "blocked"
    assert "secrets_and_auth" in res.risk_categories

def test_danger_detector_medium_risk_deployment():
    res = DangerDetector.analyze("Update deploy script", ["deploy.sh"])
    assert res.risk_level == "medium"
    assert res.recommended_profile == "workspace-write-with-approval"
    assert "deployment_config" in res.risk_categories

def test_danger_detector_medium_risk_package():
    res = DangerDetector.analyze("run pip install requests")
    assert res.risk_level == "medium"
    assert res.recommended_profile == "workspace-write-with-approval"
    assert "package_management" in res.risk_categories


@pytest.mark.parametrize(
    "prompt",
    [
        "Approve the authorization plan",
        "Review the authentication architecture",
        "Document the OAuth callback flow",
        "Explain the tokenization algorithm",
    ],
)
def test_protocol_and_substring_terms_are_not_classified_as_secrets(prompt):
    result = DangerDetector.analyze(prompt)

    assert "secrets_and_auth" not in result.risk_categories
    assert result.recommended_profile != "blocked"


@pytest.mark.parametrize(
    "prompt",
    [
        "Rotate the auth token",
        "Revoke the OAuth refresh token",
        "Replace the OAuth client secret",
        "Update the stored credentials",
    ],
)
def test_actual_authentication_secrets_remain_blocked(prompt):
    result = DangerDetector.analyze(prompt)

    assert "secrets_and_auth" in result.risk_categories
    assert result.recommended_profile == "blocked"
