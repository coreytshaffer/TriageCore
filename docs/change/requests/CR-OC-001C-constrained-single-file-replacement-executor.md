# CR-OC-001C: Constrained Single-File Replacement Executor

## 1. Status and Authority

- **Requirements status:** Accepted and merged. The requirements contract
  (§2–§24) was merged through PR #125 as merge commit
  `0b2b8a5e4397a903f5a48a07be8c86f6701ad5b8`, unamended from the reviewed
  draft. It is the authoritative baseline for everything below, as amended
  by §10.1a (`SE_DACL_AUTO_INHERITED` monotonic rule), §10.2a
  (`TokenOwner`), and §10.2b (supported DACL profile). Each amendment was
  discovered by running the contract against real Windows evidence.
  Implementation is corrected only after the corresponding
  documentation-only amendment merges; the §10.2b implementation correction
  remains pending on draft PR #128.
- **Implementation status:** Authorized and in progress on draft PR #128;
  **not merged, not accepted, and not runtime-integrated.** The
  implementation does not yet conform to §10.2b: the supported-profile
  gate, revised fixtures, T21 evidence, and M31 remain pending. §25 remains
  the planning artifact it was written as — an allowlist, module split,
  plan, evidence design, and acceptance boundary.
- **Implementation authority:** Granted separately and explicitly, bounded
  to the seven-path allowlist of §25.1 and to the work on draft PR #128. It
  did **not** come from this document: neither the merged requirements nor
  §25 authorizes code, tests, fixtures, a dependency change, a CI change, a
  CLI or `tc run` change, runtime integration, a capability or reservation
  change, IPC, Windows account work, or OpenClaw installation or
  configuration. **Merging the requirements was not implementation
  authority, and drafting §25 is not implementation authority.** No
  authority extends beyond that allowlist, and none of it is merge
  authority.
- **Approval gate:** Explicit human approval was required before
  implementation and is required again before any merge. Recording a
  proposal satisfies neither, and the implementation approval already
  granted is not merge approval.
- **Still unauthorized:** CR-OC-001D, CR-OC-001E, and every runtime surface.

Sections 2–24 define the requirements an implementation must satisfy. They
are written so that an implementation agent cannot choose materially
different safety semantics without returning for approval. Where this
document says "must", a conforming implementation has no discretion; where
it says "recorded rather than glossed", the limitation is part of the
contract and may not be papered over with stronger wording later.

Section 25 is a separate, clearly bounded implementation proposal written
against that merged baseline. Where §25 and §2–§24 could be read as
disagreeing, the merged requirements govern and §25 is the defect.

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
3. **Selected control bits** — from `GetSecurityDescriptorControl`.
   `SE_DACL_PRESENT` and `SE_DACL_PROTECTED` must be **equal**.
   `SE_DACL_AUTO_INHERITED` follows the **monotonic rule** below rather than
   strict equality.

   **`SE_DACL_AUTO_INHERITED`, amended after an implementation-discovered
   contract defect (§10.1a):**

   ```text
   False -> False    accepted
   False -> True     accepted as Windows normalization
   True  -> True     accepted
   True  -> False    rejected
   ```

   The `False -> True` exception is accepted **only when every other
   owner/DACL component in this section is exactly preserved** — owner SID,
   three-valued DACL state, `SE_DACL_PRESENT`, `SE_DACL_PROTECTED`, ACL
   revision, ACE count, and ordered complete ACE bytes. It must never excuse
   an ACE difference, an ordering difference, a revision, protection,
   presence, owner, or DACL-state difference. An implementation that lets
   this exception widen to any other component is non-conforming.
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

### 10.1a Implementation-discovered contract correction

This subsection records why `SE_DACL_AUTO_INHERITED` is governed by a
monotonic rule rather than the strict equality the contract originally
required. It is a **contract-discovery result found during implementation**,
before any test hardened the defect into permanent, misleading behavior.

**The observation.** On Windows/NTFS, a successful `ReplaceFileW` against a
file whose descriptor did not already carry `SE_DACL_AUTO_INHERITED` sets
that bit on the resulting file, while preserving every access-bearing
component exactly. Measured locally through the implemented adapter:

```text
BEFORE  control = (PRESENT=True, PROTECTED=False, AUTO_INHERITED=False)
        owner   = S-1-5-21-...-1001    revision = 2    ace_count = 3
AFTER   control = (PRESENT=True, PROTECTED=False, AUTO_INHERITED=True)
        owner   = S-1-5-21-...-1001    revision = 2    ace_count = 3
        all three complete ACE byte sequences byte-identical,
        including their AceFlags
```

The behaviour is systematic and one-directional: across repeated
replacements of the same file the bit stayed `True` and the ACEs stayed
byte-identical; a file already carrying the bit was stable in every
component across further replacements; and no observed transition ever
cleared a bit or altered an ACE.

**Why this is a contract defect rather than an adapter defect.**
`ReplaceFileW` is documented to preserve the replaced file's DACL, and it
did — the ACEs, which are what grant and deny access, were preserved
byte-for-byte. Its documentation does not promise byte-for-byte equality of
every security-descriptor *control flag*. The original requirement demanded
a guarantee the platform never offered, so as written it would have reported
`metadata_preservation_failed` for the first replacement of essentially any
inherited-DACL repository file — an honest report of a mis-specified
invariant, not of a real access change.

**Why complete exclusion was rejected.** Microsoft describes
`SE_DACL_AUTO_INHERITED` as indicating that the DACL supports the automatic
inheritance model, and Windows security APIs may set it when that model is
applied. That makes it more than a disposable provenance marker, even though
the bit grants and denies no access by itself — unlike `SE_DACL_DEFAULTED`,
which this section still excludes outright. Dropping the bit entirely would
also accept the opposite `True -> False` transition, which is **broader than
the evidence supports**: nothing observed produces it, and a descriptor
leaving the auto-inheritance model is a change this contract has no basis to
wave through.

**Why `True -> False` remains a failure.** It was never observed, it is not
a documented normalization, and it would represent the descriptor moving out
of the model rather than into it. Absent evidence, it stays a failure —
narrowing the claim rather than widening the exception.

**What this is not.** The accepted `False -> True` transition is an
**allowed normalization, not proof that Microsoft guarantees it** on every
Windows version, edition, filesystem configuration, or ACL shape. It is
local evidence from one machine, generalized only as far as "when this
occurs alongside exact preservation of every access-bearing component, do
not report a metadata failure."

**Reproduction is observational, not a merge gate.** The hosted Windows job
attempts the same replacement and **records which transition it observed**,
but not reproducing `False -> True` is not a failure. Requiring
reproduction would contradict this section directly: the invariant accepts
`False -> False`, `False -> True`, and `True -> True`, so a runner that
produces `False -> False` has exhibited another explicitly accepted
transition rather than disproving anything — and treating that as a merge
blocker would turn a single machine's observation into the very platform
guarantee this section denies.

What the hosted job **must** fail on is a `True -> False` transition, or any
other owner/DACL component differing. Those are real violations of the
amended invariant. The deterministic evidence for the rule itself is
platform-neutral (§19 T35, T36): the `False -> True` acceptance and its
narrow gating are proven by constructing the snapshots directly, which needs
no Windows at all.

### 10.2 How preservation is achieved, not just checked

The executor cannot transplant a foreign owner onto the replacement file:
the temporary file is created by, and owned by, the executing account, and
`ReplaceFileW`'s documented preservation list covers DACLs, creation time,
short name, object identifier, encryption, compression, and named streams
— **not** the owner. The requirement is therefore made satisfiable by a
precondition:

- **Pre-mutation ownership gate:** before any temporary file is created,
  the target's owner SID must equal the **token's default owner** — the SID
  from `OpenProcessToken` + `GetTokenInformation(..., TokenOwner, ...)`
  (information class `4`). Failure is `metadata_precondition_failed`, not
  attempted. This converts an unpreservable case into a refusal instead of
  a broken promise. See §10.2a for why this is `TokenOwner` and not
  `TokenUser`.
- **Supported-profile gate:** before any temporary file is created, the
  target's pre-mutation DACL must be present, non-NULL, and protected from
  inheritance. Failure is `metadata_precondition_failed`, not attempted.
  See §10.2b. **The supported-profile gate is evaluated immediately after
  validating the pre-mutation security snapshot and before the
  `TokenOwner` ownership gate** — despite the order these two bullets are
  written in. That ordering gives T21's absent, NULL, and unprotected
  cases a precise cessation point, and avoids querying the token's default
  owner for a profile already known to be unsupported.
