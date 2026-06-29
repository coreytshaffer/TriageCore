# Packaging Readiness

## Purpose

This checklist defines what "packaging-ready for review" means right now. It is about local installation, verification, and reviewer orientation. It is not a publishing plan.

## Python Version

`pyproject.toml` currently declares:

```text
requires-python = ">=3.10"
```

Use Python 3.10 or newer. Python 3.11+ is preferred for day-to-day local development.

## Local Install

From the repository root:

```powershell
python -m pip install -e .
```

For development validation:

```powershell
python -m pip install -e ".[dev]"
```

UI and mobile extras exist, but they are not required for the stabilization reviewer path.

## Smoke Commands

After install, run:

```powershell
tc --help
tc doctor
tc demo --dry-run
tc audit --self-test
tc audit --kind route_audit --last 10
tc audit --privacy-invariants
triagecore benchmark --list-only
```

These commands should stay local and reviewable. The offline demo does not call a model backend.

## Test Command

For full validation:

```powershell
python -m pytest -q
```

For docs-only changes, `git diff --check` is the minimum repository check.

## Local-Only And Offline Expectations

- The core reviewer smoke path should not require cloud credentials.
- The demo dry-run is deterministic and offline-oriented.
- Benchmark listing should not contact a backend.
- Audit readouts should stay metadata-only and avoid raw prompt or payload leakage.
- Optional cloud/backend flows require explicit configuration and are not part of this packaging readiness baseline.

## Artifacts Reviewers Should Inspect

- [README.md](../../README.md)
- [stabilization-checkpoint.md](stabilization-checkpoint.md)
- [issue-72-signed-route-decision-checkpoint.md](issue-72-signed-route-decision-checkpoint.md)
- [signed-route-decision-verification.md](signed-route-decision-verification.md)
- [../security/agent_identity_provenance.md](../security/agent_identity_provenance.md)
- [../submission/README.md](../submission/README.md)
- [../verification_guide.md](../verification_guide.md)
- [../current_backlog.md](../current_backlog.md)
- [../change/change_log.md](../change/change_log.md)

## Known Non-Goals

- No PyPI publishing.
- No release tagging.
- No installer changes.
- No new signing or identity behavior.
- No new execution pathway.
- No new agent authority.
- No GUI expansion.
- No live backend integration.

## Ready Enough Criteria

This checkpoint is ready enough when:

- the repo installs locally in editable mode
- `tc --help` and `tc doctor` are available after install
- the documented smoke commands match real command surfaces
- `python -m pytest -q` remains the full validation command
- docs clearly separate provenance, approval, execution authority, and safety claims
- known non-goals are explicit
