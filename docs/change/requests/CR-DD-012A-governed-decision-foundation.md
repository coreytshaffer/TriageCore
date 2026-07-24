# CR-DD-012A: Governed Decision Foundation

## Status

Implementation complete on the branch within the bounded allowlist below.
Validation and supervisor review passed; merge is pending.

This remains an internal, non-integrated child of CR-DD-012. The approved
implementation may add only the two foundation modules, three focused test
files, and bounded documentation updates named below. It changes no existing
runtime, CLI, ledger, artifact, routing, cloud, or worker path. CR-DD-012B
remains blocked until this implementation lands and CR-DD-012B receives its
own separate approval.

## Decision

The bounded implementation approval authorizes internal immutable value types
and pure construction functions for:

1. one `GovernedRunInputSnapshot` that distinguishes source bytes, normalized
   component bytes, and the exact application-level bytes supplied as the
   worker user message;
2. one closed, canonical `GovernedDecision`;
3. deterministic profile resolution and snapshot construction;
4. pure governed-decision construction; and
5. canonical serialization, parsing, and domain-separated decision-ID
   verification.

CR-DD-012A establishes the foundation only. No existing public command may
call these functions. CR-DD-012B owns all preview and ordinary-execution
integration.

The authoritative governed execution binding is
`AssembledExecutionBytes`, not raw filesystem bytes and not the planning-only
`prompt + "\n" + data` representation.

## Problem

CR-DD-012 requires preview and ordinary execution eventually to consume one
immutable input snapshot and decision. The current code has several distinct
representations of task content:

- `tc run` reads source files as UTF-8 text with universal-newline handling;
- it adds path-bearing source headers and appends inline input;
- `TaskPacket` keeps the prompt and data as separate strings;
- context planning currently evaluates `prompt + "\n" + data`; and
- the execution engine constructs a worker user message as
  `prompt + "\n\nDATA:\n" + data`.

Treating raw file bytes, normalized file text, planning text, or HTTP request
bytes as interchangeable would silently change current execution semantics.
Likewise, leaving mutability, limits, canonicalization, or dependency
boundaries to coding time would make compatibility choices invisible.

The merged proposal closed those choices before the bounded implementation
authority was granted.

## Existing Run Contract To Preserve

The future internal foundation must model the current behavior exactly. It
must not clean up or reinterpret that behavior in CR-DD-012A.

### File input

For each `--files` value, in operator-supplied order:

- duplicates are preserved;
- the path string is used verbatim; it is not resolved, canonicalized, or
  normalized before appearing in task data;
- the file is opened in text mode with `encoding="utf-8"`,
  the default strict decode error policy, and `newline=None`;
- UTF-8 decode errors fail the attempt;
- Python universal-newline translation converts `\r\n` and `\r` to `\n`;
- a UTF-8 BOM is not stripped by the `utf-8` codec and remains U+FEFF;
- the normalized content is prefixed with exactly
  `"\n--- " + file_path + " ---\n"`; and
- no suffix or separator is added after the file content.

The ordered file components are concatenated without deduplication.

Because the verbatim path spelling appears in worker input, two spellings that
refer to the same file are execution-significant under the current contract.
CR-DD-012A must not normalize them into one value. Their assembled execution
bytes and decision binding differ.

### Inline input

`--data` is appended after all file components only when its string value is
truthy. No separator is inserted before it. Consequently:

- `None` and `""` have the same absent representation;
- absent inline input contributes zero bytes and no component to task data;
- non-empty inline input is appended verbatim;
- when the preceding file lacks a final newline, inline input begins
  immediately after the last file character; and
- CR-DD-012A must not add a newline, label, or separator.

With no file content and no non-empty inline input, task data is the empty
string.

### Prompt and worker user message

The positional prompt is required by the CLI as a string. `None` is invalid;
an explicitly supplied empty string remains an empty string.

The current engine supplies the backend with structured messages. The
application-level user-message content is exactly:

```text
prompt + "\n\nDATA:\n" + data
```

`AssembledExecutionBytes` is the strict UTF-8 encoding of that exact
user-message content. It does not mean:

- raw bytes from a file;
- `prompt + "\n" + data`, which is the current planning/scanning
  representation in some paths;
