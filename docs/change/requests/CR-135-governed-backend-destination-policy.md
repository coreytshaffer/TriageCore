# CR-135: Governed Backend Destination Policy and Transport Binding

## Status

- **Status:** Proposed. Proposal-only documentation.
- **Type:** Governance kernel: privacy and provenance, capability and effect bounds.
  The invariant this CR strengthens: *a governed `tc run` attempt sends requests only to
  network endpoint identities that are bound to its governed decision and authorized by
  trusted destination policy. A route's name is never treated as evidence of where its
  traffic goes.*
- **Evidence baseline:** `main` at `1dc9b88631748a4c71ebdf331c0536f33a714256`. Every
  repository fact below was observed at that commit. Re-verify when the pin changes.
- **Proposal drafting authority:** Granted by the human operator on 2026-10-18 for this
  single document. Recorded verbatim under Authority Record.
- **Owner decisions:** Five recorded (D1–D5), plus two further approvals. See Owner
  Decisions.
- **Proposal acceptance / design acceptance:** Not granted.
- **Implementation authority:** Not granted.
- **Implementation acceptance / merge / release / closeout:** Not granted.

### Lifecycle state

| Stage | State |
|---|---|
| identifier allocation | CR-135, allocated by the operator after confirming that `main` at `1dc9b88` has no CR-135 (highest numeric CR there: CR-134) |
| proposal drafting | granted, single document |
| owner decisions | D1–D5 approved with binding qualifications; HTTPS-only remote transport and separate destination kinds approved |
| proposal acceptance | not granted |
| design acceptance | not granted; requires a reviewable contract, seams, and F1–F14 specification (see Acceptance Criteria) |
| implementation authority | not granted |
| implementation acceptance | not granted |
| merge authority | not granted |
| release authority | not granted |
| closeout | not granted |

## Scope

Exactly one file: this document.

No code, test, schema, configuration, CLI, credential, evidence-ledger, backlog,
change-log, architecture, or README change is made or authorized. This grant does not
authorize branch publication, push, pull request, merge, release, or deployment.

## Human Approval Requirement

Each later stage needs its own explicit human decision: proposal acceptance, design
acceptance, implementation authority (which must name a bounded file allowlist),
implementation acceptance, merge, release, and closeout. None of these is implied by
this document, by a passing test, or by a reviewer's verdict. Under change management, a
grant that names no bounded allowlist is incomplete. CR-DD-012B preserves the defect that
results when such an allowlist is inferred instead of granted.

## Implementation Authority

**Not granted.** The Proposed Implementation Slices section is a proposal for review, not
an allowlist anyone may act on.

## Authority Record

Context: the operator ran an M04 design review, a remediation work-package label from the
NIST/ISO assessment and not a CR identifier, over a read-only planning return. The
operator independently checked `main@1dc9b88`, including CR-134 and the governed-run
implementation, and recorded this disposition on 2026-10-18 (2026-10-17 PDT).

The owner-decision table, recorded verbatim:

> | Decision                       | Disposition | Binding qualification |
> | ------------------------------ | ----------- | --------------------- |
> | D1 — Reject localhost          | Approved    | Literal 127.0.0.1 and [::1] only; migrate defaults and provide an explicit compatibility refusal. |
> | D2 — Require loopback          | Approved    | Applies to every network-capable local_* route in governed tc run. Legacy/direct paths remain explicitly outside the first assurance claim. |
> | D3 — Defer trusted LAN         | Approved    | LAN requires a separately authorized expansion of trusted destinations, not merely a new configuration entry. |
> | D4 — Fail whole attempt        | Approved    | Configuration-integrity violation, exit 2, zero network requests. Never silently fall back to cloud. |
> | D5 — Bind configuration digest | Approved    | Bump CONFIGURATION_VERSION; bind canonical, route-indexed endpoint identities and transport policy, with independently testable revalidation. |
>
> I also approve HTTPS-only remote cloud transport and the separation of endpoint,
> recipient and staging destination policy kinds.

The allocation and drafting grant, recorded verbatim:

