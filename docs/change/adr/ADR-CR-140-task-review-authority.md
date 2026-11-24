# ADR-CR-140 — Authority for human task review decisions

**Status** Accepted with CR-140 design revision 1 at `37bceec4`. The first
implementation slice supplies the receipt and persistence foundation.

## Context

The task ledger records operational evidence. Its historical review rows
carry decisions from several entry points without independently proving who
reviewed which evidence. A signature can authenticate one receipt. Selection
of the current decision also needs a record of which receipt the trusted
local service committed.

## Decision

A dedicated local SQLite review store owns admission and the current review
head for each task in a configured workspace scope. The store is opened
from an operator-provisioned private directory, independently of any ledger
or import location. POSIX checks its owner and mode. Windows installations
rely on the operator-provisioned directory ACL. The deployment must protect
the store, its SQLite journal, the credential registry, and the configured
reviewer grants from unauthorized writes, replacement, or rollback.

An explicitly enrolled reviewer with a review grant confirms a local,
purpose-specific FIDO2 challenge. It binds the workspace, task, evidence
revision and digest, exact decision, reviewer, event and predecessor, local
relying party, nonce, and UTC validity window. The manifest uses digest
references to the exact bytes shown under stable item identifiers. The
receipt keeps the assertion and identifiers in local storage. Raw review
evidence stays with its original source.

Within one transaction the service matches the prepared challenge and current
evidence binding, verifies the reviewer and assertion, consumes the
challenge, records the receipt with its admission time, and advances the
review head. Exact retries resolve through the committed event ID. Readers
verify at the original admission time under current review eligibility.
Historical receipt access preserves attribution separately from current
verification. Loss of trusted state or policy is observable as a verification
failure.

## Consequences

Ledger rows can carry historical observations or a reference to a committed
review. SQLite owns selection of the current receipt. A missing audit
reference affects the audit trail on future integration. The underlying
review decision remains in the private store. Execution authorization,
artifact validation, and research conclusions are governed independently.

The first slice registers evidence metadata through a trusted local API with
an expected previous revision. Desktop and mobile review flows, evidence
capture and presentation, and projections need their own implementation
grant. That integration must supply the trusted evidence source and private
operator directory. A mobile token can request local review, with human
confirmation taking place locally.

[CR-140](../requests/CR-140-task-review-provenance.md) defines the rollout and
verification criteria.
