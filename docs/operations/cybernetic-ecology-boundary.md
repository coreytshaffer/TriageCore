# Cybernetic Ecology Boundary Policy

"Cybernetic Ecology" is TriageCore's project-specific name for a configured sensitive-context boundary policy: a set of rules that flag prompts and outputs touching tribal sovereignty and cultural sites, public health and water safety, regulatory-compliance claims, and precise geographic coordinates, and route them toward stricter review before local execution continues unchecked.

This page is explanatory. It is not the policy's source of truth and grants no approval, escalation, or execution authority on its own. Where this page and the files below disagree, the files govern.

## Purpose and Source of Truth

The operative rules live in [`policies/cybernetic_ecology_boundary.yaml`](../../policies/cybernetic_ecology_boundary.yaml), a checked-in YAML file defining named rules — each with matching terms or regex patterns, a recommended escalation decision (`human_only` or `codex`), and a human-readable message. `triagecore.toml` points at this file by default:

```toml
[policies]
boundary_rules_path = "policies/cybernetic_ecology_boundary.yaml"
```

`triage_core/project_steward.py`'s `ProjectSteward` class loads this file and evaluates it against task text. Changes to the configured rule set belong in the YAML file (or in the configured `boundary_rules_path`). The built-in fallback is separate runtime behavior in `ProjectSteward`; changing that floor is a code change and should not be conflated with editing the configured policy.

## Current Integration

- The governed `tc run` path (`TriageClient.run_task`) instantiates `ProjectSteward` and evaluates the task prompt before backend execution, on every allowed (non-blocked) route. A match returns a `handoff_required` result rather than proceeding to the backend.
- `triage_core/run_plan.py` surfaces the firewall's state in a run plan preview: `ethical_firewall_status` (`triggered` or `clear`), `ethical_firewall_policy_source`, currently emitted as the coarse label `configured_or_hardcoded`; that field does not distinguish whether a configured YAML rule or the built-in fallback produced the match. That is the behavior currently implemented — see Fallback Semantics for what the two layers actually cover.
- The separate Local Worker Council orchestrator (`triage_core/orchestration.py`) is a second, independent consumer: it calls `ProjectSteward.generate_escalation_packet()`, which includes the constraint string `"Follow Cybernetic Ecology principles."` in every escalation packet it produces. That string is a pointer for whoever receives the packet, not itself the policy definition — the rules above are.

## Fallback Semantics

Configured YAML rules are evaluated first. If the configured file is missing, unreadable, or contains no rules, or if it loaded but none of its rules matched the given text, `ProjectSteward` falls back to checking a built-in, hardcoded keyword set (`ProjectSteward.SENSITIVE_KEYWORDS`) — a narrower built-in set covering selected tribal/cultural-sensitivity and water-infrastructure terms. It does not cover the YAML file's regulatory-compliance vocabulary or its coordinate-regex rule. This fallback exists so a missing or misconfigured policy file degrades to a narrower built-in floor rather than to no check at all — it is not a replacement for the YAML file, and having a configured file does not disable it; the fallback still runs if the configured rules simply didn't match.

## Decision Semantics

A matched rule produces a *recommended escalation*, not an automatic action:

- `human_only` and `codex` are routing recommendations attached to a `handoff_required` result on the governed `tc run` path. Neither value invokes, approves, or authorizes anything by itself.
- `decision: codex` in particular does not mean Codex is automatically invoked, has approved anything, or is treated as authoritative. On the governed `tc run` path, a steward match specifically stops that path before backend execution and returns `handoff_required`. This should not be generalized into a claim that every `human_review_required` field elsewhere in TriageCore is execution-blocking — it is not.
- This follows the same non-authority pattern documented for other evidence and verdicts elsewhere in this repository (see `AGENTS.md`, "Agent verdicts are not authority"): a steward match is routing evidence, not a consequential-action grant.

## Non-Claims

A rule match is a caution and routing signal only. It does not by itself establish, prove, or certify:

- that the flagged content is actually culturally sensitive, sacred, or archaeologically significant;
- tribal authorization, endorsement, consultation, or representation of any tribe, nation, or community — this policy has no such relationship and must not be described as one unless that provenance is separately and explicitly established;
- legal noncompliance, contamination, or public-health danger;
- the factual correctness of any claim in the flagged text;
- that a non-match means content is safe, compliant, or free of any of the above.

## Verification

- Rule behavior, including the real configured YAML file and the hardcoded fallback, is exercised by [`tests/test_project_steward_firewall.py`](../../tests/test_project_steward_firewall.py).
- The rules themselves are readable directly in [`policies/cybernetic_ecology_boundary.yaml`](../../policies/cybernetic_ecology_boundary.yaml); the configured path is set in `triagecore.toml`.
- This page does not restate exact match logic, precedence details beyond what's described above, or field-level schema for the YAML file — read the source files and tests for exact behavior, per this repository's general policy of documentation pointing to code rather than forking it.
