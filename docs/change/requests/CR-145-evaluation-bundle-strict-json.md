# CR-145 evaluation bundle strict JSON validation

## Status

Proposal, design and bounded implementation were approved on November 26,
2026. The verified base is TriageCore `main` at
`241aba5bccc7977b216c993ee7dc3312a7708cb8`. This implementation is for
review in a separate draft pull request.

## Scope

The evaluation fixture loader and the bundle's actual-outcome readers
previously accepted repeated object keys. The bundle builder and validator
also opened the fixture more than once when validating and processing it.
The evaluation handoff now shares one strict decoder across fixture JSONL,
actual outcomes and the manifest. It rejects duplicate keys at every
object depth, including objects in arrays, and refuses the non-standard
numeric constants `NaN`, `Infinity` and `-Infinity`.

The builder captures the fixture bytes once and uses them for decoding,
privacy checks, hashing and bundle publication. The validator checks the
hash and decodes the same captured bytes. Each actual outcome continues to
use one byte sequence for checks and hashing, and for copying during a build.
Valid input retains its original bytes, schema, counts, order and hashes.
Previously accepted bundles with ambiguous JSON require regeneration from
valid inputs.

The fixture CLI reports parser errors by line without showing the input.
The bundle CLI keeps the existing `fixture_invalid`,
`actual_invalid_json` and `manifest_invalid_json` reason codes. A rejected
build publishes no bundle. Validation is read-only.

## Implementation authority

The operator accepted the proposal and design and authorized the eleven
paths below, synthetic verification and a separate draft pull request on
November 26, 2026.

| Path | Purpose |
| --- | --- |
| `triage_core/evaluation_json.py` | Shared strict decoder and bounded parser errors. |
| `triage_core/eval_fixture_validator.py` | Strict fixture decoding and line diagnostics. |
| `triage_core/evaluation_handoff_bundle.py` | Use one fixture byte sequence through publication. |
| `triage_core/evaluation_handoff_validator.py` | Verify and decode the captured bundle bytes. |
| `tests/test_eval_fixture_validator.py` | Fixture JSON depth and diagnostic checks. |
| `tests/test_eval_fixture_cli.py` | Bounded fixture CLI diagnostics. |
| `tests/test_evaluation_handoff_bundle.py` | Refusal, byte and hash preservation, and fixture read count. |
| `tests/test_evaluation_handoff_bundle_cli.py` | Builder CLI refusal before publication. |
| `tests/test_evaluation_handoff_validator.py` | Read-only refusal with matching hashes and fixture read count. |
| `tests/test_evaluation_handoff_validator_cli.py` | Bounded verifier CLI reasons and bundle preservation. |
| `docs/change/requests/CR-145-evaluation-bundle-strict-json.md` | Record authority and verification. |

Implementation acceptance, merge, release and closeout require separate
human decisions. Other JSON consumers, broader filesystem protections,
scoring and schema changes require separate review.

## Verification

New checks use harmless synthetic fields and values. They cover the
fixture and actual-outcome paths, the existing manifest rules, bounded
CLI reporting, refusal with matching recorded hashes and one binary
read per fixture. Existing deterministic export checks also verify
fixture CRLF preservation and exact fixture and actual-outcome hashes.

On Windows with CPython 3.12.16 and pytest 9.2.0, the six focused
evaluation suites passed 97 tests. One existing symlink test skipped
because this host cannot create symlinks. The full local and hosted
regressions are required for the candidate. Reassess the Daybreak finding
on the merged revision after implementation acceptance and merge.
