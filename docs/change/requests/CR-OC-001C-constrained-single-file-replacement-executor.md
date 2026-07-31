# CR-OC-001C: Constrained Single-File Replacement Executor

## 1. Status and Authority

- **Status:** Proposed. Requirements contract only; documentation only.
  Revised once in draft after adversarial review, before any approval.
- **Implementation authority:** None. This document authorizes no code, no
  tests, no fixtures, no dependency change, no CI change, no CLI or `tc run`
  change, no runtime integration, no capability or reservation change, no
  IPC, no Windows account work, and no OpenClaw installation or
  configuration.
- **Approval gate:** Explicit human approval is required before any
  implementation, and again before any merge. Recording this proposal
  satisfies neither.
- **Still unauthorized:** CR-OC-001D, CR-OC-001E, and every runtime surface.

This document defines the requirements an implementation must satisfy. It is
written so that an implementation agent cannot choose materially different
safety semantics without returning for approval. Where this document says
"must", a conforming implementation has no discretion; where it says
"recorded rather than glossed", the limitation is part of the contract and
may not be papered over with stronger wording later.

## 2. Why This Slice Is Next

CR-OC-001A (merged) represents one exact single-file content transition and
binds it to digests, a client request, and a connection identifier field. It
opens no file. CR-OC-001B (merged) makes the client-request-to-capability
binding atomic and durable, so two callers cannot obtain authority for the
same logical operation. It also opens no target file.

The lane's remaining gap between representation and reality is the effect
itself: nothing merged so far can carry out even one constrained replacement,
so nothing downstream (broker, tool surface) has a bounded primitive to
mediate. CR-OC-001C supplies exactly that primitive and nothing around it.

It is sequenced after B deliberately — an executor that can be driven twice
for one request is worse than no executor, and B's reservation now exists —
and before D, because the broker needs a finished, separately reviewed
filesystem primitive to invoke rather than growing one inside itself.

The executor is invoked **only by tests** until a later, separately approved
integration slice. No runtime module may import it.

## 3. Scope and Objective

One constrained filesystem effect:

> Given an already constructed and correctly bound CR-OC-001A
> `AuthorizedContentEffect`, an independently supplied exact proposed byte
> sequence, and a trusted mapping from `target_file_id` to one repository
> target, perform **at most one** single-file content replacement under
> explicit filesystem constraints, and report the outcome honestly through a
> closed vocabulary.

The slice is a library surface with **no consumers in production code**. Its
only production dependencies are `triage_core.mediated_effect` (the merged
pure effect contract) and `triage_core.privacy_invariants` (the house
persistence gate, imported for the same reason CR-OC-001B imports it: the
privacy invariant must run in-module over the exact payload intended for
persistence, not in a test that might drift). No other TriageCore module may
be imported. This one addition to the "only dependency is the effect
contract" preference is stated here so it cannot drift silently into more.

Out of scope, restated from the inherited rules so they cannot be lost:

- file creation, deletion, append, patch, rename-as-API, directory mutation,
  multi-file effects, command execution;
- authorization, reservation, capability claiming, broker identity, client
  identity, OpenClaw provenance — the executor validates internal
  consistency of what it is handed and **invents no authority** that belongs
  to CR-OC-001B, CR-YK-002, CR-OC-001D, or CR-OC-001E.

## 4. Supported Platform and Threat Model

### 4.1 The decision: a Windows/NTFS executor over a platform-neutral core

The first implementation is **Windows-specific for every mutating path**,
with a **platform-neutral pure core** for everything that touches no file.

The split, pinned:

- **Platform-neutral pure core** — input-shape validation, the trusted
  registry type and its construction rules, the relpath grammar,
  proposed-content verification against the effect's digests and sizes, the
  closed reason/outcome vocabulary, the primitive-result-to-outcome
  classifier (a pure function over a success flag and an error code), and
  the privacy-gated result projection. All of it must be factored as pure
  functions and types with no platform conditionals, testable on any
  platform including Ubuntu CI.
- **Windows/NTFS mutating path** — resolution walk, open, pre-digest read,
  security-descriptor capture, temporary file, replacement, backup
  lifecycle, and post-verification. Implemented with `ctypes` calls to
  documented Win32 APIs (`CreateFileW`, `GetFileInformationByHandle`,
  `GetFinalPathNameByHandleW`, `ReplaceFileW`, `GetSecurityInfo`,
  `GetSecurityDescriptorControl`, `GetAclInformation`, `GetAce`,
  `EqualSid` and/or `ConvertSidToStringSidW`, `OpenProcessToken`,
  `GetTokenInformation`) plus `msvcrt` handle/descriptor bridging. All
  stdlib; **no new package dependency**.

On any platform other than Windows, and on Windows when a required API is
unavailable at runtime, `execute_replacement` **fails closed** with
`platform_unsupported` before any file is opened. There is no degraded
mode, no partial execution, and no check silently skipped.

**Why not two mutating profiles.** An earlier draft of this contract
specified parallel POSIX and Windows mutating paths. Review rejected that,
and the rejection is recorded as binding rationale: the two paths shared
almost nothing safety-bearing — different containment mechanism
(`dir_fd`/`O_NOFOLLOW` construction versus final-path verification),
different replacement primitive with a different documented failure
contract, different metadata truth (uid/gid/mode versus SID/DACL),
different identity semantics, different temporary-file and backup handling.
That is two executors under one name: double the safety surface, double the
tests, double the mutants, with the POSIX half serving mainly to let Ubuntu
CI stand in for evidence about the platform this lane actually targets —
CR-OC-001D's named pipes, DACLs, and Windows account separation are
Windows work, and the operator environment is Windows. A stand-in is not
evidence. The POSIX mutating path is therefore **out of scope**, and a
future POSIX profile, if ever wanted, is its own contract addendum with its
own approval (see §24 for the access-control lesson recorded for it).

### 4.2 What the Windows executor claims, and does not

- **Namespace replacement atomicity is not claimed.** Microsoft documents
  neither `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING` nor `ReplaceFileW`
  as atomic. The claim is narrowed to: at most one replacement call per
  invocation, with `ReplaceFileW`'s documented per-error-code state
  contract used to classify the outcome (§11.2), and every undocumented
  state reported as ambiguous.
- **A failed replacement is reported as leaving the target intact only for
  the error classes Microsoft documents as doing so** when a backup name is
  supplied (§11.2). Everything else is ambiguous.
- **Crash durability of the name change is not claimed.** Temporary-file
  content is flushed to the device before the replacement call; no claim is
  made that a completed replacement survives power loss.
- Where operating-system behavior is load-bearing, the implementation must
  cite the official Microsoft or Python documentation for the exact
  guarantee used. An assumption that cannot be traced to documentation is
  treated as absent and the claim narrowed accordingly.

### 4.3 CI and evidence honesty

The repository's CI workflow runs on `ubuntu-latest` only. Consequences,
stated plainly:

- Ubuntu CI exercises the platform-neutral pure core in full, plus the
  fail-closed platform gate (`platform_unsupported` with zero file opens).
  It exercises **no mutating behavior** of this slice and can never accept
  it alone.
- Every mutating-path test, and every Windows-scoped mutant kill, requires
  real Windows/NTFS evidence. Two acceptable sources, in order of
  preference:
  1. **A Windows CI job** (`windows-latest`) added to
     `.github/workflows/tests.yml`. That file is **not** in this slice's
     provisional allowlist; it is named in §22 as an unresolved allowlist
     candidate requiring explicit approval before it may be touched.
  2. **A recorded local Windows test run** — full output captured in the
     implementation record, with commit hash, Python version, and OS build.
- The acceptance floor is the recorded local run; a Windows CI job, if
  separately approved, satisfies the same requirement repeatably. A green
  Ubuntu CI run plus neither of these does **not** satisfy acceptance, and
  no acceptance wording may imply it does.

### 4.4 Adversary and concurrency assumptions, stated honestly

The executor defends against:

- malicious or malformed **inputs**: forged or inconsistent effect objects,
  path-shaped identifiers, oversized or mismatched content;
- **pre-existing filesystem traps** present before validation: symlinks,
  junctions, mount points, and every other reparse-point form at the target
  or any ancestor beneath the workspace root; non-regular targets;
- **benign concurrent modification**, by detecting divergence: a target
  that changes between validation and replacement produces a pre-digest,
  identity re-probe, or post-verification failure, reported honestly.

The executor does **not** defend against, and this document must never be
cited as protection against:

- a **hostile local process** with write access to the workspace or its
  ancestors that races the executor between a check and the operation the
  check guards. The identity re-probe (§8.2) narrows these windows; it does
  not close them, and in particular **no handle held by the executor
  constrains how `ReplaceFileW` resolves the target name** (§8.2). The
  positive claim's "no concurrent external writer" clause (§5.1) is
  load-bearing, not decorative: between the executor's last identity probe
  and the primitive's own internal name resolution, correctness rests on
  that assumption and on nothing else.
- a process that can modify the executor's own memory, the Python runtime,
  or the trusted registry construction path;
- privileged processes of any kind.

