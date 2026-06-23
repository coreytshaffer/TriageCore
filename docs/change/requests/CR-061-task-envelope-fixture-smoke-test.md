# CR-061: Task Envelope Fixture Roundtrip Smoke Test

## Goal
Add a smoke test that validates and renders `docs/examples/task-envelope.example.json` to ensure the public example fixture remains aligned with the Task Envelope contract and schema.

## Scope
* Add `test_task_envelope_example_fixture_roundtrip` to `tests/test_task_envelope_cli.py`.
* The test should validate the fixture using `tc task-envelope validate --from-json`.
* The test should render the fixture using `tc task-envelope draft --from-json`.
* The test should assert the output is successful and contains the expected markdown sections.
* No changes to product code or validation logic.
* Update backlog and changelog.
