# CR-132: Account for the `triagecore` CLI Surface in `current_system_architecture.md`

## Status

- **Status:** Proposed. Not yet reviewed.
- **Type:** Documentation (repository architecture map — no runtime, routing,
  capability, schema, or CLI behavior component).
- **Priority:** Design review. Raised from a read-only investigation, requested during
  CR-131 design review but explicitly scoped out of CR-131 (which governs `AGENTS.md`
  repository-mutation-governance only, not orchestration architecture) and tracked as a
  separate finding per the human operator's direction.
- **Implementation authority:** Not authorized. No edit to
  `docs/architecture/current_system_architecture.md`, its accompanying SVG, or any other
  file is authorized by this CR.
- **Design acceptance:** Not granted. Remains a separate, later human decision.
- **Human approval requirement:** Proposal acceptance, design acceptance, implementation
  authority, implementation acceptance, and merge authority are separate decisions per
  `docs/change/change_management.md`. None is granted by opening this proposal.

## CR Namespace Census (evidence, not assumption)

Performed against this checkout before allocating an identifier:

- Enumerated every `docs/change/requests/CR-*.md` file in this worktree. Highest
  plain-numeric CR found: **CR-131**
  (`CR-131-agents-md-repository-governance-replacement.md`). No `CR-132` or higher
  exists as a file.
- Searched `git log --all --oneline` for any reference to `CR-13[2-9]` or `CR-1[4-9][0-9]`:
  no hits.