> Allocate `CR-135`: Governed Backend Destination Policy and Transport Binding.
>
> Recommended path:
>
> `docs/change/requests/CR-135-governed-backend-destination-policy.md`
>
> The authorization is limited to creating that single proposal document, recording the
> five decisions above, the required refinements, design assumptions, acceptance fixtures
> and explicit non-claims.
>
> No code, test, schema, configuration, CLI, credential or evidence-ledger changes are
> authorized. No branch publication, push, PR, merge, release or deployment is authorized
> by this decision. Design acceptance and implementation authority remain separate future
> gates.
>
> The new CR should preserve CR-134's accepted recipient/export contract rather than
> reopening it. M03 and M09a remain on their existing branch and are not pulled into this
> scope.

> Disposition: CR-135 proposal drafting authorized; implementation not authorized.

The operator also required five design refinements (A–E). They are recorded under
Required Refinements and carried into the design below. The operator stated the reasoning
for refinement A, recorded verbatim:

> Cloud intent permits consideration of an already-authorized cloud destination; it does
> not authorize an arbitrary URL.

## Owner Decisions

| # | Decision | Effect in this design |
|---|---|---|
| D1 | Reject `localhost` | The device-local profile accepts only the literal addresses `127.0.0.1` and `[::1]`. Defaults move to those literals. Any hostname, `localhost` included, gets the named compatibility refusal `hostname_not_literal_loopback`, with a fix hint. |
| D2 | Require loopback | Every network-capable `local_*` route in governed `tc run` (`local_fast`, `local_heavy`) must bind to a `device_loopback` endpoint, whatever the privacy class. `human_handoff` and `deterministic` contact no network and are unaffected. Legacy and direct paths stay outside the first assurance claim (see Paths Outside the First Assurance Claim). |
| D3 | Defer trusted LAN | There is no LAN profile in v1. A LAN destination would widen the built-in profile. It needs its own authorized expansion and cannot be added as a configuration entry. |
| D4 | Fail the whole attempt | Any destination-policy or configuration-integrity violation ends the attempt with exit 2, before any network request. It is never treated as an unavailable route and never falls back to another envelope member, cloud included. |
| D5 | Bind into the configuration digest | `CONFIGURATION_VERSION` is bumped. The decision's configuration digest binds canonical, route-indexed endpoint identities and the transport policy. Revalidation is a separate step that can be tested on its own. |
| — | HTTPS-only remote transport | Every `remote_cloud` identity requires `https` with TLS verification. |
| — | Separate destination kinds | `backend_endpoint`, `external_recipient` (CR-134), and `local_staging` (CR-134) are distinct kinds. They share policy versioning and provenance; claims are specific to each kind. |

## Problem Statement

A governed route can be labelled local without its actual network destination being
bound to the decision. The operator independently confirmed this finding. It is a
static design gap. It is not evidence that protected content was transmitted anywhere,
and this CR claims no such incident.

### Established facts (at `1dc9b88`)

1. **No endpoint in any binding.** `run_plan.configuration_digest`
   (`run_plan.py:185-203`) digests the cloud enabled/model settings, the local backend
   *type*, and policy versions. It includes no endpoint URL. The decision seam
   (`tc_cli.py:1143`, which reads config at `run_plan.py:369,373`) never reads the local
   base URL.
2. **The URL is read after the decision, by a separate read.** The client is built at
   `tc_cli.py:1284-1291` from a second read of `default_config`. Effective precedence
   for the local URL: `TRIAGE_BASE_URL` env > `triagecore.toml [backend].base_url` >
   backend-specific env (`TRIAGE_OLLAMA_BASE_URL`, `TRIAGE_SUPERVISOR_BASE_URL`) >
   hard-coded `http://localhost:<port>` preset (`config.py:24-33,51-81`;
   `backends.py:393-461`). `Config.get_*` reads the environment live on every call.
3. **Locality is a label.** The local-only guard (`client.py:283`) checks the route name.
   `_member_binding` (`runtime_observation.py:175-210`) receives `local_backend_type` as
   a name only.
4. **The revalidation checks no endpoint.** `_verify_governed_inputs`
   (`client.py:533-656`, digest recheck at `:614-624`) recomputes the same
   endpoint-free digest from a third config read.
