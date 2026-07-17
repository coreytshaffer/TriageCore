# Evaluation Handoff Contract

Contract identifier: `evaluation_handoff_contract.v0`

## Purpose

This document defines the CR-123 handoff boundary between TriageCore and an
external evaluator suite. TriageCore may validate and export deterministic
evidence. The external evaluator suite owns scoring, pass/fail judgment,
findings, and aggregate metrics.

The contract is intentionally file-based. It avoids cross-repository imports,
runtime callbacks, hidden model calls, and any requirement that TriageCore know
the evaluator's scoring implementation.

## Required TriageCore Inputs

The TriageCore side of the handoff requires explicit operator-named paths:

| Input | Required | Contract identifier | Notes |
| --- | --- | --- | --- |
| Expected fixture JSONL | Yes | `eval_case_v0` | One JSON object per line. Validate with `tc eval validate-fixtures --input <path>`. |
| Actual outcome directory | Yes | `actual_outcome_export.v0` | Directory containing one `<case_id>.json` file per observed case. |

The current repository fixture is:

```text
tests/fixtures/evals/safety_boundaries_v0.jsonl
```

The current documented actual-output directories are:

```text
.triagecore/eval_actuals/<run_id>/
actuals/triagecore_smoke/
```

TriageCore must not infer default evaluator inputs from the ledger, route
history, admission state, or local runtime state. The operator passes all
paths explicitly to the CR-127 bundle builder.

## Required TriageCore Outputs

TriageCore produces static files only:

| Output | Required | Deterministic path rule | Producer |
| --- | --- | --- | --- |
| Validated expected fixture JSONL | Yes | Preserve the operator-provided filename; current fixture path is `tests/fixtures/evals/safety_boundaries_v0.jsonl`. | Human-authored fixture plus CR-121/CR-122 validation |
| Actual outcome JSON files | Yes | Write one path-safe `<case_id>.json` file under the operator-provided actuals directory. | Existing actual outcome export helpers |

Actual outcome files use the existing JSON shape documented in
`docs/evals/actual_outcome_export.md`. The required fields are:

- `case_id`
- `decision`
- `boundary_family`
- `reasons`
- `audit_required`
- `human_approval_required`

Optional diagnostic fields may exist, but external scoring must treat them as
diagnostic evidence rather than primary oracle fields unless the external suite
explicitly adopts them.

## External Evaluator Outputs

The external evaluator suite, not TriageCore, produces scored artifacts such as:

```text
reports/<run_id>.jsonl
```

Those reports may include pass/fail outcomes, partial-credit findings,
aggregate metrics, or reviewer-facing summaries. TriageCore does not define the
scored report schema in this CR. TriageCore must treat evaluator findings as external artifacts unless a later CR adds an explicit import or display contract.

## Deterministic Handoff Layout

CR-127 materializes a handoff bundle using these relative paths:

```text
fixtures/safety_boundaries_v0.jsonl
actuals/<case_id>.json
manifest/evaluation_handoff_manifest.json
```

The builder is documented in
`docs/evals/evaluation_handoff_manifest.md`. It copies the already-defined
evidence byte-for-byte and records deterministic hashes without changing the
scoring boundary.

Historically, CR-123 does not create that bundle, manifest, or builder; CR-127
is the separately approved implementation slice that now materializes them.

## Exit-Code Expectations

TriageCore commands used before handoff must follow these expectations:

| Command | Success | Failure | CLI usage error |
| --- | --- | --- | --- |
| `tc eval validate-fixtures --input <path>` | Exit `0` when the JSONL fixture is valid. | Exit `1` for missing, unreadable, malformed, structurally invalid, or duplicate-case fixtures. | Exit `2` for argparse usage errors. |
| `tc eval export-smoke --output-dir <dir>` | Exit `0` after writing contract-shaped actual JSON. | Exit `1` for contract or write failures. | Exit `2` for argparse usage errors. |
| `tc eval export-privacy-smoke --output-dir <dir>` | Exit `0` after writing contract-shaped actual JSON. | Exit `1` for contract or write failures. | Exit `2` for argparse usage errors. |
| `tc eval export-forbidden-tool-smoke --output-dir <dir>` | Exit `0` after writing contract-shaped actual JSON. | Exit `1` for contract or write failures. | Exit `2` for argparse usage errors. |
| `tc eval build-handoff --fixture <path> --actuals-dir <dir> --out-dir <new-dir>` | Exit `0` after atomically publishing an unscored deterministic bundle. | Exit `1` with a stable closed reason for input, privacy, path, or write failures. | Exit `2` for argparse usage errors. |

The external evaluator suite owns its own exit-code contract. TriageCore may
document how to invoke that suite, but this CR does not add an evaluator runner
or interpret evaluator exit statuses.

## Non-Goals

CR-123 explicitly excludes:

- scoring, pass/fail judgment, aggregate metrics, partial credit, or score
  interpretation inside TriageCore
- no evaluator execution from TriageCore or any TriageCore CLI command
- model, completion, chat, embedding, backend, endpoint, or network calls
- routing, admission, approval, identity, or worker integration
- no ledger writes or durable recording that an evaluation occurred
- a bundle builder, manifest writer, bundle validator, or result importer
- changes to `eval_case_v0` or actual outcome JSON fields
- new fixture families or adversarial/tampering expansion

CR-127 implements the deterministic bundle/manifest builder. The next safe
slice is a deterministic integrity validator for an existing bundle, without
executing or scoring the evaluator.