- Checked the lettered lineages for fit before defaulting to plain numeric:
  - `CR-DD-*` — daily-driver / governed `tc run` decision and evidence contracts. Not
    applicable: this proposal is a repository-level documentation-accounting change,
    not a governed-run decision or evidence-contract change.
  - `CR-YK-*` — hardware/WebAuthn authorization receipts and capability claiming. Not
    applicable.
  - `CR-OC-*` — mediated single-file effect / atomic client-request execution
    contracts. Not applicable.
  - `CR-AR-*` — risk-tiered deferred human review. Not applicable.
  - `CR-BW-*` — evidence-bound build review. Not applicable.
  - None of the five lettered lineages govern repository architecture-mapping
    documentation, so no applicable lettered-lineage precedent was found. The
    architecture-mapping commit `6f5970d` ("docs(architecture): map current TriageCore
    system") that created `current_system_architecture.md` itself was not filed as a CR
    and is cited only as prior comparable work, not as lineage precedent. CR-131 is the
    immediate plain-numeric predecessor.
- **Allocated identifier: `CR-132`**, plain numeric lineage, immediately following
  CR-131 with no gap and no collision.

## Scope

This CR's own authorized scope right now is exactly:

```text
docs/change/requests/CR-132-triagecore-cli-architecture-accounting.md
```

No other path is authorized by this CR. This CR does **not** scope, pre-authorize, or
schedule the eventual `current_system_architecture.md` edit; that requires its own
later, separately granted implementation authority once design is accepted.

### Proposed eventual documentation scope (design boundary for future review — not authorized here)

If this proposal is accepted and later carried into a design-review stage, the
resulting edit to `current_system_architecture.md` (and, if needed, its SVG) is
intended to:

1. Refresh the architecture verification pin from current evidence. The document is
   currently pinned to `main@1c2d6242ab18cf0d961b06994cf37c7c59ea38a5` on 2026-08-01 and
   states that "integration claims" must be re-verified when the pin changes; that
   re-verification has not happened against current `main`.
2. Explicitly account for **both** packaged entry points defined in `pyproject.toml`'s
   `[project.scripts]` table — `tc` (`triage_core.tc_cli:main`) and `triagecore`
   (`triage_core.cli:main`) — rather than describing only the former, and do so on the
   basis of a read-only census of every top-level `triagecore` command (recorded below
   as of this proposal), not only the two motivating findings. `triage_core/cli.py`
   defines substantially more top-level commands than `desk` and the supervisor-review
   trio:

   ```text
   desk, audit, codex-task, antigravity-task, init-agents, install-desktop,
   push-task, benchmark, benchmark-report, propose-lessons, review-lesson,
   import-learning-seeds, record-supervisor-review, import-supervisor-usage,
   scan-supervisor-usage, run-pipeline, stability-pass, stats, lab
   (with lab subcommands: report, export, train)
   ```

   The design-review stage should group this full command set into meaningful
   architecture subsystems and statuses (for example: TriageDesk GUI and its dispatch
   paths; Codex/Antigravity task-packet generation; supervisor-review recording and
   usage import; benchmark/stability/lab analytics; learning-proposal review) rather
   than necessarily giving every individual command its own table row. Supervisor
   review and the Worker Council remain the two motivating findings that surfaced this
   gap — they are not an exhaustive description of everything the `triagecore` binary
   does, and the eventual documentation must not stop at those two rows while leaving
   the rest of the second CLI unaccounted for.
3. Add or revise integration-status entries for the working supervisor-review /
   usage-import commands (`triagecore record-supervisor-review`,
   `triagecore scan-supervisor-usage`, `triagecore import-supervisor-usage`), which are
   implemented, tested, and already documented operationally in
   `docs/verification_guide.md` §6 ("Supervisor Review Verification") and the
   "Supervisor Review Fields" table in `docs/evidence_schema.md`, but absent from the
   architecture document's integration table and authoritative-source list.
4. Add an honest Worker Council entry stating that the path is **present and wired, but
   currently non-operational for its configured role set**, and that this happens
   through **two distinct mechanisms** depending on input size, not one universal
   cause:
   - **Non-chunked inputs (the common case for small/no target files):**
     `ProjectManager.dispatch_task` queues one work order per name in
     `required_roles=["repo_mapper", "code_repair", "validator"]`, and its execution
     loop then resolves each order's worker via an exact registry-key lookup
     (`self.registry.get_worker(order.assigned_role)`) against
     `triage_core/worker_registry.py`'s `WorkerRegistry`, which registers only the keys
     `context_planner`, `test_stubber`, `review_worker`, and `implementer`. The lookup
     misses for all three configured roles, and each order is marked failed with
     `f"Worker role {order.assigned_role} not found"` before any worker or backend
     execution occurs.
   - **Chunked inputs (target files whose combined size exceeds the configured
     `max_artifact_bytes` budget):** the chunked queue-construction branch only knows
     how to create `context_planner` and `implementer` orders, gated on
     `if "context_planner" in required_roles` / `if "implementer" in required_roles`.
     Neither name is ever in the GUI's `required_roles` list, so **zero** work orders
     are queued at all — the registry lookup is never reached, and no
     `"Worker role ... not found"` message is ever produced. The execution loop finds
     no pending work and proceeds straight to steward evaluation over an empty
     completed-orders list.

   Both mechanisms are directly observed in the call path, not speculative, and both
   are triggered by the same GUI dispatch call depending only on target-file size. The
   architecture-level conclusion is the same either way — this configured Worker
   Council path is non-operational — but the eventual documentation must preserve both
   causal modes rather than flattening them into a single "lookup miss" description.
   The existence of similarly named skill Markdown files (`repo_mapper.md`,
   `code_repair.md`, `validator.md`) does not repair either gap, since neither path
   ever constructs a worker under those role names to read them.
5. Update the authoritative-source list (the document's "Authoritative Sources
   Verified" section) as necessary to include `triage_core/cli.py`,
   `triage_core/orchestration.py`, `triage_core/worker_registry.py`, and the relevant
   TriageDesk UI call site (`triage_core/ui/app.py`) — mirroring the granularity the
   document already uses for the `tc`-path modules it lists. Any test citation added
   alongside these sources must be limited to tests that actually exercise the cited
   behavior (see the evidence-characterization note in the Problem Statement below);
   where no existing test reproduces a cited code path, the source list should cite the
   code itself rather than imply regression-test coverage that does not exist.
6. Preserve the existing distinction the document already draws between architecture
   documentation and runtime correctness (its "Non-Claims" section, and the general
   principle that neither this page nor the identity/claim documents grants
   implementation, integration, mutation, merge, or standing authority). Recording the
   Worker Council's true status is a documentation-accuracy fix; it is not, and must not
   be treated as, a runtime-behavior decision.

This document intentionally does **not** propose a new universal architecture-status
taxonomy (e.g., a repository-wide fourth category such as "wired but broken") to sit
alongside the document's existing three categories (current/integrated,
implemented-but-disconnected, conceptual-or-external). One observed path does not by
itself justify a new reusable category. The design-review stage should instead give the
Worker Council row a precise, local status string — such as "Present and wired;
currently non-operational for the configured role set" — with the boundary column
naming the exact registry/role-name mismatch. Whether a reusable taxonomy category is
warranted is left to a later design review, informed by whatever else is found once
more of the repository is mapped, not decided here.

### Explicit Exclusions

This CR, and any `current_system_architecture.md` edit eventually scoped from it, does
**not** cover and must not be used to smuggle in:

- changing `triage_core/worker_registry.py` (its registered role keys or worker
  classes);
- changing `triage_core/ui/app.py`'s `required_roles` dispatch call or any other call
  site;
- adding role aliases, new worker classes, or a compatibility shim between UI role
  names and registry keys;
- renaming, rewriting, or otherwise editing any file under `triage_core/skills/`;
- changing `triage_core/orchestration.py`'s dispatch, lookup, or error-handling
  behavior;
- changing either CLI (`triage_core/cli.py` or `triage_core/tc_cli.py`) — flags,
  commands, help text, or behavior;
- changing tests, schemas, runtime behavior, routing, capability, signing, or
  authorization behavior;
- **resolving what the correct Worker Council role mapping should be** — whether the
  fix is renaming registry keys, renaming skill files and call-site roles, or something
  else is a runtime-defect decision for a separate, later CR, not a documentation
  question this CR answers.

The runtime defect described above is recorded here as an **adjacent finding requiring
its own separate governance** — a distinct, later "runtime defect CR" — and is
deliberately kept out of this documentation-accounting CR's implementation objective.

## Problem Statement

`docs/architecture/current_system_architecture.md` states its own purpose as
documenting "current integrated paths, implemented-but-disconnected foundations, and
conceptual or external actors" for "the current system architecture," and its
"Claim Supported" section makes repository-wide statements: an integrated
CLI-to-governed-run path, TriageDesk, Workspace Unifier, human-authorization
primitives, and mediated/reservation/replacement components. Its "Authority and
Persistence" table even includes a generic, unqualified "CLI surfaces" row describing
"Explicit operator commands and review decisions where implemented." The document does
not scope itself to a single binary anywhere in its text.

`pyproject.toml`'s `[project.scripts]` table packages **two** console entry points:

```text
triagecore = "triage_core.cli:main"
tc = "triage_core.tc_cli:main"
```

The document's "Authoritative Sources Verified" list enumerates modules reachable from
`tc` (`triage_core/tc_cli.py`, `triage_core/client.py`,
`triage_core/capability_evidence.py`, `triage_core/routing/resilience_router.py`,
`triage_core/engine.py`, the ledger/review-queue/adapter modules, the workspace
modules, the authorization/capability-claim modules, and the mediated-effect/
reservation/executor modules) but never mentions `triage_core/cli.py` — the module
backing the `triagecore` binary — at all. This is not a stale-pin problem (the pin
correctly describes what it covers); it is a scope omission: an entire second packaged
CLI surface, and everything reachable from it, is absent from a document that claims
repository-level current-architecture status without stating that boundary.

That omission hides two materially different things:

1. **A working, tested, already-separately-documented subsystem.**
   `triagecore record-supervisor-review`, `scan-supervisor-usage`, and
   `import-supervisor-usage` (implemented in `triage_core/cli.py`, exercised by
   `tests/test_cli.py`) write `supervisor_tool`, `supervisor_decision`,
   `supervisor_model`, `supervisor_profile`, `supervisor_notes`,
   `supervisor_artifact_path`, and supervisor token-estimate fields onto ledger records.
   This is real, current, and already has its own operational documentation
   (`docs/verification_guide.md` §6; the "Supervisor Review Fields" table in
   `docs/evidence_schema.md`) — it simply never made it into the architecture map's
   integration table or authoritative-source list.

2. **A currently non-operational subsystem presented, by omission, as if it does not
   exist.** The TriageDesk GUI (`triage_core/ui/app.py`, launched via `triagecore desk`)
   includes a "Worker Council" dispatch path. Its dispatch call requests exactly
   `required_roles=["repo_mapper", "code_repair", "validator"]` into
   `triage_core/orchestration.py`'s `ProjectManager.dispatch_task` — and that function
   fails those three roles by **two distinct mechanisms**, not one. For non-chunked
   target files (the common case), the execution loop resolves each queued order's
   worker via `self.registry.get_worker(order.assigned_role)` — an exact-key lookup
   against `triage_core/worker_registry.py`'s `WorkerRegistry`, which registers only the
   keys `context_planner`, `test_stubber`, `review_worker`, and `implementer` — and the
   lookup misses for all three configured roles, each order failing with
   `f"Worker role {order.assigned_role} not found"` before any worker or backend
   execution occurs. For target files large enough to trigger the chunking branch,
   however, the queue-construction code only ever creates `context_planner` or
   `implementer` orders, gated on those exact names appearing in `required_roles`;
   since the GUI's `required_roles` contains neither name, **zero work orders are
   queued** and the registry lookup is never reached at all — there is no
   `"not found"` message in this path, just an empty completed-orders list reaching
   steward evaluation. Both mechanisms are directly observed in the call path, not
   inferred, and both are reachable from the same GUI dispatch call depending only on
   target-file size. Skill prompt files matching those role names exist on disk
   (`triage_core/skills/repo_mapper.md`, `code_repair.md`, `validator.md`) and are
   correctly authored for their intended roles, but nothing in either path ever
   constructs a worker under those names to read them — their existence does not close
   the reachability gap.

**Evidence characterization.** Both mechanisms above are established by direct reading
of `triage_core/ui/app.py`, `triage_core/orchestration.py`, and
`triage_core/worker_registry.py` — code-path evidence, not an existing regression-test
result. `tests/test_orchestration.py` exercises `ProjectManager.dispatch_task` with
`required_roles` drawn from the registry's actual vocabulary
(`context_planner`/`implementer`/`review_worker`/`test_stubber`), which is useful
evidence that the dispatch/lookup/loopback machinery works correctly for its intended
role names, but it never calls `dispatch_task` with the GUI's actual
`repo_mapper`/`code_repair`/`validator` names and so does not reproduce either failure
mode. `tests/test_ui_smoke.py` does not exercise Council dispatch at all — it covers
TriageDesk importability, configured paths, display/formatting helpers, ledger
presentation, and telemetry summaries. Any eventual architecture-document citation of
these paths should be worded as a code-path finding, not as a described regression
test.

Neither of these two statuses is currently visible in
`current_system_architecture.md`. A reader of that document has no way to know the
`triagecore` binary exists, that a working supervisor-review subsystem hangs off it, or
that one of its GUI-facing paths is wired but non-functional for its configured inputs.

## Acceptance Criteria (for this proposal-only gate)

- [ ] CR-132 is opened for human review with an allocated, collision-free identifier
      supported by a recorded namespace census.
- [ ] The problem statement is grounded in directly observed repository content
      (`pyproject.toml`, `current_system_architecture.md`, `triage_core/cli.py`,
      `triage_core/ui/app.py`, `triage_core/orchestration.py`,
      `triage_core/worker_registry.py`, the skill files, `docs/verification_guide.md`,
      `docs/evidence_schema.md`), with no claim beyond what was directly observed,
      including a read-only census of every top-level `triagecore` command and an
      accurate, two-mechanism description of the Worker Council failure (registry
      lookup miss for non-chunked inputs; zero orders queued for chunked inputs), with
      test evidence labeled as code-path findings rather than as reproduced regression
      results.
- [ ] Proposed eventual documentation scope and explicit exclusions are stated clearly
      enough that a later design-review stage has unambiguous boundaries, that the
      runtime defect is not smuggled into a documentation-only implementation, and that
      the eventual documentation accounts for the full `triagecore` command surface
      rather than only the two motivating findings.
- [ ] No code, test, schema, CLI, worker-registry, orchestration, UI, or skill-file
      change is made by this CR.
- [ ] This document records that proposal acceptance, design acceptance, implementation
      authority, implementation acceptance, and merge authority are separate, later,
      explicit human decisions, none granted by opening this proposal.

## Verification Plan

Before requesting proposal acceptance, verify:

1. the only repository change introduced is this CR file;
2. `docs/architecture/current_system_architecture.md` remains byte-identical to its
   current committed `main` content — no proposal work modified it;
3. the CR namespace census is reproducible (`CR-132` still does not collide) at the
   time of review;
4. the two `[project.scripts]` entries, the full top-level `triagecore` command census,
   the `ui/app.py` dispatch call's exact `required_roles` list, the `WorkerRegistry`
   key set, the chunked-vs-non-chunked branching in `orchestration.py`'s
   `dispatch_task`, and the existence of the three named skill files are still as
   described above at the time of review, since this proposal's problem statement
   depends on those exact observations.

No test-suite run is required or meaningful for this proposal-only, documentation-only
change.

## Stop Point

Stop after this proposal is opened for human review. Do not begin a design-review
stage, draft the eventual `current_system_architecture.md` text, request implementation
authority, or take any action toward the separately-governed runtime-defect CR without a
separate, explicit human decision. Proposal acceptance here authorizes nothing beyond
recording that the problem statement and boundaries are accepted for further review.
