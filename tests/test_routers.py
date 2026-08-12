import socket
from unittest.mock import patch, MagicMock
from triage_core.routers import is_internet_available, extract_first_code_block, strip_code_fences, SpecialistRouter

def test_is_internet_available_does_not_mutate_global_timeout():
    original_timeout = socket.getdefaulttimeout()
    
    # Mock socket so it doesn't depend on actual network
    with patch('socket.socket') as mock_socket:
        mock_instance = MagicMock()
        mock_socket.return_value.__enter__.return_value = mock_instance
        
        try:
            result = is_internet_available(host="203.0.113.1", port=53, timeout=0.01)
            assert result is True
            assert socket.getdefaulttimeout() == original_timeout
            mock_instance.settimeout.assert_called_with(0.01)
        finally:
            socket.setdefaulttimeout(original_timeout)

def test_extract_first_code_block():
    text = "Here is the code:\n```python\nprint('hello')\n```\nAnd some more text."
    assert extract_first_code_block(text) == "print('hello')"

def test_strip_code_fences():
    text = "Here is the code:\n```python\nprint('hello')\n```\nAnd some more text."
    # The current regex leaves \n after the closing ``` if it's there, which is acceptable.
    # The most important part is removing the fences themselves.
    stripped = strip_code_fences(text)
    assert "```" not in stripped
    assert "print('hello')" in stripped
    assert "Here is the code:" in stripped
    
def test_specialist_router_offline_medium_risk():
    router = SpecialistRouter()
    
    with patch('triage_core.routers.is_internet_available', return_value=False), \
         patch('triage_core.routers.DangerDetector.analyze') as mock_analyze:
         
        mock_danger_info = MagicMock()
        mock_danger_info.risk_level = "medium"
        mock_danger_info.reasons = ["suspicious file access"]
        mock_analyze.return_value = mock_danger_info
        
        result = router.route_task("python_generation", "some prompt", "some data")
        
        assert result["offload_recommended"] is False
        assert result["offline_fallback"] is True
        assert "medium offline fallback" in result["reason"]


# --- CR-DD-018: bounded structured specialist-offload cause -------------------
#
# These are contract tests: they exercise the real SpecialistRouter/DangerDetector
# decision logic and mock only connectivity at the external is_internet_available()
# boundary, so they never depend on ambient network state.

def _cause(category, prompt, data="", *, online=True):
    with patch('triage_core.routers.is_internet_available', return_value=online):
        result = SpecialistRouter().route_task(category, prompt, data)
    return result


def test_specialist_cause_high_risk_variant():
    result = _cause("bugfix", "please rm -rf the build directory")
    assert result["offload_recommended"] is True
    cause = result["specialist_offload_cause"]
    assert cause["offload_reason_code"] == "high_risk"
    assert cause["risk_level"] == "high"
    assert "destructive_ops" in cause["risk_categories"]
    # Not a connectivity- or context-driven offload.
    assert "internet_available" not in cause
    assert "context_limit_exceeded" not in cause


def test_specialist_cause_safety_handoff_variant():
    """The explicit category triggers the branch independent of risk assessment."""
    result = _cause("safety_handoff", "summarize the meeting notes")
    assert result["offload_recommended"] is True
    cause = result["specialist_offload_cause"]
    assert cause["offload_reason_code"] == "safety_handoff"
    assert cause["risk_level"] == "low"
    assert cause["risk_categories"] == []
    assert "internet_available" not in cause
    assert "context_limit_exceeded" not in cause


def test_specialist_cause_safety_handoff_takes_precedence_over_high_risk():
    """Both conditions hold; the explicit safety trigger must not disappear, and
    coincident high risk must remain visible in risk_level/risk_categories."""
    result = _cause("safety_handoff", "please rm -rf everything")
    cause = result["specialist_offload_cause"]
    assert cause["offload_reason_code"] == "safety_handoff"
    assert cause["risk_level"] == "high"
    assert "destructive_ops" in cause["risk_categories"]


def test_specialist_cause_medium_risk_online_variant():
    result = _cause("packaging", "run pip install requests", online=True)
    assert result["offload_recommended"] is True
    cause = result["specialist_offload_cause"]
    assert cause["offload_reason_code"] == "medium_risk_online"
    assert cause["risk_level"] == "medium"
    assert "package_management" in cause["risk_categories"]
    assert cause["internet_available"] is True
    assert "context_limit_exceeded" not in cause


def test_specialist_cause_context_limit_online_variant():
    result = _cause("docs_update", "write the docs", "x" * 30001, online=True)
    assert result["offload_recommended"] is True
    cause = result["specialist_offload_cause"]
    assert cause["offload_reason_code"] == "context_limit_online"
    assert cause["risk_level"] == "low"
    assert cause["risk_categories"] == []
    assert cause["internet_available"] is True
    assert cause["context_limit_exceeded"] is True


def test_specialist_cause_absent_when_not_offloading():
    """No offload decision means no specialist-offload evidence to record."""
    result = _cause("docs_update", "write the docs", "short", online=True)
    assert result["offload_recommended"] is False
    assert "specialist_offload_cause" not in result


def test_medium_risk_offline_fallback_still_does_not_offload():
    """Connectivity is the discriminant: offline medium risk falls back locally."""
    result = _cause("packaging", "run pip install requests", online=False)
    assert result["offload_recommended"] is False
    assert "specialist_offload_cause" not in result


def test_specialist_cause_carries_no_free_form_input_content():
    sentinel_prompt = "zzqqxx-prompt-sentinel please rm -rf everything"
    sentinel_data = "zzqqxx-data-sentinel"
    result = _cause("bugfix", sentinel_prompt, sentinel_data)
    rendered = repr(result["specialist_offload_cause"])
    assert "zzqqxx-prompt-sentinel" not in rendered
    assert "zzqqxx-data-sentinel" not in rendered
    # The free-form reason stays on the routing result for compatibility, but it is
    # not part of the bounded cause the durable event is built from.
    assert "reason" not in result["specialist_offload_cause"]
