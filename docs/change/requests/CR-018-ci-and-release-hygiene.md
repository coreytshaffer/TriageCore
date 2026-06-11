# CR-018: CI and Release Hygiene

## Status

Proposed

## Goal

Add basic automated trust markers for the public alpha release.

## Scope

- Add a GitHub Actions workflow for Python tests.
- Run `python -m pytest -q` on push and pull request.
- Add a README test/status badge after the workflow passes.
- Confirm the `v0.1.0-alpha` release points to the intended public state.
- Avoid runtime behavior changes.

## Acceptance Criteria

- [ ] GitHub Actions workflow exists under `.github/workflows/`.
- [ ] Workflow runs on push and pull request.
- [ ] Workflow installs the package and runs `python -m pytest -q`.
- [ ] Workflow passes on `main`.
- [ ] README includes a test/status badge after the first successful run.
- [ ] No routing, backend, or runtime behavior changes.
