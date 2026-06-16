# Security Policy

TriageCore is an alpha research harness for local-first agent orchestration.

Do not commit API keys, private keys, `.env` files, ledgers, handoffs, or
generated agent outputs.

Report security concerns by opening a private advisory or contacting the
maintainer directly.

## Known Alpha Limitations

- Runtime model-integrity enforcement is policy/schema-stage, not fully
  enforced.
- Cloud routing requires explicit external-safe packets and environment-provided
  credentials.
- The operator is responsible for local environment and secret hygiene.
