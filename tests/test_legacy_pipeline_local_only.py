import builtins
import os
import sys

import pytest

from triage_core.cli import main
from test_endpoint_transport_guard import record_adapter, transport_tripwires


def test_pipeline_streams_through_the_approved_local_backend(monkeypatch, tmp_path, capsys):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "lmstudio")
    monkeypatch.setenv("TRIAGE_MODEL", "fixture")
    monkeypatch.setenv("TRIAGE_BASE_URL", "http://127.0.0.1:1234/v1")
    source = tmp_path / "input.txt"
    source.write_text("Synthetic input", encoding="utf-8")
    output = tmp_path / "output.txt"
    ledger = tmp_path / "ledger"
    monkeypatch.setattr(sys, "argv", [
        "triagecore", "run-pipeline", "--prompt", "Summarize this",
        "--files", str(source), "--output", str(output), "--ledger-dir", str(ledger),
    ])

    main()

    assert output.read_text(encoding="utf-8") == "done"
    assert "Status: SUCCESS" in capsys.readouterr().out
    [(request, settings)] = sends
    assert (request.method, request.url) == (
        "POST", "http://127.0.0.1:1234/v1/chat/completions",
    )
    assert settings["stream"] is True
    assert b"Synthetic input" in request.body
    assert '"event_type": "local_draft_generated"' in (ledger / "ledger.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind, url", [
    ("custom", "http://example.invalid/v1"),
    ("qwen", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
])
def test_pipeline_refuses_before_reading_input_or_creating_output(
    monkeypatch, tmp_path, capsys, kind, url
):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", kind)
    monkeypatch.setenv("TRIAGE_MODEL", "fixture")
    monkeypatch.setenv("TRIAGE_BASE_URL", url)
    source = tmp_path / "input.txt"
    source.write_text("Synthetic input", encoding="utf-8")
    output = tmp_path / "output.txt"
    ledger = tmp_path / "ledger"
    original_open = builtins.open

    def protected_open(path, *args, **kwargs):
        if not isinstance(path, int) and os.fspath(path) == str(source):
            pytest.fail("The pipeline read a file before approving the destination")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", protected_open)
    monkeypatch.setattr(sys, "argv", [
        "triagecore", "run-pipeline", "--prompt", "Summarize this",
        "--files", str(source), "--output", str(output), "--ledger-dir", str(ledger),
    ])

    with pytest.raises(SystemExit) as exit_status:
        main()

    assert exit_status.value.code == 2
    message = capsys.readouterr().out
    assert "Local destination policy refused the pipeline" in message
    assert url not in message
    assert not sends
    assert not output.exists()
    assert not ledger.exists()
