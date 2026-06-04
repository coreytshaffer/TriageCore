from triage_core import TriageClient

def demo_ollama():
    print("Testing Ollama Preset...")
    client = TriageClient(
        backend_type="ollama",
        model="qwen2.5-coder:7b",
        timeout_seconds=30,
    )

    result = client.run_task(
        prompt="Write a Python function that adds two numbers. Output code only.",
        data="No existing helper functions."
    )

    print(result)


def demo_vllm():
    print("\nTesting vLLM Preset...")
    client = TriageClient(
        backend_type="vllm",
        model="Qwen/Qwen2.5-Coder-7B-Instruct",
        timeout_seconds=30,
    )
    # result = client.run_task(prompt="...", data="...")


def demo_custom():
    print("\nTesting Custom Backend (e.g., LM Studio)...")
    from triage_core.backends import OpenAICompatibleBackend
    
    backend = OpenAICompatibleBackend(
        name="lmstudio",
        base_url="http://localhost:1234/v1",
        model="local-model"
    )
    client = TriageClient(backend=backend)
    # result = client.run_task(prompt="...", data="...")


if __name__ == "__main__":
    # Uncomment to test against a live local server
    # demo_ollama()
    pass
