# Evaluation Handoff Manifest

Contract identifier: `evaluation_handoff_manifest.v0`

## Purpose

`tc eval build-handoff` packages an explicitly named `eval_case_v0` fixture
and an explicitly named directory of `actual_outcome_export.v0` files for an
external evaluator. The manifest records deterministic relative paths, counts,
and SHA-256 digests. It does not score cases, declare pass/fail, approve work,
or invoke an evaluator.

## Command

```text
tc eval build-handoff \
  --fixture <fixture.jsonl> \
  --actuals-dir <actuals-directory> \
  --out-dir <new-bundle-directory>
```

All three paths are required. There are no default discovery rules and no
overwrite or `--force` mode. The output directory must not already exist.

## Fixed Layout

```text
<bundle>/
  fixtures/safety_boundaries_v0.jsonl
  actuals/<case_id>.json
  manifest/evaluation_handoff_manifest.json
```

The fixture and actual files are copied byte-for-byte. Actual files are direct
children of the input directory; nested paths, symlinks, and non-JSON entries
are rejected. Missing actuals for fixture cases are allowed because a handoff
may represent partial observation. Every included actual must name a unique,
path-safe fixture `case_id`, and its filename must be `<case_id>.json`.

## Manifest

The sorted-key, newline-terminated JSON contains:

- `schema_version: evaluation_handoff_manifest.v0`
- `bundle_type: evaluation_handoff`
- `handoff_contract: evaluation_handoff_contract.v0`
- `scoring_owner: external_evaluator`
- `triagecore_scored: false`
- fixture contract, fixed relative path, case count, and SHA-256
- actual contract, count, and entries sorted by `case_id`, each with its fixed
  relative path and SHA-256

It contains no timestamps, absolute source paths, scores, verdicts, approval
claims, or evaluator commands.

## Validation and Failure

Before writing, the builder validates the fixture with the existing fixture
loader, checks the six required actual-outcome fields and broad JSON types, and
applies the persistent privacy invariant to every parsed fixture and actual.
It does not introduce new decision or boundary-family enums.

Failures exit `1` and print only a stable `reason=<reason>` code. Argparse usage
errors exit `2`. Construction stages into a temporary sibling and atomically
renames it only after all output is written; failures leave no bundle.

## Integrity Boundary

SHA-256 fields describe the copied bytes and support external inspection.
CR-128 adds the read-only command:

```text
tc eval validate-handoff --bundle <bundle-root>
```

It requires the exact closed `evaluation_handoff_manifest.v0` schema, fixed
paths, exact declared inventory, regular non-symlink/non-reparse files and
directories, matching byte hashes and counts, valid fixture and actual
contracts, fixture membership, and persistent privacy safety. Partial actual
coverage remains valid, but a zero-actual bundle is invalid because the CR-127
builder cannot produce one.

Success exits `0` with a bounded fixture/actual count. Closed validation
failures exit `1` and print only `reason=<reason>` to stderr; argparse usage
errors exit `2`. Validation is read-only: it performs no normalization, repair,
report write, ledger write, expected-vs-actual comparison, or evaluator call.

Hash agreement detects drift relative to the manifest. It does not authenticate
the manifest, establish provenance, convey approval, certify safety, or prove
semantic correctness. Scoring and score interpretation remain exclusively
owned by the external evaluator.

CR-129 documents the still-unimplemented external evaluator adapter boundary in
`external_evaluator_adapter_contract.md`. Bundle integrity validation is a
required pre-launch gate for any future adapter, but successful validation
neither selects nor authorizes an evaluator.
