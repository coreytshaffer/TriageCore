# CR-136: Test-Only Reference Reconciler for Monitoring Coverage Integrity

## Status

- **Status:** Proposed. An implementation candidate is prepared on the designated
  development branch at the operator's direction (see Implementation Authority).
- **Type:** Evidence and reconstruction; review and human control. Test-only: no
  runtime, routing, CLI, ledger, schema or configuration component.
- **Identifier allocation:** CR-136, allocated by this document after a census on
  2026-10-23. At `main@610c13f253ba631d7052727abe3d68845bb09bb5` the highest numeric CR
  in `docs/change/requests/` is CR-135. No file, document, test or module in the
  repository names CR-136, and a GitHub pull-request search for `CR-136` in this
  repository returned no results.
- **Design baseline:** Monitoring Coverage Integrity contract `mci/0.1` revision r5, its
  fixture specification r5, and the frozen fixture corpus pinned to both (Pinned Inputs
  below). These remain unaccepted research drafts. On 2026-10-23 the operator found r4
  "suitable as the proposed reconciler CR baseline after two small wording corrections
  and re-pinning", and those corrections became r5. This CR records that statement as
  quoted; it does not reclassify it as proposal or design acceptance.
- **Proposal acceptance / design acceptance:** Not separately recorded.
- **Implementation authority:** Operator instruction of 2026-10-23, recorded verbatim
  under Implementation Authority. It is treated as bounded to the three files in Scope.
- **Implementation acceptance / merge / release / closeout:** Not granted.

### Lifecycle state

| Stage | State |
| --- | --- |
| identifier allocation | CR-136, census above |
| proposal acceptance | not separately recorded |
| design acceptance | not separately recorded; r5 baseline statement quoted above |
| implementation authority | operator instruction of 2026-10-23, bounded to Scope |
| implementation acceptance | not granted |
| merge authority | not granted |
| release authority | not granted |
| closeout | not granted |

## Implementation Authority

The operator's instruction of 2026-10-23, quoted without change:

> Then proceed to the proposed test-only reconciler CR: the CR record,
> tests/mci_reference_reconciler.py, and tests/test_mci_reference_reconciler.py,
> consuming the existing frozen documentation corpus directly.

This CR reads that instruction as a deliberate bundle covering two things: drafting this
record, and preparing an implementation candidate limited to the two named test files on
branch `ccr-a93d18f0-7tyn4t`. It does not read the instruction as acceptance, merge
authority or authority over any other path. If the operator did not intend
implementation authority, the implementation lives in its own commit and can be
reverted without touching this record.

## Scope

Writable, exactly:

1. `docs/change/requests/CR-136-monitoring-coverage-reference-reconciler.md` (this
   record);
2. `tests/mci_reference_reconciler.py`;
3. `tests/test_mci_reference_reconciler.py`.

Read-only inputs:
- `docs/research/monitoring-coverage-contract-v0.1.md`;
- `docs/research/monitoring-coverage-fixture-spec-v0.1.md`;
- `docs/research/monitoring-coverage-fixtures-v0.1/` (the frozen corpus, consumed
  directly and never rewritten).

Out of scope:
- everything under `triage_core/`, and the `tc` and `triagecore` entry points;
- ledgers, schemas, configuration, CI workflows and `pyproject.toml`;
- the corpus and both specifications;
- any runtime observer, monitor, gate or provider traffic.

## Human Approval Requirement

The test passing is evidence about conformance to fabricated cases, not acceptance.
Implementation acceptance, merge, release and closeout each need a separate explicit
human decision. A reconciler that disagrees with the frozen oracle is wrong until a
reviewed, synchronized specification revision says otherwise. No implementation failure
may edit the corpus.

## Purpose

Execute the frozen `mci/0.1` oracle. A pure reference implementation shows whether the
contract, as written, determines every frozen report, and it gives a later runtime
design a checked definition to compare against. It does not monitor anything. Census
assurance stays `unknown` and inhibition stays `not_implemented` in every report.

## Design

- `tests/mci_reference_reconciler.py` exposes
  `reconcile(manifest_bytes, envelope_bytes, as_of)`. It returns the closed report of
  contract section 3.5, or the section 3 `input_error` object. It imports only
  `__future__`, `hashlib`, `json`, `re` and `typing`. It performs no I/O and lives
  under `tests/`, outside the installed package (`pyproject.toml` excludes `tests*`).
- Ingestion follows contract section 3: strict JSON parsing with duplicate keys, floats
  and non-ASCII values rejected, manifest validation, and the lowest failing index.
- For each tick from 0 to `as_of`, it computes a snapshot from the envelopes visible at
  that tick. The snapshot covers:
  - source walks: prefix, holes, blocks, conflicts and quarantine, watermarks and
    contradictions;
  - witness epoch lineage;
  - the unit set and disputes;
  - context bindings, receipts, exemptions and admissions.
- A replay over those snapshots handles everything that depends on history:
  - timer, count and final cuts;
  - checkpoint receipts, each judged when it first becomes usable;
  - checkpoint completion, misses and invalidation;
  - deadline obligations, each assessed against the snapshot at its own deadline.
