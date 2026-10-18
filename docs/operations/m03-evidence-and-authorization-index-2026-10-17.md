# M03 Evidence and Authorization Index — 2026-10-17

Prepared 2026-10-17 America/Los_Angeles (PDT) / 2026-10-18 UTC. Documentation
only. This index records evidence and its provenance; it grants no authority.

## Labels used here

**M03**, **M04**, and **M09a** are assessment work-package labels from the
operator's planning record (`ACE_Resolved_and_Next_Steps_2026-10-17.txt`). They
are **not** repository Change Request identifiers, do not occupy the CR
namespace, and must not be cited as CR authority. No CR identifier is allocated
by this document.

## Authority for this documentation work

The operator's grant, recorded verbatim:

> Named grant: M03 documentation reconciliation, 2026-10-17.
>
> I authorize the following documentation work in coreytshaffer/TriageCore on
> branch "claude/new-session-xfbef6". This grant deliberately includes editing,
> proportionate verification, one commit, and a normal push to that branch.
>
> Writable scope—exactly these four files:
>
> Create:
>
> - "docs/operations/m03-evidence-and-authorization-index-2026-10-17.md"
> - "docs/operations/m09a-review-2026-10-17.md"
>
> Modify:
>
> - "docs/change/requests/CR-DD-012B-shared-preview-execution-consumption.md"
> - "docs/current_backlog.md"
>
> Required content:
>
> 1. Record this grant in the new M03 index. Identify M03, M04 and M09a as
>    assessment work-package labels, not repository CR identifiers.
>
> 2. Add a dated PR #179 merge-fact entry beside the historical
>    withheld/unmerged statements. Preserve those historical statements and the
>    original authority-defect record. Record the merged revision, merge commit,
>    timestamp and evidence sources.
>
> 3. Keep authorization-record reconciliation required. State that the original
>    merge-authority grant has not been located and that satisfaction of its
>    conditions remains unresolved. This grant authorizes the present
>    documentation work; it does not retroactively authorize PR #179's merge.
>    Release and closeout remain withheld.
>
> 4. Record ACE-RUNNER-FIXTURE-GATE-001 as resolved. You may inspect
>    "coreytshaffer/agent-control-evals" read-only to verify PR #4, merge commit
>    "b876a287fc27701e79f16208640f86845f1edafc", and the relevant tree
>    identities. Distinguish your direct observations from the PR's reported
>    97-test result and my reported post-merge verification. Do not claim raw
>    logs were retained unless you locate them.
>
> 5. Mark the M09a entry prepared for Corey's review—owner disposition pending.
>    Summarize evidence, unresolved questions and the proposed M04 increment. Do
>    not record completed owner review, accepted residual risk, or new
>    implementation authority.
>
> Before editing, verify the repository, branch, HEAD and clean worktree against
> the reported "ede8ef1" baseline, and read applicable nested instructions.
>
> Before committing, run "git diff --check", inspect the complete diff, verify
> references, and confirm that only the four authorized files are staged. Keep
> timestamps in America/Los_Angeles and UTC.
>
> After verification, make one documentation commit and push normally to
> "claude/new-session-xfbef6". Return the commit SHA, changed-file list,
> verification results and remaining gaps.
>
> No PR creation, merge, release, closeout, tag, force-push, runtime/configuration
> changes, export implementation, or writes to another repository are
> authorized.
>
> Stop and report if the work requires another writable path, the checkout has
> unexpected changes, or governing instructions conflict. This grant ends after
> the successful scoped push or three hours of work, whichever comes first.

The only editorial change is reflowing the lines into a Markdown blockquote; the
curly apostrophes in the original are rendered as straight apostrophes.

This grant authorizes the present documentation work only. **It does not
retroactively authorize the merge of TriageCore PR #179**, and it grants no
release or closeout authority for CR-DD-012B.

