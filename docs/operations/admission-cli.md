# Admission CLI

The admission CLI validates external runtime admission evidence fixtures without executing runtimes, writing to the ledger, or changing approval state.

## Commands

### `validate`

Validates a JSON fixture against the Admission Evidence structured validation rules.

```bash
tc admission validate --from-json <path/to/fixture.json>
```

**Options**:
- `--from-json <path>`: (Required) Path to the JSON fixture to validate. Must be a valid JSON map conforming to the `ExternalRuntimeAdmissionEvidence` fields.

**Behavior**:
- Parses the JSON.
- Passes it to `admission_evidence_from_mapping` to check required boolean and string types.
- Will **reject** any file named `.triagecore/ledger.jsonl` to prevent accidental state-file mixing.
- Exits `0` if valid, and prints `Validation successful.`
- Exits `1` on parsing or validation failure.