5. **The cloud backend is built late.** It is constructed only inside
   `_execute_cloud_task` (`client.py:739-744`), from a live read of
   `get_qwen_base_url()`: `TRIAGE_QWEN_BASE_URL` env > TOML >
   `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`. Any URL is accepted.
6. **Requests go straight to the network.** Backends call module-level `requests.get`
   and `requests.post` directly (`backends.py:76,114,147,193,229,266,305,336,367`). The
   first contact on the local governed path is `resolve_model`'s GET (`/models` or
   `/api/tags`) when the model is an auto sentinel (`backends.py:10`), followed by the
   generation POST, streaming or not. `base_url` and `model` are mutable dataclass
   fields; `model` is mutated at `client.py:490` and restored afterwards.
7. **A second endpoint hides in `ping`.** `OllamaBackend.ping` contacts
   `TRIAGE_SUPERVISOR_BASE_URL` (LM Studio) before its own URL (`backends.py:359-367`,
   `:69-80`). `ping` is not invoked on the governed `run_task` path.
8. **Bad config fails open.** A TOML parse failure prints a warning and returns `{}`
   (`config.py:13-21`), so execution silently uses defaults. The config root is the
   current directory. Separately, importing `sustainability.py` calls `load_dotenv()`,
   which loads a `.env` file into the process environment. That import was not observed
   among the direct imports of the governed path.
9. **Capability evidence names no endpoint.** CR-DD-013 probe records carry a redacted
   `base_url` (`local_backend_probe.py:89`), but `capability_evidence` never compares it
   with the executing endpoint (`capability_evidence.py:361-405`).
10. **`requests` defaults are unconstrained.** With default `trust_env`, the installed
    `requests` (2.34.2 observed; requirement `>=2.28.0`) can honour proxy environment
    variables, `.netrc`, and CA-bundle variables, and follows redirects for POST. A 307
    or 308 re-sends the body to the new location. These are library defaults and must be
    confirmed by fixture (see Acceptance Criteria), not assumed.
11. **Nothing persists the configuration version.** At `1dc9b88`,
    `configuration_version` and `configuration_sha256` appear in `governed_decision.py`,
    `run_plan.py` and `client.py`, and in three test files. No artifact module or schema
    in `triage_core/` or `schemas/` references them.

## Objective

Make governed `tc run` bind the actual network endpoint identities of every
network-capable member of the decision's envelope, together with the transport policy,
into the decision. Then enforce, at the real network sink, that the attempt sends
requests only to those identities, with a refusal before any request whenever policy or
binding fails.

## Required Refinements (owner, 2026-10-18)

- **A. Constrain cloud endpoints.** An allowlist *restricts* the authority a configurable
  remote URL currently provides. The first governed profile binds the approved Qwen
  provider origin and API path. Any other remote destination needs explicit operator
  policy; `--allow-cloud` does not supply it.
- **B. Guard the actual network sink.** All governed model-discovery and generation
  calls, including streaming and any applicable `ping`, pass through an injected guarded
  transport. Allowed HTTP methods and paths are bound per backend protocol. Governed
  tests must exercise that transport; a module-level `requests` mock is not evidence for
  the governed path.
- **C. Freeze effective configuration once.** Governed execution refuses malformed
  configuration instead of falling back to defaults. One immutable effective-config
  snapshot is built at S1, with the winning source of each value identified. S2
  validates the actual backend instances, including the cloud backend, before its first
  request and without a second policy decision.
- **D. Trusted LAN is an authority expansion.** Keep it out of v1. A future LAN profile
  needs explicit owner approval, a separately versioned policy, and a local-network
  threat model.
- **E. Narrow the assurance claim.** See Non-Claims.

## Design

### Destination kinds

One policy family, `triagecore.destination_policy`, with closed, separately versioned
kinds:

| Kind | Owner | Defined by | Claim it supports |
|---|---|---|---|
| `backend_endpoint` | This CR | Built-in profiles below | The governed transport attempted requests only to bound endpoint identities |
| `external_recipient` | CR-134, unchanged | CR-134 policy: provider/surface allowlist, data-class ceiling, TTLs, size cap, operation vocabulary | Eligibility bound to an *intended* recipient. Not proof of where the operator pasted anything. |
| `local_staging` | CR-134, unchanged | CR-134 Staging and Destination Security | Bytes staged locally. Not delivery, not egress. |

