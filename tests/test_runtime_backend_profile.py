import pytest

from triage_core.runtime_backends import RuntimeBackendProfile


def test_llama_cpp_backend_profile_validates():
    profile = RuntimeBackendProfile.llama_cpp(
        model_file="qwen.gguf",
        quantization="Q4_K_M",
        context_size=8192,
        threads=12,
        gpu_layers=35,
        batch_size=512,
        ubatch_size=128,
        device="cuda",
    )

    assert profile.to_dict()["name"] == "llama_cpp"
    assert profile.to_dict()["server"] == "llama-server"
    assert profile.to_dict()["endpoint_kind"] == "openai_compatible"


def test_ollama_backend_profile_validates():
    profile = RuntimeBackendProfile.ollama(
        model="qwen2.5-coder:7b",
        context_size=8192,
        device="cpu",
    )

    assert profile.to_dict()["name"] == "ollama"
    assert profile.to_dict()["endpoint_kind"] == "ollama_api"
    assert profile.to_dict()["model"] == "qwen2.5-coder:7b"


def test_generic_openai_compatible_backend_profile_validates():
    profile = RuntimeBackendProfile.generic_openai_compatible(
        server="local-openai-compatible",
        model="local-model",
        context_size=4096,
    )

    assert profile.to_dict()["name"] == "generic_openai_compatible"
    assert profile.to_dict()["endpoint_kind"] == "openai_compatible"


def test_backend_profile_rejects_wrong_endpoint_kind():
    with pytest.raises(ValueError, match="ollama profiles must use"):
        RuntimeBackendProfile(name="ollama", endpoint_kind="openai_compatible")
