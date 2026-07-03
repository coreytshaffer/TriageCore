import sys

from triage_core.route_worker_ledger import inspect_route_worker_ledger
from triage_core.tc_cli import main

FIXTURE_PATH = "docs/examples/route_worker_ledger_demo.jsonl"


def test_route_worker_ledger_demo_fixture_is_valid_and_summarized():
    summary = inspect_route_worker_ledger(FIXTURE_PATH)

    assert summary.total_records == 5
    assert summary.event_type_counts == {
        "route_decision_recorded": 2,
        "worker_result_recorded": 3,
    }
    assert summary.worker_status_counts == {
        "blocked": 1,
        "failed": 1,
        "succeeded": 1,
    }


def test_route_worker_ledger_demo_cli_output(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["tc", "route-worker-ledger", "inspect", "--ledger", FIXTURE_PATH],
    )

    main()

    out = capsys.readouterr().out
    assert "Validation: passed" in out
    assert "Total records: 5" in out
    assert "- route_decision_recorded: 2" in out
    assert "- worker_result_recorded: 3" in out
    assert "- blocked: 1" in out
    assert "- failed: 1" in out
    assert "- succeeded: 1" in out
    assert "Mutation: none" in out