- the separate fixed system message;
- serialized JSON, HTTP framing, request-library output, provider
  tokenization, or other transport bytes.

The fixed system message remains a separate execution component. Its exact
version or digest is included in explicit decision-relevant configuration so
it cannot change silently, but its content is not copied into the
privacy-safe decision body.

CR-DD-012A does not change the current planning representation, engine
assembly, structured-message shape, system message, or backend serialization.
Any future integration that supplies bytes through a string API must strictly
decode the governed UTF-8 bytes without reconstruction and prove that the
resulting user-message content is identical.

## Exact Byte Taxonomy

The snapshot contract uses three deliberately distinct layers:

```text
SourceBytes
    The bytes captured once from an operator-provided source before text
    decoding. They are provenance input, not worker input.

NormalizedComponentBytes
    Strict UTF-8 bytes of component text after the current UTF-8 decode and
    universal-newline behavior, plus the current source-header and inline
    assembly rules where applicable.

AssembledExecutionBytes
    Strict UTF-8 bytes of the exact established worker user-message content:
    prompt + "\n\nDATA:\n" + assembled task data.
```

`AssembledExecutionBytes` is authoritative for governed binding, context sent
to the worker, and future preview/execution parity. Component and source
digests support provenance and mismatch diagnosis; they cannot replace the
assembled-execution digest.

Raw `SourceBytes` may be retained only when a provenance requirement and an
explicit source-byte bound require it. Otherwise they are hashed and discarded
after successful normalization. They always remain attempt-local. Retaining
them never changes which bytes are execution-authoritative.

## Scope

### Approved implementation authority

- frozen immutable snapshot and source-component value types;
- frozen immutable canonical-decision value types;
- deterministic snapshot construction from explicitly supplied inputs;
- deterministic context/model profile resolution;
- a pure decision builder;
- canonical decision serialization and strict parsing;
- domain-separated decision-ID construction and verification;
- focused unit tests and bounded property-style test matrices; and
- CR and bounded status-document updates expressly named in that later
  approval.

### This proposal and CR-DD-012A explicitly prohibit

- wiring into ordinary `tc run`;
- wiring into `tc run --plan` or plan publication;
- changing current file-reading, decoding, newline, source-order, path-header,
  inline-input, prompt, task-data, or worker-message assembly behavior;
- accepting a saved plan artifact or adding `--confirmed-plan`;
- worker, model, backend, network, socket, or subprocess invocation;
- backend construction, capability discovery, or health probing;
- ledger access, ledger writes, task evidence, or new event fields;
- artifact publication or any `governed_run_plan.v1` or later plan-schema
  change;
- runtime-observation or execution-record persistence;
- cloud authorization, egress-gate, or approval changes;
- route execution, physical backend binding, fallback selection, fallback
  enforcement, or route injection;
- resume, retry, acceptance, quality scoring, or evaluator behavior; and
- changelog changes.

## Immutable Snapshot Contract

### Value ownership

Snapshot values use:

- `bytes` for retained byte sequences;
- frozen value objects for every record;
- tuples for every ordered collection; and
- closed enums or validated immutable strings for bounded identifiers.

Constructors copy mutable input before validation and retain no caller-owned
`list`, `dict`, `set`, `bytearray`, `memoryview`, mutable buffer, iterator, or
path object by reference. A caller-supplied path-like value is converted once
to its exact execution-significant string; the original object is not retained.
Nested values are recursively immutable. Post-construction assignment,
in-place collection edits, or buffer mutation is impossible.

Ordered source components and ordered fallback entries remain tuples in their
semantic order. Repeated values remain repeated.

### Snapshot fields

The closed `governed_run_input_snapshot.v1` value contains:

- snapshot and assembly contract versions;
- strict UTF-8 instruction bytes;
- strict UTF-8 inline-input bytes plus an absent/present posture;
- an ordered tuple of source snapshots;
- exact assembled task-data bytes;
- exact `AssembledExecutionBytes`;
- component, task-data, and assembled-execution SHA-256 digests and byte
  lengths;
- normalized operator declarations;
- one resolved context/model profile;
- the fixed worker-system-message version or digest binding; and
- the explicit construction-limit binding used for this snapshot.

