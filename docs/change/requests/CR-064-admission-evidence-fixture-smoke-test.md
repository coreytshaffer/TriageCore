# CR-064: Admission Evidence Example Fixture Smoke Test

## Goal
Add a smoke test that loads, parses, and renders `docs/examples/admission-evidence.example.json` to ensure the public example fixture remains valid against the `admission_evidence_from_mapping` validation rules and the renderer.

## Scope
* Add `test_admission_evidence_example_fixture_roundtrip` to `tests/test_admission.py`.
* Load the example fixture JSON file.
* Pass the payload through `admission_evidence_from_mapping`.
* Render the evidence via `render_admission_evidence_markdown`.
* Assert the presence of trust anchors (e.g., `**Execution Performed:**`).
* No CLI additions or runtime adapter changes.
