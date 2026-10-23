# Monitoring Coverage Baseline — 2026-10-22

## Status and method

**Static source inventory and lifecycle reconciliation evidence only.** This note
supports planning for Monitoring Coverage Integrity; it implements no monitor or
coverage contract and establishes no runtime monitoring, containment, or safety claim.
It allocates no CR and grants no implementation, merge, release, or closeout authority.

Baseline: `610c13f253ba631d7052727abe3d68845bb09bb5`, matching remote `main` when
inspected. The isolated documentation worktree was on
`docs/monitoring-coverage-inventory`; `git status --short` was empty before documentation
edits. `git worktree list` distinguished this branch from the detached review checkout
at the same commit. Local absolute paths are intentionally omitted from this record.
Source links below are pinned to the baseline, not the evolving documentation branch.

Method: read files, search call sites, parse the CLI source with Python's `ast`, inspect
Git ancestry, and read GitHub PR metadata. No TriageCore command, GUI, model inference,
backend probe, test suite, live ledger audit, or deployment inspection was run. GitHub
reads establish repository metadata only. Historical test results are not rerun results.

## Lifecycle facts to reconcile

| Item | Observed fact | Limit / remaining work |
| --- | --- | --- |
| CR-DD-012B / [PR #179](https://github.com/coreytshaffer/TriageCore/pull/179) | GitHub reports merged at **2026-08-29 11:28:35 PDT / 18:28:35 UTC**, merge `c798e0ed19d3ca59cfb464ffe8476a4e30a0c1e8`; that commit is an ancestor of this baseline. `tc_run` now passes the shared snapshot and decision to `run_task`. | Baseline backlog still says unmerged. Record the observed merge without inferring resolution of the historical authority discrepancy, moving acceptance from `bbe5336`, or granting release/closeout. |
| CR-OC-001C / [PR #128](https://github.com/coreytshaffer/TriageCore/pull/128) | GitHub reports merged at **2026-08-01 02:53:15 PDT / 09:53:15 UTC**, merge `f65a86423d520a9583c47e5863b90159b4b040ac`, also an ancestor. [CR status](../change/requests/CR-OC-001C-constrained-single-file-replacement-executor.md#1-status-and-authority) records complete, accepted and merged. | Executor remains disconnected. Old CR-OC-001A/B backlog wording grouping C with unauthorized D/E needs a current-state qualification; historical grants remain unchanged. |
| CR-135 / [PR #187](https://github.com/coreytshaffer/TriageCore/pull/187), [PR #188](https://github.com/coreytshaffer/TriageCore/pull/188) | Slice 1 merged October 18 as `1ef3f5d`; lifecycle documentation merged as this baseline. The accepted runtime module is unchanged from `149aa8e`; merged head `c2dc932` added tests. | The current [CR record][cr135] says not integrated, with no separate acceptance of `c2dc932` found and no Slice 2 implementation authority recorded. Merge is not an end-to-end transport result. |
| Architecture / CR-132 | The [architecture map][architecture] is pinned to August 12 and does not account for the full second CLI/GUI. [CR-132][cr132] identifies that omission and remains Proposed. | This inventory records concrete paths; it neither completes CR-132 nor repairs the Worker Council. |
| Daily-use window | Latest tracked [session record](daily-use-evidence-window-2026-08-06.md) says open: three distinct days, eight independent tasks and one paired retry. No closeout was found in the inspected main tree/change log. | Historical record status is not proof of current operator activity. Reconcile and explicitly dispose of the study before changing its evidence semantics; do not manufacture completion or count synthetic fixtures as natural tasks. |

The original CR-DD-012B authority defect and corrective ratification remain evidence.
This note reports completed GitHub actions without rewriting earlier grants or deriving
new authority from a merged commit.

## Packaged command census

[Packaging][scripts] installs two entry points. Parsing their top-level
`subparsers.add_parser` calls found **25 `tc` families and 19 `triagecore` commands**.
This is an inventory of declared dispatch surfaces, not proof that every branch works
or that every subprocess/provider effect has been observed.

| Entry point | Declared top-level commands |
| --- | --- |
| `tc = triage_core.tc_cli:main` | `preflight`, `handoff`, `status`, `run`, `run-plan`, `probe`, `audit`, `propose`, `doctor`, `model`, `authority`, `identity`, `demo`, `tokens`, `route-worker-ledger`, `runtime-strategy`, `task`, `task-envelope`, `admission`, `eval`, `context`, `review`, `build-review`, `packet`, `workspace` ([parser][tc-parsers]) |
| `triagecore = triage_core.cli:main` | `desk`, `audit`, `codex-task`, `antigravity-task`, `init-agents`, `install-desktop`, `push-task`, `benchmark`, `benchmark-report`, `propose-lessons`, `review-lesson`, `import-learning-seeds`, `record-supervisor-review`, `import-supervisor-usage`, `scan-supervisor-usage`, `run-pipeline`, `stability-pass`, `stats`, `lab` ([parser][legacy-parsers]) |

## Execution and evidence boundaries

| Surface / symbols | Static finding | Intended treatment in a first future profile |
| --- | --- | --- |
| Governed `tc_run` → `TriageClient.run_task` | One snapshot/decision is built before preview/execution diverge; governed policy is consumed rather than reclassified. Local execution goes through `TriageEngine.execute_task` ([CLI][tc-run], [client][client-governed]). | Candidate core boundary: one explicitly enrolled, local-only governed invocation. No present coverage claim. |
| `tc run --plan`, `build_run_plan` | Returns before client construction; `run_plan.build_governed_run_context` uses `classify_deterministic`, not classifier inference. Optional `--plan-output` writes an artifact ([preview][preview], [classifier seam][plan-classifier]). | Explicit no-execution outcome; zero eligible inference must not be displayed as 100% monitored. |
| Local engine and optional cloud lane | Engine adds the actual system/user messages and calls `backend.generate`. `_execute_cloud_task` requires an external-safe packet and Qwen enablement, constructs its own backend/engine ([engine][engine], [cloud][cloud]). | Initially local-only; cloud separately excluded. Context parity must cover effective messages, not merely the input snapshot. |
| Direct `TriageClient.run_task`, `TaskClassifier.classify`, `TriageRouter` | Callers omitting snapshot/decision retain the legacy path, including possible classifier generation and specialist connectivity checking. Directly injected backends are also possible ([client][client-governed], [classifier][classifier], [router][router]). | Excluded; an exclusion is not enforcement against bypass. |
| `triagecore run-pipeline`, `benchmark`, `stability-pass` | Pipeline calls an engine directly. Benchmark/stability call `run_task` without the governed decision pair; benchmark `--list-only` returns before client creation ([pipeline][pipeline], [benchmark][benchmark], [stability][stability]). | Excluded execution paths; list-only is separately identified as no inference. |
| `compression.compress_context`, `tc_preflight` | Compression can call a supplied backend. Its only package caller is preflight, which obtains a backend only if `TriageClient.router.get_backend` exists; current `TriageRouter` has no such method, so normal preflight supplies `None`. Governed `tc run` does not call compression ([compression][compression], [preflight][preflight], [router class][router-class]). | Direct compression callers excluded. Do not mislabel a callable library inference branch as exercised by normal preflight. Preflight can still write handoff files. |
| `WorkerBase`, `ProjectManager.dispatch_task` | Worker construction may ping and choose a fallback backend; `process` generates. Current GUI Council asks for `repo_mapper`/`code_repair`/`validator`, while registry keys are `context_planner`/`test_stubber`/`review_worker`/`implementer` ([workers][workers], [registry][registry], [dispatch][dispatch]). | Excluded; configured Council failure does not make all worker-library paths inert. CR-132 distinguishes missing-role and zero-order chunking cases. |
| TriageDesk adapter versus full GUI | Adapter exposes status, review, context and packet projections. GUI directly classifies, generates, appends events, writes handoff artifacts and probes backends; it is not exclusively adapter-based ([adapter][adapter], [GUI classification][gui-classify], [GUI generation][gui-generate], [GUI pipeline][gui-pipeline], [context review][gui-context-review], [task review][gui-task-review], [GUI export][gui-export]). | Exclude full GUI. The checklist's blanket read-only GUI assertion conflicts with current source; recording the conflict does not relax the intended invariant. |
| `tc probe`, status/doctor, GUI health checks | `tc_probe` reaches metadata GET transport. Current status/doctor inspect local state, with status constructing a ledger; doctor prints fixed safety-posture strings. GUI performs separate metadata GETs ([probe][probe], [status/doctor][status], [GUI probes][gui-probes]). | Metadata/accounting class distinct from inference. Fixed doctor text is not a live containment measurement. |
| `tc build-review create --validate` | Operator-supplied local validation commands reach `build_review.run_validation`, using a subprocess; artifact creation is a separate effect ([validation][validation]). | Excluded. This is a command execution surface, not an installed agent monitor. Arbitrary child-command behavior needs its own boundary. |
| Other network / maintenance paths | Legacy specialist routing performs a connectivity check; sustainability has optional GeoIP/grid HTTP reads. Backend repair/patch scripts contain embedded source text and write code ([router][router], [sustainability][sustainability]). | Excluded. Metadata network activity is not inference; textual matches inside patch templates are not additional live backend call sites. |

### Requests are not identical to inference events

In [backends.py][backends], OpenAI-compatible generation uses
`POST /chat/completions` and Ollama generation uses `POST /api/chat`, each with streaming
and non-streaming branches. Auto-model resolution can first use `GET /models` or
`GET /api/tags`; fixed model identity avoids that discovery branch. Ping is metadata
traffic, including Ollama's possible LM Studio side-contact. Count logical invocation,
discovery request, inference request and response/stream termination separately. A sent
request is not proof that provider-side inference completed; errors and ambiguous
disconnects cannot be silently relabeled not executed.

### Existing ledger and guard limits

- [CLI ledger wiring][ledger-cli] allows `--no-ledger` and arbitrary `--ledger-dir`.
  [Client event helpers][ledger-client] return without writing when ledger/task ID is
  absent. These are source-confirmed ways to omit this collection path, not measured
  examples of omitted real activity.
- [Config][config] and [TaskLedger][ledger] use relative paths unless explicitly
  supplied otherwise. The [worktree census limitation](evidence-ledger-worktree-limitation-2026-08-07.md)
  remains relevant: separate ledgers can be internally consistent yet absent from the
  ledger being counted. An absolute path convention is not independent observation.
- `TaskLedger` appends JSONL and provides optional signatures for selected event kinds.
  Its event envelope has UUID/time/task/type/payload, not an independent expected-event
  denominator. Do not call ordinary append-open storage immutable or infer deletion
  completeness, approval, safety, or execution authority from signature validity.
- [GuardedTransport][guard] records permitted sends in process memory, without URL,
  headers or body. Package-wide search matches `destination_policy`/`GuardedTransport`
  only inside that module. The actual backends still call module-level `requests`.
  Its recording-adapter contract evidence is not an independent runtime census.
- A `human_review_required` projection does not itself block execution; the terminal
  `human_handoff` route is a distinct control. A future monitor receipt must not
  silently acquire approval or release authority ([architecture separation][architecture]).

## Proposed first-profile boundary and unresolved questions

The planning recommendation is one local-only governed `tc run` profile with one
protocol and fixed model identity, beginning with inert synthetic streams and then a
separately scoped loopback/mock endpoint pilot. Include refused/not-attempted, timeout,
crash and ambiguous terminal outcomes. Preserve separate counts for exceptions and
missing/late acknowledgments. This is proposed scope, not deployed or approved behavior.

Before a runtime claim: establish an observer and expectation source outside worker
control; make process/worktree identity and restart lineage inspectable; enumerate
alternative credential/network access; and verify actual enforcement against a bypass.
CR-135 integration is a dependency when using its guard, not sufficient proof that an
agent cannot choose another caller or endpoint. Exceptions need bounded owner, scope,
expiry and reason; neither `--no-ledger` nor missing evidence is an authorized exemption.

Open design questions are who owns enrollment/denominator completeness, how effective
context and compaction continuity are bound without persisting raw prompts/completions,
how receipt freshness differs from queue acceptance, and what stops consequential work
when coverage fails. Long-running-agent checkpoints are future fixture obligations;
this inspection did not observe an installed autonomous agent loop or checkpoint timer.
Incident escalation ownership and human-controlled resumption remain explicit decisions.

## Reproduction record

The following commands were executed from the repository root for the bounded source
inspection (shell output paths are omitted here). Broader `rg` discovery initially named
nonexistent benchmark/stability/eval filenames; those errors supplied no evidence.
Actual files and symbols were then read as listed above. No package was imported by the
AST census.

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git worktree list
cat AGENTS.md
rg --files -g AGENTS.md -g '*monitor*' -g '*baseline*' docs triage_core tests
rg -n 'destination_policy|GuardedTransport' triage_core
rg -n '\.generate\(|\.execute_task\(|requests\.(get|post)|Session\(|socket\.create_connection|subprocess\.(run|Popen)' triage_core --glob '*.py'
rg -n 'classify_deterministic|TaskClassifier\.classify|build_governed_run_context|def build_run_plan' triage_core/run_plan.py triage_core/client.py triage_core/routers.py
rg -n 'SemanticCompression|compress_context|\.compress\(|compression' triage_core --glob '*.py'
sed -n '85,165p' triage_core/tc_cli.py
sed -n '182,225p' triage_core/client.py
sed -n '1,95p' triage_core/routers.py
sed -n '235,250p' triage_core/worker_registry.py
git merge-base --is-ancestor c798e0ed19d3ca59cfb464ffe8476a4e30a0c1e8 HEAD
git merge-base --is-ancestor f65a86423d520a9583c47e5863b90159b4b040ac HEAD
python - <<'PY'
import ast
from pathlib import Path
for name in ['tc_cli.py', 'cli.py']:
    tree = ast.parse((Path('triage_core') / name).read_text())
    names=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_parser' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subparsers':
            names.append((node.lineno, ast.literal_eval(node.args[0])))
    print(name, sorted(names))
PY
```

Both ancestry commands returned exit 0. GitHub metadata was read through GET
`/repos/coreytshaffer/TriageCore/pulls/{179,128,187,188}`; no mutation was performed.
The CLI census used `ast.parse` over each CLI file, selected `ast.Call` nodes whose
function was `subparsers.add_parser`, and read the literal first argument, sorted by
source line. Source inspection establishes reachable code structure, not live traffic
counts, provider behavior, filesystem permissions, monitor independence or test success.

[scripts]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/pyproject.toml#L43-L45
[tc-parsers]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/tc_cli.py#L2405-L3201
[legacy-parsers]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/cli.py#L25-L190
[tc-run]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/tc_cli.py#L1040-L1350
[preview]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/tc_cli.py#L1137-L1212
[plan-classifier]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/run_plan.py#L295-L365
[client-governed]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/client.py#L86-L219
[engine]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/engine.py#L10-L142
[cloud]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/client.py#L704-L765
[classifier]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/classifier.py#L13-L79
[router]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/routers.py#L6-L79
[router-class]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/routers.py#L163-L175
[pipeline]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/cli.py#L921-L1033
[benchmark]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/cli.py#L472-L558
[stability]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/cli.py#L1036-L1120
[compression]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/compression.py#L39-L114
[preflight]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/tc_cli.py#L85-L163
[workers]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/worker_registry.py#L9-L91
[registry]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/worker_registry.py#L234-L244
[dispatch]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L3845-L3857
[adapter]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/triagedesk_adapter.py#L56-L175
[gui-classify]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L3570-L3597
[gui-generate]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L3716-L3762
[gui-pipeline]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L4110-L4154
[gui-context-review]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L1964-L1971
[gui-task-review]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L2173-L2184
[gui-export]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L4002-L4060
[probe]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/local_backend_probe.py#L309-L313
[status]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/tc_cli.py#L1400-L1550
[gui-probes]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/ui/app.py#L3360-L3445
[validation]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/build_review.py#L244-L270
[sustainability]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/sustainability.py#L131-L208
[backends]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/backends.py#L69-L379
[ledger-cli]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/tc_cli.py#L1246-L1259
[ledger-client]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/client.py#L658-L686
[config]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/config.py#L43-L84
[ledger]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/task_ledger.py#L176-L285
[guard]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/triage_core/destination_policy.py#L798-L1053
[cr135]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/docs/change/requests/CR-135-governed-backend-destination-policy.md#L3-L101
[cr132]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/docs/change/requests/CR-132-triagecore-cli-architecture-accounting.md#L1-L19
[architecture]: https://github.com/coreytshaffer/TriageCore/blob/610c13f253ba631d7052727abe3d68845bb09bb5/docs/architecture/current_system_architecture.md#L43-L96