Each source snapshot contains:

- its zero-based semantic position;
- the exact path spelling needed by the existing source header;
- a locator digest, never a raw path in the decision;
- optional bounded `SourceBytes`;
- source-byte digest and length when raw bytes were supplied;
- normalized content digest and byte length;
- normalized header-plus-content digest and byte length; and
- the decode/newline contract version.

The snapshot may hold raw content because it is attempt-local. Its
privacy-safe binding does not.

### Construction and validation

Construction occurs once and validates in this order:

1. validate closed versions, declarations, ordered input types, and explicit
   finite construction limits;
2. convert mutable caller inputs to owned immutable values;
3. use checked cumulative-length arithmetic before allocating an assembled
   representation;
4. enforce caller-supplied finite source, component, task-data, and
   assembled-execution allocation limits before constructing or retaining each
   full-size representation;
5. decode source bytes with strict UTF-8 and the current universal-newline
   rules;
6. encode normalized component text with strict UTF-8;
7. assemble task-data bytes using the exact current headers, order, and inline
   behavior;
8. assemble the exact execution bytes using the current
   `"\n\nDATA:\n"` separator;
9. calculate component and aggregate digests and lengths; and
10. construct the frozen value only after every invariant passes.

Any decode error, arithmetic overflow, bound violation, type mismatch,
digest/length mismatch, version mismatch, or inconsistent assembly fails
closed. A failed constructor returns no partial snapshot.

### Size-limit decision

Ordinary `tc run` currently has no hard input-size cap. The token budget used
by planning is advisory and must not be misrepresented as an existing runtime
limit. CR-DD-012A therefore does not invent a CLI limit, does not turn an
over-budget planning posture into rejection, and does not increase any
existing allowance.

That legacy absence of a CLI cap is separate from internal construction
safety. The internal constructor requires an explicit immutable
`SnapshotConstructionLimits` value containing finite positive byte bounds for
every representation it may allocate or retain, including:

- instruction bytes;
- inline-input bytes;
- normalized bytes per source component;
- total normalized component bytes;
- assembled task-data bytes; and
- `AssembledExecutionBytes`.

Optional retention of `SourceBytes` requires an additional finite per-source
and aggregate provenance cap. Without those provenance caps, raw source bytes
must not be retained.

Every applicable bound is mandatory. There is no unbounded sentinel, omitted
posture, inferred infinity, or convenience default. Absence, non-positive
values, overflow, or internally inconsistent bounds fail closed before any
contract-required full-size allocation. A model profile's
`usable_input_tokens` remains a separate advisory decision input and is not
silently converted to a byte cap.

Construction uses checked arithmetic and incremental UTF-8
validation/normalization, hashing, and length calculation to prove each
resulting allocation fits before materializing it. Only one owned immutable
copy of each contract-required normalized component, one assembled task-data
value, and one final assembled-execution value are retained. Temporary mutable
assembly buffers are not retained, and the implementation must not create
additional full-size convenience copies.

CR-DD-012A is not publicly integrated, so it cannot change current CLI
acceptance or error behavior. CR-DD-012B must separately define and approve
how existing CLI inputs map to finite construction bounds while preserving
current behavior. CR-DD-012A does not pre-authorize that mapping.

## Normalized Operator Declarations And Profile Resolution

The snapshot normalizes only decision-relevant declarations:

- explicit task ID, or the fixed `implicit_unassigned` posture;
- declared privacy: `local_only`, `external_safe`, or `public`;
- declared cloud intent as a run-scoped input distinct from authorization;
- explicit model/profile spelling or the existing stable ordinary-run default;
- resolved canonical context/model profile ID;
- construction-limit posture; and
- supported normalization, assembly, policy, and configuration versions.

A generated execution correlation ID, timestamp, current working directory,
process identity, or runtime-health fact is excluded.

One deterministic resolver accepts a closed mapping as an explicit argument.
It does not read environment variables or `default_config`. It returns one
canonical supported profile or fails closed. It does not infer the profile
from a route, backend, model availability, or live state.

Equivalent explicit/default inputs normalize identically only when the closed
mapping says they identify the same canonical profile. Unknown, ambiguous, or
unsupported values fail closed.

