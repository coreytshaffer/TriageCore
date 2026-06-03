from triage_core.handoff import HandoffPacket

def test_handoff_packet_creation():
    packet = HandoffPacket(
        title="Test Task",
        summary="Fix the bug",
        context="System was breaking on startup",
        target_files=["main.py"],
        constraints=["No downtime"],
        acceptance_criteria=["It starts up"],
        test_commands=["pytest"],
        safety_notes=["Check secrets"],
        recommended_backend="Local",
        recommended_permission_profile="workspace-write",
        risk_level="low"
    )
    
    assert packet.title == "Test Task"
    
    md = packet.to_markdown()
    assert "# Test Task" in md
    assert "- main.py" in md
    assert "- [ ] It starts up" in md
