from triage_core.tc_cli import main



def run_cli(monkeypatch, capsys, tmp_path, args):
    monkeypatch.chdir(tmp_path)
    import sys

    with monkeypatch.context() as m:
        m.setattr(sys, "argv", ["tc"] + args)
        main()

    return capsys.readouterr().out



def test_tokens_smoke_test_prints_expected_summary_and_writes_no_runtime_state(
    tmp_path, monkeypatch, capsys
):
    out = run_cli(monkeypatch, capsys, tmp_path, ["tokens", "smoke-test"])

    assert "Token efficiency smoke test passed" in out
    assert "baseline_estimated_total=4800" in out
    assert "candidate_estimated_total=1800" in out
    assert "estimated_tokens_saved=3000" in out
    assert "estimated_percent_saved=62.5" in out
    assert not (tmp_path / ".triagecore").exists()