## Canonical Governed Decision Contract

### Closed primitive structure

The `GovernedDecision` is generated from one closed tree containing only JSON
primitives: objects with string keys, arrays, strings, booleans, null where
explicitly allowed, and bounded integers. No Python object, bytes value, path,
enum instance, mapping subclass, tuple, set, or float enters the canonicalizer
directly.

Its top-level form is exactly:

```text
identity_domain
contract_version
canonicalization_version
decision_id
decision_body
```

`decision_body` is a closed object with these exact sections:

```text
normalization
snapshot_binding
operator_intent
configuration_binding
privacy_and_egress
context_budget
classification
logical_route_policy
escalation_and_review
verification
authority_boundary
```

The sections contain bounded fields from CR-DD-012:

- contract/configuration version identifiers;
- instruction, inline, ordered source, task-data, and assembled-execution
  digests and lengths;
- normalized declarations and canonical profile;
- non-secret decision-relevant configuration identifiers or digests;
- privacy preflight, egress eligibility, and cloud intent as separate values;
- advisory token estimate, usable budget, and budget posture;
- deterministic classification and bounded risk posture;
- preferred logical route and an ordered permitted fallback envelope;
- terminal escalation, ethical-firewall, and human-review posture;
- ordered required verification/review checks; and
- explicit statements that identity, cloud intent, decision validity, and
  confirmation grant no execution or egress authority.

Free-form reasons, exceptions, matched sensitive values, and runtime state are
not allowed. All enums and reason codes come from closed versioned registries.
The implementation contract must enumerate every allowed field, enum, and
nullable position; permissive catch-all metadata is forbidden.

### Canonical bytes

`governed_decision_canonical_json.v1` is:

- UTF-8;
- no BOM;
- recursively lexicographically sorted object keys;
- compact separators `,` and `:` with no insignificant whitespace;
- closed schema keys are ASCII;
- string values preserve their exact Unicode code-point sequence without NFC,
  NFD, NFKC, NFKD, or other Unicode normalization;
- string serialization uses the deterministic standard JSON profile equivalent
  to `ensure_ascii=False`: non-ASCII code points remain literal UTF-8, while
  quotation marks, reverse solidus characters, and U+0000 through U+001F
  control characters receive mandatory JSON escaping;
- integers only, with booleans not accepted where integers are required;
- no floats, NaN, or infinities; and
- no trailing newline.

Arrays retain schema-defined semantic order. In particular, ordered source
bindings, permitted fallback entries, escalation conditions, and required
verification/review checks are never sorted or deduplicated. Only a field
explicitly declared set-like in the closed schema may be sorted, and its exact
sort key plus duplicate-rejection policy must be part of the schema version.

Parsing rejects duplicate object keys at every depth, missing or unknown
fields, malformed UTF-8, lone surrogates, BOMs, floats, invalid integers,
invalid nulls, malformed digests, invalid enum values, unsupported versions,
and noncanonical serialization. After structural validation, parsing
reserializes the value and requires byte-for-byte equality with the supplied
canonical bytes. Canonically equivalent human text expressed as different
code-point sequences remains byte-distinct, produces distinct canonical
decision bytes, and produces a distinct decision ID.

### Decision ID

Identity uses the exact fixed ASCII domain:

```text
triagecore.governed_decision.identity.v1
```

The identity envelope contains exactly:

```text
identity_domain
contract_version
canonicalization_version
decision_body
```

`decision_id` is excluded only to avoid self-reference. The ID is:

```text
sha256:<64 lower-case hexadecimal characters>
```

over the canonical bytes of that complete envelope. Changing the domain,
contract version, canonicalization version, or any decision-body value changes
the ID.

Parsing reconstructs the closed envelope, recomputes the ID using a constant
algorithm choice, and rejects any mismatch. The decision ID is content
linkage, not authenticity, secrecy, identity, approval, authorization,
acceptance, or quality evidence. It cannot be substituted for CR-DD-011's
`plan_body_digest` or `artifact_byte_digest`.

## Pure Decision Builder

One pure function accepts:

