"""Tests for tools/check_change_scope.py."""

import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Dict, List, Tuple

SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "tools" / "check_change_scope.py"
)


def _setup_git_repo(repo_dir: pathlib.Path) -> None:
    """Initialize a clean Git repository in repo_dir."""
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "TestUser"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )


def _run_checker(cwd: pathlib.Path, args: List[str]) -> Tuple[int, Dict, str]:
    """Run tools/check_change_scope.py in cwd and parse stdout JSON."""
    cmd = [sys.executable, str(SCRIPT_PATH)] + args
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    stdout_json = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, stdout_json, proc.stderr


def test_all_changed_files_allowed():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "file1.txt").write_text("initial 1")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "file1.txt").write_text("modified 1")
        (repo_dir / "file2.txt").write_text("new 2")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "changes"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir, ["--base", "HEAD~1", "--allow", "file1.txt", "--allow", "file2.txt"]
        )

        assert code == 0
        assert data["status"] == 0
        assert data["base"] == "HEAD~1"
        assert data["changed_paths"] == ["file1.txt", "file2.txt"]
        assert data["allowed_paths"] == ["file1.txt", "file2.txt"]
        assert data["unexpected_paths"] == []
        assert stderr == ""


def test_one_unexpected_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "file1.txt").write_text("initial 1")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "file1.txt").write_text("modified 1")
        (repo_dir / "unallowed.txt").write_text("unexpected")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "changes"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir, ["--base", "HEAD~1", "--allow", "file1.txt"]
        )

        assert code == 2
        assert data["status"] == 2
        assert data["changed_paths"] == ["file1.txt", "unallowed.txt"]
        assert data["allowed_paths"] == ["file1.txt"]
        assert data["unexpected_paths"] == ["unallowed.txt"]
        assert "unallowed.txt" in stderr


def test_invalid_base_reference():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "file1.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir, ["--base", "invalid_ref_12345", "--allow", "file1.txt"]
        )

        assert code == 3
        assert data["status"] == 3
        assert data["changed_paths"] == []
        assert data["allowed_paths"] == ["file1.txt"]
        assert data["unexpected_paths"] == []
        assert "invalid_ref_12345" in stderr


def test_execution_outside_git_repository():
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_git_dir = pathlib.Path(tmp_dir)

        code, data, stderr = _run_checker(
            non_git_dir, ["--base", "main", "--allow", "file1.txt"]
        )

        assert code == 3
        assert data["status"] == 3
        assert data["changed_paths"] == []
        assert data["allowed_paths"] == ["file1.txt"]
        assert data["unexpected_paths"] == []
        assert "Not a Git repository" in stderr or "Git" in stderr


def test_no_tracked_changes():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "file1.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir, ["--base", "HEAD", "--allow", "file1.txt"]
        )

        assert code == 3
        assert data["status"] == 3
        assert data["changed_paths"] == []
        assert data["allowed_paths"] == ["file1.txt"]
        assert data["unexpected_paths"] == []
        assert "No tracked files differ" in stderr


def test_renamed_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "old_name.txt").write_text("content to rename")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        subprocess.run(
            ["git", "mv", "old_name.txt", "new_name.txt"], cwd=repo_dir, check=True
        )
        subprocess.run(["git", "commit", "-m", "rename"], cwd=repo_dir, check=True)

        # Both old and new path allowed
        code, data, stderr = _run_checker(
            repo_dir,
            [
                "--base",
                "HEAD~1",
                "--allow",
                "old_name.txt",
                "--allow",
                "new_name.txt",
            ],
        )

        assert code == 0
        assert data["status"] == 0
        assert data["changed_paths"] == ["new_name.txt", "old_name.txt"]

        # Only new path allowed -> old path is unexpected
        code2, data2, stderr2 = _run_checker(
            repo_dir, ["--base", "HEAD~1", "--allow", "new_name.txt"]
        )

        assert code2 == 2
        assert data2["status"] == 2
        assert data2["unexpected_paths"] == ["old_name.txt"]


def test_paths_containing_spaces():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        sub_dir = repo_dir / "dir with spaces"
        sub_dir.mkdir()
        file_with_spaces = sub_dir / "file with spaces.txt"
        file_with_spaces.write_text("initial content")

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        file_with_spaces.write_text("modified content")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "modified"], cwd=repo_dir, check=True)

        rel_path = "dir with spaces/file with spaces.txt"
        code, data, stderr = _run_checker(
            repo_dir, ["--base", "HEAD~1", "--allow", rel_path]
        )

        assert code == 0
        assert data["status"] == 0
        assert data["changed_paths"] == [rel_path]
        assert data["allowed_paths"] == [rel_path]


def test_windows_style_allowlist_input_normalized():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        pkg_dir = repo_dir / "src" / "triagecore"
        pkg_dir.mkdir(parents=True)
        authz_file = pkg_dir / "authz.py"
        authz_file.write_text("authz content")

        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        authz_file.write_text("modified authz content")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "mod"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir,
            ["--base", "HEAD~1", "--allow", r"src\triagecore\authz.py"],
        )

        assert code == 0
        assert data["status"] == 0
        assert data["allowed_paths"] == ["src/triagecore/authz.py"]
        assert data["changed_paths"] == ["src/triagecore/authz.py"]
        assert data["unexpected_paths"] == []


