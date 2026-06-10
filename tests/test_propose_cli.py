import pytest

from triage_core.tc_cli import _slugify, tc_propose


def test_slugify():
    assert _slugify("Example New Change") == "example-new-change"
    assert _slugify("CR-004B: Local-only privacy routing!") == "cr-004b-local-only-privacy-routing"
    assert _slugify("   Spaces  -- ") == "spaces"


def test_propose_creates_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    tc_propose("CR-012", "example new change", False)

    proposal = tmp_path / "docs/change/requests/CR-012-example-new-change.md"
    assert proposal.exists()

    content = proposal.read_text(encoding="utf-8")
    assert "# CR-012: Example New Change" in content
    assert "Proposed" in content
    assert "Acceptance Criteria" in content

    out = capsys.readouterr().out
    assert "Success: Created proposal template" in out


def test_propose_refuses_overwrite(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    proposal_dir = tmp_path / "docs/change/requests"
    proposal_dir.mkdir(parents=True)
    proposal = proposal_dir / "CR-012-example.md"
    proposal.write_text("existing content", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        tc_propose("CR-012", "example", False)

    assert exc.value.code == 1
    assert proposal.read_text(encoding="utf-8") == "existing content"

    out = capsys.readouterr().out
    assert "already exists. Refusing to overwrite" in out


def test_propose_rejects_invalid_cr_id(capsys):
    invalid_ids = ["CR-12", "CR-0001", "PR-012", "012", "CR-012AB"]

    for cr_id in invalid_ids:
        with pytest.raises(SystemExit) as exc:
            tc_propose(cr_id, "title", False)

        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert f"Invalid CR ID format '{cr_id}'" in out


def test_propose_accepts_cr_004b_style(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    tc_propose("CR-004B", "local only routing", False)

    proposal = tmp_path / "docs/change/requests/CR-004B-local-only-routing.md"
    assert proposal.exists()


def test_propose_changelog_adds_entry(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    changelog = tmp_path / "docs/change/change_log.md"
    changelog.parent.mkdir(parents=True)
    changelog.write_text("## [Unreleased]\n- Existing entry\n", encoding="utf-8")

    tc_propose("CR-012", "example change", True)

    content = changelog.read_text(encoding="utf-8")
    assert "CR-012" in content
    assert "Example Change" in content

    out = capsys.readouterr().out
    assert "Success: Added 'CR-012' to [Unreleased] in changelog." in out


def test_propose_changelog_no_duplicate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    changelog = tmp_path / "docs/change/change_log.md"
    changelog.parent.mkdir(parents=True)
    changelog.write_text(
        "## [Unreleased]\n- Proposed CR-012: Example Change\n",
        encoding="utf-8",
    )

    tc_propose("CR-012", "example change", True)

    content = changelog.read_text(encoding="utf-8")
    assert content.count("CR-012") == 1

    out = capsys.readouterr().out
    assert "Notice: Changelog entry for CR-012 already exists." in out
