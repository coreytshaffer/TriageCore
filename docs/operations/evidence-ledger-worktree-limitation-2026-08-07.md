# Evidence-Ledger Worktree Census Limitation — 2026-08-07

## What this document is, and is not

**This is a formally recorded methodological limitation and a prospective mitigation for
the remainder of the current daily-use evidence window. It is not an edit to the Window
Protocol, not a retroactive change to eligibility rules, not a runtime change, and not a
Change Request.**

It was produced by a read-only static audit of TriageCore's own ledger path-resolution
code, performed without invoking `tc run`, without creating synthetic executions, and
without writing to any ledger. No TriageCore route, capability, privacy, ledger, or
authority surface participated in producing it. Repository facts below were verified by
direct source inspection at commit `c86a117`.

This document does not modify, and should not be read as modifying:

- [`daily-use-evidence-window-2026-08-01.md`](daily-use-evidence-window-2026-08-01.md) or
  any Day-N evidence record;
- the Window Protocol's eligibility rules, trial parameters, or minimum-duration
  requirement;
- `docs/current_backlog.md` or `docs/futures/futures_register.md` (no candidate or backlog
  entry is created by this document);
- any `triage_core/` source, schema, test, or fixture.

## Why this was audited

During the active evidence window, an operator observation noted that TriageCore work was
occurring inside a dedicated git worktree, structurally separate from the main checkout
where all recorded trials to date live. This raised a concrete question worth resolving
before, not after, an eligible natural run occurred in a location the existing census does
not inspect: if an otherwise-eligible `tc run` were invoked from a different git worktree
of the same repository, where would TriageCore actually resolve and write its ledger
state? The audit traced this statically from the CLI entry point through ledger
initialization.

## Audit findings

**Path-resolution chain for `tc run` (default, unflagged):** `tc_cli.py`'s `tc_run` handler
resolves `ledger_dir = args.ledger_dir or default_config.get_ledger_dir()`
(`tc_cli.py:1182`). `default_config` is a module-load-time `Config()` singleton
(`config.py:155`) constructed with `root_dir="."` (`config.py:44`), so it reads
`./triagecore.toml` relative to the process's current working directory at import time.
`get_ledger_dir()` (`config.py:83-84`) returns `[paths].ledger_dir` from that file — the
tracked `triagecore.toml` sets this to the literal, still-relative string `.triagecore`.
`TaskLedger.__init__` (`task_ledger.py:177-181`) then does
`os.makedirs(".triagecore", exist_ok=True)`, which resolves against `os.getcwd()` at
construction time. Every step in this chain is anchored to the invoking process's working
directory, with no `.git` lookup, no repo-root computation, and no environment-variable
override for `paths.ledger_dir`.

**A second, independent resolver exists and converges on the same non-unifying answer.**
`tc_cli.py` also defines `_ledger_path()` (`tc_cli.py:216-223`), used by essentially every
read-side subcommand (`tc audit`, `tc task show`, and others). It walks upward via
`_repo_root_without_subprocess()` (`tc_cli.py:207-213`) looking for a `.git` entry.
`Path.exists()` returns `True` for both a `.git` directory (main checkout) and a `.git`
file (a linked worktree's git-link pointer — confirmed present as a 97-byte file in the
worktree used for this audit). Git worktrees are, by design, independent top-level
directories that each satisfy this check against themselves. `_repo_root_or_cwd()`
(`tc_cli.py:190-204`, used as a further fallback and by `AgentIdentityRegistry` at
`tc_cli.py:227`) shells out to `git rev-parse --show-toplevel`, which has the identical
per-worktree behavior. The one git primitive that would actually unify worktrees of the
same repository — `git rev-parse --git-common-dir` — is never called anywhere in this
file. Two structurally different resolvers, built for different purposes, independently
land on **the invoking worktree's own root** rather than a shared location.

**`daily-use-window/` isolation is entirely operator-maintained, not a runtime concept.** A
repository-wide search for `daily-use-window` / `daily_use_window` inside `triage_core/`
returns no matches. The isolation seen in the Day-1 through Day-3 records is constructed
solely by the operator supplying `--ledger-dir` with a chosen relative path on each
invocation. Nothing in the software distinguishes an evidence-window ledger from any other
ad-hoc isolated ledger; several other pre-existing isolated `--ledger-dir` trees already
coexist in the main checkout for unrelated purposes (smoke tests, hardware-authorization
review, pytest-authz review), confirming the pattern is generic and untagged at the
runtime level.

## Classification

**EVIDENCE-CENSUS GAP.** Not a runtime defect — the code behaves exactly as written,
consistently, across two independently-designed resolvers, and violates no stated
contract. Not a pure documentation gap either, in the sense of needing only better prose to
fully resolve: the software has no detection or warning mechanism for "this run is landing
outside the canonical tree." The precise, named risk is that an otherwise-eligible run
could occur and never enter the ledger tree currently treated as authoritative.

**Two distinct assurance levels, not to be conflated:** a protocol rule requiring a
canonical checkout plus an absolute evidence-ledger path can **operationally contain** this
gap for the current experiment, conditional on operator compliance. It does not, and
cannot by itself, provide a **runtime-enforced guarantee** that an accidental off-path run
would be detected. This document adopts the former as prospective discipline; it does not
claim the latter, and it does not describe the underlying software behavior as fixed or
closed.

## Practical behavior

- Canonical checkout, relative evidence-window ledger path → counted (the pattern all
  recorded trials to date follow).
- A secondary worktree, the *same relative* `--ledger-dir` value → a separate, invisible
  ledger at a different absolute path, uncounted by the existing census.
- An unflagged `tc run` in either location can also land somewhere the current census does
  not inspect (the main checkout's plain `.triagecore/ledger.jsonl`, last touched
  2026-07-03 and unrelated to this window).

## Prospective mitigation — remainder of the current window only

Effective immediately and only for observations still to come in this window:

> Eligible runs should originate from the canonical checkout and use the canonical
> absolute evidence-ledger path. Runs discovered elsewhere remain evidence and must be
> reconciled rather than silently excluded.

This is methodological containment, not a new scoring criterion. It does not retroactively
reclassify any prior trial, does not change the Window Protocol's eligibility definition,
and does not alter the ≥7-distinct-day or 10–15-task trial parameters. A run discovered
outside the canonical tree remains eligible evidence to be reconciled into the census, not
grounds for exclusion.

## Recorded result

> Observed methodological limitation: multi-worktree execution can fragment ledger
> provenance and cause eligible executions to escape the authoritative census. No eligible
> execution is known to have been omitted so far. Mitigation for remaining observations:
> canonical checkout + absolute ledger path. Runtime hardening deferred until after the
> active evidence window.

## Deferred follow-up (not authorized, not scheduled)

After the evidence window closes, this observation motivates a small future design item:
give TriageCore a runtime-level notion of a "canonical evidence ledger" distinct from an
arbitrary isolated ledger, so that this distinction stops existing only in operator
procedure. No Change Request is opened here, no identifier is minted, and no
implementation, schema, or runtime authority is granted by this document. This is a
candidate for later consideration, explicitly gated on the current window closing first.