- the completed immutable `GovernedRunInputSnapshot`; and
- one immutable, explicit bundle of decision-relevant policy and
  configuration facts.

It returns one validated immutable `GovernedDecision`. For identical inputs it
returns byte-identical canonical bytes and the same decision ID.

The builder may perform deterministic classification, privacy/egress posture,
context-budget calculation, logical-route policy, ordered fallback-envelope
construction, escalation posture, and required-check derivation. It performs
none of those activities again after returning the decision.

The builder and canonicalization path must not access or construct:

- a model or worker;
- a network, socket, URL, or HTTP client;
- a subprocess or shell;
- the filesystem or a reopened source;
- a clock, timer, timestamp, random generator, UUID, or process ID;
- environment variables, working-directory discovery, or ambient
  `default_config`;
- a ledger, task store, artifact publisher, or plan renderer;
- a backend, router with live state, health probe, or circuit state; or
- runtime observations or execution outputs.

Every decision-relevant fact is passed explicitly. Unsupported, missing,
secret-bearing, or mutable configuration fails validation; the builder does
not discover or repair it.

## Privacy Boundary

Raw and normalized task bytes remain inside the attempt-local snapshot. They
are never included in canonical decision bytes, plan artifacts, ledger
metadata, logs, exceptions, or status documents.

The decision body may contain only:

- bounded SHA-256 digests and lengths;
- closed enums and reason codes;
- non-secret version/profile/policy identifiers; and
- bounded non-secret configuration digests.

It must not contain prompt text, inline data, source content, raw source paths,
path basenames, matched privacy values, secret values, credentials, tokens,
backend exception text, or model output. Locator digests are linkage only and
may disclose low-entropy guesses; the decision remains operator-controlled and
is not a public redaction artifact.

Focused tests serialize decisions built from distinctive prompt text, source
paths, sensitive values, and secret-like tokens, then assert that none of
those supplied byte sequences or their plain/base64 representations appear.
Tests also recursively inspect keys and values against the persistent-privacy
forbidden-field vocabulary. Snapshot tests separately prove that task bytes
remain available only in the attempt-local immutable value.

## No-Premature-Integration Boundary

The CR-DD-012A implementation may expose internal library types and pure
functions for tests and later consumption. It may not modify an existing
public command, parser, engine, client, worker, backend, ledger, renderer, or
artifact path to call them.

In particular:

- `tc run` continues its current assembly and execution path;
- `tc run --plan` continues its current preview path;
- `governed_run_plan.v1` remains byte-for-byte contract compatible and gains
  no decision field;
- no decision or snapshot is persisted;
- no route or fallback is executed or enforced from the new values; and
- no confirmation or digest is accepted as authority.

CR-DD-012B alone may propose replacing current preview and execution decision
seams with these completed internal values.

## Approved Implementation Categories

The separately approved implementation remains limited to:

- one internal module for immutable snapshot types, byte normalization,
  assembly, limit validation, and profile resolution;
- one internal module for immutable decision types, pure construction,
  canonical JSON, parsing, and ID verification;
- focused unit tests for each module; and
- bounded property-style tests using existing test dependencies or
  deterministic generated cases.

The exact implementation paths are listed below. No existing CLI, client,
engine, router, backend, ledger, artifact, or plan module is implied by this
section.

## Implementation Acceptance Criteria

- [x] Frozen values, bytes, and tuples provide recursive immutability without
  retained caller-owned mutable values or path objects.
- [x] The exact SourceBytes, NormalizedComponentBytes, and
  AssembledExecutionBytes taxonomy is implemented without conflation.
- [x] `AssembledExecutionBytes` equals strict UTF-8 encoding of
  `prompt + "\n\nDATA:\n" + data` under the existing data assembly rules.
- [x] File order, duplicate sources, verbatim path headers, strict UTF-8,
  universal-newline translation, BOM preservation, source separators, inline
  truthiness, and absent-value behavior match current `tc run`.
- [x] The current plan-only `prompt + "\n" + data` representation is not
  labeled or bound as execution bytes.
- [x] Explicit finite construction bounds cover every retained/full-size
  representation and are validated before allocation; absent, unbounded, or
  exceeded bounds fail closed, and no advisory token budget is silently
  converted into a hard byte limit.