Rules that hold across kinds:
- No URL locality check is ever applied to a chat recipient.
- An approved recipient is never authority for a backend URL.
- An endpoint allowlist never satisfies a recipient binding.

### Built-in endpoint profiles (v1)

Profiles are in-code constants, each with a version and a digest of its canonical
serialization. **No operator file can add an endpoint in v1.** A request (CLI flag or
proposal) may tighten a profile and can never enlarge one.

| Profile | Locality class | Identity | Allowed for |
|---|---|---|---|
| `device_local_loopback.v1` | `device_loopback` | Scheme `http` or `https`; host exactly `127.0.0.1` or `::1` (written `[::1]`); explicit or scheme-default port; normalized base path | `local_fast`, `local_heavy` |
| `qwen_dashscope_intl.v1` | `remote_cloud` | `https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1` exactly | `cloud_primary`, `cloud_secondary`, only when the decision's envelope already contains that route and cloud execution is enabled |

`trusted_lan` is a reserved, unsupported class in v1. A LAN address gets
`trusted_lan_not_in_profile`.

A configured cloud URL that does not equal the approved identity gets
`cloud_endpoint_not_approved`. This check runs only when the envelope contains a cloud
route. Otherwise the cloud URL is recorded as `not_bound` and has no effect.

### Endpoint normalization (closed)

| Input | Outcome |
|---|---|
| Missing scheme or host; unparsable URL | `endpoint_malformed` |
| Scheme other than `http`/`https`; `http` on a `remote_cloud` identity | `endpoint_scheme_not_permitted` |
| Userinfo (`user:pass@`) | `endpoint_credentials_embedded` |
| Query string or fragment | `endpoint_query_or_fragment` |
| Any hostname on a local route, including `localhost` (D1) | `hostname_not_literal_loopback` |
| Non-canonical IPv4 (`127.1`, `0x7f.0.0.1`, `2130706433`, `0177.0.0.1`), `0.0.0.0`, other `127.0.0.0/8` addresses, IPv4-mapped IPv6 (`::ffff:127.0.0.1`), zone IDs, percent-encoded or IDNA hosts, trailing dots | `endpoint_deceptive_identity` |
| A host that strict parsing of the literal string accepts as a non-loopback address | `endpoint_not_device_local` (or `trusted_lan_not_in_profile` for private ranges) |
| Remote host not exactly equal to an approved remote identity (lowercase ASCII, no trailing dot) | `cloud_endpoint_not_approved` |

The host is parsed from the literal string with strict address parsing, so the OS's
lenient IPv4 parsing never gets a say. The device-local profile involves no DNS lookup.
For `remote_cloud`, the identity is the origin name plus TLS certificate verification
against that name, using the library's bundled trust store, since environment CA
variables are ignored (see transport). DNS resolution of the remote name is not pinned.

The canonical identity is `scheme://host:port/base-path`. The base path has no trailing
slash, and the port is always explicit.

### Effective configuration snapshot (refinement C)

At S1, governed `tc run` builds one immutable `EffectiveBackendConfiguration`:

- **Values recorded:** local backend type, model, local URL, timeout, cloud enabled,
  cloud model, cloud URL, and whether a cloud API key is *present*. The key's value and
  any digest of it are never recorded.
- **Sources recorded:** the winning source of each value, by name only:
  `env:<NAME>`, `toml:triagecore.toml`, `backend_env:<NAME>`, `preset`, or `absent`.
- **Environment:** read once, at S1. Values that a `.env` file loaded into the
  environment earlier are indistinguishable from other environment values, and are
  recorded as `env:<NAME>`.

Failure handling:
- A configuration file that exists but cannot be parsed, or cannot be read, or that
  needs a TOML parser the runtime lacks, gives `configuration_unreadable`, exit 2. It
  never falls back to defaults.
- An absent file is not an error; its values come from `preset` and are recorded that
  way.

Every later step reads from this snapshot. The client, the local backend, and the cloud
backend are all built from it, never from a fresh `default_config` read.

### Binding (S1) and the configuration digest (D5)

For each network-capable member of the envelope (`preferred_logical_route` followed by
`permitted_fallback_envelope`, in order), S1:

1. normalizes and classifies that member's endpoint against its profile;
2. on any failure, ends the attempt with exit 2 and the reason code (D4); and
3. on success, records a route-indexed entry:
   `route=<name>, profile=<id>@<version>, class=<locality>, protocol=<backend protocol>,
   identity_sha256=<digest of canonical identity>`.

`configuration_digest` gains:
- one line per route-indexed entry, in envelope order;
- a `transport_policy_sha256` line; and
- a `destination_profiles_sha256` line.

`CONFIGURATION_VERSION` moves from `governed_decision_configuration.v1` to
`governed_decision_configuration.v2`. Decision identifiers and the plan digests derived
from them change value once. Because nothing persists the configuration version (fact
11), no stored artifact needs migration.

Evidence records carry a **safe label**, such as `loopback-ipv4:11434`, `loopback-ipv6:1234`
or `qwen_dashscope_intl`, plus the identity digest. They never carry a raw URL, a
credential, or a key digest.

### Backend construction and S2 revalidation

Both the local backend and, when the envelope contains a cloud route and cloud execution
is enabled, the cloud backend are **built once from the snapshot, before any request**.
`_execute_cloud_task` uses that pre-built instance and no longer calls `create_backend`
from live configuration. Building it earlier is a projection of the snapshot, not a
second policy decision: it adds no route and evaluates no policy.

S2 runs inside `_verify_governed_inputs`, before any backend call. It is a separately
testable function, `verify_destination_binding(decision, backends)`, that:

1. recomputes each bound route's canonical identity from the **actual backend
   instance's** fields (`base_url`, protocol, transport settings);
2. checks that each instance carries the guarded transport and that its bound identity
   matches; and
3. on any mismatch, raises `GovernedBindingError` with `destination_binding_mismatch`,
   `transport_not_guarded`, or `transport_settings_changed`. Exit 2, zero requests.

### Guarded transport (S3, refinement B)

Every governed backend instance receives an injected transport. Its HTTP calls go only
through that transport; no governed request may reach module-level `requests`. The
transport is a session with:

- environment trust disabled: no environment proxies, no `.netrc`, no CA-bundle
  variables;
- an explicitly empty proxy map;
- redirects disabled on every call; and
- a per-call check of scheme, host, port, method and path against the bound identity and
  the protocol table below.

| Backend protocol | Allowed calls, relative to the bound base path |
|---|---|
| OpenAI-compatible, local (`lmstudio`, `vllm`, `llama.cpp`, `custom`) | `GET models` (model discovery or `ping`); `POST chat/completions` (streaming or not) |
| Ollama, local | `GET api/tags` (model discovery or `ping`); `POST api/chat` (streaming or not) |
| Qwen, `remote_cloud` | `POST chat/completions` only. `create_backend` replaces an auto-sentinel cloud model with `TRIAGE_QWEN_MODEL` or `qwen-max` (`backends.py:413`), so discovery is unnecessary by default. Discovery is refused. **Proposed (not owner-approved; subject to design acceptance):** a cloud model that still resolves to an auto sentinel when a cloud binding is required is refused at S1 with `cloud_model_unbound`. This is a missing-model-identity failure, distinct from endpoint-policy violations. It refuses before any network contact, and no fallback may mask it. |

Refusals:
- A call outside the table → `transport_request_not_permitted`. No request is sent.
- Any 3xx response (301, 302, 303, 307, 308) → `endpoint_redirect_refused`. The redirect
  is not followed and no second request is made.
- `OllamaBackend.ping`'s LM Studio side-contact is a different identity and is refused
  if any governed path ever invokes `ping`.

The transport also counts and records every call, so tests can assert exact counts.

Compatibility, narrowed per refinement B:
- Legacy and direct callers keep the module-level default transport, so existing tests
  that patch `triage_core.backends.requests.*` stay valid **for legacy paths only**.
- Those tests are not evidence for the governed path. Governed tests must go through the
  guarded transport and assert that module-level `requests` is never called.

### Ordering

```text
S1 (tc_run seam): effective-config snapshot -> endpoint binding -> decision (digest v2)
     | refusal: exit 2, zero requests
build client + backends from the snapshot (no network)
S2 (_verify_governed_inputs): instance identity == bound identity; transport guarded
     | refusal: exit 2, zero requests
route binding (unchanged envelope filter; capability is availability only)
S3 (every request): guarded transport enforces identity, method, path, no redirect
```

