import os
import pytest
from triage_core.packet_renderer import render_packet, _read_file_text
from triage_core.token_budget import TokenBudget

def test_read_file_text(tmp_path):
    p = tmp_path / "hello.txt"
    p.write_text("world", encoding="utf-8")
    assert _read_file_text(str(p)) == "world"

def test_read_file_text_missing():
    with pytest.raises(FileNotFoundError):
        _read_file_text("does_not_exist.txt")

def test_read_file_text_binary(tmp_path):
    p = tmp_path / "bin.dat"
    p.write_bytes(b"\xff\xfe\x00\x00")
    with pytest.raises(ValueError, match="binary or unreadable"):
        _read_file_text(str(p))

def test_render_packet_fits(tmp_path):
    task = tmp_path / "task.md"
    task.write_text("Fix the bug.", encoding="utf-8")
    
    inc1 = tmp_path / "file1.py"
    inc1.write_text("print('hello')", encoding="utf-8")
    
    budget = TokenBudget("test", 1000, 100, 100) # usable=800
    
    res = render_packet(str(task), budget, [str(inc1)])
    
    assert res.fits_budget is True
    assert "Status: fits" in res.content
    assert "## Task" in res.content
    assert "Fix the bug." in res.content
    assert "## Included Files" in res.content
    assert "print('hello')" in res.content
    assert "## Safety Boundaries" in res.content
    assert "TriageCore Handoff Packet" in res.content

def test_render_packet_over_budget(tmp_path):
    task = tmp_path / "task.md"
    task.write_text("Fix the bug.", encoding="utf-8")
    
    inc1 = tmp_path / "big.py"
    inc1.write_text("a" * 4000, encoding="utf-8") # 1000 tokens
    
    budget = TokenBudget("test", 500, 100, 100) # usable=300
    
    res = render_packet(str(task), budget, [str(inc1)])
    
    assert res.fits_budget is False
    assert "Status: over budget" in res.content
    assert "WARNING" in res.content
    assert "a" * 4000 in res.content
