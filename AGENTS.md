# AGENTS.md — Global Orchestration Configuration

> This file applies to all Antigravity workspaces. It establishes a
> **local-first** model architecture for software development: the local LLM
> handles the majority of coding tasks; the cloud flagship model is a persistent
> **supervisor** that monitors output quality and drives feedback loops — not a
> fallback that takes over when things go wrong.

---

## 1. Core Philosophy

**Local executes. Cloud supervises.**

The local model is the primary execution engine. It writes the code, generates
the tests, formats the data. The cloud model's job is not to do that work — it
is to **watch the local model's output, catch errors early, and send targeted
corrections back** so the local model can revise before anything is committed.

The feedback loop is the architecture. Cloud tokens are spent on review and
direction, not re-execution. The local model never gets replaced — it gets
corrected.

---

## 2. Role Definitions

### Local Worker Council — Primary Executors

Does the work. Handles all routine coding tasks via specialized roles (RepoMapper, TestStubber, Validator, CodeRepair) without interruption.

| Task Category | Examples |
|---|---|
| Feature implementation | New functions, classes, endpoints, UI components |
| Bug fixes | Localized logic errors, off-by-one, null checks |
| Refactoring | Extracting functions, renaming, simplifying conditionals |
| Code generation | CRUD ops, API wrappers, DB migrations |
| Tests | Unit tests, pytest fixtures, test data generators |
| Boilerplate | Config files, schema definitions, README sections |
| Data formatting | JSON, CSV, Markdown, SQL |
| Cleanup scripts | Linting fixes, file normalization, one-off migrations |
| Docs & comments | Docstrings, inline comments, changelogs |

The local models should be dispatched immediately for all of the above.
Do not wait for cloud approval before starting local execution.

---

### Cloud Supervisor — Review & Feedback

Does not execute tasks. Supervises local output by:

1. **Reviewing** the local model's artifact against the original task spec
2. **Identifying** specific defects — logic errors, missing edge cases, schema
   mismatches, security gaps
3. **Issuing a correction prompt** back to the local model with precise, bounded
   feedback
4. **Approving** the revised output once it passes, or **escalating** to direct
   cloud execution only if the feedback loop fails to converge

The supervisor's output is always one of three things:
- ✅ **APPROVED** — artifact is correct; commit it
- 🔁 **REVISE** — targeted feedback prompt for the local model to act on
- 🚨 **ESCALATE** — local cannot fix this; cloud takes over for this task only

---

## 3. The Feedback Loop

```
┌─────────────────────────────────────────────────────┐
│                    TASK RECEIVED                    │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │   Local Worker         │
         │   Executes task →      │
         │   Returns artifact     │
         └────────────┬───────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │   Cloud Supervisor     │
         │   Reviews artifact     │
         └────────────┬───────────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
        APPROVED    REVISE    ESCALATE
           │          │          │
           ▼          ▼          ▼
        Commit    Send feedback   Cloud executes
                  → Local retries this task only
                  → Supervisor
                    reviews again
                  (max 2 cycles)
```

**Cycle limit:** If the local model fails to produce an acceptable artifact
after **2 feedback cycles**, the Project Manager escalates and executes the task
directly. Do not loop indefinitely.

---

## 4. Supervisor Review Protocol

When reviewing local output, the cloud supervisor must:

1. **Be specific, not general.** Do not say "this has issues." Point to the exact
   line, function, or schema key that is wrong and why.

2. **Issue the smallest possible correction.** Do not rewrite the whole artifact.
   Tell the local model exactly what to fix and what the correct behavior is.

3. **Use a structured feedback prompt:**

   ```
   REVISION REQUEST — [task name]

   The following issues were found in your output:

   ISSUE 1: [exact location — file, function, line if known]
   PROBLEM: [what is wrong]
   REQUIRED FIX: [exact correction or behavior expected]

   ISSUE 2: [if applicable]
   ...

   Return the corrected artifact only. No explanations.
   ```

4. **Do not introduce scope creep.** The review covers correctness against the
   original spec only — not style preferences or future refactoring opportunities.

---

## 5. Local Worker Handoff Protocol

When sending a handoff packet to the local worker council, keep prompts tight:

1. **Bounded input:** Pass only the specific file or code chunk needed.
2. **One task per dispatch:** One instruction → one artifact.
3. **Exact output format:** Specify format explicitly — no freeform prose.

**Dispatch wrapper:**
```
You are a local code execution worker. Complete the following task.
Output ONLY the requested artifact. No explanations or commentary.

TASK: [single precise instruction]
OUTPUT FORMAT: [raw Python / JSON / Markdown / etc.]
INPUT:
[bounded code or data]
```

---

## 6. Escalation Criteria

The Project Manager escalates to direct cloud execution **only** when:

- The local model failed to correct the same issue after **2 feedback cycles**
- The task requires reasoning across **3+ files simultaneously** and cannot be
  decomposed into bounded sub-tasks
- The output involves a **security-critical path** (auth, access control, audit
  trail) where a single error has outsized consequences
- The task is **genuinely novel** — not implementing a known pattern, but
  determining the right approach from scratch

Escalation covers **only the specific task** that failed. All other concurrent
tasks remain with the local worker council.

---

## 7. What This Is Not

- The cloud supervisor is not a co-pilot writing code alongside the local model.
  It reviews completed artifacts, not in-progress generation.
- This is not a ban on direct cloud execution. If the user explicitly requests
  the cloud model for a task, honor it — this config governs autonomous routing,
  not user intent.
- Human review gates are not part of this loop. Compliance, legal, or evidence
  decisions always stop at a human, regardless of which tier produced the output.