- [x] No public CLI acceptance, error, file-read, or assembly behavior changes.
- [x] Snapshot digests, lengths, ordered bindings, and assembled bytes are
  internally consistent and fail closed on mismatch.
- [x] One deterministic resolver uses only an explicit closed profile map.
- [x] One pure builder uses only the immutable snapshot and explicit immutable
  policy/configuration facts.
- [x] The canonical decision uses one closed primitive structure, the pinned
  JSON profile, and the pinned domain-separated identity envelope.
- [x] Duplicate keys, floats, unknown or missing fields, malformed digests,
  unsupported versions, noncanonical bytes, and decision-ID mismatch fail
  closed.
- [x] Ordered sources and fallback/check arrays preserve order and duplicates.
- [x] Canonical decisions contain only bounded privacy-safe bindings and pass
  supplied-prompt/path/sensitive-value/secret absence tests.
- [x] Tests trap model, network, socket, subprocess, filesystem reopen, clock,
  randomness, environment, ledger, backend, and artifact access.
- [x] No existing command imports or calls the foundation.
- [x] No ledger, plan artifact, runtime observation, execution record, route
  enforcement, fallback enforcement, or cloud authority behavior changes.

## Validation Record

- Focused CR-DD-012A suite: 103 passed.
- Full suite: 1167 passed, 4 skipped.
- Privacy-invariant audit: 698 records.
- Both foundation modules passed `py_compile`.
- The external ledger SHA-256 remained unchanged, and no artifact file
  changed.
- The existing ignored `.triagecore/triagecore.log` received one metadata-only
  `supervisor usage scan` line from the full suite. The line was preserved
  transparently; no cleanup or history rewrite was performed.
- Staged diff and exact scope checks passed: the cached diff check was clean,
  the cached name list exactly matched the allowlist, and prohibited seams and
  the changelog had zero cached diff.

## Required Focused Tests

### Snapshot and execution-byte compatibility

- table tests for no files/no inline, empty prompt, empty files, multiple
  ordered files, duplicate files, files with and without final newlines,
  non-empty inline data, `None` versus empty inline data, non-ASCII text, BOM,
  LF, CRLF, and CR inputs;
- exact byte fixtures for each source header, task-data concatenation,
  `"\n\nDATA:\n"` worker separator, and final assembled execution bytes;
- proof that verbatim alternative path spellings produce different assembled
  bytes and bindings under the current contract;
- strict UTF-8 decode failure and no partial snapshot;
- proof that the planning-only newline assembly differs where expected and is
  never substituted for execution bytes; and
- mutation attempts against input lists, dictionaries, bytearrays, path
  objects, returned tuples, and frozen records.

### Limits and allocation posture

- instruction, inline, per-source normalized, normalized aggregate, assembled
  task-data, and assembled-execution boundary cases at limit, one below, and
  one above;
- rejection of missing, zero, negative, unbounded-sentinel, inferred, or
  inconsistent bounds before full-size allocation;
- checked-length overflow and fail-before-duplicate-allocation traps;
- refusal to retain raw source bytes without finite per-source and aggregate
  provenance caps;
- explicit finitely bounded raw-source retention; and
- proof that advisory token-budget posture does not silently become a byte
  rejection rule.

### Canonical decision and identity

- repeated identical inputs produce byte-identical canonical decisions and
  IDs;
- changes to any instruction/data/source byte, source order, duplicate count,
  path spelling, declaration, version, profile, or policy binding change the
  relevant binding and decision ID;
- recursive key-order permutations normalize to one canonical form before
  publication, while parsing rejects noncanonical serialized input;
- canonically equivalent text represented by NFC and NFD code-point sequences
  remains byte-distinct, is not normalized, and produces different decision
  IDs;
- mandatory quote, reverse-solidus, and control-character escaping plus
  literal non-ASCII UTF-8 behavior;
- duplicate-key, float, unknown-field, missing-field, unsupported-version,
  bad-domain, malformed-digest, malformed-ID, and ID-mismatch rejection;
- property-style generated Unicode, ordered-source, ordered-fallback, and
  bounded-integer cases with fixed seeds and bounded sizes; and
