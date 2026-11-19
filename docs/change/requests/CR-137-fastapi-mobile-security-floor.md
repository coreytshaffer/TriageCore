# CR-137 — Require patched FastAPI and Python 3.11 for mobile

## Status

Proposed and accepted on 2026-11-18. The operator recorded the decision in
the CR-137 chat: “I accept the CR-137 proposal.”

Design accepted and bounded implementation authorized on 2026-11-18.
Implementation accepted on 2026-11-18 against the locally verified candidate
identified below. Commit, push, and pull request creation are authorized for
the six paths in the exact file scope. Merge, release, and closeout remain
pending.

CR-137 is the next numeric identifier in the observed namespace. CR-136 was the
highest numeric request in local Git history. The GitHub comparison from local
`ffb47b1a` to `main` showed no new numeric CR files, and repository issue and
pull request searches for `CR-137` and `GHSA-f56c-v883-vx8r` returned no matches.

## Problem

FastAPI published GHSA-f56c-v883-vx8r on 2026-11-17 and rated it High (7.5).
The optional `mobile` extra currently allows `fastapi>=0.115.0`. TriageCore's
scalar `Authorization` header and `limit` query parameter match the affected
paths on FastAPI `>=0.123.2,<0.157.0`. For `>=0.157.0,<0.163.2`, the
advisory's query and header cases require Pydantic parameter models. The
inspected routes use scalar parameters and a JSON review body. FastAPI 0.163.2
contains the upstream fix and requires Python 3.11 or later.
[Maintainer advisory](https://github.com/fastapi/fastapi/security/advisories/GHSA-f56c-v883-vx8r)
· [FastAPI 0.163.2 package metadata](https://pypi.org/project/fastapi/0.163.2/)

The dependency, mobile server, and test workflow were inspected at
`ffb47b1a`. The prior Windows host check found no identifiable TriageCore
Mobile process or listener on the default port. The serving versions,
reachability, and effective ingress limits of any separate deployment remain
unverified. [Dependency declaration](../../../pyproject.toml) ·
[Mobile server](../../../triage_core/web/server.py) ·
[CI workflow](../../../.github/workflows/tests.yml)

## Proposed scope

- `pyproject.toml` — Retain the project's `requires-python = ">=3.10"` and
  set the mobile extra's FastAPI requirement to `fastapi>=0.163.2`. Apply that
  dependency whenever the mobile extra is requested, including on Python 3.10.
  The patched FastAPI releases' Python metadata lets the resolver reject an
  incompatible mobile install. A Python marker that skips FastAPI on 3.10 would
  let the extra resolve without a usable mobile API.
  [Python packaging metadata](https://packaging.python.org/en/latest/specifications/core-metadata/#requires-python)
  · [Dependency markers](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#environment-markers)
- `triage_core/web/server.py` — Enforce both version floors before creating the
  mobile ASGI app so direct imports and launcher calls from existing
  environments also respect the requirement. Check Python before importing
  optional dependencies. For missing or unsupported FastAPI, report the
  required version and how to install the mobile extra. Use a PEP 440-aware
  FastAPI version comparison and declare its dependency in the mobile extra if
  needed.
- `.github/workflows/tests.yml` — Change the Ubuntu install and test steps as
  specified below.
- `tests/test_mobile_web.py` — Cover the supported and rejected version paths
  with synthetic version values. Use the existing mobile API tests for
  authenticated review, unauthenticated requests, and startup binding.
- `README.md` — Document the Python and FastAPI floors for mobile and the
  unchanged Python 3.10 floor for core. Tell operators of existing mobile
  deployments to rebuild or upgrade the serving environment and verify the
  resolved versions before restarting.

The implementation scope is limited to packaging, mobile startup compatibility
checks, targeted tests, CI, and operator documentation. Deployment changes and
ingress configuration need separate authority.

## Proposed CI changes

Keep the existing Ubuntu matrix and check names. Select dependencies and test
coverage by Python version.

| Job | Install and verify |
| --- | --- |
| Ubuntu Python 3.10 | Install `.[dev]` in a clean environment and run `python -m pytest -q --ignore=tests/test_mobile_web.py`. The exclusion prevents collection of the mobile test module, which imports FastAPI at module scope. Verify separately that a mobile-extra install is rejected because the required FastAPI is incompatible with Python 3.10, and that direct mobile startup reports the Python requirement. |
| Ubuntu Python 3.11 | Install `.[dev,mobile]` with a CI-only constraint of `fastapi==0.163.2` to exercise the minimum supported version. Check the resolved version, run the full suite, and require `tests/test_mobile_web.py` to execute. |
| Ubuntu Python 3.12 | Install `.[dev,mobile]` using the declared dependency range. Check that the resolved FastAPI meets the floor, run the full suite, and require `tests/test_mobile_web.py` to execute. |

The Windows executor job continues its Python 3.12 core-only checks. Record the
Python and FastAPI versions in the Ubuntu mobile job output. A missing dependency
or skipped mobile suite fails the mobile jobs.

## Acceptance criteria

- [ ] Core and development extras install on Python 3.10 and the core regression
  suite passes with only the mobile test module excluded by CI configuration.
- [ ] In a clean Python 3.10 environment, explicitly requesting `.[mobile]`
  fails dependency resolution because of the mobile FastAPI requirement. An
  unrelated install or index failure does not satisfy this check.
- [ ] On Python 3.11 and 3.12, mobile installs and passes the full test suite,
  including the mobile tests. Python 3.11 verifies FastAPI 0.163.2 exactly.
- [ ] Direct mobile startup on Python 3.10 reports the Python requirement.
  Missing FastAPI and versions below 0.163.2 are rejected before the ASGI app is
  constructed. Use synthetic version inputs for these checks.
- [ ] Existing bearer authentication, task projection, review behavior, and
  loopback binding tests pass with patched FastAPI, consistent with
  [CR-019](CR-019-mobile-api-access-boundary.md).
- [ ] The README records the compatibility split and migration instructions.
  Implementation evidence identifies the exact commit, commands, environments,
  and results. Deployment remediation requires separate runtime evidence.

## Draft design for review

The design is based on local `main` at `ffb47b1aafd44e43347e3c0b39a6f0f00a6460b4`.
Recheck the approved paths against the implementation base before editing.

### Exact file scope

| Path | Proposed change |
| --- | --- |
| `pyproject.toml` | In the `mobile` extra, replace the FastAPI floor with `fastapi>=0.163.2` and add `packaging` as a direct mobile dependency for version comparison. Keep `project.requires-python` at `>=3.10`. |
| `triage_core/web/server.py` | Add the import-time mobile compatibility check before constructing the ASGI app or opening the ledger. |
| `tests/test_mobile_web.py` | Add isolated compatibility cases and retain the existing mobile behavior coverage. |
| `.github/workflows/tests.yml` | Change the install and verification steps of the Ubuntu `pytest` job. |
| `README.md` | Add the core and mobile requirements and mobile environment upgrade instructions under Installation. |
| `docs/change/requests/CR-137-fastapi-mobile-security-floor.md` | Record the human decisions and exact-head verification evidence as each stage occurs. |

The five implementation files above are the complete implementation allowlist.
The CR record covers governance and evidence. Deployment changes and
ingress configuration remain outside this scope.

### Mobile version checks

1. On evaluation of `triage_core.web.server`, compare
   `sys.version_info[:2]` with `(3, 11)` before importing optional
   dependencies. An older interpreter raises `RuntimeError` with
   “TriageCore Mobile requires Python 3.11 or later.”
2. On a supported interpreter, load FastAPI and `packaging.version.Version`.
   Read `fastapi.__version__` from the imported module so the check covers
   the code this process will use. Compare
   `Version(fastapi.__version__)` with `Version("0.163.2")` using PEP 440
   ordering. The minimum release and later versions pass. For example,
   `0.163.2rc1` fails and `0.163.2.post1` passes.
   [FastAPI 0.163.2 version declaration](https://github.com/fastapi/fastapi/blob/0.163.2/fastapi/__init__.py#L3)
   · [PyPA version comparison](https://packaging.pypa.io/en/stable/version.html)
3. An older FastAPI release or an absent, non-string, or invalid version
   raises `RuntimeError` with the FastAPI floor and the installation
   command `python -m pip install '.[mobile]'` from the repository root.
   A missing FastAPI or `packaging` dependency raises the same actionable
   error. Translate `ModuleNotFoundError` only for the explicitly checked
   dependency. Let unrelated import errors retain their original cause.
4. Run the check once per module load, before `FastAPI(...)`, ledger
   construction, route registration, or any invocation of Uvicorn. Direct
   ASGI imports and `python -m triage_core.web.server` reach this same
   check. On success, proceed through the existing app configuration and
   `start_server` flow, including bearer authentication and the loopback
   default.

The resolver and startup check enforce different parts of the contract.
Keep the mobile FastAPI requirement active on Python 3.10 so pip can reject
the request using FastAPI's `Requires-Python` metadata. The startup check
enforces TriageCore's Python floor independently of dependency resolution.
The README will direct existing operators to create a Python 3.11 or later
environment, install `.[mobile]`, and verify the Python and FastAPI versions
in the serving environment before restarting.

### CI verification steps

Retain the `pytest` job key and its existing `matrix.python-version` axis
and values to preserve the check names. Use conditions on that axis to
choose the following steps. The `windows_executor` job continues to run
its existing Python 3.12 core-only checks.

**Ubuntu Python 3.10**

1. Install with `python -m pip install -e '.[dev]'` and run
   `python -m pytest -q --ignore=tests/test_mobile_web.py`.
2. Run `python -m pip install --dry-run --ignore-installed '.[mobile]'`.
   Require a nonzero exit and resolver diagnostics that both identify
   `fastapi>=0.163.2` as unsatisfied and identify the patched floor's
   `Requires-Python >=3.11` as incompatible. An index, build, or unrelated
   dependency error cannot satisfy the assertion.
   [pip dry-run and resolver options](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-dry-run)
3. From the same core-only environment, run
   `python -m triage_core.web.server` with an empty mobile token and a
   temporary ledger path. Require a nonzero exit with the Python 3.11
   diagnostic and verify that the ledger path was never created.

**Ubuntu Python 3.11 and 3.12**

1. On 3.11, write a one-line `fastapi==0.163.2` constraint under
   `RUNNER_TEMP` and install with
   `python -m pip install -c "$RUNNER_TEMP/triagecore-fastapi-constraints.txt" -e '.[dev,mobile]'`.
   On 3.12 run `python -m pip install -e '.[dev,mobile]'` without the
   constraint. The temporary constraint exercises the minimum release on 3.11.
2. Print the serving Python version and imported `fastapi.__version__`.
   Assert that the parsed FastAPI version equals 0.163.2 on 3.11 and meets
   the floor on 3.12.
3. Run `python -m pytest -q --junitxml="$RUNNER_TEMP/triagecore-pytest.xml"`.
   Require pytest success. Parse the XML with the standard library and
   require at least one passing testcase from `tests.test_mobile_web` and
   zero skipped, failed, or errored cases from that module. A missing report
   or absent mobile module fails the job.

Add synthetic tests in `tests/test_mobile_web.py` for a missing dependency,
missing or malformed version, a version below the floor, the floor's
release candidate, the exact floor, and a later version. Exercise the
import check in a fresh module execution with a temporary ledger path.
Assert that rejected cases fail before ledger construction. Use the existing
in-process API and binding tests with the installed, patched FastAPI. The
acceptance evidence will report the checkout, commands, resolved versions,
and test outcomes. These are planned checks under the
[verification guide](../../verification_guide.md).

## Human approval requirement

The operator accepted the proposal and then granted design acceptance and
bounded implementation authority in the CR-137 chat on 2026-11-18:

> I accept the CR-137 design and authorize implementation within its exact file scope.
> Run the specified verification and report the results for review.
> Stop before committing, pushing, merging, or releasing.

After reviewing the local verification, the operator granted implementation
acceptance and the next bounded actions in the CR-137 chat on 2026-11-18.

> I accept the CR-137 implementation. Commit only the six scoped files on a
> dedicated branch, push it, and open a PR. Verify hosted CI and report the
> results. Stop before merging or releasing.

[TriageCore change management](../change_management.md) requires subsequent
explicit human decisions for merge authority, release authority, and closeout.

## Implementation verification

Executed on 2026-11-18 against the uncommitted candidate on base
`ffb47b1aafd44e43347e3c0b39a6f0f00a6460b4`. The five implementation files
matched the Ubuntu test overlay byte for byte. Their raw Git object hashes,
as reported by `git hash-object --no-filters`, identify the tested candidate.

```text
3662dadf7a88d977515f18980b20de3594a21f16  .github/workflows/tests.yml
bba76e0a325347b3bbf71d24b700b6893636fdf3  README.md
3c3dae65ffc9c64c1cb895e4912f6745752301e6  pyproject.toml
1ce7c73e61226a6c53e605eaf1b8b317e51b587b  tests/test_mobile_web.py
20209eef48227fee7ed412d3d5b784701157abbc  triage_core/web/server.py
```

The workflow shell steps ran locally on Ubuntu 24.04.5 LTS and on Windows
build 10.0.26300.0. The Ubuntu image digest was
`sha256:77eb101c607d6e3d4f5ad0c8a02c2136c689b98aba1f359e6502ba517e5c57ec`.
The runs used the install, pytest, resolver, and startup commands specified
in the design above. The Ubuntu test runner used temporary base interpreters
so the existing nested-virtualenv tests could inherit installed dependencies.
The source archive preserved the pinned specification bytes from Git.

| Environment | Observed result |
| --- | --- |
| Ubuntu, Python 3.10.22 | Core suite passed with 2,429 passed and 77 skipped. Pip rejected `.[mobile]` because FastAPI 0.163.2 requires Python 3.11 or later. Direct startup emitted the Python diagnostic and created no ledger. |
| Ubuntu, Python 3.11.18, FastAPI 0.163.2 | Full suite passed with 2,448 passed and 77 skipped. JUnit confirmed all 19 mobile tests passed with zero mobile skips. |
| Ubuntu, Python 3.12.16, FastAPI 0.165.0 | Full suite passed with 2,448 passed and 77 skipped. JUnit confirmed all 19 mobile tests passed with zero mobile skips. |
| Windows, Python 3.12.16, NTFS | All 214 mandatory executor tests passed with zero skips and the structured gate recorded `True->True`. The supplemental symlink case was skipped. The workflow summary reports that step as a pass because pytest exited zero. |

On Windows with Python 3.11.18 and FastAPI 0.163.2, the original server failed
the seven new rejection cases and passed the two supported-version cases.
After the guard was added, `python -m pytest -q tests/test_mobile_web.py`
passed all 19 tests. `python -m ruff check --select E402
triage_core/web/server.py tests/test_mobile_web.py` passed.

The first Ubuntu run exposed two problems in the temporary test setup. Its
outer virtualenv hid dependencies from nested CLI tests, and the
Windows-created source archive converted the pinned specification files to
CRLF. The final run used the base interpreter layout and a byte-verified
archive. Both mobile-negative checks and all three Ubuntu lanes exited zero.
The full Ubuntu suites reported 46 warnings each.

`git diff --check` passed for the reviewed candidate. Hosted verification
is tracked in the pull request's GitHub Actions checks. Deployment
verification requires separate runtime evidence.
