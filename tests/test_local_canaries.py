import os
import pytest
from triage_core.backends import create_backend, BackendUnavailableError

# These tests execute live network requests to local backends and should only run 
# if the environment explicitly opts in via RUN_LOCAL_LLM_TESTS=1
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LOCAL_LLM_TESTS") != "1",
    reason="Live local LLM canary tests require RUN_LOCAL_LLM_TESTS=1"
)

def test_ollama_canary_generation():
    """Verify Ollama health endpoint and generate a minimal prompt."""
    backend = create_backend("ollama")
    
    # Check if backend is reachable by checking ping
    if not backend.ping():
        pytest.skip("Ollama is not running or unreachable at the default base_url.")
        
    response = backend.generate([{"role": "user", "content": "Reply with only the exact token: TRIAGECORE_OLLAMA_CANARY_7291"}])
    assert response.text is not None
    assert "TRIAGECORE_OLLAMA_CANARY_7291" in response.text

def test_lmstudio_canary_generation():
    """Verify LM Studio health endpoint and generate a minimal prompt."""
    backend = create_backend("lmstudio")
    
    # Check if backend is reachable by checking ping
    if not backend.ping():
        pytest.skip("LM Studio is not running or unreachable at the default base_url.")
        
    response = backend.generate([{"role": "user", "content": "Reply with only the exact token: TRIAGECORE_LMSTUDIO_CANARY_7291"}])
    assert response.text is not None
    assert "TRIAGECORE_LMSTUDIO_CANARY_7291" in response.text
