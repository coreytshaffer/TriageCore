from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from triage_core.task_review_service import ReviewServiceError
from triage_core.ui.app import TriageDeskApp


class DeskReviewActions:
    _execute_context_review = TriageDeskApp._execute_context_review
    _review_task = TriageDeskApp._review_task
    _confirm_task_review = TriageDeskApp._confirm_task_review
    _prompt_review_pin = TriageDeskApp._prompt_review_pin

    def __init__(self, service):
        self.ledger = SimpleNamespace(
            review_service=service,
            get_task=Mock(return_value=SimpleNamespace(
                description="Synthetic review prompt",
                target_files=["synthetic.txt"],
                review=SimpleNamespace(status="verified", decision="accepted", binary_label=True),
            )),
        )
        self.prompt_box = Mock()
        self.files_entry = Mock()
        self.status_label = Mock()
        self.select_frame = Mock()
        self._refresh_ledger = Mock()
        self._refresh_compact_ledger_feed = Mock()
        self._update_ticker = Mock()
        self._refresh_telemetry = Mock()
        self._update_workflow_glow = Mock()
        self.current_loaded_task_id = "task-original"


@pytest.mark.parametrize("entry_point", ["_execute_context_review", "_review_task"])
def test_approve_and_load_waits_for_the_same_local_confirmation(entry_point):
    items = (("first", "Line one\nLine two"), ("second", "Final synthetic evidence\n"))

    class LocalReview:
        def confirm(self, task_id, decision, show_snapshot, *, intent_id=None, request_pin=None):
            assert (task_id, decision, intent_id) == ("task-review", "accepted", None)
            assert show_snapshot(SimpleNamespace(items=items))
            desk.prompt_box.insert.assert_not_called()
            desk.select_frame.assert_not_called()
            return SimpleNamespace(status="verified", decision=decision)

    desk = DeskReviewActions(LocalReview())
    desk._show_review_snapshot = Mock(return_value=True)

    getattr(desk, entry_point)("task-review", True)

    task_id, decision, snapshot = desk._show_review_snapshot.call_args.args
    assert (task_id, decision, snapshot.items) == ("task-review", "accepted", items)
    desk.prompt_box.insert.assert_called_once_with("0.0", "Synthetic review prompt")
    desk.select_frame.assert_called_once_with("dashboard")
    assert desk.current_loaded_task_id == "task-review"


def test_pending_intent_confirmation_uses_its_exact_decision_and_does_not_load():
    class LocalReview:
        def confirm(self, task_id, decision, show_snapshot, *, intent_id=None, request_pin=None):
            assert (task_id, decision, intent_id) == ("task-review", "needs_revision", "intent-1")
            assert show_snapshot(SimpleNamespace(items=(("item", "Synthetic text"),)))
            return SimpleNamespace(status="verified", decision=decision)

    desk = DeskReviewActions(LocalReview())
    desk._show_review_snapshot = Mock(return_value=True)

    desk._confirm_task_review("task-review", "needs_revision", intent_id="intent-1")

    desk.prompt_box.insert.assert_not_called()
    desk.select_frame.assert_not_called()
    assert desk.current_loaded_task_id == "task-original"
    assert "needs revision" in desk.status_label.configure.call_args.kwargs["text"]


def test_portable_pin_is_masked_and_cancellation_leaves_the_prompt_unloaded(monkeypatch):
    from triage_core.ui import app

    class PinProtectedReview:
        def confirm(self, task_id, decision, show_snapshot, *, intent_id=None, request_pin=None):
            assert show_snapshot(SimpleNamespace(items=(("item", "Synthetic text"),)))
            assert request_pin() is None
            raise ReviewServiceError("review_cancelled")

    desk = DeskReviewActions(PinProtectedReview())
    ask_pin = Mock(return_value=None)
    monkeypatch.setattr(app.simpledialog, "askstring", ask_pin)
    desk._show_review_snapshot = Mock(return_value=True)

    desk._execute_context_review("task-review", True)

    assert ask_pin.call_args.kwargs == {"show": "*", "parent": desk}
    desk.prompt_box.insert.assert_not_called()
    assert ask_pin.call_args.kwargs == {"show": "*", "parent": desk}


def test_unverified_result_never_loads_or_claims_success(monkeypatch):
    from triage_core.ui import app

    local_review = Mock()
    local_review.confirm.return_value = SimpleNamespace(status="unavailable", decision=None)
    desk = DeskReviewActions(local_review)
    errors = Mock()
    monkeypatch.setattr(app, "messagebox", SimpleNamespace(showerror=errors))

    desk._review_task("task-review", True)

    desk.prompt_box.insert.assert_not_called()
    desk.select_frame.assert_not_called()
    assert desk.current_loaded_task_id == "task-original"
    assert errors.called
