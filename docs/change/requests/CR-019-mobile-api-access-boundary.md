# CR-019: Mobile API Access Boundary

## Status

Implemented

## Goal

Make the mobile review surface local-only and authenticated by default without
turning it into a general remote-control API.

## Scope

- Default the mobile server to `127.0.0.1`.
- Require bearer authentication for every `/api/*` route.
- Reject non-loopback binding unless network access is explicitly enabled.
- Return a safe task projection without prompt-derived titles, descriptions,
  filesystem paths, or artifact paths.
- Disable mobile log access.
- Validate review decisions and workload values, and record a configured actor
  identifier.
- Keep the browser token in memory only and send it in the authorization header.
- Render ledger values as text rather than executable markup.

## Configuration

- `TRIAGECORE_MOBILE_TOKEN`: required bearer token.
- `TRIAGECORE_MOBILE_ACTOR`: optional review actor identifier.

Tokens must be generated and stored by the operator. They are not logged or
written to the ledger.

## Acceptance Criteria

- [x] Unauthenticated API requests return `401`.
- [x] Default startup listens only on loopback.
- [x] Non-loopback binding requires an explicit network decision and a token.
- [x] Task responses omit prompt-derived titles, raw descriptions, filesystem
  paths, and artifact paths.
- [x] Logs are unavailable.
- [x] Review decisions are restricted to accepted or rejected.
- [x] Review workload is restricted to the UI's fixed values.
- [x] Review events contain a configured actor identifier.
- [x] The browser token is held in memory, not local or session storage.
- [x] Ledger values are rendered with text nodes rather than HTML injection.
- [x] Targeted tests and the full suite pass.

## Validation

- `python -m pytest tests\test_mobile_web.py -q`
- `python -m pytest -q`
- `python -m py_compile triage_core\web\server.py`
- `node --check triage_core\web\static\app.js`
- Local HTTP smoke checks for unauthenticated and authenticated API responses

Browser visual verification was attempted but blocked by the Windows browser
runtime; HTTP smoke checks and JavaScript syntax validation passed.

## Remaining Limitations

TriageCore does not provide TLS termination, user accounts, token rotation, or
internet-safe hosting. Any non-loopback use still requires an operator-managed
private access method such as a VPN or private tunnel.