Route binding (`runtime_observation`) is unchanged. The endpoint check never adds,
removes, or reorders an envelope member.

## Relationship to Existing Contracts

| Contract | Treatment |
|---|---|
| CR-134 `public_export_v0` | **Preserved as accepted.** Its recipient and staging rules, Parent Normalization, approval-gate interpretation, and non-claims are not reopened. CR-135 defines only the `backend_endpoint` kind. When CR-134 is implemented, its policy file carries CR-134's sections, and its whole-file digest binds as CR-134 specifies. |
| CR-DD-012B snapshot/decision pattern | **Extended.** Configuration digest v2. Seam, projection, and envelope-filter semantics unchanged. |
| CR-DD-013 capability evidence | **Unchanged.** Availability evidence only. A probe of one endpoint never authorizes another. |
| CR-114/118/119 local probe | Outside the governed path. `redact_base_url` is prior art for normalization; its rules are looser than this CR's local profile. |
| CR-095 parent manifests | Not consulted for endpoints. A parent field claiming an endpoint dimension is `unsupported_constraint` under CR-134's closure. |

## Paths Outside the First Assurance Claim

These paths keep their current behaviour, and the assurance claim says nothing about
them:

- non-governed `TriageClient.run_task`, including `TaskClassifier.classify`, which sends
  the prompt to an Ollama backend at a configured URL (`classifier.py:12-20`);
- `triagecore` CLI (`cli.py:496,947,1074`);
- `worker_registry.py:16-27`;
- TriageDesk (`ui/app.py:3494-3528`);
- `tc probe`, `tc status`, `tc doctor`;
- `apply_triagecore_local_backend_repair.py`; and
- library callers that inject their own backend.

## Acceptance Criteria

### Acceptance standards by stage (owner, 2026-10-18)

| Stage | Required evidence |
|---|---|
| Proposal acceptance | Problem statement, scope and boundaries are sound |
| Design acceptance | Contract, enforcement seams, F1–F14 fixture specifications and expected outcomes are reviewable |
| Implementation authorization | Explicit bounded file allowlist and permitted actions |
| Implementation acceptance | Executed F1–F14 results, regression tests, and evidence demonstrating enforced transport behavior |

F1–F14 do not need to pass before design acceptance. Until implementation is
independently authorized, they are planned verification, not evidence. If an
architectural assumption cannot be evaluated without experimentation, a synthetic,
offline feasibility test may be proposed. It needs its own grant and authorizes no
runtime change.

For design acceptance, the fixture **specification** must cover each of the following:

1. zero-call refusals;
2. mutable endpoint substitution after decision formation;
3. redirect handling, including 307 and 308;
4. proxy and `.netrc` isolation;
5. every actual governed request path;
6. cloud-host substitution;
7. TOML parse failure; and
8. the changed decision/configuration digest.

A successful configuration check is not evidence of controlled egress unless every
relevant request goes through the enforced transport.

### Fixture specification: planned tests, not evidence; nothing is created or executed by this CR

**Common setup.**
- Synthetic protected marker bytes, `M04-PROTECTED-<uuid>`.
- A recording fake transport, injected as the guarded transport's underlying sender, that
  logs `(method, url, body)`.
- A tripwire on module-level `requests.get`, `requests.post` and `requests.Session.request`
  that fails the test if called on a governed path.

**Assertions.**
- **Refusals:** zero sends and zero tripwire hits.
- **Permitted runs:** the exact call list, with markers seen only at bound identities.

