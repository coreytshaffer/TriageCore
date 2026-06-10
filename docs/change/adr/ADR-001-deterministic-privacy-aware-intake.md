# ADR-001: Deterministic Privacy-Aware Intake

## Status
Accepted as architectural direction. Implementation still requires approved Change Requests.

## Context
TriageCore currently routes tasks using a resilience router that can select cloud, local heavy, local fast, deterministic, or human handoff paths. As the system processes more sensitive information, we need to ensure that tasks containing private or restricted data are never inadvertently sent to external or untrusted models. Relying on an LLM to determine the privacy level of a prompt is probabilistic and poses an unacceptable risk of data leakage.

## Decision
We will implement a deterministic, non-LLM privacy-aware intake process. Tasks will be encapsulated in a structure (e.g., TaskPacket) that includes explicit privacy metadata. A deterministic scanner will evaluate both declared metadata and actual task content before the task reaches the resilience router. 

## Consequences
- **Positive**: Guarantees that privacy constraints are evaluated deterministically, reducing the risk of accidental data leakage. Enforces token efficiency by failing fast before invoking an LLM.
- **Negative**: Requires strict discipline in task creation to ensure metadata is present and accurate. May increase the initial friction of defining tasks.
