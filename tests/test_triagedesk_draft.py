import json
import os
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from triage_core import cli
from triage_core.ui import app

PROMPT = "Summarize the synthetic garden notes.\nKeep the plant names: lavandā."


def _unexpected(*_args, **_kwargs):
    pytest.fail("Draft operations cannot start work or touch the activity ledger.")


@pytest.fixture
def run_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.default_config, "get_ledger_dir", lambda: str(tmp_path / "ledger"))
    monkeypatch.setattr(cli, "_log_cli_activity", _unexpected)
    # Keep the test inert on revisions that still expose the retired producer.
    if hasattr(cli, "_push_task_to_ui"):
        monkeypatch.setattr(cli, "_push_task_to_ui", _unexpected)

    def invoke(*args):
        monkeypatch.setattr(sys, "argv", ["triagecore", "push-task", "--prompt", PROMPT, *args])
        cli.main()

    return invoke


def test_cli_exports_prompt_only_to_explicit_new_destination(tmp_path, run_cli, capsys):
    output = tmp_path / "garden.json"
    run_cli("--output", str(output), "--files")
    assert json.loads(output.read_bytes()) == {"version": 1, "prompt": PROMPT}
    assert "Import Draft" in capsys.readouterr().out
    assert sorted(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize(
    "flags",
    [
        ("--files", "garden.txt"),
        ("--files", "garden.txt", "--files"),
        ("--auto-dispatch", "local"),
    ],
)
def test_cli_explains_retired_options_without_side_effects(tmp_path, run_cli, capsys, flags):
    output = tmp_path / "garden.json"
    with pytest.raises(SystemExit) as exc:
        run_cli(*flags)
    assert exc.value.code == 2
    assert "Import Draft" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        run_cli("--output", str(output), *flags)
    assert exc.value.code == 2
    assert "Import Draft" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_cli_requires_new_destination_and_preserves_existing_file(tmp_path, run_cli, capsys):
    with pytest.raises(SystemExit) as exc:
        run_cli()
    assert exc.value.code == 2
    assert "--output" in capsys.readouterr().err
    output = tmp_path / "garden.json"
    output.write_bytes(b"existing synthetic content")
    with pytest.raises(SystemExit) as exc:
        run_cli("--output", str(output))
    assert exc.value.code == 2
    assert "already exists" in capsys.readouterr().err
    assert output.read_bytes() == b"existing synthetic content"
    assert sorted(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize(
    "raw",
    [
        b'["synthetic marker"]',
        b'{"version":1,"prompt":"synthetic marker","files":[]}',
        b'{"version":1,"prompt":"synthetic marker","auto_dispatch":null}',
        b'{"version":1,"prompt":"synthetic marker","prompt":"duplicate"}',
        b'{"version":1,"version":1,"prompt":"synthetic marker"}',
        b'{"version":true,"prompt":"synthetic marker"}',
        b'{"version":1.0,"prompt":"synthetic marker"}',
        b'{"version":2,"prompt":"synthetic marker"}',
        b'{"version":1,"prompt":false}',
        b'{"version":1,"prompt":" \n "}',
        b'{"version":1,"prompt":"synthetic marker',
        b'{"version":1,"prompt":"synthetic marker"} trailing',
        b'{"version":1,"prompt":"synthetic marker\xff"}',
        b'{"version":1,"prompt":"synthetic marker\\ud800"}',
        b'{"version":1,"prompt":"synthetic marker\\u0000"}',
        b"[" * 1000 + b'"synthetic marker"' + b"]" * 1000,
    ],
)
def test_invalid_draft_schema_returns_fixed_diagnostic(tmp_path, raw):
    from triage_core import triagedesk_draft

    draft = tmp_path / "garden.json"
    draft.write_bytes(raw)
    with pytest.raises(triagedesk_draft.DraftError) as exc:
        triagedesk_draft.read_draft(draft)
    assert "synthetic marker" not in str(exc.value)


def test_maximum_size_is_measured_on_encoded_file(tmp_path):
    from triage_core import triagedesk_draft

    output = tmp_path / "garden.json"
    raw = json.dumps({"version": 1, "prompt": PROMPT}).encode("utf-8")
    raw = raw.ljust(triagedesk_draft.MAX_DRAFT_BYTES)
    output.write_bytes(raw)
    assert triagedesk_draft.read_draft(output) == PROMPT
    output.write_bytes(raw + b" ")
    with pytest.raises(triagedesk_draft.DraftError, match="too large"):
        triagedesk_draft.read_draft(output)
    too_large = tmp_path / "too-large.json"
    with pytest.raises(triagedesk_draft.DraftError, match="too large"):
        triagedesk_draft.write_draft(too_large, "é" * (triagedesk_draft.MAX_DRAFT_BYTES // 2))
    assert not too_large.exists()


@pytest.mark.parametrize("prompt", ["", "\n \t", "garden\x00notes", "garden\ud800"])
def test_export_rejects_non_displayable_or_empty_prompt(tmp_path, prompt):
    from triage_core import triagedesk_draft

    output = tmp_path / "garden.json"
    with pytest.raises(triagedesk_draft.DraftError):
        triagedesk_draft.write_draft(output, prompt)
    assert not output.exists()


def _stat_with_changes(info, **changes):
    fields = ("st_mode", "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
    values = {field: getattr(info, field) for field in fields}
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("after_write", [False, True])
def test_export_refuses_uncertain_open_file_metadata(tmp_path, monkeypatch, after_write):
    from triage_core import triagedesk_draft

    output = tmp_path / "garden.json"
    real_fstat = os.fstat

    def fstat_with_unexpected_links(fd):
        info = real_fstat(fd)
        if bool(info.st_size) == after_write:
            return _stat_with_changes(info, st_nlink=2)
        return info

    monkeypatch.setattr(triagedesk_draft.os, "fstat", fstat_with_unexpected_links)
    with pytest.raises(triagedesk_draft.DraftError, match="incomplete"):
        triagedesk_draft.write_draft(output, PROMPT)
    assert output.exists()
    if not after_write:
        assert output.stat().st_size == 0


def test_export_reconciles_output_name_under_the_same_parent(tmp_path, monkeypatch):
    from triage_core import triagedesk_draft

    output = tmp_path / "garden.json"
    other_parent = tmp_path / "other"
    other_parent.mkdir()
    native_chain = triagedesk_draft._chain
    opened = []

    @contextmanager
    def check_other_parent(path):
        opened.append(path)
        with native_chain(path if len(opened) == 1 else other_parent) as token:
            yield token

    monkeypatch.setattr(triagedesk_draft, "_chain", check_other_parent)
    with pytest.raises(triagedesk_draft.DraftError, match="incomplete"):
        triagedesk_draft.write_draft(output, PROMPT)
    assert output.exists()
    assert list(other_parent.iterdir()) == []


def test_export_reconciles_the_name_with_the_open_file(tmp_path, monkeypatch):
    from triage_core import triagedesk_draft

    output = tmp_path / "garden.json"
    if os.name == "nt":
        monkeypatch.setattr(triagedesk_draft, "_is_windows_regular", lambda *_: False, raising=False)
    else:
        real_stat = os.stat

        def stat_with_unexpected_identity(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == output.name and kwargs.get("dir_fd") is not None:
                return _stat_with_changes(info, st_ino=info.st_ino + 1)
            return info

        monkeypatch.setattr(triagedesk_draft.os, "stat", stat_with_unexpected_identity)

    with pytest.raises(triagedesk_draft.DraftError, match="incomplete"):
        triagedesk_draft.write_draft(output, PROMPT)
    assert output.exists()


@pytest.mark.skipif(os.name != "posix", reason="Double-slash anchors are a POSIX path form.")
def test_draft_rejects_double_slash_anchor_before_open(tmp_path, monkeypatch):
    from triage_core import triagedesk_draft

    output = tmp_path / "garden.json"
    monkeypatch.setattr(triagedesk_draft, "_chain", _unexpected)
    ambiguous = f"/{output}"
    with pytest.raises(triagedesk_draft.DraftError):
        triagedesk_draft.write_draft(ambiguous, PROMPT)
    with pytest.raises(triagedesk_draft.DraftError):
        triagedesk_draft.read_draft(ambiguous)
    assert not output.exists()


def test_read_refuses_hardlinked_leaf(tmp_path):
    from triage_core import triagedesk_draft

    source = tmp_path / "original.json"
    triagedesk_draft.write_draft(source, PROMPT)
    linked = tmp_path / "linked.json"
    try:
        os.link(source, linked)
    except OSError as exc:
        if os.name == "nt" and exc.winerror in (5, 1314):
            pytest.skip("Windows hardlink permission is unavailable.")
        raise
    for path in (source, linked):
        with pytest.raises(triagedesk_draft.DraftError):
            triagedesk_draft.read_draft(path)


@pytest.mark.parametrize("ancestor", [False, True])
def test_read_refuses_symlink_at_leaf_or_ancestor(tmp_path, ancestor):
    from triage_core import triagedesk_draft

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    source = real_dir / "original.json"
    triagedesk_draft.write_draft(source, PROMPT)
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real_dir if ancestor else source, target_is_directory=ancestor)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Windows symlink permission is unavailable.")
        raise
    with pytest.raises(triagedesk_draft.DraftError):
        triagedesk_draft.read_draft(linked / source.name if ancestor else linked)


@pytest.mark.skipif(os.name != "nt", reason="Junctions are a Windows reparse type.")
def test_windows_refuses_junction_ancestor(tmp_path):
    from triage_core import triagedesk_draft

    actual = tmp_path / "actual"
    actual.mkdir()
    source = actual / "garden.json"
    triagedesk_draft.write_draft(source, PROMPT)
    linked = tmp_path / "linked"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/j", str(linked), str(actual)],
        check=False,
        capture_output=True,
    )
    if result.returncode == 1 and b"access is denied" in (result.stdout + result.stderr).lower():
        pytest.skip("Windows junction creation permission is unavailable.")
    result.check_returncode()
    try:
        with pytest.raises(triagedesk_draft.DraftError):
            triagedesk_draft.read_draft(linked / source.name)
    finally:
        linked.rmdir()


def test_read_refuses_directory_and_missing_file(tmp_path):
    from triage_core import triagedesk_draft

    for path in (tmp_path, tmp_path / "missing.json"):
        with pytest.raises(triagedesk_draft.DraftError):
            triagedesk_draft.read_draft(path)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is a POSIX file type.")
def test_read_refuses_fifo(tmp_path):
    from triage_core import triagedesk_draft

    fifo = tmp_path / "garden.json"
    os.mkfifo(fifo)
    with pytest.raises(triagedesk_draft.DraftError):
        triagedesk_draft.read_draft(fifo)


class _Entry:
    def __init__(self, value):
        self.value = value

    def get(self, *_args):
        return self.value

    def delete(self, *_args):
        self.value = ""

    def insert(self, _index, value):
        self.value = value

    def configure(self, **_kwargs):
        pass


@pytest.fixture
def composer(monkeypatch):
    monkeypatch.setattr(app, "create_context_pack_artifact", _unexpected)
    return SimpleNamespace(
        prompt_box=_Entry("Unsaved garden notes"),
        files_entry=_Entry("old-garden.txt"),
        current_loaded_task_id="previous-task",
        status_label=Mock(),
        ledger=SimpleNamespace(append_event=_unexpected),
        focus_force=_unexpected,
        _handle_task=_unexpected,
        _dispatch_local=_unexpected,
        _dispatch_council=_unexpected,
        _dispatch_codex=_unexpected,
        _dispatch_antigravity=_unexpected,
        _dispatch_pipeline=_unexpected,
        after=_unexpected,
    )


def _choose_file(monkeypatch, path):
    monkeypatch.setattr(app.filedialog, "askopenfilename", lambda **_kwargs: str(path))


def test_background_watcher_is_retired():
    assert not hasattr(app.TriageDeskApp, "_start_ipc_watcher")
    assert not hasattr(app.TriageDeskApp, "_check_ipc_inbox")


@pytest.mark.parametrize("confirm", [False, True])
def test_explicit_import_previews_before_replacing_composer(tmp_path, monkeypatch, composer, confirm):
    draft = tmp_path / "garden.json"
    draft.write_text(json.dumps({"version": 1, "prompt": PROMPT}), encoding="utf-8")
    _choose_file(monkeypatch, draft)

    def preview(prompt):
        assert prompt == PROMPT
        assert composer.prompt_box.value == "Unsaved garden notes"
        assert composer.files_entry.value == "old-garden.txt"
        # Confirm the reviewed in-memory snapshot even if the file is later edited.
        draft.write_text(json.dumps({"version": 1, "prompt": "Later edit"}), encoding="utf-8")
        return confirm

    composer._confirm_draft_import = Mock(side_effect=preview)
    app.TriageDeskApp._import_draft(composer)
    composer._confirm_draft_import.assert_called_once_with(PROMPT)

    if confirm:
        assert composer.prompt_box.value == PROMPT
        assert composer.files_entry.value == ""
        assert composer.current_loaded_task_id is None
    else:
        assert composer.prompt_box.value == "Unsaved garden notes"
        assert composer.files_entry.value == "old-garden.txt"
        assert composer.current_loaded_task_id == "previous-task"
        composer.status_label.configure.assert_not_called()


def test_picker_cancel_does_not_show_preview_or_change_composer(monkeypatch, composer):
    _choose_file(monkeypatch, "")
    composer._confirm_draft_import = _unexpected
    app.TriageDeskApp._import_draft(composer)
    assert composer.prompt_box.value == "Unsaved garden notes"
    assert composer.files_entry.value == "old-garden.txt"
    composer.status_label.configure.assert_not_called()


def test_invalid_import_keeps_composer_and_omits_raw_data(tmp_path, monkeypatch, composer):
    draft = tmp_path / "garden.json"
    draft.write_bytes(b"invalid synthetic marker")
    _choose_file(monkeypatch, draft)
    composer._confirm_draft_import = _unexpected
    error = Mock()
    monkeypatch.setattr(app.messagebox, "showerror", error)
    app.TriageDeskApp._import_draft(composer)
    error.assert_called_once()
    assert "invalid synthetic marker" not in str(error.call_args)
    assert composer.prompt_box.value == "Unsaved garden notes"
    assert composer.files_entry.value == "old-garden.txt"
    assert composer.current_loaded_task_id == "previous-task"
    composer.status_label.configure.assert_not_called()


@pytest.mark.skipif(
    os.name != "nt" or os.getenv("TRIAGECORE_WINDOWS_DESKTOP_SMOKE") != "1",
    reason="Requires an opt-in Windows desktop session.",
)
def test_windows_desktop_draft_import_smoke(tmp_path, monkeypatch):
    import tkinter

    from triage_core.triagedesk_draft import write_draft

    assert app.UI_AVAILABLE
    ledger = tmp_path / "ledger"
    monkeypatch.setattr(app.default_config, "get_ledger_dir", lambda: str(ledger))
    monkeypatch.setattr(app.TriageDeskApp, "_check_backends", lambda self: None)
    runner = Mock()
    monkeypatch.setattr(app.TriageDeskApp, "_dispatch_local", runner)
    for name in ("_dispatch_council", "_dispatch_codex", "_dispatch_antigravity", "_dispatch_pipeline"):
        monkeypatch.setattr(app.TriageDeskApp, name, _unexpected)

    draft = tmp_path / "garden.json"
    prompt = PROMPT + "\n" * 100 + "The last line is part of the review."
    write_draft(draft, prompt)
    _choose_file(monkeypatch, draft)
    desk = app.TriageDeskApp()
    try:
        desk.update()
        desk.btn_local.invoke()
        runner.assert_not_called()
        assert not (ledger / "ledger.jsonl").exists()
        desk.prompt_box.delete("0.0", "end")
        desk.prompt_box.insert("0.0", "Unsaved garden notes")
        desk.files_entry.insert(0, "old-garden.txt")

        inbox = ledger / "ipc_inbox.json"
        old_payload = b'{"prompt":"An inert legacy garden draft"}'
        inbox.write_bytes(old_payload)
        desk.after(1300, desk.quit)
        desk.mainloop()
        assert inbox.read_bytes() == old_payload
        assert desk.prompt_box.get("0.0", "end-1c") == "Unsaved garden notes"
        assert desk.files_entry.get() == "old-garden.txt"

        control = next(
            widget for widget in desk.dispatch_frame.winfo_children()
            if isinstance(widget, app.ctk.CTkButton) and widget.cget("text") == "Import Draft"
        )
        assert control.winfo_viewable()
        errors = []

        def choose(button):
            dialog = next(
                widget for widget in desk.winfo_children() if isinstance(widget, app.ctk.CTkToplevel)
            )
            try:
                assert dialog.winfo_viewable()
                assert dialog.title() == "Review Draft"
                preview = next(widget for widget in dialog.winfo_children() if isinstance(widget, app.ctk.CTkTextbox))
                text = next(widget for widget in preview.winfo_children() if isinstance(widget, tkinter.Text))
                assert text.cget("state") == "disabled"
                assert preview.get("0.0", "end-1c") == prompt
                if "\n" * 100 in prompt:
                    assert preview.yview()[1] < 1
                    preview.yview_moveto(1)
                    dialog.update_idletasks()
                    assert preview.yview()[1] == 1
                actions = next(widget for widget in dialog.winfo_children() if isinstance(widget, app.ctk.CTkFrame))
                next(widget for widget in actions.winfo_children() if widget.cget("text") == button).invoke()
            except (AssertionError, StopIteration, tkinter.TclError) as exc:
                errors.append(exc)
                dialog.destroy()

        desk.after(250, choose, "Cancel")
        control.invoke()
        assert not errors, errors
        assert desk.prompt_box.get("0.0", "end-1c") == "Unsaved garden notes"
        assert desk.files_entry.get() == "old-garden.txt"

        desk.after(250, choose, "Load Draft")
        control.invoke()
        assert not errors, errors
        assert desk.prompt_box.get("0.0", "end-1c") == prompt
        assert desk.files_entry.get() == ""
        assert not (ledger / "ledger.jsonl").exists()
        assert not (ledger / "context_packs").exists()
        runner.assert_not_called()

        attachment = tmp_path / "new-garden.txt"
        attachment.write_text("Synthetic attachment selected after review.", encoding="utf-8")
        desk.files_entry.insert(0, str(attachment))
        desk.btn_local.invoke()
        runner.assert_called_once()
        _, received_prompt, files, _ = runner.call_args.args
        assert received_prompt == prompt
        assert files == [str(attachment)]
        pack_path, = (ledger / "context_packs").iterdir()
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        assert [item["label"] for item in pack["items"]] == ["task_prompt", str(attachment)]
        assert (ledger / "ledger.jsonl").is_file()

        # The placeholder's label is also valid user text.
        prompt = "Describe your task here…"
        literal_draft = tmp_path / "literal-draft.json"
        write_draft(literal_draft, prompt)
        _choose_file(monkeypatch, literal_draft)
        desk.after(250, choose, "Load Draft")
        control.invoke()
        assert not errors, errors
        textbox = next(widget for widget in desk.prompt_box.winfo_children() if isinstance(widget, tkinter.Text))
        textbox.event_generate("<FocusIn>")
        assert desk.prompt_box.get("0.0", "end-1c") == prompt
        desk.btn_local.invoke()
        assert runner.call_count == 2
        assert runner.call_args.args[1:3] == (prompt, [])
    finally:
        desk.destroy()
