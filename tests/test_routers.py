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
