# CR-007: Operator Bootstrap and First-Run Setup

## Status
Implemented

## Scope
Define and document the first-run setup, environment configuration, and smoke-testing process required for operators to correctly utilize the `tc` workflow commands introduced in CR-006.

## Implementation Authority
Not authorized until human approval.

## Human Approval Requirement
Explicit human approval required before any source code implementation.

## Description
This document provides operators with the necessary bootstrap steps for setting up TriageCore locally in a new shell or environment. Because Python entry points often suffer from `PATH` resolution issues across operating systems (particularly on Windows), this document specifies the canonical installation step (`python -m pip install -e .`), identifies common `PATH` pitfalls, and provides robust fallback access methods. 

It also defines a standard smoke test utilizing `CR-006` files to verify that the workflow is fully operational and generating artifacts correctly.

## Acceptance Criteria
- [x] Documents the core installation step: `python -m pip install -e .`
- [x] Documents using `tc --help` as the post-install verification command.
- [x] Documents the fallback usage pattern: `python -m triage_core.tc_cli ...`
- [x] Documents a PowerShell temporary shim workaround: `function tc { python -m triage_core.tc_cli @args }`
- [x] Documents the `PATH` issue and provides guidance on the Python Scripts folder resolution.
- [x] Documents the canonical smoke test workflow:
  - `tc preflight CR-006 --files docs/change/requests/CR-006-seamless-operator-workflow-integration.md triage_core/tc_cli.py tests/test_tc_cli.py`
  - `tc handoff latest --print`
  - `tc handoff latest`
- [x] Confirms that the preflight/handoff commands write only operational artifacts under `.triagecore/handoffs/`.
- [x] Confirms that no source files or project docs are modified by executing the smoke workflow.
- [x] Confirms the generated handoff successfully includes the source verification reminder, file refs/hashes, and token estimate metadata.

## Relationship to CR-006
CR-006 created the core operator workflow commands and aliases. CR-007 documents how to bootstrap, configure, and verify those commands on a fresh or newly opened shell.
