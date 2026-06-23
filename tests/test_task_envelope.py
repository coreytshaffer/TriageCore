from triage_core.task_envelope import TaskEnvelope, render_task_envelope_markdown

def _get_base_envelope() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="CR-053",
        title="Markdown Task Report Export",
        objective="Render task envelopes as Markdown.",
        repo="TriageCore",
        operator_agent_lane="test-lane",
        route="test-route",
        risk_level="Low",
        requested_capability="read_only",
        allowed_files=(),
        forbidden_files_or_areas=(),
        explicit_non_scope=(),
        approval_gates="None",
        validation_plan="Tests",
        evidence_to_produce=(),
        current_status="proposed",
        operator_decision="Pending",
        next_allowed_action="Review",
    )

def test_render_task_envelope_markdown_contains_required_sections():
    env = _get_base_envelope()
    md = render_task_envelope_markdown(env)
    
    assert "# CR-053 Task Envelope" in md
    assert "**Title:** Markdown Task Report Export" in md
    assert "## Scope & Risk" in md
    assert "## Governance" in md
    assert "## Admission State" in md
    assert "**Next Allowed Action:** Review" in md
    assert "**Current Status:** proposed" in md

def test_render_task_envelope_markdown_renders_allowed_and_forbidden_files():
    env = TaskEnvelope(
        task_id="TEST",
        title="Files Test",
        objective="Test files",
        repo="TriageCore",
        operator_agent_lane="lane",
        route="route",
        risk_level="Low",
        requested_capability="read_only",
        allowed_files=("file_a.txt", "dir_b/"),
        forbidden_files_or_areas=("secret.key",),
        explicit_non_scope=("Network",),
        approval_gates="None",
        validation_plan="None",
        evidence_to_produce=("evidence.md",),
        current_status="admitted",
        operator_decision="Approved",
        next_allowed_action="Execute",
    )
    md = render_task_envelope_markdown(env)
    
    assert "**Allowed Files:**\n- file_a.txt\n- dir_b/" in md
    assert "**Forbidden Files or Areas:**\n- secret.key" in md
    assert "**Explicit Non-Scope:**\n- Network" in md
    assert "**Evidence to Produce:**\n- evidence.md" in md

def test_render_task_envelope_markdown_renders_blocked_reasons():
    env = TaskEnvelope(
        task_id="TEST-BLOCK",
        title="Blocked Test",
        objective="Test block",
        repo="TriageCore",
        operator_agent_lane="lane",
        route="route",
        risk_level="High",
        requested_capability="mutate",
        allowed_files=(),
        forbidden_files_or_areas=(),
        explicit_non_scope=(),
        approval_gates="None",
        validation_plan="None",
        evidence_to_produce=(),
        current_status="blocked",
        operator_decision="Denied",
        failure_modes_or_blocked_reasons="Unapproved route",
        next_allowed_action="Fix route",
    )
    md = render_task_envelope_markdown(env)
    assert "**Failure Modes / Blocked Reasons:** Unapproved route" in md

    # Empty blocked reasons renders as "None"
    env_empty = _get_base_envelope()
    md_empty = render_task_envelope_markdown(env_empty)
    assert "**Failure Modes / Blocked Reasons:** None" in md_empty

def test_render_task_envelope_markdown_is_deterministic():
    env = _get_base_envelope()
    md1 = render_task_envelope_markdown(env)
    md2 = render_task_envelope_markdown(env)
    assert md1 == md2