def test_copied_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "source_file.txt").write_text(
            "substantial content line 1\nline 2\nline 3\n"
        )
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "copied_file.txt").write_text(
            "substantial content line 1\nline 2\nline 3\n"
        )
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "copy file"], cwd=repo_dir, check=True)

        # Unchanged copy source (source_file.txt) is not a changed path;
        # only the newly created destination (copied_file.txt) is in changed_paths.
        code, data, stderr = _run_checker(
            repo_dir,
            [
                "--base",
                "HEAD~1",
                "--allow",
                "copied_file.txt",
            ],
        )

        assert code == 0
        assert data["status"] == 0
        assert data["changed_paths"] == ["copied_file.txt"]
        assert data["allowed_paths"] == ["copied_file.txt"]
        assert data["unexpected_paths"] == []
        assert stderr == ""


def test_copied_file_with_modified_source():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "source_file.txt").write_text(
            "substantial content line 1\nline 2\nline 3\n"
        )
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "copied_file.txt").write_text(
            "substantial content line 1\nline 2\nline 3\n"
        )
        (repo_dir / "source_file.txt").write_text(
            "modified source content line 1\nline 2\n"
        )
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", "copy file and modify source"],
            cwd=repo_dir,
            check=True,
        )

        code, data, stderr = _run_checker(
            repo_dir,
            [
                "--base",
                "HEAD~1",
                "--allow",
                "copied_file.txt",
                "--allow",
                "source_file.txt",
            ],
        )

        assert code == 0
        assert data["status"] == 0
        assert data["changed_paths"] == ["copied_file.txt", "source_file.txt"]
        assert data["allowed_paths"] == ["copied_file.txt", "source_file.txt"]
        assert data["unexpected_paths"] == []
        assert stderr == ""


def test_repeated_allow_arguments_with_duplicates():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "file1.txt").write_text("initial 1")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "file1.txt").write_text("modified 1")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "mod"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir,
            [
                "--base",
                "HEAD~1",
                "--allow",
                "file1.txt",
                "--allow",
                "file1.txt",
            ],
        )

        assert code == 0
        assert data["status"] == 0
        assert data["allowed_paths"] == ["file1.txt"]
        assert data["changed_paths"] == ["file1.txt"]
        assert data["unexpected_paths"] == []
        assert stderr == ""


def test_unsorted_allowlist_paths():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "z_file.txt").write_text("initial z")
        (repo_dir / "a_file.txt").write_text("initial a")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "z_file.txt").write_text("modified z")
        (repo_dir / "a_file.txt").write_text("modified a")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "mod"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir,
            [
                "--base",
                "HEAD~1",
                "--allow",
                "z_file.txt",
                "--allow",
                "a_file.txt",
            ],
        )

        assert code == 0
        assert data["status"] == 0
        assert data["allowed_paths"] == ["a_file.txt", "z_file.txt"]
        assert data["changed_paths"] == ["a_file.txt", "z_file.txt"]
        assert data["unexpected_paths"] == []


def test_mixed_path_separators_for_same_path():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        pkg_dir = repo_dir / "src" / "pkg"
        pkg_dir.mkdir(parents=True)
        mod_file = pkg_dir / "module.py"
        mod_file.write_text("initial module")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        mod_file.write_text("modified module")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "mod"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(
            repo_dir,
            [
                "--base",
                "HEAD~1",
                "--allow",
                r"src\pkg\module.py",
                "--allow",
                "src/pkg/module.py",
            ],
        )

        assert code == 0
        assert data["status"] == 0
        assert data["allowed_paths"] == ["src/pkg/module.py"]
        assert data["changed_paths"] == ["src/pkg/module.py"]
        assert data["unexpected_paths"] == []


def test_empty_allowlist_with_tracked_changes():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "file1.txt").write_text("initial 1")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "file1.txt").write_text("modified 1")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "mod"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(repo_dir, ["--base", "HEAD~1"])

        assert code == 2
        assert data["status"] == 2
        assert data["allowed_paths"] == []
        assert data["changed_paths"] == ["file1.txt"]
        assert data["unexpected_paths"] == ["file1.txt"]
        assert "file1.txt" in stderr


def test_multiple_unexpected_paths_sorted_order():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir)
        _setup_git_repo(repo_dir)

        (repo_dir / "z_file.txt").write_text("initial z")
        (repo_dir / "m_file.txt").write_text("initial m")
        (repo_dir / "a_file.txt").write_text("initial a")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True)

        (repo_dir / "z_file.txt").write_text("mod z")
        (repo_dir / "m_file.txt").write_text("mod m")
        (repo_dir / "a_file.txt").write_text("mod a")
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "mod"], cwd=repo_dir, check=True)

        code, data, stderr = _run_checker(repo_dir, ["--base", "HEAD~1"])

        assert code == 2
        assert data["status"] == 2
        assert data["allowed_paths"] == []
        assert data["changed_paths"] == ["a_file.txt", "m_file.txt", "z_file.txt"]
        assert data["unexpected_paths"] == ["a_file.txt", "m_file.txt", "z_file.txt"]