| # | Scenario | Expected | Refused at | Sends |
|---|---|---|---|---|
| F1 | `http://127.0.0.1:11434` (Ollama) and `http://[::1]:1234/v1` (OpenAI-compatible), benign local-only task, auto model | Success; calls are discovery GET then generation POST, both to the bound identity; tripwire unhit | — | 2 |
| F2 | `TRIAGE_BASE_URL=http://203.0.113.5:11434` with type `ollama` | Exit 2, `endpoint_not_device_local` | S1 | 0 |
| F3 | `localhost`, an `.attacker.example` suffix, `127.1`, `0x7f.0.0.1`, `2130706433`, `0177.0.0.1`, `0.0.0.0`, `::ffff:127.0.0.1`, `fe80::1%eth0`, IDNA host, trailing dot, userinfo, query, fragment, `ftp:`/`file:` | One named code per case (Endpoint normalization table) | S1 | 0 |
| F4 | `192.168.1.10`, `10.0.0.2`, `fe80::1` on a local route | `trusted_lan_not_in_profile` | S1 | 0 |
| F5 | Public task, `--allow-cloud`, cloud enabled, approved Qwen identity | `remote_cloud` binding; one POST to the approved origin; never labelled device-local | — | 1 |
| F6 | **Cloud-host substitution:** `TRIAGE_QWEN_BASE_URL` set to another `https` host, to an `http` URL, or to the approved host with a different path or port | `cloud_endpoint_not_approved` / `endpoint_scheme_not_permitted`; the local route does **not** proceed (D4) | S1 | 0 |
| F7 | **Mutation after decision:** (a) env changed between S1 and construction; (b) `backend.base_url` mutated after S2; (c) engine backend swapped; (d) cloud instance replaced; (e) transport setting changed; (f) profile digest changed | (a, d, f) `destination_binding_mismatch` at S2; (b, c) `transport_request_not_permitted` or `destination_binding_mismatch` at S2/S3; (e) `transport_settings_changed` | S2 / S3 | 0 |
| F8 | **Redirects:** the bound endpoint answers 301, 302, 303, 307 and 308 to a remote URL, on both GET and POST | `endpoint_redirect_refused`; no request to the redirect target; body never re-sent | S3 | 1 (bound endpoint only) |
| F9 | **Proxy and `.netrc` isolation:** `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` set with no `NO_PROXY`; a `.netrc` with an entry for the host; `REQUESTS_CA_BUNDLE` set | Request goes direct to the bound identity; no proxy contact; no `Authorization` from `.netrc`; CA variable ignored | — | 1 per call, bound only |
| F10 | **Every governed request path:** discovery GET for both protocols; streaming and non-streaming POST for both protocols; cloud POST; `ping` reached through a governed instance, including the Ollama LM Studio side-contact | Each goes through the guarded transport; the side-contact gives `transport_request_not_permitted`; tripwire never hit | S3 | per path |
| F11 | **TOML failure:** unparsable `triagecore.toml`; unreadable file; parser unavailable | `configuration_unreadable`, exit 2; legacy behaviour unchanged for non-governed commands | S1 | 0 |
| F12 | **Digest change:** same inputs with a different loopback port, a different envelope order, or a different transport policy | Different `configuration_sha256` and `decision_id`; `CONFIGURATION_VERSION` is `…v2`; a v1-digest decision is rejected at S2 | S2 | 0 |
| F13 | Capability probe record for `127.0.0.1:1234` while executing against `127.0.0.1:11434` | Binding uses the configured identity; capability changes availability only; no destination authority derived from the probe | — | per F1 |
| F14 | **Usefulness controls:** existing suite; default `triagecore.toml` migrated to `127.0.0.1` | Unchanged pass; benign tasks complete | — | — |

**Retained results (future run):**
- machine-readable test output;
- fixture-corpus digest and destination-profile digests;
- commit;
- Python, `requests` and OS versions;
- an explicit coverage boundary: unit and fake-transport level.

These fixtures do not earn a G1 pass (see Non-Claims).

## Non-Claims

This CR, and any implementation of it, does not claim that:

- a loopback listener is a trustworthy process, or that it cannot forward or proxy
  requests elsewhere. A service on `127.0.0.1` may be an SSH tunnel, a proxy, or a
  runtime that uses remote models;
- the device made no other network connections, through other processes, other
  TriageCore paths, or the OS;
- DNS answers for the remote origin were authentic beyond what TLS verification
  establishes;
- protected content was ever transmitted anywhere. The motivating finding is a static
  design gap;
- capability or probe evidence is destination authorization;
- legacy or direct paths (Paths Outside the First Assurance Claim) are covered;
- an intended external recipient received anything, or that staging is delivery (CR-134
  non-claims stand); or
