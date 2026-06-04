def test_ui_import_graceful_degradation():
    from triage_core.ui.app import UI_AVAILABLE, TriageDeskApp
    # As long as it imports without throwing an error when customtkinter isn't present,
    # or loads fine when it is, the smoke test passes.
    assert TriageDeskApp is not None
