# Local Worker Optimization: Models & Configurations

To truly perfect the TriageCore architecture, we need to eliminate the "Generation Ceiling" and "Schema Hallucination" bottlenecks. The current local model (`Nemotron-3-Nano-Omni`) is highly capable but too heavy/slow for rapid agentic loops. 

By strategically pairing the right **small-parameter, high-density code models** with **constrained inference configurations**, we can push local generation velocity from ~10 tokens/sec to **70+ tokens/sec**, effectively eliminating timeouts.

---

## 1. Top Open-Source Models for the Local Worker

The Local Worker does not need broad worldly knowledge; it needs strict instruction-following, Python proficiency, and blazing speed.

### A. The Gold Standard: Qwen2.5-Coder (7B & 1.5B)
* **Why:** Qwen2.5-Coder is currently dominating the open-source coding benchmarks. The 7B parameter version rivals GPT-4 in syntax correctness while being small enough to run entirely in VRAM on a consumer GPU.
* **Velocity:** ~60-80 tokens/sec.
* **Best For:** `patch_prompt` tasks. It handles multi-file Python context windows flawlessly.

### B. The MoE Alternative: DeepSeek-Coder-V2-Lite (16B)
* **Why:** A Mixture-of-Experts (MoE) model where only ~2.4B parameters are active during inference. This gives it the reasoning capacity of a 16B model but the generation speed of a tiny model. 
* **Velocity:** ~50-60 tokens/sec.
* **Best For:** `extraction_prompt` tasks that require reading dense logs or narrative text alongside code.

### C. The Micro-Worker: Llama-3.1-8B-Instruct
* **Why:** Meta's latest 8B model is heavily fine-tuned for instruction following and has an 128k context window. It is slightly weaker at pure coding than Qwen, but exceptionally rigid at formatting.
* **Velocity:** ~60 tokens/sec.
* **Best For:** Data formatting, markdown stripping, and general JSON enforcement.

---

## 2. The Ultimate Local Configuration

Swapping the model is only half the battle. To truly mitigate timeouts and hallucinations, your local inference engine needs to be configured specifically for agentic orchestration.

### A. Constrained Decoding (Zero Hallucinations)
Instead of prompting the model to "output JSON" and hoping it complies, you must force it at the engine level. 
* **Implementation:** If using LM Studio or `llama.cpp`, pass a **JSON Schema/Grammar** via the API request. 
* **Result:** The local engine physically restricts the LLM from predicting any token that violates the JSON schema. It guarantees 100% schema compliance and saves tokens by bypassing conversational filler entirely.

### B. Optimal Quantization format (EXL2 or AWQ)
* **Current Bottleneck:** Standard `.gguf` files run well on CPU/GPU hybrids but aren't purely optimized for GPU throughput.
* **The Fix:** Switch to **EXL2 (ExLlamaV2)** or **AWQ** quantized models. These formats are designed for pure VRAM execution and Flash Attention. 
* **Result:** Time-to-first-token (TTFT) drops to milliseconds, and generation speed doubles.

### C. Backend Engine: vLLM or SGLang
While LM Studio is fantastic for desktop testing, an automated loop like TriageCore benefits from an enterprise-grade local backend.
* **vLLM / SGLang:** These are high-throughput open-source inference engines. They implement *PagedAttention*, which minimizes memory fragmentation during large context window prompts (e.g., injecting an entire codebase for review).

---

## 3. The Recommended Stack

To make TriageCore virtually immune to timeouts, deploy this exact local stack:

1. **Model:** `Qwen/Qwen2.5-Coder-7B-Instruct-AWQ`
2. **Engine:** `vLLM` running an OpenAI-compatible server.
3. **Execution Parameter:** `guided_json` (vLLM's native JSON schema enforcer).
4. **TriageCore Update:** Drop the local timeout from `120s` to a blisteringly fast `30s`, because Qwen2.5 running on vLLM will generate 1,500 tokens in under 20 seconds.