- assessment scores or gate G1 are changed. Local-only remains a routing policy under
  trusted configuration until endpoint enforcement is verified by integration evidence.

The supported claim, once implemented and accepted: *for a governed `tc run` attempt, the
guarded transport attempted requests only to the network endpoint identities bound to
that attempt's governed decision, using the bound methods, paths and transport settings;
every refusal case sent zero requests.*

A stronger no-egress claim needs separate evidence: an integration run against a real
loopback service under an OS-level control, such as a network namespace containing only
loopback or a per-process outbound-deny rule, with a capture showing the markers never
left loopback, plus evidence of the local service's own forwarding configuration.

## Design Assumptions

- The operator's environment variables and `triagecore.toml` are trusted inputs. Anyone
  who can write to them can choose a destination *within* the profiles, never outside
  them.
- The installed `requests` honours session-level `trust_env=False`, explicit empty
  proxies, and per-call `allow_redirects=False`. F8 and F9 must confirm this.
- The governed path does not import a module that calls `load_dotenv()` *after* S1.
  Fixture F7(a) covers changes that happen after S1, whatever their source.
- Windows proxy-bypass behaviour (registry and system settings) is not separately
  examined. F9 must also run in the `windows_executor` job.

## Proposed Implementation Slices (not authorized)

For review only. Each slice needs its own grant naming its exact file allowlist.

1. **Contract module** (about 2–3 hours).
   - Files: new `triage_core/destination_policy.py` (profiles, normalization, effective-config
     snapshot type, binding digest, guarded transport, reason codes) and new
     `tests/test_destination_policy.py` (F3, F4, F12 at unit level, plus normalization
     positive controls).
   - Not wired into runtime.
   - Stop point: module and unit tests pass, the full suite is unchanged.
2. **Governed integration** (about 3–4 hours).
   - Files: `triage_core/backends.py` (injected transport for all nine call sites;
     literal-loopback presets), `triage_core/config.py` (a strict snapshot reader for
     governed use; legacy reader unchanged), `triage_core/run_plan.py` (S1, digest v2),
     `triage_core/governed_decision.py` (`CONFIGURATION_VERSION`),
     `triage_core/client.py` (S2, pre-built cloud instance, guarded transports),
     `triage_core/tc_cli.py` (exit-2 mapping, snapshot hand-off), `triagecore.toml`
     (literal default; a configuration change the grant must name), new
     `tests/test_endpoint_transport_guard.py` (F7–F10), and updates to
     `tests/test_governed_consumption_parity.py` (F1, F2, F5, F6, F11, F13) and
     `tests/test_backends.py` (preset assertions).
   - Stop point: governed `tc run` enforces S1–S3, with legacy paths untouched and
     documented.
3. **CR-134 consumer.** Separate, under a CR-134 implementation grant.

## Deferred Work and Open Questions

- **Trusted LAN profile.** A future authority expansion (D3, refinement D) needing owner
  approval, a separately versioned policy, and a local-network threat model.
- **Additional remote origins.** Need explicit operator policy (refinement A). The trust
  location of an operator policy file, outside any working tree and not agent-writable,
  is to be settled with CR-134's policy file.
- **`cloud_model_unbound` (proposed).** Consistent with D4's fail-closed policy, but not
  independently approved as new runtime behavior. It stays a proposed reason code until
  design acceptance. Proposed semantics: a missing cloud model identity is distinct from
  an endpoint-policy violation; it refuses before network contact whenever a cloud
  binding is required; and no fallback may conceal it.
- **Legacy paths.** Bringing any of them under the guard is separate work.
- **Integration evidence for G1.** See Non-Claims.

## Explicit Exclusions

- Any code, test, fixture file, schema, configuration, CLI, credential, or ledger change.
- Any network or provider call, or any probe.
- Any change to CR-134's accepted contract.
- Branch publication, push, pull request, merge, release, deployment, and closeout.
- M03 and M09a records.
- Backlog, change-log, architecture, and README updates.

## Stop Point

This document is the stop point. It records CR-135's allocation, five owner decisions,
the required refinements, the design, the acceptance fixtures, and the non-claims. It
grants no acceptance and no implementation, publication, merge, release, or closeout
authority.
