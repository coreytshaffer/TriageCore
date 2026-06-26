# Qwen Global AI Hackathon Submission Packet

## Project Name
TriageCore: Safer MemoryAgent Control

## Elevator Pitch
TriageCore is a privacy-first control plane for MemoryAgents. It makes persistent AI memory safer by adding identity, bounded memory, privacy metadata, revocation, human approval gates, routing decisions, and audit trails.

## Project Story
MemoryAgents are incredibly powerful because they retain context across sessions. However, persistent memory introduces significant privacy and governance risks if left unchecked. Many agent platforms focus entirely on capability, treating safety as an afterthought.

TriageCore takes a different approach: **Conscious Design > Good Intentions**. 

Drawing inspiration from physical CPTED (Crime Prevention Through Environmental Design), TriageCore introduces **Cyber CPTED**. We believe the safe path should be easier, more visible, and more useful than the unsafe path. Just like physical CPTED, Cyber CPTED requires qualified observers, active feedback loops, and ongoing vigilance. TriageCore provides exactly that by serving as the control plane for MemoryAgents—ensuring that every read/write to persistent memory is governed, auditable, and explicitly approved when dealing with sensitive data.

## Qwen Usage
TriageCore explicitly routes approved external-safe `TaskPackets` to **Qwen Cloud**. Qwen is utilized as the primary engine for the MemoryAgent operations, showcasing how a powerful cloud LLM can be safely integrated into a local-first governance framework without exposing unreviewed raw data.

## Demo Workflow
1. **Task Initialization**: The operator submits a task locally.
2. **Local Preflight & Privacy Scan**: TriageCore converts the task into a structured `TaskPacket` and performs a local privacy scan. If sensitive data is detected, the task fails closed or requires human approval.
3. **Route Classification**: TriageCore evaluates the route manifest and determines if the task is safe to escalate to Qwen Cloud.
4. **Handoff Generation**: A reviewable handoff artifact is generated.
5. **MemoryAgent Execution**: The approved packet is routed to the Qwen Cloud MemoryAgent.
6. **Audit Ledger**: A privacy-safe `route_audit` event is logged to the append-only ledger, recording the routing decision without exposing the raw prompt.

## Repo Link
[https://github.com/coreytshaffer/TriageCore](https://github.com/coreytshaffer/TriageCore)

## Thumbnail
*(Concept)*: A sleek architecture diagram showing a lock symbol (Local Governance) gating traffic. On the left, messy user tasks enter. In the center, TriageCore applies Privacy Checks and Approval Gates. On the right, clean, approved tasks flow into the Qwen MemoryAgent node. The color palette emphasizes trust, security, and visibility.

## Video Script (Draft)

**[0:00 - 0:15] Introduction (Screen: TriageCore Architecture Diagram)**
"Hi, this is TriageCore: a privacy-first control plane for MemoryAgents. Persistent memory makes AI powerful, but it also makes it dangerous if ungoverned. We built TriageCore to make the safe path the easiest path using Cyber CPTED principles."

**[0:15 - 0:35] The Problem & Preflight (Screen: Terminal running `tc preflight`)**
"Let's look at a typical workflow. When an operator initiates a task, TriageCore doesn't just blindly send it to the cloud. It runs a local preflight and privacy scan to classify the data and determine if it's safe to escalate."

**[0:35 - 0:55] Route Classification & Qwen Escalation (Screen: Terminal showing routing output & `tc handoff`)**
"Once the privacy checks pass, TriageCore evaluates the routing policy. Here, we can see the task is explicitly approved for escalation to Qwen Cloud. We generate a structured `TaskPacket` and hand it off to the Qwen MemoryAgent for processing."

**[0:55 - 1:15] Audit & Governance (Screen: Terminal running `tc audit --kind route_audit --last 5`)**
"Every routing decision is recorded in an append-only audit ledger. Notice that the ledger captures the metadata and the decision—proving governance—without leaking the raw prompt itself."

**[1:15 - 1:30] Conclusion (Screen: TriageCore Logo & Qwen Logo)**
"TriageCore proves that you can have the power of Qwen MemoryAgents without sacrificing privacy, visibility, or control. Thank you."
