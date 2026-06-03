from triage_core.cli import _create_packet

def test_create_packet():
    packet = _create_packet("Fix the syntax error", ["main.py"])
    
    assert packet.title == "Task: Bugfix"
    assert "main.py" in packet.target_files
    assert packet.risk_level == "low"
    assert packet.recommended_permission_profile == "workspace-write"
