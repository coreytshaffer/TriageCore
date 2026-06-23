# Operator UX and Task Envelope Console Design

This document outlines the interaction model and display envelope for the TriageCore operator console. The goal is to provide humans with a calm, transparent, and authoritative central control panel for observing external runtime proposals, admission decisions, and boundaries.

## 1. The Task Envelope Model

The **Task Envelope** is the visual representation of a proposal traversing the TriageCore boundaries. Rather than raw logs, the operator sees structured "envelopes" containing:
- The declared payload (manifest contents)
- The requested `capability_profile`
- The `runtime_name`
- The current evaluation status

The envelope grounds the operator by clearly showing exactly what is being evaluated before any downstream execution occurs.

## 2. Console Display States (CLI Mockups)

The following are non-binding CLI-style mockups showing how different envelope states are presented to the operator. These mockups visually distinguish between states and emphasize the `execution_performed=false` invariant.

### A. Proposed State
When a manifest is first normalized into a proposal but has not yet hit the admission boundary, the envelope is in a draft or `proposed` state.

```text
[ ENVELOPE : PROPOSED ]
Runtime:     example-read-only-runtime
Capability:  read_only_summary
Status:      Pending Admission Gate
Execution:   [ BLOCKED ] (Execution Performed: False)
--------------------------------------------------
Awaiting admission boundary evaluation...
```

### B. Blocked State (RuntimeAdmissionError)
If a proposal fails structural or policy validation (e.g., missing required fields, or unapproved mutations), TriageCore raises a `RuntimeAdmissionError`. This state is presented as a hard stop.

```text
[ ENVELOPE : BLOCKED ] 
Runtime:     unknown-runtime
Capability:  approved_mutation
Status:      Rejected at Admission Gate
Execution:   [ BLOCKED ] (Execution Performed: False)
--------------------------------------------------
ERROR: RuntimeAdmissionError
Blocked Reasons:
  - missing_or_blank:schema_version
  - approval_required_false
```

### C. Approval Required State
If a valid proposal requests mutation capabilities but lacks explicit approval, it halts in the `approval_required` state. This state provides a clear action point for the operator.

```text
[ ENVELOPE : APPROVAL REQUIRED ]
Runtime:     example-mutation-runtime
Capability:  approved_mutation
Status:      Awaiting Operator Approval
Execution:   [ BLOCKED ] (Execution Performed: False)
--------------------------------------------------
This proposal requests mutation authority. 
To admit this proposal, an explicit approval flag must be provided.
```

*(Note: Future iterations will define the specific operator interaction, such as typing `APPROVE` or passing an `--approve` flag, to securely transition this state).*

### D. Admitted State
When a proposal successfully passes the admission gate (either because it is read-only or because explicit approval was provided), the console displays the structured admission evidence.

```text
[ ENVELOPE : ADMITTED ]
Runtime:     example-read-only-runtime
Capability:  read_only_summary
Evidence:    external_runtime_admission_stub
Execution:   [ INERT ] (Execution Performed: False)
--------------------------------------------------
Proposal successfully admitted.
Approval Used: False
Blocked Reasons: []
```

## 3. The "Inert by Default" Guarantee

A critical feature of the operator console is the persistent, loud display of the `execution_performed=false` invariant. In every mockup above, the execution status is explicitly visible. 

By surfacing `execution_performed=False` alongside the admission evidence, the console provides verifiable confidence that TriageCore is safely evaluating boundaries and strictly returning inert evidence, rather than covertly executing side-effects.

## 4. Historical Rendering

In the future, the operator console will render these mockups by querying `.triagecore/ledger.jsonl`. 
- `.triagecore/ledger.jsonl` will serve as the immutable, append-only source of truth.
- The console will read these ledger entries to display historical envelopes exactly as they were evaluated at the time of admission. 

*(Note: Reading from or writing to the ledger is not implemented in this design phase. This document merely establishes `.triagecore/ledger.jsonl` as the designated rendering source).*