Cross-process mutual exclusion is **not provided and not claimed** (§14).

## 5. Positive Claim and Non-Claims

### 5.1 The one positive claim

A completed CR-OC-001C may support exactly this claim:

> On Windows with an NTFS workspace, given a trusted target registry
> constructed by the operator-side caller and an `AuthorizedContentEffect`
> whose proposed bytes are supplied exactly, and in the absence of any
> concurrent writer to the target or its enclosing directories during the
> invocation, the CR-OC-001C executor can resolve one target exclusively
> through `target_file_id` without using caller path data for resolution;
> verify that the existing regular file inside the trusted workspace holds
> exactly the bytes named by `expected_pre_digest`; prepare the exact
> authorized replacement bytes in an exclusively created same-directory
> temporary file; issue at most one `ReplaceFileW` call with a private
> same-directory backup name; and report, through a closed outcome
> vocabulary, whether the target name was observed — at the
> post-verification instant, on a freshly resolved handle obtained through
> the trusted registry — to hold exactly the bytes named by
> `expected_post_digest` at exactly `content_size_bytes`, as a regular
> file, inside the workspace, with the owner and DACL invariants of §10
> preserved, reporting every ambiguous state as ambiguous rather than as
> success or as "unchanged".

Every clause is individually tested (§19). The no-concurrent-writer clause
is an environmental assumption of the claim (§4.4), not something the
executor enforces. And one causation limit is part of the claim itself:
**observing the postcondition is not proof that this invocation performed a
replacement** — the verified outcome asserts the conjunction of "this
invocation's single replacement call returned success" and "the
postcondition was observed afterward", never that the observation alone
establishes what caused the state (§12).

### 5.2 Non-claims

CR-OC-001C establishes **none** of the following, and no wording in code,
docstrings, results, or evidence may imply otherwise:

- OpenClaw containment;
- caller or broker authentication;
- truth of any declared invocation context;
- trusted provenance merely from syntactically valid identifiers;
- capability validity, claiming, or that a capability exists at all;
- reservation ownership, inspection, or advancement — including any form
  of duplicate-request or replay prevention, which is CR-OC-001B's
  authority exclusively (§7.1);
- exactly-once execution across crashes;
- namespace-replacement atomicity on Windows;
- global protection against hostile or privileged local processes;
- indefinite persistence of the postcondition after the verification
  instant;
- exact preservation of all timestamps or of file identity across the
  replacement (both change; §8.3, §10.3);
- transactional consistency with the reservation SQLite store, the
  capability SQLite store, or the JSONL ledger — this slice owns none of
  those stores and coordinates with none of them;
- safe multi-file mutation;
- POSIX support of any kind;
- file creation, deletion, append, patch, rename-as-API, directory
  mutation, or command execution.

## 6. Trusted Inputs and Target Registry

### 6.1 The trusted mapping

```text
target_file_id -> TrustedTargetEntry
```

**Who constructs it.** The operator-side caller — in this slice, only
tests; in a later separately approved slice, the broker, from a reviewed
allowlist artifact. Never the client, never OpenClaw, never anything derived
from a proposal. The registry constructor is a trusted boundary and its
inputs are trusted by definition; nothing reaching it may originate from
`proposed_bytes`, a declared context, or any client-supplied field.

**Entry fields**, all required, all validated at construction:

```text
target_file_id       CR-OC-001A identifier syntax; never path-like
workspace_relpath    the registry's own resolution path (grammar in §6.2)
maximum_size_bytes   positive integer; bounds BOTH existing and proposed
                     content for this target
```

**Registry construction inputs:**

```text
workspace_root       trusted absolute path, supplied once by the
                     constructor's caller; opened at construction and its
                     final path captured via GetFinalPathNameByHandleW —
                     the containment anchor for every later check
entries              iterable of TrustedTargetEntry
```

**Immutability.** The registry is frozen at construction: entries are
copied into an internal mapping, the entry type is a frozen dataclass, and
no mutation API exists. One registry instance is immutable for its entire
lifetime, which covers every execution that uses it.

**Duplicates.** A duplicate `target_file_id` at construction raises
`MediatedExecutorContractError`. Duplicates are a defect in trusted-side
construction, not a decision about untrusted input, so they raise rather
than entering the closed vocabulary — the same doctrine A applies to
cross-object transplants.

**Why client paths cannot influence it.** The executor API (§15) accepts no
path parameter anywhere. The only path-bearing strings it ever receives are
`workspace_root` and `workspace_relpath`, both supplied by the trusted
constructor. `canonical_relpath` from the effect is compared for evidential
consistency (§7.1) and is never joined, resolved, or opened.

**Absolute paths.** Absolute paths exist internally — the anchored root's
final path, the resolved target, temporary and backup names. None of them
may appear in the result object, the persistent projection, any exception
message, or any log line. Only `target_file_id` and the already-authorized
`canonical_relpath` identify the target in evidence.

### 6.2 The `workspace_relpath` grammar

Platform-neutral string validation, enforced at registry construction;
violation raises `MediatedExecutorContractError`:

