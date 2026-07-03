import pytest
from unittest.mock import MagicMock

def test_execute_context_review_payload_keys():
    import triage_core.ui.app
    
    class DummyApp:
        def __init__(self):
            self.ledger = MagicMock()
            self.prompt_box = MagicMock()
            self.files_entry = MagicMock()
            self.status_label = MagicMock()
            self.select_frame = MagicMock()
            self._refresh_ledger = MagicMock()
            self._refresh_compact_ledger_feed = MagicMock()
            self._update_ticker = MagicMock()
            self._refresh_telemetry = MagicMock()
            self.current_loaded_task_id = None
            self.review_timers = {}

    app = DummyApp()
    # Bind the method to the dummy app
    execute_review = triage_core.ui.app.TriageDeskApp._execute_context_review.__get__(app)

    # Test "approved"
    execute_review("task-1", accepted=True)
    app.ledger.append_event.assert_called_with("task-1", "review_completed", {"accepted": True})

    # Test "rejected"
    app.ledger.append_event.reset_mock()
    execute_review("task-2", accepted=False)
    app.ledger.append_event.assert_called_with("task-2", "review_completed", {"accepted": False})

    # Test "needs revision"
    app.ledger.append_event.reset_mock()
    execute_review("task-3", accepted=False, decision_override="needs_revision")
    app.ledger.append_event.assert_called_with("task-3", "review_completed", {"accepted": False, "review_decision": "needs_revision"})
