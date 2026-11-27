# CR-144 direct backend redirect refusal

## Status

Implementation authorized on November 26, 2026. The verified base is TriageCore
`main` at `241aba5bccc7977b216c993ee7dc3312a7708cb8`.

## Finding

Direct OpenAI-compatible and Ollama backends use the default Requests
redirect behavior for generation. TriageDesk and the model-backed
legacy classifier can invoke those backends. The governed, legacy
local-only, and Qwen paths already use the sealed transport, which
refuses redirects. [Daybreak finding](https://chatgpt.com/mcp-app/connector_openai_defense_factory/open_defense_factory#/findings/raw/rf_wfr_c2b8bccbd563ef7a1f8a9270c124ab9831c6ab2dfa8ee8c9adc4c26c9f4453ad%3Awfo_c1e700000cec5e39f99c4c66bf3303af830dcf1b5781605eef1a611b80024759%3Aocc_0c0017d81112d59fb36c7fae) · [Direct backend](https://github.com/coreytshaffer/TriageCore/blob/241aba5bccc7977b216c993ee7dc3312a7708cb8/triage_core/backends.py#L171-L253) · [Classifier](https://github.com/coreytshaffer/TriageCore/blob/241aba5bccc7977b216c993ee7dc3312a7708cb8/triage_core/classifier.py#L19-L57)

## Proposed behavior

- Apply a shared no-redirect request rule to the direct
  OpenAI-compatible and Ollama generation methods, including streaming.
  Apply it to their model discovery and health checks and the direct
  TriageDesk inventory calls.
- Refuse all 3xx responses, including same-origin redirects. Close the
  response and discard its body before parsing a model response or
  invoking a stream callback. Generation and discovery return a bounded
  backend-unavailable error. A redirect during discovery ends that
  generation attempt. Health and inventory checks report the endpoint
  as unavailable.
- Keep the existing deterministic classification fallback. Direct
  callers must configure the final backend URL. The bounded refusal
  reveals neither the redirect destination nor request or response data.
- Preserve the governed and Qwen transport contracts, including their
  existing refusal evidence, and verify successful direct streaming,
  model discovery, and generation against unchanged response formats.

A generation-only fix would leave discovery and the desk's direct
inventory HTTP calls following redirects. Applying the same rule at
these related request boundaries keeps handling consistent. The
configured first destination remains part of the existing backend
configuration contract. Separate probe commands, new origin allowlists,
proxy policy, response-size limits, and maintenance scripts are outside
this scope.

## Authorized writable paths

| Path | Purpose |
| --- | --- |
| `triage_core/backends.py` | Centralize direct redirect refusal and apply it to generation, discovery, and health checks. |
| `triage_core/ui/app.py` | Apply the same rule to direct TriageDesk inventory calls. |
| `tests/test_backends.py` | Cover both protocols, streaming and non-streaming generation, discovery, and health. |
| `tests/test_classifier.py` | Cover deterministic fallback after a bounded backend refusal. |
| `tests/test_ui_smoke.py` | Cover the headless inventory refusal paths. |
| `docs/change/requests/CR-144-direct-backend-redirect-refusal.md` | Record the approved scope, authority, and verification evidence. |

## Acceptance criteria

- Synthetic 3xx responses produce one request to the configured
  endpoint and zero requests to any redirect destination. The result
  carries a bounded reason. Backend code neither parses the redirect
  body nor invokes the stream callback. A discovery refusal stops the
  generation attempt.
- Direct health and TriageDesk inventory checks do not mark a
  redirecting endpoint online. The legacy classifier still falls back
  deterministically.
- Approved successful direct calls retain existing response, streaming,
  usage, and model-selection behavior. Existing governed, CR-142, and
  Qwen transport tests pass with their expected refusal semantics.
- Use recording adapters and synthetic inputs. Run the focused backend,
  classifier, and UI tests, the existing guarded transport regressions,
  and the full local and hosted suites. Reassess the finding on the
  merged revision after implementation acceptance.

## Authority

Corey Shaffer approved the proposal, design, and the six listed paths on
November 26, 2026. The grant covers synthetic verification and
publication as a separate draft pull request. Implementation acceptance,
merge, release, and closeout are separate decisions.