- **DACL carry-over, scoped to the supported profile:** `ReplaceFileW` is
  documented to give the resulting file the replaced file's DACL, which is
  the load-bearing reason §11 selects it over `MoveFileExW` (whose result
  would carry the temporary file's directory-inherited DACL instead). That
  documentation is **not** treated as establishing general exact
  preservation: hosted evidence (§10.2b) shows an inheritance-enabled
  target differing in `SE_DACL_AUTO_INHERITED`, ACE count, and the ordered
  ACE bytes across a *successful* call, while a present-and-protected
  target was exactly preserved under the same comparison. Documentation is
  trusted to **choose the primitive**, never to skip the check.
  Post-verification (§12) still performs the full §10.1 comparison and
  remains the deciding evidence.

### 10.2a Implementation-discovered contract correction: `TokenOwner`

This subsection records why the ownership gate reads the token's **default
owner** rather than its user. Like §10.1a, it is a contract-discovery result
found by running the contract, not by reading it.

**The two token quantities answer different questions.** `TokenUser`
identifies the user account associated with the access token. `TokenOwner`
is the **default owner SID applied to newly created objects**: when a process
creates an object without supplying an explicit owner in a security
descriptor, Windows takes the owner from the token's default owner. The two
frequently coincide, and on many ordinary accounts they always do.

**Only `TokenOwner` answers the question this gate asks.** The gate exists
because `ReplaceFileW`'s documented preservation list covers the replaced
file's DACL, timestamps, short name, object identifier, encryption,
compression, and named streams, but **not** the owner — and the resulting
file retains the replacement file's identity. The precondition therefore has
to reason about the owner Windows will actually assign to the temporary
object this process is about to create. Comparing the target's owner against
`TokenUser` answers a different question — "is this object owned by the
token's user identity?" — and says nothing about the owner the new object
will receive.

**Discovery trigger: hosted run `30686689771`.** The first hosted execution
of the `windows_executor` job against the implementation reported:

```text
NTFS verification            passed
mandatory executor group     131 passed, 34 failed
all 34 failures uniform      metadata_precondition_failed
structured-result gate       correctly did not run after the failure
```

Every failure reached the ownership gate's closed refusal path before
mutation. Because the implementation compared the target owner against
`TokenUser`, while `TokenOwner` is the quantity governing the default owner
of newly created objects, the hosted run exposed the contract defect. The
job did not disclose SID values and therefore does not establish the exact
SID relationship on that runner.

Local evidence had been green because the gate passed in the development
environment; no persisted evidence established whether or why `TokenUser`
and `TokenOwner` coincided there. The zero-skip and fail-closed design of
the job is what surfaced the defect rather than letting it pass quietly.

**Scope of the claim, stated carefully.** This amendment does **not** assert
that hosted runners necessarily execute elevated, nor that the target's owner
was any particular well-known SID. Those would be unverified explanations of
*why* the two values differed, and the contract defect does not depend on
proving them: `TokenUser` was the wrong quantity for this precondition
regardless of which specific SIDs a given machine reports.

**No raw SIDs leave the process.** SID values are necessarily read into
memory — the gate cannot compare owners without them, and `capture_security`
and `GetTokenInformation` both return them. What is forbidden is disclosure
and persistence: no raw SID is logged, serialized, persisted, placed in
JUnit, included in the bounded job summary, or otherwise emitted. Tests may
compare SID values in memory but report only equality or inequality. §17's
exclusion of SIDs from results, projections, errors, JUnit, and the job
summary is unchanged.

The `ctypes` code lives inside the executor module itself under the
proposed allowlist (§22) — no new dependency (no pywin32), no subprocess
(`icacls` is forbidden by the no-subprocess rule), no smuggled helper
module. If implementation finds a separate platform helper file genuinely
necessary, that is an allowlist change requiring explicit approval first.

### 10.2b Implementation-discovered contract correction: the supported DACL profile

This subsection narrows the **supported target profile** rather than
weakening the invariant. Like §10.1a and §10.2a, it is a contract-discovery
result found by running the contract, not by reading it.

**The requirement.** CR-OC-001C supports only targets whose pre-mutation
DACL is **present, non-NULL, and protected from inheritance**
(`SE_DACL_PROTECTED` set). Any absent DACL, NULL DACL, or
inheritance-enabled DACL is refused as `metadata_precondition_failed` with
outcome `not_attempted`, **before temporary-file creation and before any
replacement attempt**.

**What this amendment does and does not change:**

- The exact owner, DACL state, control-bit, `AclRevision`, ACE-count,
  ACE-order, and complete-ACE-byte invariant of §10.1 is **unchanged**. No
  comparison is relaxed, made unordered, made partial, or replaced by an
  effective-permissions rule.
- The §10.1a `SE_DACL_AUTO_INHERITED` monotonic rule is **unchanged**.
- Post-verification (§12) remains **mandatory and authoritative**. The
  narrowed profile is a precondition, never a substitute for checking.
- Unsupported targets are **not normalized, repaired, protected
  automatically, or attempted**. The executor never modifies a security
  descriptor to make a target supportable; it refuses.
- This amendment narrows the supported profile. It does **not** claim that
  Microsoft guarantees exact DACL preservation for all protected DACLs.

**Why an effective-permissions rule was rejected.** Relaxing the comparison
to "same effective permissions" would be materially harder to prove safely
than exact equality: ACE order affects access decisions, and common
effective-rights helpers omit owner rights, privileges, logon-session
groups, resource-manager policy, and some inherited-deny cases. Exact
equality over a narrower profile is the conservative direction.

**Discovery record.** Three hosted `windows_executor` runs, in sequence:

```text
30689442321:
  unprotected target differed in
  dacl_auto_inherited, ace_count, ace_bytes_or_order

30690450931:
  paired protected control did not fail, but was under-asserted

30691068391:
  strengthened protected control passed all fixture, result,
  outcome, exact-byte, and exact-metadata assertions
  unprotected control reproduced the same three differences
```

The middle run is recorded deliberately. The protected control's *absence
from the failure list* was not evidence: as first written it failed only on
a metadata label beyond `dacl_auto_inherited`, so a refusal such as
`temp_creation_failed` accompanied by no metadata differences would also
have passed it — and the recorded result property was unrecoverable,
because the mandatory command failed before the gate or summary exposed it
and no artifact is uploaded. The control was strengthened to require,
simultaneously, a protected and nonempty fixture, `reason_code == ok`,
outcome `replacement_verified`, target bytes equal to the proposed bytes,
and metadata differences of none or `dacl_auto_inherited` alone.

**What run `30691068391` establishes, stated narrowly:**

> On the hosted runner, the unprotected profile violated the exact
> invariant, while the present-and-protected profile completed a verified
> replacement under the exact same comparison.

**What it does not establish.** It does **not** prove that inheritance
recomputation is the underlying Windows mechanism. The diagnostic reported
field labels only; it did not establish that every new or changed ACE was
inherited, nor that effective access was unchanged. Microsoft documents
`ReplaceFileW` as preserving the DACL, and separately describes the
operation as merging attribute and ACL information into the replacement
file; it does not promise byte-identical ACE enumeration in every
inheritance environment. Automatic inheritance can set
`SE_DACL_AUTO_INHERITED`, materialize inherited ACEs, and order inherited
entries after explicit ones. The governance conclusion above does not
depend on which of these explanations is correct.

**The hosted environment, recorded as bounded evidence:**

```text
Windows Server 2025
build 10.0.26100
windows-2025-vs2026
Python 3.12.10
NTFS
```

This is evidence from one bounded environment, **not a universal Windows
guarantee**.

**`pre_dacl_nonempty` was a diagnostic validity control, not a production
requirement.** Its only purpose was to prove the hosted success was not a
trivial empty-ACL comparison. The executor does **not** require a nonempty
DACL: a present, non-NULL, protected DACL with zero ACEs remains supported,
and §10.1's three-state classification continues to distinguish
present-empty from NULL and absent.

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
must surface, not be swallowed. That the operation *merges* rather than
verbatim-copies ACL information is precisely why §10.2b restricts the
supported profile and why §12's post-verification, not the documentation,
decides whether the invariant held. A **backup name is always supplied**
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
20. [W] Owner gate and preservation, against the token's **default owner**
    (§10.2a). Revised rather than supplemented, so the obligation count is
    unchanged. Three parts:

    - **injected incompatible default owner** — the seam returning a
      default owner that differs from the target's owner yields
      `metadata_precondition_failed` with nothing attempted and no
      artifacts left behind;
    - **genuine newly created file** — a file created by this process
      without an explicit security descriptor has an owner equal to the
      token's default owner, proving the gate compares the quantity that
      actually governs the temporary file's ownership. Equality-shaped
      only: **no SID value is recorded or emitted**;
    - **supported-profile replacement passes the ownership gate** — a
      target created by this process, then placed into a present,
      non-NULL, protected DACL profile **without changing its owner**,
      reaches `replacement_verified`, and post owner equals pre owner. The
      profile qualifier is required by §10.2b: an inheritance-enabled
      target must refuse before mutation, so a healthy result may not be
      asserted for an unrestricted "ordinary" target.
21. [W] DACL invariant **and supported-profile gate** (§10.2b). Four
    parts. (a) **Unsupported profile refuses before mutation:** a target
    whose DACL is present but *unprotected* is refused with
    `metadata_precondition_failed` and outcome `not_attempted` **before
    temporary-file creation and before `ReplaceFileW`**, asserted from the
    mechanism call log; the target's original bytes are unchanged and no
    temporary or backup artifact remains in the directory. (b)
    **Seam-injected absent and NULL DACL states refuse identically**, with
    the same reason code, outcome, cessation point, byte preservation, and
    artifact absence. (c) **Supported profile completes:** a present,
    non-NULL, protected target yields `ok`, outcome
    `replacement_verified`, target bytes exactly equal to the proposed
    bytes, and the full exact metadata invariant of §10.1 preserved. (d)
    **Injected post-replacement differences still fail:** the §10.1
    structured comparison passes on a real replacement including a
    non-default explicit DACL on the target; an
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
35. [N and W] The `SE_DACL_AUTO_INHERITED` monotonic rule accepts
    `False -> True` **only** alongside exact preservation of every other
    owner/DACL component.

    [N] The deterministic half, and the one that carries the rule: the pure
    comparison is handed **directly constructed** snapshots and accepts
    `False -> False`, `False -> True`, and `True -> True`; it then rejects
    the `False -> True` pair as soon as any one of owner SID, DACL state,
    `SE_DACL_PRESENT`, `SE_DACL_PROTECTED`, ACL revision, ACE count, ACE
    order, or any ACE byte also differs — asserted per component, so the
    exception cannot widen. No Windows is involved and nothing is left to
    what a runner happens to do.

    [W] The observational half: a genuine NTFS replacement starts from a
    **confirmed pre-state** — the pre-replacement value of the bit is
    captured and asserted, **and the target is confirmed to be within the
    §10.2b supported profile (DACL present, non-NULL, protected) before the
    replacement** — performs the replacement, and requires that the
    observed transition be one of the three accepted transitions, that
    every other owner/DACL component be exactly preserved, and that the
    result be `replacement_verified`. The observed transition is recorded.
    **Failing to reproduce `False -> True` is not a failure** — a runner
    that yields `False -> False` has exhibited another accepted transition
    (§10.1a). The test fails on `True -> False`, on any other metadata
    difference, or on a non-verified outcome.
36. [N] The monotonic rule rejects `True -> False`: a snapshot pair
    identical in every other component but clearing
    `SE_DACL_AUTO_INHERITED` fails the comparison and, through the
    executor, reports `metadata_preservation_failed`.

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
| M28 | Replace the `SE_DACL_AUTO_INHERITED` monotonic rule with strict equality (the pre-amendment defect) | T35[N] — the directly constructed `False -> True` pair is rejected under the mutant. Killed deterministically, without depending on what a hosted runner exhibits |
| M29 | Ignore `SE_DACL_AUTO_INHERITED` entirely (the rejected complete-exclusion option) | T36 `True -> False` rejection — the mutant accepts it |
| M30 | Query `TokenUser` instead of `TokenOwner` in the ownership gate (the pre-amendment defect, §10.2a) | T20's **deterministic instrumented** assertion that the adapter requests information class `TokenOwner` (`4`). Uses a fake or instrumented `GetTokenInformation`, so the kill does **not** depend on the two SIDs happening to differ on the machine under test — otherwise the mutant would survive on any host where they coincide, which is exactly how the defect escaped local evidence |
| M31 | Omit the present-and-protected DACL precondition, or treat an inheritance-enabled target as supported (the pre-amendment defect, §10.2b) | T21[W] unprotected-target test: asserts refusal **before** temporary-file creation or `ReplaceFileW` (mechanism call log), original bytes unchanged, and no artifacts left behind. Venue: Windows |

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
- **the supported DACL profile (§10.2b) is enforced and evidenced:** every
  healthy replacement case in the Windows evidence pass uses a target whose
  DACL is present, non-NULL, and protected from inheritance; T35[W]
  confirms that supported pre-state **before** the replacement; every other
  participating owner/DACL component is exactly preserved; absent, NULL,
  and unprotected profiles are shown failing **before mutation** with
  `metadata_precondition_failed` / `not_attempted` (T21[W]); and M31 is
  killed cleanly;
- the hosted Windows job observes a `SE_DACL_AUTO_INHERITED` transition
  that is one of the three §10.1a accepted transitions, with every other
  owner/DACL component exactly preserved, and records which transition it
  saw. **Reproducing `False -> True` specifically is not required**:
  `False -> False` is an accepted transition, so requiring the
  normalization would contradict §10.1a and elevate one machine's
  observation into a platform guarantee. The job fails on `True -> False`
  or on any other metadata difference;
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

**Both named unresolved candidates have since been resolved into scope by
the operator, and §25.1 supersedes this five-path list with the settled
seven-path allowlist.** This section is retained as the requirements-era
record of what was open at merge time:

- `.github/workflows/tests.yml` — was conditional on choosing a Windows CI
  job (§4.3) as the evidence source. **Resolved: a dedicated repeatable
  Windows job is the evidence mechanism** (§25.7), so this path is in
  scope.
- `triage_core/mediated_executor_win32.py` — was conditional on a separate
  platform helper being necessary for reviewability. **Resolved: the
  helper is required** (§25.2), so this path is in scope, and the Windows
  `ctypes` code lives there rather than in `mediated_executor.py`.

Resolving these two candidates enlarged the allowlist by exactly two paths,
by explicit operator decision recorded in §25.1 — not silently, and not by
implementation discretion.

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
CR-OC-001C  constrained replacement executor        requirements merged;
                                                    implementation proposed
                                                    (§25), unauthorized
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
- **The `SE_DACL_AUTO_INHERITED` normalization is local evidence, not a
  documented platform guarantee.** §10.1a accepts `False -> True` because
  that is what one Windows/NTFS machine did, repeatedly, alongside exact
  preservation of every access-bearing component. Microsoft documents that
  `ReplaceFileW` preserves the replaced file's DACL; it does not document
  byte-for-byte stability of every control flag in either direction. The
  accepted transition may therefore vary by Windows version, edition,
  filesystem configuration, or ACL shape. That variability is exactly why
  hosted reproduction of `False -> True` is **observational rather than an
  acceptance gate** — `False -> False` is itself accepted, so demanding the
  normalization would convert one machine's observation into the platform
  claim this contract refuses to make. `True -> False` stays a failure
  precisely because no evidence supports it, and the rule itself is proven
  deterministically off Windows (§19 T35[N], T36).
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

---

# Part II — Implementation Proposal

## 25. Implementation Proposal (planning only — grants no authority)

This part is a **planning and authorization proposal** drafted against the
requirements contract merged as `0b2b8a5e4397a903f5a48a07be8c86f6701ad5b8`.
It proposes *how* the contract would be satisfied and *what evidence* would
be produced. It writes no code and authorizes none.

### 25.1 The exact implementation allowlist

Seven paths, settled by operator decision, closed:

```text
triage_core/mediated_executor.py
triage_core/mediated_executor_win32.py
tests/test_mediated_executor.py
.github/workflows/tests.yml
docs/change/requests/CR-OC-001C-constrained-single-file-replacement-executor.md
docs/current_backlog.md
docs/change/change_log.md
```

No other path may be created, modified, deleted, renamed, or implied. In
particular the implementation adds **no new package dependency** (no
pywin32), touches no other workflow, and leaves unmodified:

```text
triage_core/authz.py
triage_core/capability_claims.py
triage_core/request_reservation.py
triage_core/task_ledger.py
triage_core/mediated_effect.py
triage_core/client.py
triage_core/tc_cli.py
pyproject.toml
```

Discovering that any eighth path is needed is a **stop condition** (§25.10),
not an implementation decision.

### 25.2 Module split and dependency direction

Dependency direction is strictly one-way, with no cycle:

```text
tests/test_mediated_executor.py
        |
        v
triage_core/mediated_executor.py        (policy, platform-neutral core)
        |  imports ONLY inside the Windows-gated path, never at module scope
        v
triage_core/mediated_executor_win32.py  (mechanism, Windows-only adapter)
```

**`triage_core/mediated_executor.py` — policy and orchestration.** Owns:
immutable public and internal contract types; trusted target-registry
construction and validation; platform-neutral input validation; exact
proposed-content checks; the closed outcome and reason vocabulary; pure
`ReplaceFileW` result classification; the metadata-only privacy-safe result
projection; the process-local orchestration lock; the Windows platform
gate; and high-level sequencing. It performs **no direct Win32 structure
parsing** — it never interprets a security-descriptor, ACL, or ACE layout,
and never touches `ctypes` or `msvcrt`. It receives already-extracted plain
Python values from the helper and reasons over them.

**`triage_core/mediated_executor_win32.py` — a private Windows-only
adapter.** Provides narrowly typed mechanism operations: opening targets
without ever accepting a caller path; final-path and NTFS/workspace
verification; file-identity capture; reparse and regular-file checks; exact
bounded reads and writes; exclusive private same-directory temporary
creation; flushing and closing; owner and DACL capture including complete
ordered ACE-byte extraction with `AceSize` bounds validation; `ReplaceFileW`;
backup deletion only after verified success; and the bounded cleanup
operations the contract permits.

It must contain **no** policy decision, outcome classification, persistence,
logging, capability logic, reservation logic, ledger access, IPC, OpenClaw
code, subprocess use, or network access. It raises a narrow adapter error or
returns plain values; it never decides what an error *means*.

**Import safety.** `mediated_executor.py` must import cleanly on
non-Windows and perform **zero filesystem access** at import time. The
helper is imported dynamically, inside the Windows-gated code path only and
only after the gate has passed — `ctypes.windll` does not exist off
Windows, so a module-scope import would break the neutral core on Ubuntu. A
test asserts the absence of a module-scope helper/`ctypes`/`msvcrt` import
(§25.5, T31).

**The dependency is one-way, and no type crosses it upward.**
`mediated_executor_win32.py` **must not import
`triage_core.mediated_executor`**, must not reference any core-owned type,
and must not import any other TriageCore module. It owns its own private
value type (`Win32SecurityCapture`, §25.3.4) carrying mechanism-level
primitive data only. The core receives that capture, validates it, and
converts it into the core-owned `SecuritySnapshot` before any policy runs.

An earlier draft of this proposal had the helper hand back a core-owned
`SecuritySnapshot` directly. That was a defect: it would have required the
helper to import the core, contradicting the one-way direction claimed in
this very section. The two-type seam below is the correction. **No third
shared module is introduced** to hold a common type — that would be an
eighth path (§25.1) and is non-conforming.

**Why the split, given the contract preferred a single module.** The merged
contract left the helper as an unresolved candidate "only if implementation
review concludes a separate platform helper file is genuinely necessary for
reviewability" (§22). The operator has resolved it into scope, and the
reviewability argument is concrete: the ACE-comparison rule (§10.1) is the
single most defect-prone requirement in this slice, and splitting *parsing*
(helper, Windows-only, untestable on CI's Ubuntu jobs) from *comparison*
(core, pure, exhaustively testable on every job) is what lets mutants M22–M26
be killed on Ubuntu rather than only on Windows.

### 25.3 Function- and type-level plan

#### 25.3.1 Types in `mediated_executor.py`

```text
TrustedTargetEntry            frozen dataclass
    target_file_id: str            A-syntax identifier, never path-like
    workspace_relpath: str         §6.2 grammar
    maximum_size_bytes: int        positive

MediatedTargetRegistry        frozen; no mutation API
    workspace_root_final_path: str    captured once at construction
    _entries: Mapping[str, TrustedTargetEntry]   copied, frozen
    lookup(target_file_id) -> TrustedTargetEntry | None

SecuritySnapshot              frozen dataclass; CORE-owned. The only
                              security type policy reasons over. Built by
                              the core from a helper capture, never
                              constructed by the helper.
    owner_sid: bytes               canonical form; compared for identity
    dacl_state: str                "absent" | "null" | "present"  (core
                                   vocabulary; the classification decision
                                   belongs to the core, not the helper)
    control_bits: tuple[bool,bool,bool]   PRESENT, PROTECTED, AUTO_INHERITED
    acl_revision: int
    ace_count: int
    aces: tuple[bytes, ...]        complete AceSize-byte sequences, in order

ReplacementResult             frozen dataclass; §17 field set exactly
    persistent_projection() -> dict     privacy-gated in-module

MediatedExecutorError                  base
MediatedExecutorContractError          trusted-side/caller defect; raises

OUTCOMES / REASON_CODES       frozensets; REASON_TO_OUTCOME mapping (§16)
```

The `Win32SecurityCapture` → `SecuritySnapshot` conversion is the seam that
keeps the split honest and the dependency one-way. The helper performs
every Win32 structure walk and returns its **own** private capture of
primitive data; the core validates that capture, classifies it into its own
vocabulary, and compares — and never parses a Win32 structure. Because
`SecuritySnapshot` is core-owned and constructible from plain values,
**platform-neutral tests build it directly** and exercise
`compare_security_snapshots` on Ubuntu with crafted inputs, with no helper
import and no Windows involved.

#### 25.3.2 Pure functions in `mediated_executor.py`

```text
build_target_registry(workspace_root, entries) -> MediatedTargetRegistry
_validate_workspace_relpath(value) -> str          §6.2 grammar
_reject_duplicate_ids(entries) -> None             raises on duplicate
_validate_effect_against_entry(effect, entry) -> str | None   §7.1 steps 3-6
_verify_proposed_bytes(effect, entry, proposed) -> str | None §15.2
classify_replace_result(succeeded, last_error) -> str         §11.2, pure
snapshot_from_capture(capture) -> SecuritySnapshot            pure; validates
        the helper capture's shape and derives the three-valued dacl_state
        in core vocabulary; raises MediatedExecutorContractError on a
        malformed or internally inconsistent capture
compare_security_snapshots(pre, post) -> bool                 §10.1, pure
_build_result(...) -> ReplacementResult
```

`classify_replace_result`, `snapshot_from_capture`, and
`compare_security_snapshots` take no handles, no paths, and no I/O — they
carry the most safety weight in this slice and are unit-testable on Ubuntu
with crafted inputs. `snapshot_from_capture` is where a helper capture stops
being mechanism data and becomes core vocabulary; the three-valued DACL
classification (§10.1) is decided here, in the core, never by the helper.

`compare_security_snapshots` implements §10.1 exactly and in order: owner
SID identity; three-valued DACL state equality; `SE_DACL_PRESENT` and
`SE_DACL_PROTECTED` equality; the `SE_DACL_AUTO_INHERITED` monotonic rule
(§10.1a), which accepts `False -> True` and rejects `True -> False`;
`acl_revision` and `ace_count`; then ordered per-index equality of the
complete ACE byte sequences. It compares only what the snapshot carries, so
ACL slack space cannot enter the decision — the helper never extracts it.

The monotonic exception is applied to that one bit and to nothing else. It
is evaluated independently of the other components, so it can never mask a
difference in owner, DACL state, presence, protection, revision, count,
ACE order, or ACE bytes — each of those is compared on its own terms and
fails on its own.

#### 25.3.3 Orchestration in `mediated_executor.py`

```text
_EXECUTION_LOCK = threading.Lock()      module-level, process-local only

execute_replacement(registry, effect, proposed_bytes) -> ReplacementResult
```

Holds `_EXECUTION_LOCK` for the whole invocation (§14). Performs the §25.4
sequence, calling the helper for every filesystem action and deciding every
outcome itself.

#### 25.3.4 Adapter surface in `mediated_executor_win32.py`

Narrowly typed; every function takes validated components and returns plain
values or its own private capture type, or raises `Win32AdapterError`. This
module imports **no** TriageCore module — in particular never
`triage_core.mediated_executor` — so the dependency stays one-way:

```text
Win32SecurityCapture          frozen dataclass; HELPER-owned, private to
                              this module. Mechanism-level primitives only:
                              no core vocabulary, no policy, no decision.
    owner_sid: bytes               canonical owner SID representation
    dacl_present: bool             SE_DACL_PRESENT as observed
    dacl_is_null: bool             present flag set with a NULL ACL pointer
    control_bits: tuple[bool,bool,bool]   PRESENT, PROTECTED, AUTO_INHERITED
    acl_revision: int              0 when there is no ACL to read
    ace_count: int                 0 when there is no ACL to read
    aces: tuple[bytes, ...]        complete AceSize-byte sequences, in order,
                                   each already bounds-validated

windows_support_probe() -> bool          required APIs resolvable
open_anchor(root_path) -> handle         registry construction only
final_path(handle) -> str
volume_is_ntfs(handle) -> bool
walk_open_target(anchor_final_path, relpath_segments) -> handle
        never accepts a caller-supplied path string
has_reparse_or_not_regular(path_or_handle) -> bool
file_identity(handle) -> tuple[int, int, int]
read_exact_bounded(handle, limit) -> bytes
process_default_owner_sid() -> bytes
capture_security(handle) -> Win32SecurityCapture
        performs every Win32 structure walk and AceSize bounds validation;
        raises Win32AdapterError on a malformed descriptor, ACL, or ACE.
        Reports observed facts only — it does not classify DACL state into
        the core's three-valued vocabulary and reaches no conclusion.
create_private_temp(dir_final_path, name) -> handle    exclusive CREATE_NEW
write_all(handle, data) -> int
flush_and_close(handle) -> None
replace_file(replaced, replacement, backup) -> tuple[bool, int]
        returns (succeeded, last_error); classifies nothing
delete_file(path) -> bool                temp cleanup / verified backup only
```

`replace_file` returning `(succeeded, last_error)` rather than an outcome is
the boundary that keeps classification in the core, where it is pure and
Ubuntu-testable.

### 25.4 Filesystem observation sequence and the single replacement call

The contract's required order, preserved exactly, with the owning module:

```text
 1 validate immutable inputs                          core
 2 freeze and validate trusted registry               core
 3 verify Windows and NTFS                            core gate -> helper
 4 resolve target only from target_file_id            core -> helper walk
 5 validate original object and containment           helper -> core decides
 6 capture pre-identity and owner/DACL state          helper -> core
 7 read and verify exact pre-content                  helper read, core hash
 8 independently verify exact proposed bytes          core (pure)
 9 prepare and verify private temporary file          helper, core verifies
10 perform immediate identity re-probe                helper, core compares
11 issue at most ONE ReplaceFileW call                helper (once)
12 classify the primitive result                      core (pure)
13 freshly resolve post-state through the registry    core -> helper walk
14 verify content, size, type, containment, owner,    helper reads,
   and DACL                                           core compares
15 delete backup ONLY after complete verified success helper, core gates
16 produce the privacy-safe result                    core
```

Step 11 executes at most once per invocation. There is no retry loop around
it, and no code path reaches it twice.

Explicitly **not** introduced anywhere in this plan: automatic rollback,
retries of the replacement primitive, path-based fallback, best-effort ACL
parsing, cleanup during ambiguous states, or any integration with
authorization or reservation machinery.

### 25.5 Where each of the 36 test obligations is exercised

Venue: **U** = the existing Ubuntu jobs via the normal full suite (pure
core, platform-neutral); **W** = the proposed Windows CI job against a real
NTFS workspace; **U+W** = required evidence in both.

| # | Obligation | Venue |
|---|---|---|
| 1 | Only `target_file_id` selects the target | W |
| 2 | `canonical_relpath` cannot redirect execution | W |
| 3 | Unknown id fails closed (W); duplicate ids raise (U) | U+W |
| 4 | Caller paths cannot enter the API; §6.2 grammar | U |
| 5 | Target outside the workspace fails closed | W |
| 6 | Reparse-point target fails closed (junction) | W |
| 7 | Reparse-point ancestor fails closed; not lexical | W |
| 8 | Directory target fails closed | W |
| 9 | Missing target fails closed, nothing created | W |
| 10 | Pre-digest mismatch leaves target unchanged | W |
| 11 | Proposed-content mismatch leaves target unchanged | W |
| 12 | Proposed size mismatch leaves target unchanged | W |
| 13 | Oversized pre / oversized proposed fail closed | W |
| 14 | Exact bytes preserved (CRLF, BOM, NFD) | W |
| 15 | Temp and backup created exclusively, same directory | W |
| 16 | Partial temp write never alters the target | W |
| 17 | Temp flushed before replacement | W |
| 18 | Replacement on the same volume | W |
| 19 | Success writes exact bytes; backup deleted | W |
| 20 | Owner gate and owner preservation | W |
| 21 | DACL invariant: pure comparison (U); real DACL, supported-profile gate, and unsupported-profile refusal before mutation (W) | U+W |
| 22 | Result remains a regular file | W |
| 23 | Result remains in the workspace | W |
| 24 | Post mismatch ⇒ ambiguous, one call, backup retained | W |
| 25 | Classifier pure fn incl. distinct 1175 (U); e2e (W) | U+W |
| 26 | Degenerate pre==post rejected (U); thread race (W) | U+W |
| 27 | Cross-process exclusion excluded, structural | U |
| 28 | Projection shape (U); real-run payload (W) | U+W |
| 29 | Errors expose no bytes or sensitive paths | W |
| 30 | No network/subprocess/IPC/DB/ledger/capability ops | U+W |
| 31 | No runtime module imports the executor; no module-scope `ctypes`/`msvcrt`/helper import in the core; the helper imports no TriageCore module | U |
| 32 | Unsupported platform fails closed (U); forced API-probe failure (W) | U+W |
| 33 | Backup lifecycle: delete on success, retain otherwise | W |
| 34 | Identity re-probe catches a swapped target | W |
| 35 | `SE_DACL_AUTO_INHERITED` monotonic rule: deterministic `False -> True` acceptance and per-component gating on constructed snapshots (U); genuine NTFS replacement observes and records **any** accepted transition with all other components preserved (W) | U+W |
| 36 | `SE_DACL_AUTO_INHERITED` `True -> False` rejected | U |

Totals: 20 W-only, 7 U-only, 9 U+W — **exactly 36 required obligations**.
Every obligation has a named venue; none is left to "wherever it happens to
run".

Obligations 35 and 36 were added by the §10.1a amendment. The totals are
stated honestly rather than held cosmetically at their pre-amendment
values: a discovered contract defect that changes the invariant changes the
evidence required to trust it.

**Mandatory Windows evidence cannot skip.** All 20 required
Windows-only obligations (plus the Windows half of the 8 U+W items) execute
on `windows_executor`. `[W]` tests carry a `windows` marker so the Ubuntu
suite skips them cleanly, which creates the exact hazard the contract's
review discipline names — "platform skips that leave the central safety
claims untested". The Windows job therefore **fails if any mandatory
Windows test is skipped**, verified by machine-reading a structured result
file rather than trusting the human-readable tail (§25.7). A broken
platform gate must turn the job red, never silently green.

**T6 and T7 are satisfied by junctions, which the hosted runner reliably
supports.** Both obligations require *reparse-point* rejection, and a
junction is a reparse point; `mklink /J` needs no elevation, so this
evidence is dependable on `windows-latest`. T6 and T7 are therefore
mandatory, zero-skip, and fully within the 34.

**The symbolic-link variant is a supplemental probe, not an obligation.**
Symlink creation may require a privilege the runner does not grant. The
symlink probe is therefore:

- **outside the 34 acceptance obligations** — it adds no obligation and
  replaces none;
- **outside the required-zero-skip calculation** — it carries a distinct
  `windows_optional` marker and is deselected from the mandatory run;
- **run separately and non-gating**, reporting either pass or
  environment-unavailable;
- **never evidence for acceptance.** A skipped or unavailable symlink probe
  contributes nothing and must never be counted toward acceptance, quoted
  as coverage, or used to argue that reparse handling was verified. The
  junction evidence carries that claim on its own.

If a reviewer concludes that §19 T6 requires genuine *symbolic-link*
coverage for acceptance rather than reparse-point coverage generally, that
is a contract question and a stop condition (§25.10 item 10) — the merged
requirements would have to change first.

**Genuine filesystem behavior versus seam injection, stated honestly.**
Every `[W]` obligation runs against real files on a real NTFS volume: real
directories, real junctions, real DACLs, a real `ReplaceFileW` call. Some
branches cannot be provoked on demand by any test — Windows will not
produce a chosen `ReplaceFileW` error code, a post-verification divergence,
or a foreign-owner target to order. For those the plan uses a **closed,
enumerated set of injection seams**, and the evidence record must label
them as seam-injected rather than counting them as genuine-filesystem
evidence for the injected branch:

```text
replace_file()        forced (succeeded=False, last_error=<code>)   T25
post-verification     forced divergent read                          T24
process_default_owner_sid() forced incompatible default owner        T20
windows_support_probe() forced False                                 T32
capture_security()    crafted malformed AceSize                      T21
```

Where a condition *can* be provoked genuinely it must be, not injected —
junction ancestors via real `mklink /J`, sharing violations via a real
handle held without `FILE_SHARE_DELETE`, oversize via real files.

### 25.6 Designated killer test for each of the 31 mutants

Each mutant must be demonstrated **failing** against its defective variant,
with the module hash verified pristine after each cycle, following the
CR-YK-002/A/B bar. Controls are reported as controls, never as kills.

| Mutant | Designated killer | Venue |
|---|---|---|
| M1 resolve via `canonical_relpath` | T2, T3 | W |
| M2 lexical containment only | T7 | W |
| M3 follow final symlink/reparse | T6 | W |
| M4 skip ancestor checks | T7 | W |
| M5 omit pre-digest verification | T10 | W |
| M6 normalize content before hashing | T14 | W |
| M7 temp/backup outside target directory | T18 | W |
| M8 predictable temp/backup name | T15, T33 | W |
| M9 permit partial writes | T16 | W |
| M10 skip flush before replacement | T17 | W |
| M11 call primitive with no backup name | T25 | W |
| M12 omit owner verification | T20 | W |
| M13 omit DACL comparison / substitute SDDL | T21 | U+W |
| M14 report success before post-verification | T24 | W |
| M15 flatten ambiguous into `target_unchanged` | T24, T25 | W |
| M16 absolute path in persistent evidence | T28 | U |
| M17 proposed bytes in error or result | T29 | W |
| M18 claim cross-process exclusion | T27 (weak, reviewer-controlled) | U |
| M19 second mutation during rollback | T24 | W |
| M20 import reservation/capability/ledger/IPC/subprocess | T30, T31 | U |
| M21 delete backup early / on non-verified outcome | T33, T24 | W |
| M22 omit object-type GUID data | T21 | U |
| M23 omit callback application data | T21 | U |
| M24 compare only type/mask/SID | T21 | U |
| M25 ignore ACE order | T21 | U |
| M26 accept malformed `AceSize` | T21 | U |
| M27 flatten 1175 into the ambiguous 1177 outcome | T25 | U+W |
| M28 strict equality instead of the `SE_DACL_AUTO_INHERITED` monotonic rule (the pre-amendment defect) | T35[N] | U |
| M29 ignore `SE_DACL_AUTO_INHERITED` entirely (the rejected complete-exclusion option) | T36 | U |
| M30 query `TokenUser` instead of `TokenOwner` (§10.2a) | T20 instrumented information-class assertion | W |
| M31 omit the present-and-protected DACL precondition, or treat an inheritance-enabled target as supported (§10.2b) | T21[W] unprotected-target refusal before temporary-file creation or `ReplaceFileW`, original bytes unchanged, no artifacts | W |

Mutant totals: **31 total — 21 Windows, 10 Ubuntu.**

Ten mutants (M16, M18, M20, M22–M26, M28, M29) are killed on Ubuntu, which
is the direct payoff of the §25.2 module split: the ACE-comparison mutants
that matter most are killed on every pull request, not only in the Windows
job.

M31 is Windows-scoped by necessity: its killer asserts refusal against a
genuine NTFS security descriptor and a real mechanism call log, which the
neutral core cannot produce.

M28 is deliberately Ubuntu-only. Its killer must be deterministic, and only
the constructed-snapshot half of T35 is: a hosted runner that produced
`False -> False` would leave a strict-equality mutant alive, so pointing
M28 at the Windows half would make the kill depend on which accepted
transition the runner happened to exhibit. That is the same
mutant-target-precision lesson CR-OC-001B recorded, applied before the
evidence was collected rather than after.

### 25.7 Windows CI evidence design and acceptance contract

**One additive job** in the existing `.github/workflows/tests.yml`. The
existing Ubuntu Python 3.10/3.11/3.12 matrix is **left exactly intact** and
is not converted into an OS × Python matrix — converting it would multiply
job count, change evidence for three unrelated Python versions, and couple
this slice to the whole suite's CI shape. The Ubuntu jobs continue to run
the normal full suite, exercising the pure core and the non-Windows
fail-closed gate.

Proposed shape (`windows_executor`, additive, nothing else in the file
changes):

```yaml
  windows_executor:
    runs-on: windows-latest
    permissions:
      contents: read
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install package
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"
      - name: Verify workspace volume is NTFS
        # fails the job when the workspace is not NTFS
      - name: Run mandatory executor and guard suites
        # deselects the windows_optional marker; writes JUnit XML to
        # $env:RUNNER_TEMP
      - name: Assert zero mandatory skips
        # parses that XML; fails when skipped != 0
      - name: Supplemental symlink probe (non-gating)
        # runs the windows_optional marker only; reports pass or
        # environment-unavailable; never gates the job
      - name: Bounded job summary
        # commit SHA, Windows build, Python version, filesystem type,
        # mandatory totals, mandatory skip count, symlink probe status
```

- **Runner and Python:** `windows-latest`, Python 3.12 (single version —
  this slice's risk is the filesystem and Win32 surface, not Python
  version drift, which the Ubuntu matrix already covers).
- **Permissions:** job-level `permissions: contents: read`. The job needs
  no secrets, no write scope, and no package or deployment access; it reads
  the checkout and runs tests. Nothing it produces is uploaded.
- **Dependencies, pinned:** the install command is exactly
  `python -m pip install -e ".[dev]"`. Current repository inspection shows
  the focused executor suite and the two selected guards require no
  `mobile` extra — that extra's consumers (`triage_core/web/server.py`,
  `triage_core/validators.py`) are not among the absence guard's public
  import seams. **There is no conditional fallback.** If implementation
  finds the focused suite cannot collect under `.[dev]`, that is a stop
  condition (§25.10 item 14): stop and return for approval rather than
  silently broadening the installed dependency surface. The existing Ubuntu
  job keeps its current `.[dev,mobile]` install, unchanged.
- **NTFS verification:** the workspace volume's filesystem is queried
  (`Get-Volume` on the workspace drive, falling back to
  `Get-CimInstance Win32_LogicalDisk`) and the job **fails** if it is not
  NTFS. Without this, an unexpected runner volume could silently reduce
  every DACL and reparse claim to noise.
- **Mandatory suites:** `tests/test_mediated_executor.py` with the
  `windows_optional` marker deselected, plus the two guards identified by
  repository inspection — `tests/test_privacy_invariants.py`
  (persistent-privacy invariant) and
  `tests/test_governed_decision_integration_absence.py`
  (runtime-integration absence).
- **Structured result and the zero-skip assertion:** the mandatory run
  writes JUnit XML (or an equivalent bounded machine-readable result) to a
  path under `$env:RUNNER_TEMP`. A dedicated step parses it and **fails the
  job when the mandatory group reports a non-zero skip count**, and also
  fails if the result file is missing or unparseable — a vanished report
  must not read as success. The file stays under `RUNNER_TEMP`, is **not
  uploaded as an artifact**, and no filesystem-diagnostic artifact of any
  kind is published.
- **Supplemental symlink probe:** a separate non-gating step runs only the
  `windows_optional` marker and reports pass or environment-unavailable.
  Its result never affects the job outcome and never counts toward
  acceptance (§25.5).
- **Bounded job summary**, emitted to the step summary, carrying exactly:
  commit SHA, Windows image/OS build, Python version, detected filesystem
  type, mandatory test totals (passed/failed/errored/skipped), the
  mandatory skip count, the symlink probe's status, and the
  `SE_DACL_AUTO_INHERITED` transition observed by T35[W], recorded as one
  of `False->False`, `False->True`, or `True->True`. Counts come from the
  structured report, not from echoing test output. The transition is two
  booleans and a bit name -- no descriptor, ACL, ACE, or SID material
  reaches the summary, and recording it is observational (§10.1a), never a
  pass/fail criterion for the normalization itself.
- **Disclosure ban:** the summary and job log must disclose no file
  content, previous content, absolute paths, temporary names, backup names,
  raw ACLs, raw security descriptors, tokens, or credentials. Test node
  IDs are not echoed into the summary.
- **Repeatability:** the job runs on every pull request and every push the
  existing workflow triggers already cover; no new trigger is added.

**Acceptance contract.** The implementation may be considered complete only
when: every `[N]` obligation passes in the Ubuntu jobs across 3.10/3.11/3.12;
every mandatory `[W]` obligation passes in `windows_executor` with **zero
skips in the mandatory group**, asserted from the structured result file;
the NTFS verification step passes; the hosted Windows job observes and
records one of the three §10.1a accepted `SE_DACL_AUTO_INHERITED`
transitions, with every other owner/DACL component exactly preserved —
reproducing `False -> True` specifically is **not** required, while
`True -> False` or any other metadata difference fails (T35[W]); **every
healthy replacement case runs within the §10.2b supported profile (present,
non-NULL, protected DACL), T35[W] confirms that pre-state before
replacement, and absent, NULL, and unprotected profiles are shown refusing
before mutation (T21[W])**; all 31
mutants are
demonstrated failing against their defective variants with the module hash
pristine after each cycle, and controls reported as controls; the privacy
gate runs in-module over the exact projection payload; the full suite passes
with no new `xfail`; `git diff --check` passes; the diff stays inside the
seven-path allowlist; the six untouched modules of §25.1 are unmodified; no
runtime module imports the executor; no new dependency is added; and the
implementation record cites the Microsoft/Python documentation each
load-bearing behavior rests on, naming which behaviors were verified by test
rather than by documentation.

**A local Windows run may supplement this evidence and may never substitute
for it.** A recorded local run is useful for iteration and for the §24
implementation-time documentation obligations; it is not acceptance
evidence, because it is neither repeatable by a reviewer nor re-run on
future changes.

### 25.8 Privacy and diagnostic-output restrictions

The §17 rules govern the result, the projection, every exception, and every
reachable repr. This plan adds the implementation-side obligations that make
them hold:

- The helper raises `Win32AdapterError` carrying **only** a numeric error
  code and a fixed operation label — never a path, name, handle value,
  SID, ACL, or descriptor. OS message strings are never propagated.
- The core maps adapter errors to closed reason codes; no OS text reaches
  a result, an exception, or a log.
- Absolute paths, temporary names, and backup names exist only in local
  variables inside the helper and the orchestrator, and are never stored on
  a result object, formatted into a message, or emitted.
- `SecuritySnapshot` values are compared and discarded; owner SIDs and ACE
  bytes never reach a result, projection, or error, and SDDL text is never
  produced at all in production paths.
- Pre-content and proposed bytes are hashed and dropped; neither is stored
  on any object that outlives the call.
- `persistent_projection()` runs `assert_persistent_privacy_safe` over the
  exact payload before returning it.
- **Test diagnostics obey the same rules in CI.** Assertion messages,
  captured output, and the job summary must not embed content, absolute
  paths, temp/backup names, or descriptor material; canary-based tests
  (T28, T29) assert their absence.

### 25.9 Concrete verification command set

Run by the implementer before requesting review, and reproducible by a
reviewer:

```powershell
# Windows machine — the mandatory slice and the two guards
python -m pytest tests/test_mediated_executor.py -m "not windows_optional" -q
python -m pytest tests/test_privacy_invariants.py tests/test_governed_decision_integration_absence.py -q

# Windows machine — no mandatory test may skip (structured, then eyeballed)
python -m pytest tests/test_mediated_executor.py -m "not windows_optional" -q -rs `
    --junit-xml="$env:RUNNER_TEMP\mediated-executor.xml"

# Windows machine — supplemental symlink probe; never gates acceptance
python -m pytest tests/test_mediated_executor.py -m windows_optional -q -rs

# Any machine — full suite, no new xfail
python -m pytest -q

# Non-Windows machine — the neutral core and the fail-closed gate
python -m pytest tests/test_mediated_executor.py -q

# Diff hygiene and allowlist containment
git diff --check
git status --short
git diff --name-only
git diff --stat
```

Plus, per the standing evidence bar, the mutant cycle for each of the 27
variants: back up the module, apply the defect, run the designated killer
and record the failure, restore with `git checkout HEAD -- <file>`, and
verify the module hash is pristine before the next cycle.

### 25.10 Stop conditions requiring renewed approval

Implementation halts and returns for explicit approval if any of these
occurs. None may be resolved by implementation discretion:

1. Any path outside the §25.1 seven would need to be created or modified —
   including any "shared types" module introduced to bridge the core and
   the helper. There is no eighth path, and a third module is not a
   workaround for a dependency problem.
2. Any new package dependency, or any change to `pyproject.toml`.
3. A required Win32 capability turns out to need a privilege the executing
   account lacks (for example `SeSecurityPrivilege`), or an API is
   unavailable on the runner.
4. Current Microsoft documentation does not support the `target_unchanged`
   classification for `ERROR_UNABLE_TO_REMOVE_REPLACED` (1175) or
   `ERROR_UNABLE_TO_MOVE_REPLACEMENT` (1176) — the claim narrows to
   ambiguous and the contract text must change first (§24).
5. The §8.2 capture-then-close plus identity re-probe design does not hold
   on real Windows, or `ReplaceFileW` interacts with held handles
   differently than the contract assumes.
6. A `[W]` obligation cannot be exercised genuinely **and** has no
   acceptable seam in the §25.5 enumerated set.
7. The NTFS verification step fails on `windows-latest`, or the runner's
   workspace volume is not NTFS.
8. Any mutant cannot be killed by its designated test, or a designated
   killer turns out to kill for the wrong reason (the CR-OC-001B lesson:
   a collection error is not a kill).
9. The neutral core cannot be kept import-safe and filesystem-silent on
   non-Windows.
10. Symlink privilege is unavailable and the reviewer requires genuine
    symlink coverage rather than junction coverage plus a visible skip.
11. Any temptation to convert the Ubuntu matrix into an OS × Python matrix,
    touch another workflow, or alter the existing Ubuntu jobs.
12. Any runtime module would need to import the executor, or the executor
    would need to import authorization, reservation, or ledger machinery.
13. The requirements contract (§2–§24) would need to change for the
    implementation to proceed.
14. The focused executor suite or the two selected guards cannot collect
    on Windows under exactly `python -m pip install -e ".[dev]"`. Stop and
    return for approval; do not silently broaden the installed dependency
    surface.
15. `mediated_executor_win32.py` would need to import
    `triage_core.mediated_executor`, reference any core-owned type, or
    import any other TriageCore module — or the core would need to consume
    a helper-owned type as policy input rather than converting it through
    `snapshot_from_capture`. Either direction breaks the one-way
    dependency and is non-conforming.
16. A mandatory Windows test cannot be made to run without skipping, or
    the structured result file cannot be produced or parsed. A missing or
    unreadable report is a failure, never a pass.

### 25.11 This proposal grants no implementation authority

Explicitly, and without qualification:

- **Drafting §25 is not implementation authority.** No file in the §25.1
  allowlist may be created or modified on the strength of this section.
- **Merging the requirements contract was not implementation authority.**
  PR #125 published requirements; it authorized nothing.
- **Merging this proposal would not be implementation authority either.**
  It would settle the plan, not license the work.

Implementation may begin only after **all** of the following:

```text
1. this implementation proposal is reviewed;
2. its exact seven-path allowlist is accepted;
3. the Windows CI evidence design is accepted;
4. the module boundary is accepted;
5. explicit human implementation approval is granted.
```

Until every one of those is satisfied, `triage_core/mediated_executor.py`,
`triage_core/mediated_executor_win32.py`,
`tests/test_mediated_executor.py`, and `.github/workflows/tests.yml` remain
**unauthorized and must not exist**. CR-OC-001D and CR-OC-001E remain
unauthorized independently of anything decided here.

---

# Part III — Implementation Record

## 26. Implementation Record

Implementation authority over the §25.1 seven-path allowlist was granted after
the §25 proposal merged (PR #126, `0ab1522`) and the §10.1a amendment merged
(PR #127, `8c0ad3c`). This section records what was built and what the
evidence actually establishes. It does **not** claim CR-OC-001C is complete,
merged, or runtime-integrated: the branch is unpushed, hosted Windows CI has
never run, and merge authority was not granted.

### 26.1 What was implemented

Four of the seven allowlisted paths were touched:

```text
triage_core/mediated_executor.py        new  policy core
triage_core/mediated_executor_win32.py  new  Windows mechanism adapter
tests/test_mediated_executor.py         new  36-obligation suite
.github/workflows/tests.yml             modified, additively only
```

The three documentation paths carry this record. No eighth path was created,
no dependency was added, `pyproject.toml` is untouched, and none of the six
"remain unmodified" modules of §25.1 changed.

The core owns policy: immutable contract types, the frozen trusted registry
and its grammar, exact proposed-content verification, the closed vocabularies
with a single `REASON_TO_OUTCOME` source of truth, pure
`classify_replace_result`, pure `snapshot_from_capture` and
`compare_security_snapshots`, the privacy-gated projection, the process-local
lock, the Windows gate, and the sixteen-step sequence. The adapter owns
mechanism only and imports no TriageCore module; the core imports it
dynamically and only after the gate.

### 26.2 Implementation discoveries

Three defects were found **by building and testing the contract**, not by
reading it. Each is a correction a reviewer should see.

**`SE_DACL_AUTO_INHERITED` strict equality was unimplementable.** §10.1
originally required strict equality of that control bit. A successful
`ReplaceFileW` on real NTFS sets it on a file whose descriptor lacked it while
preserving owner, DACL state, presence, protection, ACL revision, ACE count,
and every complete ACE byte sequence byte-identically. As written the contract
would have reported `metadata_preservation_failed` for the first replacement
of essentially any inherited-DACL file. Amended to the monotonic rule of
§10.1a before any test hardened the defect into permanent behaviour.

**T8 exposed a reason-code defect in directory handling.** A directory cannot
be opened without `FILE_FLAG_BACKUP_SEMANTICS`, so the open failed and the
executor reported `containment_violation` where §19 T8 requires
`target_not_regular_file`. The adapter now opens with directory-capable flags
and the core *classifies* the opened object, which preserves the required
reason code. Opening and then classifying is the more faithful design; the
flag grants no rights the executing token does not already hold.

**M3/M4 exposed a missing pre-open final-target reparse rejection.** §7.2
requires reparse rejection "for the target **and** every ancestor", ordered
before `CreateFileW`. The first implementation walked only
`segments[:-1]`, so a reparse *target* was rejected after the handle was
opened rather than before. `has_reparse_target` was added as a separate
adapter call so both halves of the rule are independently enforceable and
independently mutable, and the core now rejects either before any target
handle exists. Without the M3/M4 mutant analysis this would have shipped as a
latent ordering defect.

### 26.3 Evidence-harness corrections

Three harness defects were found. None weakened a mutant or a test; each was
producing a false reading about otherwise-correct behaviour.

- **M26** — `pytest.raises` reporting `DID NOT RAISE` was scored as an unclean
  failure. It is a clean behavioural kill: the test collected, executed, and
  the guarded condition stopped occurring. This is the marker CR-OC-001B
  settled on after its own harness mis-scored two mutants.
- **M6** — `subprocess(text=True)` decoded pytest output using the Windows
  console codepage and hit byte `0x81` from T14's BOM/NFD failure diff,
  blanking captured output entirely and making a real kill look unclean.
  Output is now decoded UTF-8 with replacement.
- **M10** — T17 called `order.index("flush")`, which raises `ValueError` when
  the flush never happens. Membership assertions now precede ordering
  assertions so a missing flush fails on a clean assertion rather than a test
  error, because an unclean failure is not a valid kill.

### 26.4 Evidence-integrity incident

Recorded plainly, because it demonstrates why the hash and healthy-suite
controls exist rather than being embarrassing residue.

A legitimate post-baseline change — the §26.2 `has_reparse_target` fix —
produced a hash mismatch against a manifest captured *before* that change. The
mismatch was initially misdiagnosed as PowerShell re-encoding the file on a
read/write round-trip. Acting on that mistaken diagnosis, the file was
restored from the container's older staging copy, which **reverted an
authorized implementation change**. The healthy suite exposed the regression
on the next run with a precise failure
(`assert 'target_not_regular_file' == 'containment_violation'`). The change
was reapplied, the baseline and container staging authority were refreshed,
and every subsequent mutation used the byte-safe Python harness rather than a
shell round-trip.

The root error was comparing against a baseline already invalidated by
authorized work. No evidence was lost and no incorrect result was reported;
the controls caught it within one cycle.

### 26.5 Mutant outcome

```text
29 designated mutants
29 clean behavioural kills
10 Ubuntu venue
19 Windows venue
 0 surviving mutants
 0 syntax/import/collection/fixture/timeout failures counted as kills
byte-exact restoration verified after every cycle
```

**Evidence rebinding.** The healthy tree changed after some early cycles
(§26.2 fixes, plus strengthened T6/T7 containment assertions, the T25 backup
name-pattern assertion, and the T17 membership assertions). Mutant evidence
must bind to the final production and killer-test text, so every mutant
executed before the final rebaseline was **rerun against it**: ten Windows
mutants (M1–M9, M11) and all ten Ubuntu mutants, the latter after syncing the
container to the final tree and regenerating its 640-file manifest. The nine
Windows mutants already executed on the final tree (M10, M12–M15, M17, M19,
M21, M27) were not rerun. Every rerun killed cleanly with byte-exact
restoration.

Windows venue was exercised on a real NTFS workspace. Ubuntu venue was
exercised in container `tc-ubuntu-mutants` (`triagecore-ubuntu-mutants:24.04`,
Python 3.12.3, pytest 9.0.3). Running a `U`-venue killer on Windows was never
counted as Ubuntu evidence.

### 26.6 Validation results

Final tree, all venues:

```text
Ubuntu   neutral executor suite   95 passed / 47 deselected / 0 skipped
Ubuntu   privacy + absence guards 24 passed
Ubuntu   640-file manifest        verified
Windows  focused executor suite  141 passed / 1 skipped (optional probe)
Windows  mandatory group + gate  165 passed / 1 deselected / 0 skipped
         structured-result gate  PASS
         recorded transition     False->True (observational, CR 10.1a)
```

All 36 obligations have a designated test, machine-checked by a ledger test
that parses the suite and asserts coverage of exactly 1–36 with no strays.

### 26.7 What this evidence does not establish

- **Hosted Windows CI has never run.** The branch is unpushed, so the
  `windows_executor` job has produced no result. All Windows evidence here is
  **local and supplemental**, exactly as §4.3 requires; it cannot substitute
  for the hosted job, and §21 acceptance is therefore not yet satisfied.
- The `windows_optional` symlink probe **skipped locally** (the environment
  withheld the privilege). It is outside the 36 obligations and outside the
  zero-skip calculation, and contributes nothing to acceptance.
- The recorded `False->True` transition is one machine's observation. §10.1a
  governs: reproduction is observational, never a gate.
- Nothing here establishes OpenClaw containment, caller or broker
  authentication, capability or reservation integration, exactly-once
  execution, cross-process exclusion, or that observing a postcondition proves
  this invocation caused it. CR-OC-001C is **not complete, not merged, and not
  runtime-integrated**, and no runtime module imports either new module.
- Implementation authority is spent only when this implementation is accepted.
  **Merge authority was not granted.**

### 26.8 Known cosmetic residue

`pytest.mark.windows` and `pytest.mark.windows_optional` are unregistered, so
pytest emits `PytestUnknownMarkWarning` (40 occurrences). Registering them
would require editing `pyproject.toml` — an eighth path. The warnings are
cosmetic, marker-based selection works, and escalation to strict-marker
enforcement is treated as a stop condition rather than a reason to widen
scope.

A local environment note, not a repository defect: this machine's editable
install resolves `triage_core` to a different worktree, so local runs used an
explicit path. **No `PYTHONPATH` manipulation was added to CI** — a clean
hosted runner's editable install points at its own checkout, and injecting an
override could mask a genuine packaging defect.
