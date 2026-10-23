# Monitoring Coverage Integrity — Frozen Fixtures v0.1

Status: **hand-authored expected results for an unaccepted draft**. These files
are an oracle for a test-only reference reconciler. They are not test results,
and they confer no design acceptance, CR or implementation authority. A
reconciler that disagrees with them is wrong until a reviewed, synchronized
revision says otherwise.

Pinned specification (also recorded in `index.json` and every case file):

| Document | Revision | SHA-256 |
| --- | --- | --- |
| [Contract](../monitoring-coverage-contract-v0.1.md) | r5 | `f8ece79edc562a30c413f7b3946151b6a87213ad4d5c6e67a4ebfc9b83e3d643` |
| [Fixture specification](../monitoring-coverage-fixture-spec-v0.1.md) | r5 | `9039f4ea979823c7a713ec28842c6a73b1880c80f275f9e8ca18b839974ab024` |

`mci/0.1` alone does not identify a revision. A change to either document makes
these files stale until they are re-derived and re-pinned in a synchronized
revision. The r5 re-pin changed only pins and file hashes; every input and
expected report payload is byte-identical to the r4 freeze. An implementation
failure never changes them.

## Layout

- `index.json` lists every case file and raw fixture with its SHA-256, the
  report ticks of each case, and the pins above.
- `cases/<case>-<variant>.json`: F01–F39, 71 files with 85 expected reports.
  Each holds `case`, `variant`, `title`, `pins`, `manifest`, `envelopes` (each
  `{visible_at, record, context_views}`) and `reports` (each `{as_of, expected}`,
  where `expected` is the complete closed report of contract section 3.5).
- `raw/I01`–`raw/I06`: ingestion-boundary cases whose bytes matter. Each holds
  `manifest.json`, `envelopes.jsonl` and `expected.json` (fixture specification
  section 10).

## Reconciler input

For a case file, feed the canonical bytes of `manifest`, then the canonical bytes
of each element of `envelopes` in file order, and the report's `as_of`. File
order is irrelevant to well-formed results. Canonical bytes and every digest
follow contract section 8: sorted keys, compact separators, ASCII only, no
floats, and SHA-256 over the domain prefix `mci/0.1/<domain>` plus LF plus those
bytes. For raw cases, feed `manifest.json` and each LF-terminated line of
`envelopes.jsonl` (without the LF) exactly as stored.

## How the expected reports were derived

Every classification was decided by hand from the pinned documents: partitions,
`disputed` flags, source, admission and checkpoint states, evidence record IDs,
commitment choices (or null), verdicts, window states and every finding. A small
helper outside the repository did only mechanical work. It computed canonical
bytes and digests, numbered records by source in the fixture specification's
merge order, added deadline arithmetic (`dispatch_tick` + 3 or + 5, admission
tick + 3, cut + 2), totalled hand-assigned partitions, sorted rows and findings,
and filled source rows the author declared clean. A clean row is
`accepted_prefix` = `highest_seen` = delivered count; the helper checked that
those sequences were contiguous, single-variant and watermark-free rather than
inferring it. It also checked that partition totals equal the counts frozen in
the fixture specification, that persisted codes appear historically and that
`closed_reconciled` has no findings.

An independent check, written separately, confirmed that a strict parser rejects
each raw case exactly at its expected index, that every file hash matches
`index.json`, and that every `input_set_digest` recomputes from its case file.

## Reading notes

- F18 and F22 have labeled variants whose inputs are identical; the labels add
  no wire record.
- F29's omitted execution is author knowledge, not an input, so the expected
  report cannot reflect it.
- Findings about a disputed unit are candidate findings. Check the subject's
  `unit_states.disputed`; they do not confirm execution.
- Reports do not index all evidence. Uncredited records remain in `envelopes`.

These fixtures use fabricated public data only and test no provider traffic,
credentials, live monitor, clocks across hosts, compaction in a real runtime,
cryptographic custody or refusal behavior.