- `tests/test_mci_reference_reconciler.py` reads the corpus directly and canonicalizes
  inputs independently of the reconciler.

## Acceptance Criteria (proposed)

1. Every one of the 85 frozen reports in the 71 case files equals the reconciler's
   output exactly. All six raw-byte cases return their exact `input_error` objects.
2. The pinned SHA-256 values in `index.json` equal the current contract and fixture
   specification at revision r5. Every corpus file matches its indexed hash.
3. For every case file, reversing or shuffling the envelope order, and adding later
   exact retransmissions of every envelope, leave every report unchanged.
4. Every report states `census_assurance=unknown` and `inhibition=not_implemented`.
5. An AST check confirms the reconciler imports only the allowlisted standard-library
   modules, makes no file, process, network or dynamic-execution calls, and does not
   reference `triage_core`.
6. The repository's existing tests are unaffected, and no file outside Scope changes.
7. The corpus is not modified.

## Implementation Candidate Evidence

Observed on 2026-10-23 in the agent's cloud container at candidate commit
`cd44e11752d26e477deb0b49bc8d1545a74b604e`, with a clean working tree, Python 3.13.16
and pytest 9.1.1. This is local evidence, not CI.

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_mci_reference_reconciler.py -q` | 237 passed |
| `python -m pytest -q` (full suite) | 2428 passed, 77 skipped, 11 failed |

The 11 failures are in `tests/test_ui_smoke.py` and
`tests/test_ui_execute_context_review.py`. Each raises `ModuleNotFoundError` for
`tkinter`, which this container lacks. The same 11 fail with the two new test files
moved aside, so they are environmental and unrelated to this change. The working tree
stayed clean.

Pinned inputs:

| Document | Revision | SHA-256 |
| --- | --- | --- |
| Contract | r5 | `f8ece79edc562a30c413f7b3946151b6a87213ad4d5c6e67a4ebfc9b83e3d643` |
| Fixture specification | r5 | `9039f4ea979823c7a713ec28842c6a73b1880c80f275f9e8ca18b839974ab024` |

A mutation check was run outside the repository. Each mutant disabled one rule, and it
was killed by the frozen cases that exercise that rule:
- receipt time order: F10(c);
- the count-trigger exclusion of initially disputed units: F35, F38(b) and F39(b);
- deadline assessment at the deadline rather than now: F05, F21 and F32;
- rejected reopenings leaving accepted epochs intact: F39;
- first-grant binding of an exemption ID: F37(a);
- sticky membership mismatch: F26(a).

The mutant removing the check that a grant was usable at dispatch survived. In this
corpus that check is equivalent to the human-gap suspension: a grant first usable after
dispatch implies a missing earlier human record at dispatch. The mutation check is
supporting evidence only.

CI on Python 3.10–3.12 has not been observed for this candidate.

## Implementation Interpretations Outside the Frozen Oracle

These choices are not pinned by r5 and are not exercised by any frozen case. They are
recorded so a reviewer can accept them, pin them in a later specification revision with
cases, or reject them.
- An epoch counts as unresolved for ratios and current `EPOCH_CONTINUITY_FAILURE` only
  through blocked witness records or epoch-caused disputes: a dispatch after a child
  opened, or a contradicted first child dispatch. Other disputes in that epoch, such as
  an identity conflict, do not count.
- The witness dispatch and terminal of a disputed unit are not context-checked.
- An admit or terminal whose epoch, action or `retry_of` disagrees with the unit's
  dispatch descriptor is an `ATTEMPT_IDENTITY_CONFLICT`.
- A shape failure is reported only as `INVALID_RECORD`. A shape-valid record may carry
  both `SOURCE_ROLE_MISMATCH` and `POLICY_MISMATCH`.
- An envelope whose `visible_at` is not a nonnegative integer is treated as visible from
  tick 0.
- Context checks are deferred for evaluated members naming an unknown attempt until
  corroborated. `received` receipts are never context-checked. A `received` receipt
  naming an unknown attempt is also `ORPHAN_RECEIPT`.
- A unit unknown at its review deadline is assessed as missed, even if an exemption
  would have applied to its dispatch.
- Record-ID reuse is detected within one source only.
- Any non-contiguous source, blocked prefixes included, keeps the window open.
- `EXEMPTION_NOT_APPLICABLE` is raised only when no named valid grant applies.

## Independence Limitation

The same agent, in one session, hand-derived the oracle and wrote this reconciler. The
oracle was frozen first and then spot-checked semantically by the operator. Agreement
between the two is consistency evidence, not independent verification.

## Non-Claims

This CR establishes no runtime monitoring, census completeness, non-bypassable boundary,
safety, authorization or inhibition. It does not integrate with CR-135 or `tc run`. It
neither changes nor counts toward the daily-use evidence window, and it adopts no
off-repository decision text, including TC-AM-001. It grants no merge, release or
closeout authority.

## Remaining Decisions

- Implementation acceptance of the candidate, against the criteria above.
- Disposition of each implementation interpretation.
- Merge authority, and observation of CI on Python 3.10–3.12.
- Whether TC-AM-001, absent from this repository, applies to or would interfere with
  this test-only work.