- explicit distinction among `decision_id`, `plan_body_digest`, and
  `artifact_byte_digest`.

### Purity, privacy, and integration absence

- traps for model, network, socket, subprocess, filesystem, clock, randomness,
  UUID, environment, ambient config, ledger, backend, renderer, and artifact
  access;
- decision serialization absence tests for supplied prompt text, inline data,
  file content, exact paths and basenames, sensitive markers, secrets,
  credentials, and their plain/base64 forms;
- low-entropy digest limitation documentation tests where applicable;
- import/call traps proving no existing public command consumes the new
  modules; and
- regression tests establishing that current `tc run`, `tc run --plan`,
  `governed_run_plan.v1`, ledger, and worker behavior is untouched.

Property-style tests must be deterministic, bounded, offline, and use no new
service or heavy infrastructure.

## Risks And Mitigations

- **Filesystem bytes mistaken for execution bytes:** the three-layer taxonomy
  makes assembled user-message bytes authoritative.
- **Planning text mistaken for worker input:** exact fixtures distinguish the
  current single-newline planning representation from the engine's
  `"\n\nDATA:\n"` user message.
- **Normalization changes behavior:** UTF-8 errors, universal newlines, BOM,
  order, duplicate, path-header, separator, and absent-input behavior are
  pinned to current code.
- **Path normalization causes hidden drift:** verbatim CLI spelling remains
  execution-significant until a separately approved compatibility migration.
- **Mutable aliases alter governed content:** constructors own bytes and frozen
  values and retain no caller-owned mutable references.
- **Ephemeral snapshot becomes an unlimited duplicate:** mandatory finite
  allocation bounds, checked lengths, separately capped optional raw
  retention, and single-copy rules bound every full-size representation
  without inventing a public CLI limit.
- **Canonicalization ambiguity changes identity:** one closed primitive
  structure, strict parsing, byte equality, and a domain-separated envelope
  fail closed.
- **Digest treated as secrecy or authority:** decisions remain
  operator-controlled and state that IDs are linkage only.
- **Pure builder consults live state:** prohibited-dependency traps cover every
  ambient and volatile source.
- **Foundation quietly becomes integration:** existing public modules remain
  outside the later CR-DD-012A implementation allowlist; CR-DD-012B owns
  consumption.

## Rollout And Rollback

The approved implementation is complete and validated as an internal,
non-integrated foundation and now stops pending merge. It does not ship a new
operator capability. A failure in final staged scope or diff verification
prevents the implementation from landing. Rollback before merge is removal of
the two new modules and three new tests plus restoration of these bounded
status updates; no runtime, ledger, or artifact state requires rollback.

CR-DD-012B may be proposed only after CR-DD-012A lands and is reviewed. It must
start from the then-current `main`, on a new branch, with separate authority.

## Dependencies And Sequencing

- Depends on the merged CR-DD-012 architecture.
- Preserves the merged CR-DD-010 preview and CR-DD-011 exact-confirmation
  contracts.
- Received separate human implementation approval with the exact bounded
  allowlist below; implementation, validation, and supervisor review passed.
- Must land before CR-DD-012B may receive implementation approval.
- CR-DD-012B owns preview/execution consumption, runtime observations, fallback
  envelope enforcement, and bounded existing-evidence linkage.
- A later separately approved CR owns any decision-bearing plan schema or
  confirmed-plan execution.

## Implementation File Allowlist

The approved implementation branch may change exactly:

- `triage_core/governed_run_snapshot.py`
- `triage_core/governed_decision.py`
- `tests/test_governed_run_snapshot.py`
- `tests/test_governed_decision.py`
- `tests/test_governed_decision_integration_absence.py`
- `docs/change/requests/CR-DD-012A-governed-decision-foundation.md`
- `docs/current_backlog.md`
- `docs/architecture/daily_driver_orchestrator_spec.md`
- `docs/change/requests/CR-DD-012-shared-governed-run-decision.md` —
  status/sequencing only

`docs/change/change_log.md` remains intentionally untouched. No existing code
or test file, runtime integration, CLI, ledger, artifact contract, or other
documentation change is authorized. Implementation and validation stop before
CR-DD-012B.