Baseline verified before editing: repository root `/home/user/TriageCore`,
branch `claude/new-session-xfbef6`, `HEAD` =
`ede8ef154d916389dd140345b256b46fd7b19eaa` (merge of PR #183), single worktree,
no tracked or untracked changes, no stashes. No nested `AGENTS.md` exists below
the repository root.

## Evidence classes

Each entry below is tagged with one of three provenance classes, which are not
interchangeable:

- **Observed** — read directly during this work from Git objects, refs, or the
  GitHub API, by the exact command or call named.
- **PR-reported** — stated in a PR body or verification record; not re-executed
  here.
- **Operator-reported** — stated by Corey; accepted as reported, not
  independently reproduced.

## Entry 1 — ACE-RUNNER-FIXTURE-GATE-001: RESOLVED

**Disposition: resolved.** Retained as a closed corrective-action record in an
independent evaluator repository, `coreytshaffer/agent-control-evals`. This is a
bounded evaluator-integrity correction; it does not raise any TriageCore runtime
operating-effectiveness claim and closes no unrelated SafeTask or TriageCore
finding.

| Fact | Value | Class |
|---|---|---|
| Pull request | `coreytshaffer/agent-control-evals` PR #4, branch `fix/ace-runner-fixture-gate-001` | Observed (merge-commit message; `refs/pull/4/head`) |
| Merge commit | `b876a287fc27701e79f16208640f86845f1edafc`, parents `24d74debbe77ed1e5fb77b50f5cbe26d39100e36` (base) and `f4fd641f202f0bb20f50eb68f32bf2d8723b3172` (PR head) | Observed |
| Merge time | 2026-10-17 20:39:27 PDT / 2026-10-18 03:39:27 UTC (merge-commit committer date) | Observed |
| `main` ref | `refs/heads/main` = `b876a287fc27701e79f16208640f86845f1edafc` at observation time | Observed (`git ls-remote`) |
| PR head ref | `refs/pull/4/head` = `f4fd641f202f0bb20f50eb68f32bf2d8723b3172` | Observed (`git ls-remote`) |
| Tree identity | merge tree and PR-head tree are both `c41980b272e46cb28e24d01992ca79149956d8a2` | Observed (`git rev-parse <commit>^{tree}`) |
| Locally tested commit | `e6656543b8da049060b712010987332ffbf43ec4`, stated to share tree `c41980b…` | PR-reported; that object is **not present** on the remote (`git cat-file -t` fails), so the tree match is not independently verified |
| Test result | 97 passed, no skips, including optional JSON Schema tests; fixture validation and mock self-test exit 0 over 22 fixtures; adversarial actuals exit exactly 1 | PR-reported |
| Post-merge integrity | exact post-merge file match | Operator-reported (Corey) |

Observation method, run 2026-10-17 ~20:50 PDT / 2026-10-18 ~03:50 UTC from a
read-only shallow clone (`git clone --depth 10`):

```text
git remote get-url origin        # https://github.com/coreytshaffer/agent-control-evals
git log -1 --format='%H %P %T %ci' b876a287fc27701e79f16208640f86845f1edafc
git log -1 --format='%H %P %T %ci' f4fd641f202f0bb20f50eb68f32bf2d8723b3172
git rev-parse b876a287^{tree} f4fd641f^{tree}   # both c41980b272e46cb28e24d01992ca79149956d8a2
git ls-remote origin HEAD refs/heads/main refs/pull/4/head
```

Limitations, stated rather than filled:

- **No raw test log was located.** The clone contains no JUnit, `.log`, or other
  file recording the 97-test run, and no file naming the finding ID. The
  97-test figure therefore rests on the PR's verification record only. It is not
  relabelled here as a newly executed log, and no log is reconstructed.
- **PR #4 API metadata was not read in this work.** An unauthenticated request
  to `api.github.com/repos/coreytshaffer/agent-control-evals/pulls/4` returned
  HTTP 403, and the repository is not attached to this session's GitHub tools.
  `merged=true` is therefore not directly observed here; the merge is evidenced
  by the merge commit on `main` whose second parent is the PR head ref.
- No test suite was executed in either repository during this work.
- The evaluator's 97-test result is distinct from TriageCore's own suite results
  (for example, the 1802 passed / 6 skipped recorded for CR-DD-012B) and from any
  87-test TriageCore subset referenced in assessment material. These figures must
  not be combined.

Reopen only on new regression evidence, a materially changed affected path, or
failure of the repaired invariant. Do not rerun the settled suite solely to
reconfirm closure.

## Entry 2 — TriageCore PR #179 (CR-DD-012B) authorization reconciliation

**Status: authorization-record reconciliation REQUIRED.** The merge is an
observed fact; authorization of that merge is not established.

### Observed merge facts

| Fact | Value | Source |
|---|---|---|
| Merge commit | `c798e0ed19d3ca59cfb464ffe8476a4e30a0c1e8`, parents `fa66c644c95dcdd68c879313225822d696568643` (base `main`) and `5cb95057ac7c498b9256f9688dc6e47483b85ae5` (PR head) | `git log -1 --format='%H %P' c798e0e` |
| Merged revision | PR head `5cb9505` on `claude/cr-dd-012b-shared-preview-execution-35b467` | GitHub PR #179 `get` (`head.sha`) |
| Merge time | 2026-08-29 11:28:35 PDT / 2026-08-29 18:28:35 UTC | GitHub `merged_at`; merge-commit committer date |
| Merged by | `coreytshaffer` | GitHub `merged_by` |
| Ancestry | `c798e0e` is an ancestor of `ede8ef1` (current `main` lineage) | `git merge-base --is-ancestor c798e0e HEAD` |
| Tree | merge tree = PR-head tree = `a9607e4795e84a8771056e5fc11540eddaf7b602` | `git rev-parse c798e0e^{tree} 5cb9505^{tree}` |
| Code/test identity | `git diff bbe5336 5cb9505 -- triage_core/ tests/` is empty | `git diff --quiet` |
| Non-doc change after `bbe5336` | one line in `.github/workflows/tests.yml` (the authorized CI-reference repair) | `git diff --stat bbe5336 5cb9505 -- .github` |
| `e5f3218..5cb9505` | documentation only: the CR-DD-012 and CR-DD-012B CR documents and `docs/current_backlog.md` | `git diff --stat e5f3218 5cb9505` |
| CI at merged head | Actions run `32584514430` at `5cb9505` (2026-08-22 ~16:23 UTC): `pytest (3.10)`, `pytest (3.11)`, `pytest (3.12)`, `windows_executor` all `success` | GitHub PR #179 `get_check_runs` |
| GitHub reviews | none submitted | GitHub PR #179 `get_reviews` (empty) |
| PR title at merge | "CR-DD-012B: shared preview/execution consumption (accepted at bbe5336; merge withheld)" | GitHub PR #179 `get` |

### Reconciliation table

| Question | Evidence | Status |
|---|---|---|
| (a) Was the required independent review performed, and did it satisfy the actual approval? | The CR records that "a subsequent independent merge review found four record-integrity defects", repaired in `5cb9505` under a bounded governance-record grant. The PR's suggested review gate lists the checks expected. No GitHub review was submitted, and no record states that the review completed, or that it satisfied a merge-authority condition. | **Unresolved.** A review occurred in part; its completion and sufficiency are not evidenced. |
| (b) Which revision or PR state was authorized to merge? | Implementation acceptance is pinned to `bbe5336`. The merged head is `5cb9505`, which is code/test-identical to `bbe5336` plus the authorized CI line and documentation-only repairs. No merge-authority grant naming any revision was located. | **Unresolved.** What was merged is observed; what was authorized to merge is not recorded. |
| (c) What recording duties applied after merge? | The repository's practice (for example, the CR-DD-013 closeout in `docs/change/change_log.md`) retires pre-merge status language after merge. Before this work, the CR-DD-012B status table, the PR #179 title and body, and `docs/current_backlog.md` still read "merge withheld" or "unmerged branch". `docs/operations/classifier-terminal-fallback-2026-08-29.md` already recorded the merge as a fact. | **Partially discharged by this work:** dated merge-fact entries are added beside the historical statements, which are preserved. The PR #179 title/body are untouched, because PR metadata is outside this grant. |
| (d) What closeout or release decisions remain withheld? | No release or closeout grant for CR-DD-012B was located. | **Release and closeout remain WITHHELD.** |

### Missing record

The **original merge-authority grant for PR #179 has not been located.** The
search covered the CR-DD-012B and CR-DD-012 documents, `docs/current_backlog.md`,
`docs/change/change_log.md`, a repository-wide search for "merge authority", and
PR #179's metadata, reviews, and comments. Operator-held notes or chat logs were
not available to this search.

Per the planning record's stop rule, this missing record is a bounded unresolved
result. Retroactive permission is not inferred from the merge, from the merger's
identity, from green CI, or from the present grant, and no new grant is
manufactured. Satisfaction of whatever conditions that grant carried is
unresolved until the grant text is recovered and compared against the facts
above.

## Sources

- TriageCore PR #179: https://github.com/coreytshaffer/TriageCore/pull/179
- TriageCore merge commit: https://github.com/coreytshaffer/TriageCore/commit/c798e0ed19d3ca59cfb464ffe8476a4e30a0c1e8
- CR record: `docs/change/requests/CR-DD-012B-shared-preview-execution-consumption.md`
- Prior merge-fact note: `docs/operations/classifier-terminal-fallback-2026-08-29.md` (Reconciliation section)
- agent-control-evals PR #4: https://github.com/coreytshaffer/agent-control-evals/pull/4
- agent-control-evals merge commit: https://github.com/coreytshaffer/agent-control-evals/commit/b876a287fc27701e79f16208640f86845f1edafc
- agent-control-evals published head: https://github.com/coreytshaffer/agent-control-evals/commit/f4fd641f202f0bb20f50eb68f32bf2d8723b3172
- Operator planning record: `ACE_Resolved_and_Next_Steps_2026-10-17.txt` (supplied to this session; not committed to the repository)
- Owner review: `docs/operations/m09a-review-2026-10-17.md` (prepared; disposition pending)
