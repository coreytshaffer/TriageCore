# Runtime Efficiency Ledger

## Purpose

The runtime efficiency ledger records evidence for comparing local LLM runtime
choices. It is meant to answer narrow questions such as:

- Did the selected route use fewer tokens than the baseline?
- Did it complete faster under the recorded runtime profile?
- Is any energy claim a proxy, software estimate, or measured result?
- Which backend settings produced the result?

This ledger does not change default runtime behavior. It does not call Ollama,
llama.cpp, or any OpenAI-compatible server. It records comparable evidence that
future smoke or benchmark commands can write after they have gathered local
measurements.

## Runtime Profiles

Each record includes a `runtime_backend` block. Supported backend names are:

- `ollama`
- `llama_cpp`
- `generic_openai_compatible`

For `llama_cpp`, records can capture `llama-server`, GGUF model file,
quantization, context size, threads, GPU layers, batch settings, device, and
build metadata. These fields matter because "llama.cpp is faster" is not a
single measurable claim. Runtime speed depends on the model, quantization,
context length, hardware, and server settings.

For `ollama`, records can capture model name, context size, device, and build
metadata. The goal is comparison before migration, not replacement.

## Measurement Tiers

The ledger supports four measurement tiers:

- `token_proxy`: token counts only; energy fields may be null.
- `runtime_proxy`: token and latency evidence; energy fields may be null.
- `software_energy_estimate`: energy is estimated by software or configured
  assumptions.
- `wall_power_measured`: energy comes from explicit wall-power measurement.

Token reductions are proxy evidence. They are useful for showing that less work
was sent through a model, but they are not measured energy savings by
themselves.

## Fail-Closed Rules

Records are rejected when:

- The selected route total tokens exceed the declared selected token budget.
- Token-savings claims cannot be computed from both baseline and selected token
  totals.
- Measured energy savings are claimed without numeric energy evidence and an
  explicit measurement method.
- A quality gate is missing.

Benefit claims are only considered valid when the quality gate passed. This
keeps "faster" or "cheaper" routes from being counted as successful when the
output failed the task.

## Comparing Ollama and llama.cpp

Use this ledger to compare Ollama and llama.cpp before changing runtime
defaults:

1. Run the same bounded task with an Ollama route and record token and latency
   evidence.
2. Run the same bounded task with a llama.cpp-compatible route and record its
   backend profile.
3. Compare token totals, latency, and measurement tier.
4. Treat energy claims as provisional unless the record uses measured or
   clearly documented software-estimate evidence.

The first implementation slice is schema, builders, validation, and
documentation only. Live benchmark capture belongs in a later, separately
scoped change.
