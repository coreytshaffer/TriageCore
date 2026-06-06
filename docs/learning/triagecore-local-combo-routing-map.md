# TriageCore Local Combo Routing Map

## Purpose

This starter map defines how TriageCore should assign task classes to local LLM and tool combinations.

The map is based on SafeTask AI development examples, but it is not part of the SafeTask AI runtime. TriageCore should own the final lesson store and routing engine.

## Design Rule

Assign each task to the smallest reliable local combination that can complete it with the required verification.

Do not choose a larger model just because it is available. Do not choose a smaller model when the task has already shown high correction burden, missing context, or repeated failure.

## Starter Routing Map

| Task class | Default local combo | Required checks | Starting confidence | Human review |
| --- | --- | --- | --- | --- |
| `repo_search_summary` | small summarizer + deterministic search | source file references, no unsupported claims | high | optional |
| `documentation_synthesis` | medium drafter + repo search + diff check | source references, `git diff --check` | high | recommended |
| `smoke_check_design` | medium drafter + route/code scan | route inventory, threat or workflow evidence, diff check | high | required for security-sensitive checks |
| `configuration_review` | medium reasoner + deterministic file inspection | observed config/dependency files, no version claims without evidence | medium | recommended |
| `ui_copy_cleanup` | small editor + layout/visual check | text fit, no feature overclaiming, visual review when possible | medium | optional |
| `code_patch_planning` | medium reasoner + static inspection | file references, risk list, smoke plan | medium | recommended |
| `ui_api_slice` | reasoning coder + syntax checks + endpoint smoke | JS/Python syntax, focused API smoke check, diff check | medium-high | required |
| `multi_file_code_edit` | stronger reasoner + deterministic tests | syntax checks, focused integration smoke, rollback awareness | medium | required |
| `compliance_sensitive_interpretation` | local drafter + source registry review + human approval | approved source citation, boundary labels | low | required |

## Assignment Confidence Rules

TriageCore should raise confidence when:

- similar outcome records were accepted with low correction burden
- deterministic checks passed
- source artifacts were cited directly
- the task class stayed within a known scope

TriageCore should lower confidence when:

- correction burden is medium or high
- the model lacked source context
- the result needed repeated retries
- the task required legal, compliance, safety, medical, or release judgment
- deterministic checks failed or were skipped

## Initial Rules From SafeTask AI Examples

### Documentation Synthesis

SafeTask examples:

- source registry docs
- handoff/backlog synchronization
- dependency/configuration review

Starter rule:

Route scoped documentation synthesis to a medium local drafter with deterministic repo search and diff checks. Human review is recommended when the doc influences product direction or safety boundaries.

### Smoke Check Design

SafeTask examples:

- Gate 4 security smoke checklist
- threat-model aligned route checks

Starter rule:

Route smoke-check design to a medium local drafter plus route/code scan. Require human review when the checklist becomes a release gate or security gate.

### UI/API Slice

SafeTask examples:

- read-only Admin Governance source registry display
- Flask source-registry endpoint
- JavaScript Admin Governance renderer

Starter rule:

Route scoped UI/API slices to a reasoning coder with mandatory syntax checks and one focused endpoint smoke check. Do not allow this combo to expand into broad refactors without explicit approval.

## Stop Conditions

Stop assignment and switch strategy when:

- two attempts fail on the same syntax or runtime error
- a source claim cannot be tied to a file, route, or record
- the task becomes broader than the requested slice
- the output requires policy, compliance, safety, or evidence-release approval
- deterministic tooling can answer the question more reliably than model generation

## Next Integration Step

Move this map into TriageCore's own lesson store and connect it to assignment outcome records. SafeTask AI should remain one source of examples, not the owner of the routing map.