- non-empty; at most 4096 bytes (matching A's relpath bound);
- separator is `/` only; `\` is rejected outright;
- not absolute: no leading `/`, no drive designator (`:` is rejected
  anywhere in the string), no UNC prefix (`//` or `\\`), no device or
  verbatim prefix (`\\.\`, `\\?\`);
- no segment equal to `.` or `..`; no empty segment;
- no NUL, no control characters;
- no segment ending in `.` or a space (Windows silently strips these,
  which would make two spellings name one file);
- no segment whose base name is a reserved Windows device name
  (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`), compared
  case-insensitively, with or without an extension.

### 6.3 `canonical_relpath` never becomes a second lookup mechanism

The inherited rule is carried forward exactly: `target_file_id` is the sole
resolution key. The executor looks up the entry by `target_file_id` and
resolves **only** through `entry.workspace_relpath` under the anchored
root. `effect.canonical_relpath` participates in exactly one comparison —
byte-for-byte equality with `entry.workspace_relpath` (§7.1) — and in
evidence. It is never used to select, join, resolve, or open anything.

One equivalence limitation is recorded rather than glossed: because that
equality is enforced, a defective implementation that looked up the entry
and then joined `effect.canonical_relpath` instead of
`entry.workspace_relpath` would be behaviorally identical on every input
that passes the equality check. The mutant contract (§20, M1) kills the
registry-bypass variant; the equivalent-join variant is unkillable by test
and reviewers are the control, exactly as recorded for A's M9.

## 7. Resolution and Containment

### 7.1 Order of operations, before any handle is opened

1. Verify the platform gate: Windows, with every required API present;
   else `platform_unsupported`, with zero file opens.
2. Verify caller input shape (§15); violations are `invalid_executor_input`
   or raise `MediatedExecutorContractError` per §15.3.
3. Look up `effect.target_file_id` in the registry; absence is
   `target_id_unknown`.
4. Require `effect.canonical_relpath == entry.workspace_relpath`,
   byte-for-byte, no case folding, no separator normalization; mismatch is
   `effect_registry_mismatch`. This is a decision about possibly
   untrusted-origin input (the effect's descriptor fields originate on the
   proposal side), so it takes a reason code rather than raising —
   unlike trusted-side registry defects, which raise.
5. Require `effect.content_size_bytes <= entry.maximum_size_bytes`;
   violation is `proposed_size_exceeded`.
6. Require `effect.expected_pre_digest != effect.expected_post_digest`;
   equality is `invalid_executor_input`. **This is a scope and API rule.**
   The operation CR-OC-001C defines is an actual content transition —
   `expected_pre_digest -> expected_post_digest` with the two digests
   naming different content — and an effect whose digests are equal
   describes no such transition, so it is outside this executor's
   operation contract and is rejected at the boundary. The rule is **not
   replay prevention**: nothing about it prevents, detects, or reasons
   about duplicate requests, and duplicate-request authority remains
   **CR-OC-001B's alone**; this rule must never be cited in that role.
   Nor would accepting such an effect and observing that the file already
   holds the expected bytes prove anything — observation is not causation
   (§12), so "the target already has the authorized content" is not
   evidence that this invocation, or any invocation, produced that state.
   A future, separately scoped **observational** operation could define an
   `already_at_authorized_postcondition` result with its own claim and
   its own approval; this executor defines and implements no such
   operation.

### 7.2 Windows containment: reparse rejection plus final-path verification

Windows exposes no `openat`-style construction, so the design layers three
checks, and the third is the load-bearing one:

1. **Grammar** (§6.2) — string-shape only; explicitly not sufficient alone.
2. **Reparse rejection on the walk.** For the target and every ancestor
   strictly beneath the anchored root: `os.lstat` must not carry
   `FILE_ATTRIBUTE_REPARSE_POINT`, following the existing house helper
   pattern (`run_plan_artifact._is_link_or_reparse`,
   `evaluation_handoff_validator._is_link_or_reparse`). This rejects
   symlinks, junctions, mount points, and every other reparse tag without
   trying to enumerate tags. Failure or inability to read attributes fails
   closed as `containment_violation`.
3. **Final-path verification on the opened handle.** The target is opened
   via `CreateFileW` (§8.2). `GetFinalPathNameByHandleW` on the **opened
   handle** must equal the final path captured for the anchored root at
   registry construction, joined with `workspace_relpath` — compared
   ordinally and case-insensitively after stripping the `\\?\` verbatim
   prefix, with `/` mapped to `\`. Any disagreement is
   `containment_violation`. Because the comparison runs on what the handle
   *actually resolved to*, a link or junction anywhere in the chain that
   survived step 2 (created after the walk, or hidden from it) is still
   caught if it redirected resolution outside the workspace.

Recorded residuals, not glossed: NTFS per-directory case sensitivity can in
principle make a case-insensitive comparison accept a same-letters path
that is a different file in a case-sensitive directory; the identity checks
in §8 bound the damage to a file that still resolved under the workspace
root. A lexical prefix check over caller strings appears nowhere — the
only string comparison is against the anchored root's final path, on the
handle's own resolution.

### 7.3 What containment failure looks like

Every failure in this section is closed, is `not_attempted`, performs no
mutation, and never selects a fallback target, retries with a variant path,
or widens to a parent directory. Uncertainty — an unreadable attribute, an
unexpected error while walking — fails closed as `containment_violation`
rather than proceeding.

## 8. Target Identity, Existence, and File Type

### 8.1 What identity means

File identity is `(dwVolumeSerialNumber, nFileIndexHigh, nFileIndexLow)`
from `GetFileInformationByHandle` on an open handle — Microsoft documents
this triple as identifying a file on a volume while it is open. Python's
`os.stat` documents deriving `st_ino`/`st_dev` on Windows from the same
information; the implementation may use either spelling but must state
which and use it consistently.

### 8.2 How identity is used — and what it cannot do

**Existence before execution** is established by the §7 open succeeding —
the validated handle refers to a file object that existed. File creation
never occurs on any path: no creating disposition ever reaches the target
name, and `target_missing` is terminal.

**The opened object is what the registry intended** is established by §7:
resolution ran only through trusted registry data under the anchored root,
and the final path of the actual handle was verified.

**The validation handle's role, stated precisely.** The validation handle
is opened with `CreateFileW`, `GENERIC_READ`, sharing `FILE_SHARE_READ |
FILE_SHARE_WRITE | FILE_SHARE_DELETE`. Through it the executor performs the
final-path check (§7.2), captures the identity triple (§8.1), reads and
hashes the existing content (§9), and captures the security descriptor
components (§10). The handle is then **closed**. A handle to the original
object validates **that object only**: it does not bind the target *name*,
and `ReplaceFileW` resolves its `lpReplacedFileName` argument
independently of any handle this executor holds. Holding the validation
handle open across the replacement call therefore closes no hostile
namespace race, and this contract does not keep it open or claim anything
from doing so.

**The identity re-probe.** Immediately before the replacement call, the
executor re-opens the target name (fresh `CreateFileW`, same flags),
re-verifies the final path, requires the identity triple to equal the
validated identity, and closes the probe. Mismatch or failure is
`target_observation_unstable`; nothing is mutated. This narrows the window
in which a name swap goes unnoticed to the interval between the probe's
close and `ReplaceFileW`'s own internal open. **That interval cannot be
closed by this design.** Within it, correctness rests entirely on the
load-bearing no-concurrent-external-writer assumption (§4.4, §5.1). No
wording anywhere may describe the re-probe as preventing hostile races.

### 8.3 Post-replacement identity

After a successful `ReplaceFileW`, the object at the target name is the
**replacement file's object** — a different identity from the validated
original, legitimately and by design (`ReplaceFileW`'s documented
preservation list transfers attributes, not identity continuity as far as
this contract assumes). No identity-continuity claim exists across the
replacement. Post-verification (§12) therefore proceeds **only** through an
independent fresh resolution via the frozen trusted registry — the full §7
walk, open, and final-path verification — never through any pre-replacement
handle, cached path, or cached identity.

### 8.4 File type

Only a regular file is acceptable, at validation (§7) and again at
post-verification (§12). Directories, devices, symlinks, junctions, and
every reparse-point form fail closed (`target_not_regular_file` or
`containment_violation` per which check observes them). There is no code
path that follows a link "just this once".

## 9. Exact Precondition Verification

Sequence, on the validated handle from §7–§8:

1. Size via `GetFileInformationByHandle`. If size >
   `entry.maximum_size_bytes` → `pre_size_exceeded`, not attempted. The
   size is a bound for the read, never the truth about content.
2. Read the entire content through the open handle in bounded chunks,
   reading at most `entry.maximum_size_bytes + 1` bytes total. If more
   than `maximum_size_bytes` bytes are readable → `pre_size_exceeded`. If
   the total read differs from the size observed in step 1 → the
   observation was unstable → `target_observation_unstable`. An OS read
   error → `target_read_failed`.
3. Hash the exact bytes read with SHA-256. **No normalization of any
   kind**: no UTF-8 re-encoding, no Unicode normal form, no newline
   conversion, no BOM handling. The bytes on disk are the bytes hashed.
4. Require `sha256(bytes) == effect.expected_pre_digest`. Mismatch →
   `pre_digest_mismatch`, not attempted, target untouched. The observed
   digest (a digest, never content) is recorded in the result as
   `observed_pre_digest` for evidence.

No mutation of any kind — no temporary file creation, nothing — may begin
until step 4 has passed. The existing content bytes are dropped after
hashing; they are never retained, logged, or placed in any result.

## 10. Metadata Preservation

### 10.1 The invariant, pinned to exact comparisons

The A-deferred constraints — owner unchanged, DACL not broadened, regular
file, inside the workspace — are owned here. "Not broadened" is verified
as **exact structural equality** of the pre- and post-replacement values of
the components below: equality is testable without interpreting ACL
semantics, and an unchanged descriptor trivially is not broadened.

**Components that participate in the invariant**, captured pre-mutation
through the validation handle and re-captured at post-verification through
the fresh handle, both via `GetSecurityInfo` with
`OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION`:

1. **Owner SID** — semantically equal, compared with `EqualSid` (or as
   canonical `S-1-…` strings via `ConvertSidToStringSidW`; the
   implementation picks one and uses it consistently). Byte-copy layout of
   the SID structure is not the comparison; SID identity is.
2. **DACL state, three-valued** — the DACL is classified as exactly one
   of: **absent** (`SE_DACL_PRESENT` unset), **NULL** (present flag set
   with a NULL ACL pointer — the documented grant-everyone state), or
   **present** (a non-NULL ACL, including the present-with-zero-ACEs
   empty DACL, which denies all access and is a different state from
   NULL). Pre and post must classify identically; only present-versus-
   present proceeds to the structural comparison below.
3. **Selected control bits** — the following bits from
   `GetSecurityDescriptorControl` must be equal: `SE_DACL_PRESENT`,
   `SE_DACL_PROTECTED`, `SE_DACL_AUTO_INHERITED`.
4. **ACL structure header** — `AclRevision` and `AceCount` (via
   `GetAclInformation`) must be equal.
5. **Ordered complete-ACE comparison** — ACEs are enumerated in order
   with `GetAce`. For each ACE, `ACE_HEADER.AceSize` is validated before
   any use: it must be non-zero, at least the ACE header size, and the
   running sum of enumerated `AceSize` values must stay within the
   containing ACL's in-use bounds. Then, for each index `i`, the
   **complete `AceSize`-byte sequence** of ACE `i` pre must equal that of
   ACE `i` post. Order participates: ACE order is access-semantically
   significant on Windows, so a reordering fails the invariant.

   Complete per-ACE byte comparison is the rule *because* Windows ACE
   forms carry access-relevant data beyond any small field tuple: object
   ACEs carry `ObjectType`/`InheritedObjectType` GUIDs, callback and
   conditional ACEs carry application data that parameterizes access
   decisions, and inheritance-related fields shape propagation. A
   `(AceType, AceFlags, AccessMask, SID)` tuple would silently ignore all
   of that; the full byte sequence cannot.

   **Unknown ACE types** are compared as complete opaque `AceSize`-byte
   sequences — header parsing is used only for the bounds validation
   above, and no ACE is ever partially parsed, partially compared, or
   skipped because its type is unrecognized.

   **Malformed input fails closed.** A descriptor, ACL, or ACE that fails
   the bounds validation — or any capture that cannot produce a
   well-formed comparable structure — is never compared best-effort:
   observed pre-mutation it is `metadata_precondition_failed`
   (`not_attempted`); observed at post-verification it is
   `metadata_preservation_failed` (`replacement_may_have_occurred`).

   **Slack space does not participate.** Unused ACL capacity and any
   padding outside the enumerated per-ACE byte sequences are excluded
   from the equality decision; two ACLs differing only in buffer slack
   are equal.

**Components that do not participate**, with the reason recorded:

- **SACL** — reading it requires `SeSecurityPrivilege`; it carries audit
  policy, not access rights. Excluded, and the exclusion is stated in the
  result's documentation.
- **Primary group SID** — carries no access semantics on Windows; a
  POSIX-subsystem vestige. Excluded.
- **`SE_DACL_DEFAULTED`** and other provenance-only control bits — they
  record where a descriptor came from, not what it grants. Excluded.

**Raw SDDL text is not the invariant.** SDDL serialization is not
documented as canonical, so string equality of
`ConvertSecurityDescriptorToStringSecurityDescriptorW` output is neither
required nor accepted as the comparison. SDDL may appear in test
diagnostics on a developer machine; it may never appear in results,
errors, or evidence (§17), and never substitutes for the structured
comparison above.

The comparison in both directions is conservative: a false mismatch fails
toward `metadata_preservation_failed` (safe); nothing in the design can
report equality for descriptors that differ in a participating component.

### 10.2 How preservation is achieved, not just checked

The executor cannot transplant a foreign owner onto the replacement file:
the temporary file is created by, and owned by, the executing account, and
`ReplaceFileW`'s documented preservation list covers DACLs, creation time,
short name, object identifier, encryption, compression, and named streams
— **not** the owner. The requirement is therefore made satisfiable by a
precondition:

- **Pre-mutation ownership gate:** before any temporary file is created,
  the target's owner SID must equal the executing principal — the process
  token's user SID from `OpenProcessToken` + `GetTokenInformation
  (TokenUser)`. Failure is `metadata_precondition_failed`, not attempted.
  This converts an unpreservable case into a refusal instead of a broken
  promise.
- **DACL carry-over:** `ReplaceFileW` is documented to give the resulting
  file the replaced file's DACL, which is the load-bearing reason §11
  selects it over `MoveFileExW` (whose result would carry the temporary
  file's directory-inherited DACL instead). Post-verification (§12) still
  performs the full §10.1 comparison; documentation is trusted to choose
  the primitive, never to skip the check.

The `ctypes` code lives inside the executor module itself under the
proposed allowlist (§22) — no new dependency (no pywin32), no subprocess
(`icacls` is forbidden by the no-subprocess rule), no smuggled helper
module. If implementation finds a separate platform helper file genuinely
necessary, that is an allowlist change requiring explicit approval first.

### 10.3 Permitted incidental changes

Timestamps (modification, change, creation as observed), file identity
(§8.3), NTFS attributes outside `ReplaceFileW`'s documented preserved
list, and allocation details may change and are **not** part of the
invariant. The result never claims they were preserved.

## 11. Temporary File, Replacement Primitive, and Backup Lifecycle

### 11.1 Temporary file

- **Placement:** the target's own parent directory, always — this
  guarantees same-volume placement for `ReplaceFileW`, and is asserted by
  test (T18).
- **Naming:** `.` + the fixed documented prefix `tcx-tmp-` + 32 lowercase
  hex characters from 16 bytes of `os.urandom` + `.tmp`. Unpredictable by
  construction; the documented prefix exists so a human can recognize
  abandoned artifacts (§13.4). The exact name never enters evidence.
- **Creation:** exclusive — `CREATE_NEW` disposition (or `O_CREAT |
  O_EXCL` through the CRT, which maps to it). A same-name collision fails
  `temp_creation_failed` and is never retried with a new name in the same
  invocation ("at most one attempt" includes preparation: one invocation
  constructs at most one temporary file).
- **Access-control limitation, recorded rather than glossed:** the
  temporary file inherits the parent directory's DACL for the window
  between creation and replacement. Any principal the directory ACL admits
  could read proposed content during that window. The exposure is bounded
  — such a principal typically reaches sibling files in that directory
  anyway — and applying the target's DACL to the temp before writing
  (`SetSecurityInfo`) is noted as a hardening candidate, **not** required
  by this slice; requiring it silently would smuggle more Win32 surface
  than the claim needs.
- **Writing:** the exact `bytes` object, written completely; a short write
  is completed by looping or fails closed — a partial temp never survives
  to replacement. Then flush via `os.fsync` (documented as
  `_commit`/`FlushFileBuffers` on Windows) **before** the replacement
  call, and the temp handle is closed before the call.
- **Post-write verification:** after flush, the temp's size must equal
  `content_size_bytes` via its own handle. (Re-hashing the temp is
  permitted but not required: the written buffer is immutable `bytes`
  already verified in §15.2.)
- **Cleanup on pre-replacement failure:** every failure after creation and
  before replacement removes the temporary file before returning. If that
  removal itself fails, the **original failure's reason code is kept** —
  cleanup failure never overwrites it — and the leftover file is a §13.4
  abandoned artifact. `temp_file_failure` is reserved for preparation
  steps with no more specific code (the post-write size check). The target
  is untouched in every pre-replacement failure.

### 11.2 The replacement primitive and its outcome classification

`ReplaceFileW(replaced_name, replacement_name, backup_name, 0, NULL,
NULL)` via `ctypes`, with `dwReplaceFlags` pinned to `0`:
`REPLACEFILE_IGNORE_MERGE_ERRORS` is forbidden because a failure while
merging the replaced file's metadata (the DACL this contract depends on)
must surface, not be swallowed. A **backup name is always supplied**
(§11.3); Microsoft documents that without one, the
`ERROR_UNABLE_TO_MOVE_REPLACEMENT` failure class leaves the replaced file
**deleted** — an unacceptable silent-loss mode this contract forbids.

The mapping from primitive result to outcome must be implemented as a
**pure function** over `(succeeded, last_error)` so the classification
table is unit-testable platform-neutrally:

Microsoft documents exactly three special errors for `ReplaceFileW`, and
the closed classifier must account for each of them by name — leaving a
documented special error to the catch-all would discard state information
the documentation provides:

```text
success                                   -> proceed to §12 post-verification

ERROR_UNABLE_TO_REMOVE_REPLACED (1175)    -> replacement_refused
                                             (target_unchanged)
     Documented state: the replaced file could not be deleted, and the
     replaced and replacement files retain their original file names.
     The target is intact at its own name. The executor removes its own
     temporary file. If, contrary to the documented state, a file exists
     at this invocation's backup name, it is retained (safe direction)
     and backup_retained is set.

ERROR_UNABLE_TO_MOVE_REPLACEMENT (1176)   -> replacement_refused
                                             (target_unchanged)
     Documented state: with a backup name specified, the replaced and
     replacement files retain their original file names. Same handling
     as the 1175 class, and the same contingency for an unexpected
     backup-name file.

ERROR_UNABLE_TO_MOVE_REPLACEMENT_2 (1177) -> replacement_outcome_unknown
                                             (replacement_may_have_occurred)
     Documented state: the replacement file still exists under its
     original (temporary) name — having inherited streams and attributes
     from the file it was to replace — and the replaced file exists
     under the backup name. The TARGET NAME MAY BE ABSENT. Both
     artifacts are retained (§11.3); nothing further is mutated.

any other failure                         -> replacement_outcome_unknown
                                             (replacement_may_have_occurred)
     No documented state exists, so nothing is asserted: the target is
     not reported unchanged, and no artifact is deleted.
```

The `target_unchanged` classification for 1175 and 1176 rests strictly on
Microsoft's documented name-retention statements for those codes; the
1177 class and the catch-all stay conservative because their target-name
condition cannot be established. The 1175 mapping must be asserted
distinctly by test (T25) so it can never be flattened into the ambiguous
1177 outcome (mutant M27).

`ReplaceFileW` is chosen over `MoveFileExW` for two documented properties:
the DACL/attribute preservation list (§10.2) and this per-error state
contract, which is what makes honest outcome classification possible. The
cost — Microsoft documents no atomicity for it — is priced into §4.2.

**Sharing note:** `ReplaceFileW` requires delete access to the files it
manipulates; another process holding the target open without
`FILE_SHARE_DELETE` causes a sharing-violation failure, which classifies
under "any other failure" above unless it maps to a documented-intact
class. It is reported honestly and never retried.

### 11.3 Backup lifecycle, complete

The backup is not an optional nicety; it is the mechanism that converts
`ReplaceFileW`'s documented worst intermediate into a recoverable state,
and it holds **the original file's bytes**, so its entire lifecycle is
specified:

- **What it is.** `ReplaceFileW` renames the *replaced file itself* to the
  backup name as part of the call. The backup is therefore the original
  file object carrying the original file's own DACL — its protection is
  exactly the protection the original had. The executor never copies
  content to create it, and no second content mutation is involved.
- **Naming and placement.** `.` + the fixed documented prefix `tcx-bak-` +
  32 lowercase hex characters from 16 bytes of `os.urandom` + `.bak`, in
  the target's own parent directory (same volume by construction — a
  requirement of the rename-based mechanism). The name is generated fresh
  per invocation; predictability would let another principal pre-create or
  squat the name, so the same unpredictability rule as §11.1 applies. The
  executor verifies no file exists at the generated backup name before the
  call (`temp_creation_failed` on collision, without retry).
- **Disclosure boundary.** The backup name never appears in the result,
  the projection, any exception, or any log line — the same rule as every
  absolute path and temporary name (§17). Humans locate backups by the
  documented prefix, not by evidence records.
- **Success cleanup.** Only after §12 post-verification passes in full is
  the backup deleted. The backup's content at that point is the verified
  pre-content's file object; the target's post-state is verified; deleting
  it destroys nothing unrecoverable. If deletion fails, the result remains
  `replacement_verified` with `backup_retained = true` — a hygiene fact,
  never a downgrade of the verified outcome.
- **Failure and ambiguous-state retention.** For every outcome other than
  `replacement_verified` in which the backup may exist — the
  `ERROR_UNABLE_TO_MOVE_REPLACEMENT_2` class, any undocumented failure,
  and every post-verification failure — the backup is **retained
  deliberately**: it may be the only on-disk copy of the original content,
  and deleting it while the target's state is unverified would destroy the
  recovery path. In these states the executor performs **no further
  filesystem operations at all** — no backup deletion, no temp deletion,
  no probing writes — because any additional mutation in an unknown state
  can only make the state harder to reason about. `backup_retained` is set
  accordingly.
- **When deletion would be unsafe, pinned:** whenever the outcome is not
  `replacement_verified`; whenever post-verification could not be
  completed; and during any window in which the target name's state has
  not been re-verified after the primitive returned. The implementation
  must not contain a cleanup path reachable from those states.
- **Restart cleanup.** A later invocation never scans for, reports, or
  deletes `.tcx-bak-*` (or `.tcx-tmp-*`) files. It cannot know whether
  such an artifact belongs to a crashed invocation or a live concurrent
  one — the same observability honesty CR-OC-001B applied to unbound
  reservations — and deleting a live invocation's backup would destroy its
  recovery path. Random names mean abandoned artifacts never collide with
  new invocations.
- **Human recovery authority.** Recovery from a retained backup is a human
  operation, exclusively. The human verifies the backup's content against
  `expected_pre_digest` from the result **before** trusting it (the digest
  identifies the authorized pre-content exactly), then decides whether to
  restore, keep, or delete. The executor never restores from a backup
  under any circumstances — restoration is a content mutation this
  contract does not authorize (§13.1).

### 11.4 "At most one replacement attempt"

Per invocation: the replacement primitive is invoked **at most once**.
There are no retries on any failure, including transient-looking errors. A
caller that wants to try again constructs a new invocation, which re-runs
every validation from the top. The in-process lock (§14) serializes
invocations so two threads cannot interleave inside one target's
prepare-replace-verify sequence.

## 12. Postcondition Verification

Runs only when the replacement primitive reported success. On a **freshly
resolved** handle — the full §7 resolution through the frozen trusted
registry repeated from the top, never a cached path, never any
pre-replacement handle or identity (§8.3):

1. The target name resolves under the anchored workspace root (final-path
   verification per §7.2) — else `post_containment_lost`.
2. It is a regular file with no reparse attribute — else
   `post_not_regular_file`.
3. Its exact bytes (read bounded as in §9) hash to
   `expected_post_digest` — else `post_digest_mismatch`.
4. Its byte size equals `content_size_bytes` — else `post_size_mismatch`.
5. The §10.1 structured owner/DACL comparison holds against the
   pre-captured components — else `metadata_preservation_failed`.
6. The result payload intended for persistence passes
   `assert_persistent_privacy_safe` and contains no content, no absolute
   path, and no temporary or backup name (§17) — a violation raises
   `MediatedExecutorContractError` rather than returning a result, because
   an unsafe evidence payload must never be handed to a caller that might
   persist it.

Any failure in steps 1–5, and any error while attempting them (open
failure, read failure), classifies as `replacement_may_have_occurred` with
the step's reason code — the mutation already happened or may have
happened, and nothing may claim otherwise. The backup is retained (§11.3).

**Observation point and causation, stated precisely:** every postcondition
claim is a claim about the instant of this verification on this handle.
The executor holds no lock against later writers and makes no claim that
the file remains in the verified state afterward. And **observation is not
causation**: finding the post-content at the target name does not by
itself prove this invocation put it there. `replacement_verified` asserts
the conjunction — this invocation's single primitive call returned
success, *and* the postcondition was subsequently observed. Under the
§4.4 no-concurrent-writer assumption the conjunction supports attributing
the state to this invocation; without that assumption it does not, and no
consumer of this result may treat the outcome as stronger than that.

## 13. Crash, Rollback, and Ambiguous Outcomes

### 13.1 No automatic rollback — the decision and its rejection rationale

If replacement succeeds and post-verification then fails, the executor
**does not** write the target again — not directly, and not by restoring
the backup. Automatic rollback is rejected because:

- restoring pre-content is a second mutation performed without a fresh
  precondition check — the verification failure just proved the world is
  not in the state the authorization described, so no guard for a second
  write exists;
- a rollback could overwrite a concurrent change that is the very reason
  verification failed, converting one detected anomaly into one silent
  data loss;
- a rollback that itself fails creates a third state no vocabulary honestly
  covers.

Evaluated alternatives: **automatic rollback** — rejected above;
**retained backup** — adopted: `ReplaceFileW` produces one as part of the
single replacement call (no second mutation involved) and §11.3 retains it
whenever verification does not fully succeed; **terminal partial-failure
result** — adopted: `replacement_may_have_occurred` with a step-specific
reason; **human recovery** — adopted as the only recovery path, with the
authority and digest-verification rule pinned in §11.3.

### 13.2 The outcome taxonomy

```text
not_attempted                the replacement primitive was never invoked;
                             this invocation issued no mutating operation
                             against the target name
target_unchanged             the primitive was invoked and failed in one
                             of the error classes Microsoft documents as
                             leaving the replaced and replacement files
                             under their original names (1175; 1176 with
                             a backup name supplied — §11.2)
replacement_may_have_occurred  the primitive failed ambiguously, or
                             succeeded but post-verification failed or
                             could not be completed
replacement_verified         the primitive succeeded and §12 passed in full
```

An exception during validation yields `not_attempted` with its reason code
— which is a statement that *this invocation issued no mutation*, not a
verified claim about the file's bytes; the file may have been changed by
others at any time. `target_unchanged` is asserted **only** on the
documented-intact error paths; every undocumented or unexpected failure of
the primitive reports `replacement_may_have_occurred`. Flattening an
ambiguous state into `target_unchanged` is the lie this taxonomy exists to
prevent.

### 13.3 Crash observability table

No result is returned after a crash, so these are the observable filesystem
states a human or a later process may find:

| Crash point | Observable state |
|---|---|
| before temp creation | target intact; nothing else |
| during temp writing | target intact; abandoned `.tcx-tmp-*` file |
| after temp complete, before replacement | target intact; abandoned complete `.tcx-tmp-*` |
| during the replacement call | any of: both originals intact; original at the backup name with the replacement still at the temp name (target name absent); or replacement complete — plus abandoned `.tcx-tmp-*`/`.tcx-bak-*` |
| after replacement, before post-verification | new content at the target name; original at the abandoned backup name; no evidence returned |
| after verification, before returning | new content in place, verified but unreported; backup possibly already deleted |

### 13.4 Abandoned artifacts

A later invocation does **not** scan for, report, or delete `.tcx-tmp-*`
or `.tcx-bak-*` files (rationale in §11.3, restart cleanup). Cleanup and
recovery are human operations, aided by the documented prefixes and the
result digests. No reason code claims "crash detected"; only artifacts are
observable, never their cause.

**No cross-store transactionality:** this slice does not touch the
reservation store, the capability store, or the JSONL ledger, and makes no
claim of consistency with any of them. Whether and how an executor result
becomes ledger evidence is a later integration slice's problem.

## 14. Concurrency Model

- **Two executor calls in one process:** serialized by one process-local
  `threading.Lock` held for the entire invocation (validation through
  post-verification or failure). The second invocation then observes
  post-state and fails `pre_digest_mismatch`. Because §7.1 prohibits
  degenerate no-op effects, two in-process invocations cannot both report
  `replacement_verified` for the same effect.
- **Cross-process:** **no exclusion exists and none is claimed.** A
  process-local mutex is not cross-process protection; Windows sharing
  modes apply per-handle and cannot be imposed on an uncooperative
  process's future opens; the repository contains no cross-process
  file-locking machinery to reuse. Rather than claim a protection the
  platform does not grant, the claim is narrowed: cooperating processes
  are expected not to run the executor concurrently on one workspace (an
  operator assumption, part of §5.1's environment clause), and a violated
  assumption is *detected* — as pre-digest, identity re-probe, or
  post-verification mismatch — not prevented.
- **Unrelated local process writing the target:** before the pre-digest
  read — detected as `pre_digest_mismatch`; between pre-digest and
  replacement — the replacement clobbers that write and post-verification
  reports `replacement_verified` if the result matches the authorized
  post-content (their write is lost; this is exactly the no-concurrent-
  writer environmental assumption, recorded plainly); after replacement,
  before verification — `post_digest_mismatch` →
  `replacement_may_have_occurred`.
- **Unrelated process renaming a parent:** detected at the final-path
  verification points (§7.2 open, §8.2 re-probe, §12 re-resolution);
  between the last check and the primitive's internal resolution it is the
  §4.4/§8.2 residual, covered only by the load-bearing assumption.
- **Simultaneous readers:** a reader holding the target open without
  delete sharing causes the primitive to fail; classified per §11.2 and
  never retried.

## 15. Proposed API

Proposed for the later separately approved implementation; **not**
implemented by this document.

### 15.1 Types

```text
triage_core/mediated_executor.py

TrustedTargetEntry            frozen dataclass
    target_file_id: str
    workspace_relpath: str
    maximum_size_bytes: int

MediatedTargetRegistry        frozen; built once by the trusted caller
    build_target_registry(workspace_root, entries) -> MediatedTargetRegistry

ReplacementResult             frozen dataclass; §16/§17 fields
    persistent_projection() -> dict   (privacy-gated, §17)

MediatedExecutorError         base
MediatedExecutorContractError caller/trusted-side defect; raises
```

### 15.2 The one entry point

```text
execute_replacement(
    registry: MediatedTargetRegistry,
    effect: AuthorizedContentEffect,
    proposed_bytes: bytes,
) -> ReplacementResult
```

The executor accepts **only** what its own claim needs:

- `AuthorizedContentEffect` — carries `target_file_id`,
  `canonical_relpath`, both digests, `content_size_bytes`. Accepted.
- `MediatedFileDescriptor`, `MediatedClientRequest`,
  `MediatedPlanLinkage` — **not accepted**. They prove request identity,
  reservation linkage, and decision linkage, none of which this slice's
  claim covers; accepting them would imply the executor checks things it
  does not. `MediatedFileEffect` is A's schema name for the effect object
  already covered above.
- Raw capability or reservation credentials — **not accepted**; the
  executor must not even appear to consume authority tokens.
- exact `bytes` — accepted; **only** the built-in immutable `bytes` type.
  `bytearray`, `memoryview`, and every other buffer are
  `invalid_executor_input`: a mutable buffer could change between the
  digest check and the write, making "the bytes verified are the bytes
  written" unprovable. (This is deliberately stricter than A's
  `verify_proposed_bytes`, which tolerates `bytearray` for hashing-only
  use.)

The API structurally cannot accept: caller-supplied target paths (no such
parameter exists), unbounded streams (no file-like or iterator input),
arbitrary metadata dictionaries, or free-form reason strings.

Proposed-content verification inside the call, independent of whatever the
caller already did — a typed effect object is *not* proof that A's
validation ran on these bytes:

```text
sha256(proposed_bytes) == effect.expected_post_digest   else proposed_content_mismatch
len(proposed_bytes)    == effect.content_size_bytes     else proposed_size_mismatch
len(proposed_bytes)    <= entry.maximum_size_bytes      else proposed_size_exceeded
UTF-8 validity gate (A's rule: a gate, not a normalization)
                                                        else invalid_executor_input
```

A's helpers are reused for the digest and UTF-8 gates rather than
re-derived. One additional in-memory copy of the content is permitted
transiently (e.g., a slice during chunked writing); the content is never
placed in any object that outlives the call. This entire block is
platform-neutral pure-core logic (§4.1) and is factored as such.

### 15.3 Error doctrine

Following A and B: **decisions about possibly untrusted-origin input**
return a `ReplacementResult` with a closed reason code — the effect's
field values originate on the proposal side, so their failures are
decisions, not bugs. **Trusted-side defects** raise
`MediatedExecutorContractError`. The split, pinned so implementation has
no discretion:

- raises: malformed registry construction, duplicate entry IDs, a value
  that is not a `MediatedTargetRegistry` where the registry belongs, a
  value that is not an `AuthorizedContentEffect` where the effect belongs
  (a typed effect object can only be built by A's validating constructors,
  so a non-effect here is always a caller bug), and an evidence payload
  that fails the in-module privacy gate;
- returns `invalid_executor_input`: `proposed_bytes` of any type other
  than built-in `bytes`, content failing the UTF-8 gate, and the §7.1
  degenerate identity transition.

Exception messages must carry no absolute path, no temporary or backup
name, no content bytes, and no security-descriptor material.

## 16. Closed Result and Reason Vocabulary

The complete reason vocabulary, each code naming an observable condition,
with its fixed outcome:

```text
reason_code                     outcome
------------------------------- -------------------------------
ok                              replacement_verified
invalid_executor_input          not_attempted
effect_registry_mismatch        not_attempted
platform_unsupported            not_attempted
target_id_unknown               not_attempted
target_missing                  not_attempted
containment_violation           not_attempted
target_not_regular_file         not_attempted
target_read_failed              not_attempted
target_observation_unstable     not_attempted
pre_size_exceeded               not_attempted
pre_digest_mismatch             not_attempted
metadata_precondition_failed    not_attempted
proposed_content_mismatch       not_attempted
proposed_size_mismatch          not_attempted
proposed_size_exceeded          not_attempted
temp_creation_failed            not_attempted
temp_write_failed               not_attempted
temp_file_failure               not_attempted
replacement_refused             target_unchanged
replacement_outcome_unknown     replacement_may_have_occurred
post_containment_lost           replacement_may_have_occurred
post_not_regular_file           replacement_may_have_occurred
post_digest_mismatch            replacement_may_have_occurred
post_size_mismatch              replacement_may_have_occurred
post_verification_failed        replacement_may_have_occurred
metadata_preservation_failed    replacement_may_have_occurred
```

Reservation rules, carried from A and B: each code is reserved narrowly for
the condition it names. A containment problem must not surface as a
registry problem; a proposed-size mismatch must not surface as a content
mismatch; an ambiguous replacement must never surface as
`replacement_refused`. Deliberately absent, because this module cannot
observe them: crash detection (only artifacts are observable, §13.3),
reservation and capability lifecycle conditions, broker or client
authenticity, ledger conditions, and cross-process interference as a
distinct cause (it is observable only through the mismatch codes above). A
code for an unobservable condition would be a false capability claim in
vocabulary form.

## 17. Privacy and Evidence

`ReplacementResult` is immutable and metadata-only:

```text
outcome                 closed vocabulary (§13.2)
reason_code             closed vocabulary (§16)
target_file_id          effect-authorized identifier
canonical_relpath       effect-authorized evidence path (workspace-relative)
effect_digest           binds the result to the exact effect executed
expected_pre_digest
expected_post_digest
content_size_bytes
observed_pre_digest     "" until computed; a digest, never content
observed_post_digest    "" unless the §12 read completed
platform_profile        literal "windows" in this slice
backup_retained         bool; per §11.3
```

`persistent_projection()` returns exactly these fields and runs
`assert_persistent_privacy_safe` over the exact payload before returning
it — in-module, following B's corrected pattern of gating what is actually
intended for persistence rather than a later copy of it.

The result, the projection, every exception, and every reachable repr must
**exclude**: proposed content in whole or part; previous content in whole
or part; content excerpts of any length; absolute filesystem paths;
temporary names; backup names; security descriptors, SIDs, ACE data, or
SDDL text; access tokens; raw reservation ownership tokens; raw capability
material; and exception strings that might embed any of the above (OS
errors are mapped to reason codes; their messages are not propagated into
evidence). Field names avoid the privacy invariant's forbidden keys by
construction (no field is named `content`, `token`, etc.).

## 18. Integration Boundary

CR-OC-001C explicitly:

- does not issue or claim capabilities;
- does not inspect or advance reservations;
- does not write the task ledger;
- does not expose a CLI;
- does not import OpenClaw or anything of it;
- does not create IPC of any kind;
- does not authenticate the broker connection;
- does not authenticate declared client context;
- does not make direct `authz.claim_capability` callers safer in any way;
- is not imported by any existing runtime module.

Permitted imports, closed: Python stdlib (`hashlib`, `os`, `stat`, `re`,
`dataclasses`, `typing`, `threading`, and — on the Windows paths only —
`ctypes` and `msvcrt`) plus `triage_core.mediated_effect` and
`triage_core.privacy_invariants`. Importing `triage_core.authz`,
`triage_core.capability_claims`, `triage_core.task_ledger`,
`triage_core.request_reservation`, `socket`, `subprocess`, or `sqlite3` is
a contract violation and is tested for (T30/T31).

The executor is invoked only by tests until a later separately approved
integration slice. Sequencing the reservation store in front of the
executor — the whole point of B — happens in that later slice, not here,
and nothing in this document is authority for it.

## 19. Test Contract

Designed before implementation. Tags: **[N]** — platform-neutral, runs
everywhere including Ubuntu CI, against the pure core (§4.1); **[W]** —
requires real Windows/NTFS, runs in the §4.3 Windows evidence pass.
Validation items tagged [W] whose logic lives in the pure core (items 3,
4, 10–13's input checks) additionally get [N] coverage against the
factored pure functions; the [W] run exercises them through the real entry
point.

1. [W] Only `target_file_id` selects the target: two registry entries with
   different files; the executed target is the entry's file, asserted by
   on-disk content.
2. [W] Changing `canonical_relpath` cannot redirect execution: registry
   maps id→A while the effect names existing file B with matching
   pre-content; result is `effect_registry_mismatch`; **both** A and B are
   byte-identical to their originals afterward.
3. [W] Unknown `target_file_id` → `target_id_unknown`, nothing touched;
   [N] duplicate IDs at registry construction raise
   `MediatedExecutorContractError`.
4. [N] Caller paths cannot enter the API: the entry point's signature
   accepts no path; a path-like `target_file_id` cannot exist (A's
   validation, re-asserted against the registry too); [N] the §6.2
   grammar rejections, including trailing-dot/space segments and reserved
   device names.
5. [W] A registry entry whose resolved target lies outside the workspace
   (constructed via a trusted-but-wrong root fixture) fails
   `containment_violation` before any read.
6. [W] Symlink and junction targets fail closed via reparse rejection; the
   link's destination file is untouched.
7. [W] Link/junction **ancestor** inside the workspace redirecting outside
   fails closed; a lexical prefix of the unresolved string would have
   passed, proving the check is not lexical. Includes a junction created
   after registry construction, caught by final-path verification.
8. [W] Directory targets fail `target_not_regular_file`.
9. [W] Missing target fails `target_missing`; asserts the target was not
   created and no creating disposition reached the target name.
10. [W] Existing-content digest mismatch → `pre_digest_mismatch`,
    `not_attempted`, target byte-identical afterward, no temp file left.
11. [W] Proposed-content digest mismatch → `proposed_content_mismatch`,
    target untouched.
12. [W] Proposed byte count ≠ `content_size_bytes` →
    `proposed_size_mismatch`, target untouched.
13. [W] Oversized existing content → `pre_size_exceeded`; oversized
    proposed content → `proposed_size_exceeded`; both leave the target
    untouched.
14. [W] Exact bytes preserved: CRLF pre-content with digest over exact
    bytes, BOM-carrying and NFD-form proposed bytes — replacement succeeds
    and the resulting file is byte-identical to `proposed_bytes`; no
    variant is ever silently reconciled.
15. [W] Temporary files are created exclusively (pre-seeding the temp name
    makes creation fail closed as `temp_creation_failed`, no retry) and in
    the target's own directory; the same exclusivity and collision test
    covers the backup name.
16. [W] Partial temporary writes never alter the target: fault-inject a
    short/failed write; result `temp_write_failed`, target byte-identical,
    temp removed.
17. [W] Temp content is flushed before replacement: a call-order recorder
    asserts the flush on the temp precedes the replacement primitive.
    (Designated killer for M10; implementation-shaped by necessity and
    recorded as such.)
18. [W] Replacement occurs on the same volume: the temp's and backup's
    parent directory equals the target's parent directory.
19. [W] Successful replacement produces exactly the expected bytes on
    disk, `replacement_verified`, `ok`, and the backup file is deleted.
20. [W] Owner gate and preservation: the §10.2 fault-injection seam
    returning a foreign owner SID pre-mutation yields
    `metadata_precondition_failed` with nothing attempted; on the real
    path, post owner SID equals pre owner SID.
21. [W] DACL invariant: the §10.1 structured comparison passes on a real
    replacement including a non-default explicit DACL on the target; an
    injected post-comparison difference in each participating component —
    owner SID, DACL three-state classification (absent versus NULL versus
    present-empty), a selected control bit, `AclRevision`, ACE count, ACE
    order, and a single differing byte inside one ACE's complete byte
    sequence — yields `metadata_preservation_failed` and outcome
    `replacement_may_have_occurred`. [N] the comparison function itself is
    pure over captured byte structures and is exhaustively tested
    platform-neutrally with crafted ACL buffers, including: a byte
    difference located in an object-ACE GUID region; a byte difference
    located in a callback-ACE application-data region; a difference only
    in `AceFlags`; an order swap of two otherwise-identical ACEs; an
    unknown ACE type compared as a complete opaque byte sequence (equal
    buffers pass, one differing byte fails); malformed `AceSize` values
    (zero, smaller than the header, running past the ACL's in-use bounds)
    failing closed rather than being compared; and two ACLs differing
    only in slack space beyond the enumerated ACEs comparing equal.
22. [W] Result remains a regular file (post-check asserted).
23. [W] Result remains in the workspace (post containment re-verification
    asserted; injected failure yields `post_containment_lost`).
24. [W] Postcondition mismatch produces the honest ambiguous outcome:
    fault-inject post-read divergence; outcome is
    `replacement_may_have_occurred`, never `target_unchanged`, never `ok`;
    the target is **not** written a second time (call-count recorder on
    the replacement primitive and on writes: exactly one replacement, no
    restore); and the backup file is retained.
25. [N] The §11.2 primitive-result classifier, as a pure function: success
    → verify; `ERROR_UNABLE_TO_REMOVE_REPLACED` (1175) →
    `replacement_refused`; `ERROR_UNABLE_TO_MOVE_REPLACEMENT` (1176) →
    `replacement_refused`; `ERROR_UNABLE_TO_MOVE_REPLACEMENT_2` (1177)
    and every other error → `replacement_outcome_unknown`. The 1175 case
    is asserted as its own distinct case — not via a shared refused-class
    fixture — so flattening 1175 into the ambiguous 1177 outcome fails
    this test (designated killer for M27). [W] end-to-end: injected
    1175-class and 1176-class failures each report `target_unchanged`
    with the target proven byte-identical and the temp removed; an
    injected 1177-class failure reports `replacement_may_have_occurred`
    with backup and temp retained.
26. [W] Two in-process attempts (real threads, house barrier pattern from
    `test_request_reservation._run_threads`) produce exactly one
    `replacement_verified`; the loser reports `pre_digest_mismatch`. [N]
    the degenerate pre==post effect is rejected as
    `invalid_executor_input` (its own test, asserting the reason is
    reported without any file being opened).
27. [N] Cross-process behavior is **explicitly excluded**, with a test
    asserting the module exposes no cross-process locking API and no
    result field or docstring claims cross-process exclusion. Recorded as
    a weak structural control in the style of A's M9; reviewers are the
    real control.
28. [B: N for the projection shape, W for a real run's payload] Persistent
    results contain no content and no absolute paths: canary content and
    canary-named workspace directories; the projection and its JSON
    serialization contain no canary, no drive letter, no root-anchored
    path, no `.tcx-` name, no SID or ACE material;
    `assert_persistent_privacy_safe` passes.
29. [W] Errors expose no proposed bytes or sensitive paths: for every
    closed failure code reachable by test, the raised/returned artifacts'
    `str`/`repr` contain no canary content and no absolute path.
30. [N and W] The implementation performs no network, subprocess, IPC,
    database, ledger, capability, or reservation operation: A's
    exploding-stub pattern (`socket`, `subprocess`, `sqlite3` stubs) while
    exercising the pure core everywhere and a full replacement on Windows
    — file I/O inside the workspace is expected and permitted, everything
    else explodes.
31. [N] No existing runtime module imports the executor: repository-wide
    import scan; only tests may import it.
32. [N] Unsupported platforms fail closed: on any non-Windows platform
    (and on Windows with a required-API probe forced to fail), every entry
    point reports `platform_unsupported` before any file is opened (open
    recorder asserts zero opens), rather than skipping any check.
33. [W] Backup lifecycle: on success the backup is deleted (T19); on
    injected backup-deletion failure the outcome stays
    `replacement_verified` with `backup_retained = true`; on every
    non-verified outcome where the backup exists it is retained; a
    pre-seeded file at the generated backup name fails closed before the
    primitive; the backup name matches the documented pattern and appears
    nowhere in result, projection, or errors.
34. [W] Identity re-probe: swapping the target file (same name, different
    file object) between validation and the probe seam yields
    `target_observation_unstable` with nothing mutated.

Each test targets a requirement or a plausible defective variant; tests
that merely restate implementation structure are avoided except where the
mutant contract forces one (T17, T18, parts of T33), and those are
labeled.

## 20. Mutant Contract

A mutant counts only if its designated killer test is demonstrated to
**fail** against the defective implementation during the later
implementation phase, per the standing CR-YK-002/A/B bar. Windows-scoped
mutants are exercised in the §4.3 Windows evidence pass. Tests that pass
under both intended and mutated behavior are controls, not mutant
evidence, and must be reported as controls.

| # | Deliberate defect | Designated killer |
|---|---|---|
| M1 | Resolve using `canonical_relpath` (registry bypassed) | T2 (file B untouched; mismatch reported), T3 (unknown id must not resolve) — the equality-preserving join variant is recorded unkillable (§6.3); reviewers are the control |
| M2 | Lexical containment only (string prefix over unresolved paths) | T7 (link ancestor passes lexically, must fail) |
| M3 | Follow the final symlink or reparse point | T6 |
| M4 | Skip ancestor checks | T7 |
| M5 | Omit pre-digest verification | T10 |
| M6 | Normalize content before hashing (newline/BOM/NFC) | T14 (refuses exact-CRLF pre or writes normalized bytes; either fails the byte-identity assertion) |
| M7 | Create the temporary or backup file outside the target directory, or in a world-readable shared location such as `%TEMP%` | T18 (parent-directory equality); the inherited-DACL window inside the target directory remains the §11.1 recorded limitation |
| M8 | Predictable temporary or backup name (counter or fixed name) | T15/T33: pre-seeding the deterministic name the mutant generates forces a collision failure where the intended random name succeeds |
| M9 | Permit partial writes to survive | T16 |
| M10 | Skip flush before replacement | T17 call-order recorder |
| M11 | Call the primitive with no backup name | T25[W] injected refused-class run: with no backup the documented state for that class is a deleted target, so the killer asserts the primitive was invoked with a backup name matching the documented pattern — implementation-shaped by necessity and labeled as such |
| M12 | Omit owner verification | T20 (injected foreign owner proceeds under the mutant) |
| M13 | Omit the DACL comparison entirely, or substitute SDDL string equality for the §10.1 structured rule | T21[N] component fixtures (SDDL round-trips can mask structural differences the crafted buffers expose); T21[W] injected differences report `ok` under the mutant |
| M14 | Report success before postcondition verification | T24 (injected post divergence reports `ok` under the mutant) |
| M15 | Flatten ambiguous post-replacement failure into `target_unchanged` | T24/T25 outcome assertions |
| M16 | Include an absolute path in persistent evidence | T28 |
| M17 | Include proposed bytes in an error or result | T29 |
| M18 | Claim cross-process exclusion while using only a process-local lock | T27 structural assertion — **recorded as weak**, reviewer-controlled, like A's M9 |
| M19 | Second automatic mutation during rollback without a fresh guard (including restoring from the backup) | T24 call-count recorder (exactly one replacement invocation, zero restores, backup retained) |
| M20 | Import or call reservation, capability, ledger, IPC, or subprocess machinery | T30 exploding stubs, T31 import scan |
| M21 | Delete the backup before post-verification completes, or on a non-verified outcome | T33 retention assertions; T24 backup-retained assertion |
| M22 | Omit object-type GUID data from the ACE comparison (parse object ACEs and compare only their common fields) | T21[N] object-ACE GUID-region byte-difference fixture |
| M23 | Omit callback/conditional application data from the ACE comparison | T21[N] callback-ACE application-data byte-difference fixture |
| M24 | Regress to comparing only ACE type, mask, and SID | T21[N] fixtures differing only in `AceFlags`, a GUID region, or application data |
| M25 | Ignore ACE order | T21[N] order-swap fixture (two otherwise-identical ACEs exchanged) |
| M26 | Accept an out-of-bounds or malformed `AceSize` (compare whatever parses) | T21[N] malformed-`AceSize` fixtures must fail closed; the mutant proceeds to a comparison and reports a result |
| M27 | Flatten `ERROR_UNABLE_TO_REMOVE_REPLACED` (1175) into the ambiguous 1177 outcome | T25[N] distinct 1175 assertion; T25[W] 1175-class end-to-end (`target_unchanged`, target byte-identical) |

Controls, identified in advance: the healthy-path test (T19), determinism
of the projection key set, and the vocabulary-membership test all pass
under most mutants and are counted as controls only.

## 21. Acceptance Contract

CR-OC-001C may be considered implemented only when:

- explicit human implementation approval was granted first, and the diff
  stays within the approved allowlist (§22);
- all [N] items pass in CI on `ubuntu-latest` across the supported Python
  matrix, **and** all [W] items pass with real Windows/NTFS evidence from
  one of the two §4.3 sources — a separately approved Windows CI job, or a
  recorded local Windows run captured in the implementation record with
  commit hash, Python version, and OS build. A green Ubuntu CI run alone
  cannot satisfy acceptance;
- every §20 mutant is demonstrated failing against its defective variant
  (Windows-scoped mutants in the Windows evidence pass), with the module
  hash verified pristine after each cycle, and controls reported as
  controls;
- the §12.6/§17 privacy gate runs in-module over the exact projection
  payload and passes;
- the full test suite passes with no new `xfail`;
- `git diff --check` passes;
- `triage_core/authz.py`, `triage_core/capability_claims.py`,
  `triage_core/request_reservation.py`, `triage_core/task_ledger.py`,
  `triage_core/client.py`, and `triage_core/tc_cli.py` are unmodified;
- no runtime module imports the executor; only tests do;
- no new package dependency was added;
- the implementation record states which Microsoft or Python documentation
  each load-bearing platform behavior rests on, and which behaviors were
  verified by test rather than documentation (§24's obligations resolved
  or narrowed).

Recording this proposal satisfies none of these items.

## 22. Provisional Implementation Allowlist

Proposed — **not authorized** — for the later implementation slice:

```text
triage_core/mediated_executor.py
tests/test_mediated_executor.py
docs/change/requests/CR-OC-001C-constrained-single-file-replacement-executor.md
docs/current_backlog.md
docs/change/change_log.md
```

The Windows `ctypes` code lives inside `triage_core/mediated_executor.py`.

**Named unresolved allowlist candidates, each requiring explicit approval
before it may be touched, never added silently:**

- `.github/workflows/tests.yml` — only if a Windows CI job (§4.3) is
  chosen as the Windows evidence source. Without that approval, the
  recorded local Windows run is the evidence mechanism and CI stays
  unmodified.
- `triage_core/mediated_executor_win32.py` — only if implementation review
  concludes a separate platform helper file is genuinely necessary for
  reviewability.

Expected to remain unmodified unless a separate change request proves
otherwise:

```text
triage_core/authz.py
triage_core/capability_claims.py
triage_core/request_reservation.py
triage_core/task_ledger.py
triage_core/client.py
triage_core/tc_cli.py
```

This candidate list confers no implementation authority.

## 23. Downstream Sequence

```text
CR-OC-001A  pure effect contract                    complete and merged
CR-OC-001B  atomic client-request reservation       complete and merged
CR-OC-001C  constrained replacement executor        this proposal
CR-OC-001D  privilege-separated broker and pipe     unauthorized
CR-OC-001E  exclusive OpenClaw tool and schema      unauthorized
```

Each slice retains its own requirements approval, implementation approval,
merge approval, and closeout. Runtime orchestration — wiring reservation,
capability claiming, and this executor into one governed path — belongs to
a later separately approved slice and is not begun by anything here. A
POSIX mutating profile, if ever wanted, is likewise its own separately
approved contract addendum (§24).

## 24. Limitations and Unresolved Uncertainty

Recorded rather than glossed:

- **Nothing here is implemented.** Every claim above is a requirement on a
  future implementation, not a property of existing code.
- **Windows atomicity is not claimed and cannot be upgraded by wording.**
  If a future reviewer wants an atomic Windows claim, that is new OS
  research and a contract change, not an implementation detail.
- **The unclosable race is stated, not solved.** Between the §8.2 identity
  re-probe and `ReplaceFileW`'s internal name resolution, and again
  between the primitive and §12's re-resolution, correctness rests on the
  load-bearing no-concurrent-writer assumption. No handle the executor
  holds constrains the primitive's own name resolution.
- **`ReplaceFileW`'s documented error-state contract is trusted for
  exactly three error codes.** The implementation must verify at
  implementation time, against current Microsoft documentation, the
  precise wording for `ERROR_UNABLE_TO_REMOVE_REPLACED` (1175: the
  replaced and replacement files retain their original file names),
  `ERROR_UNABLE_TO_MOVE_REPLACEMENT` (1176: with backup, both files
  retain their original names), and `ERROR_UNABLE_TO_MOVE_REPLACEMENT_2`
  (1177: replacement at its original name; replaced file at the backup
  name), and must cite it in the implementation record. If the
  documentation does not support the `target_unchanged` classification
  for the 1175 or 1176 class, that class reclassifies to
  `replacement_may_have_occurred` — the claim narrows; the code never
  guesses.
- **The structured DACL comparison covers what it lists.** SACL, primary
  group, and provenance-only control bits are excluded with stated
  reasons (§10.1); a future reviewer who wants them covered is asking for
  a contract change.
- **The temp-file DACL-inheritance window** (§11.1) is a stated exposure
  bounded by the parent directory's ACL; hardening via `SetSecurityInfo`
  is deferred and would need approval.
- **The equality-preserving relpath-join mutant is unkillable by test**
  (§6.3, M1); reviewers are the control.
- **Cross-process concurrency is excluded, not solved** (§14, T27).
- **Crash durability of the name flip is not claimed** (§4.2).
- **NTFS per-directory case sensitivity** is a recorded containment
  residual (§7.2).
- **Windows evidence is environment-dependent.** Junction creation,
  explicit DACL manipulation, and foreign-owner scenarios may behave
  differently on hosted Windows runners than on a developer machine; the
  implementation record must state where each [W] item actually ran.
- **A future POSIX profile must not reuse this contract's metadata rules
  blindly.** Mode-bit equality does **not** establish access-control
  preservation where POSIX extended ACLs (`system.posix_acl_access`) or
  NFSv4 ACLs may exist; a POSIX addendum must either compare full ACLs,
  fail closed when extended ACLs are present, or explicitly narrow its
  claim to mode-bit preservation. Recorded here so the lesson is not
  relearned.
- **This slice proves nothing about the lane's end goal.** A working
  executor does not make OpenClaw containable, does not authenticate
  anything, and must not be cited as progress on CR-OC-001D or CR-OC-001E
  claims.
