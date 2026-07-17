# OpenAI Build Week Scope — Evidence-Bound Build Review

## Provenance boundary

- **Public integration baseline:** `0795c0435153106c9734d1d7ff273fd6f5709fa0`
- **Baseline branch:** `origin/main`
- **Integration started:** 2026-07-17
- **Integration branch:** `codex/build-week-evidence-bound-review`
- **Primary build environment:** Codex desktop using GPT-5.6
- **Primary Codex feedback/session evidence:** pending submission capture

An earlier isolated prototype was developed from a legacy FieldAware/SafeTask
history. That history is preserved locally as provenance but is not being
pushed as an unrelated branch. The submission branch above ports only the
bounded Build Review capability into the actual public TriageCore repository.

## Work attributable to this Build Week slice

- `tc build-review create|decide|verify`
- Change-request parsing for declared scope and validations
- Git base/head and worktree comparison
- Scope drift and validation evidence findings
- Canonical evidence hashes and deterministic derived artifacts
- Non-overwriting human decision records bound to exact evidence
- Strict, read-only verification with duplicate-key and symlink rejection
- Persistent privacy checks before packet or decision writes
- Portable clean and adversarial example packets
- Installed-command subprocess tests

## Human decisions

- Keep this as a review boundary, not another coding agent.
- Integrate into the existing public `tc` command rather than replacing its
  package metadata or established command surface.
- Preserve system recommendation and human decision as separate states.
- Treat internal hash consistency honestly: it is not authorship or historical
  immutability.
- Keep all review activity local and require trusted operator validation
  commands.

## Release gate

```powershell
python -m pytest -q
python -m build
python -m pip install --force-reinstall dist/triagecore-0.1.0-py3-none-any.whl
tc build-review --help
tc build-review verify examples/build-week/clean-self-review
tc build-review verify examples/build-week/adversarial-scope-drift
python -m ruff check triage_core/build_review*.py tests/test_build_review_cli.py examples/build-week/generate_packets.py
git diff --check
git status --short
```

Repository-wide Ruff cleanup remains separate baseline debt; this slice lints
the new files and uses the complete pytest suite as the repository regression
gate.

Do not tag until the branch is merged, CI is green on `main`, installation from
the tagged public repository works, and the exact tag and commit are recorded
in the submission materials.
