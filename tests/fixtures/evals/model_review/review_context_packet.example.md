# Example reviewer context packet

A small deterministic context bundle used to exercise section-scoped citation
resolution for the review harness. It is intentionally tiny and hand-readable,
not a real repository export. The `FILE:` markers below are the anchors the
checker resolves citations against.

---
FILE: pyproject.toml
---

[project]
name = "triagecore"
description = "A lightweight, local-compute-first orchestration harness for token-efficient agent workflows."
dependencies = [
    "cryptography>=42.0.0",
    "pyyaml>=6.0"
]

[project.scripts]
tc = "triage_core.tc_cli:main"

---
FILE: tests/test_identity_cli.py
---

def test_identity_init_creates_key_and_public_metadata(tmp_path):
    # Registry at .triagecore/identity/agents.json maps agent_id -> role,
    # public_key, capabilities.
    ...


def test_signed_smoke_test_fails_if_identity_lacks_route_audit_sign(tmp_path):
    # Capabilities include route_audit:sign and validation_result:sign.
    ...
