import os
import tempfile
from unittest.mock import MagicMock
import pytest

from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.compression import compress_context, ContextBundle
from triage_core.backends import BackendUnavailableError, BackendResponse

@pytest.fixture
def temp_file():
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as f:
        f.write("test file content secret data")
        path = f.name
    yield path
    os.remove(path)

@pytest.mark.parametrize("privacy_kwargs", [
    {"contains_sensitive_content": True},
    {"redaction_required": True},
    {"external_model_allowed": False},
])
def test_sensitive_metadata_bypasses_summarization(temp_file, privacy_kwargs):
    # Setup sensitive packet
    meta = PrivacyMetadata(**privacy_kwargs)
    packet = TaskPacket(prompt="Fix this", data="data here", privacy_metadata=meta)
    
    # Mock backend
    backend = MagicMock()
    
    bundle = compress_context(packet, [temp_file], backend=backend)
    
    # Assert LLM was not called
    backend.generate.assert_not_called()
    
    # Assert deterministic fallback with no raw content
    assert "[Sensitive content bypassed." in bundle.summary_text
    assert "test file content secret data" not in bundle.summary_text
    assert "Sensitive metadata detected" in bundle.warnings[0]
    
    # Assert token estimates and source refs still exist
    assert bundle.raw_tokens > 0
    assert len(bundle.source_files) == 1
    assert bundle.source_files[0]["path"] == temp_file
    assert type(bundle.source_files[0]["size_bytes"]) is int

def test_local_llm_summarization_records_provenance(temp_file):
    meta = PrivacyMetadata(contains_sensitive_content=False)
    packet = TaskPacket(prompt="Fix this", data="data here", privacy_metadata=meta)
    
    # Mock backend
    backend = MagicMock()
    backend.name = "ollama"
    backend.model = "llama3"
    backend.get_sanitized_uri.return_value = "http://localhost:11434"
    backend.generate.return_value = BackendResponse(
        text="This is an LLM summary",
        raw={},
        usage={},
        backend_name="ollama"
    )
    
    bundle = compress_context(packet, [temp_file], backend=backend)
    
    backend.generate.assert_called_once()
    assert "This is an LLM summary" in bundle.summary_text
    assert bundle.provenance is not None
    assert bundle.provenance["backend_type"] == "ollama"
    assert bundle.provenance["backend_uri"] == "http://localhost:11434"
    assert bundle.provenance["model"] == "llama3"
    assert "generated_at" in bundle.provenance
    
def test_backend_unavailability_returns_deterministic_fallback(temp_file):
    meta = PrivacyMetadata(contains_sensitive_content=False)
    packet = TaskPacket(prompt="Fix this", data="data here", privacy_metadata=meta)
    
    backend = MagicMock()
    backend.generate.side_effect = BackendUnavailableError("Offline")
    
    bundle = compress_context(packet, [temp_file], backend=backend)
    
    backend.generate.assert_called_once()
    assert "Backend unavailable" in bundle.warnings[0]
    # Falls back to deterministic which includes raw snippet since it's not sensitive
    assert "test file content secret data" in bundle.summary_text
    
def test_context_bundle_includes_estimates_and_reminders(temp_file):
    meta = PrivacyMetadata()
    packet = TaskPacket(prompt="A prompt", data="Some data", privacy_metadata=meta)
    
    bundle = compress_context(packet, [temp_file])
    
    # Reminder
    assert "[REMINDER: This is a compressed preflight summary" in bundle.summary_text
    
    # Estimates
    assert bundle.raw_tokens > 0
    assert bundle.compressed_tokens > 0
    assert bundle.reduction_ratio is not None
    
def test_compression_does_not_mutate_task_packet(temp_file):
    meta = PrivacyMetadata()
    packet = TaskPacket(prompt="P", data="D", privacy_metadata=meta)
    
    bundle = compress_context(packet, [temp_file])
    
    assert packet.prompt == "P"
    assert packet.data == "D"
    assert packet.privacy_metadata.contains_sensitive_content is False
