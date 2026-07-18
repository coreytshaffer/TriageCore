"""Regression proofs that CR-DD-012A remains an unintegrated foundation."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import textwrap


REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOT = REPO_ROOT / "triage_core"

FOUNDATION_MODULES = frozenset(
    {
        "triage_core.governed_run_snapshot",
        "triage_core.governed_decision",
    }
)
FOUNDATION_FILES = frozenset(
    {
        PRODUCTION_ROOT / "governed_run_snapshot.py",
        PRODUCTION_ROOT / "governed_decision.py",
    }
)

# These are the existing integration seams expressly excluded from CR-DD-012A.
PROHIBITED_INTEGRATION_FILES = (
    REPO_ROOT / "docs" / "change" / "change_log.md",
    PRODUCTION_ROOT / "__init__.py",
    PRODUCTION_ROOT / "tc_cli.py",
    PRODUCTION_ROOT / "run_plan.py",
    PRODUCTION_ROOT / "run_plan_artifact.py",
    PRODUCTION_ROOT / "client.py",
    PRODUCTION_ROOT / "engine.py",
    PRODUCTION_ROOT / "routers.py",
    PRODUCTION_ROOT / "task_ledger.py",
)

PUBLIC_IMPORT_SEAMS = (
    "triage_core",
    "triage_core.cli",
    "triage_core.tc_cli",
    "triage_core.run_plan",
    "triage_core.run_plan_artifact",
    "triage_core.client",
    "triage_core.engine",
    "triage_core.routers",
    "triage_core.task_ledger",
)

FORBIDDEN_DECISION_IMPORT_ROOTS = frozenset(
    {
        "datetime",
        "http",
        "os",
        "pathlib",
        "random",
        "requests",
        "secrets",
        "socket",
        "subprocess",
        "time",
        "urllib",
        "uuid",
    }
)
FORBIDDEN_DECISION_TRIAGE_MODULE_PARTS = frozenset(
    {
        "artifacts",
        "backends",
        "client",
        "config",
        "engine",
        "ledger",
        "model",
        "renderer",
        "router",
    }
)


def _production_python_files() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(PRODUCTION_ROOT.rglob("*.py"))
        if path not in FOUNDATION_FILES
    )


def _imported_modules(tree: ast.AST) -> tuple[str, ...]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = ("." * node.level) + (node.module or "")
            imports.append(module)
            imports.extend(
                f"{module}.{alias.name}" if module else alias.name
                for alias in node.names
            )
    return tuple(imports)


def test_no_existing_production_module_mentions_or_imports_foundation() -> None:
    violations: list[str] = []

    for path in _production_python_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imports = _imported_modules(tree)

        if any(
            module.lstrip(".") in FOUNDATION_MODULES
            or module.lstrip(".") in {
                "governed_run_snapshot",
                "governed_decision",
            }
            or module.lstrip(".").startswith("governed_run_snapshot.")
            or module.lstrip(".").startswith("governed_decision.")
            for module in imports
        ):
            violations.append(f"{path.relative_to(REPO_ROOT)} imports foundation")

        # This also catches dynamic imports and indirect module-qualified calls.
        if "governed_run_snapshot" in source or "governed_decision" in source:
            violations.append(f"{path.relative_to(REPO_ROOT)} mentions foundation")

    assert violations == []


def test_excluded_integration_seams_remain_unintegrated() -> None:
    missing = [
        str(path.relative_to(REPO_ROOT))
        for path in PROHIBITED_INTEGRATION_FILES
        if not path.is_file()
    ]
    assert missing == []

    for path in PROHIBITED_INTEGRATION_FILES:
        source = path.read_text(encoding="utf-8")
        assert "governed_run_snapshot" not in source, path
        assert "governed_decision" not in source, path


def test_public_import_graph_does_not_load_foundation() -> None:
    script = textwrap.dedent(
        f"""
        import importlib
        import importlib.abc
        import sys

        forbidden = {sorted(FOUNDATION_MODULES)!r}

        class FoundationImportBlocker(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname in forbidden:
                    raise AssertionError(
                        "existing public import loaded CR-DD-012A foundation: "
                        + fullname
                    )
                return None

        sys.meta_path.insert(0, FoundationImportBlocker())
        for module_name in {PUBLIC_IMPORT_SEAMS!r}:
            importlib.import_module(module_name)

        loaded = sorted(set(forbidden).intersection(sys.modules))
        if loaded:
            raise AssertionError("foundation unexpectedly loaded: " + repr(loaded))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_governed_decision_has_no_ambient_or_runtime_subsystem_imports() -> None:
    path = PRODUCTION_ROOT / "governed_decision.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for imported in _imported_modules(tree):
        root = imported.split(".", 1)[0]
        if root in FORBIDDEN_DECISION_IMPORT_ROOTS:
            violations.append(imported)
        lowered_parts = {
            part.lower().replace("-", "_") for part in imported.split(".")
        }
        if any(
            forbidden in part
            for part in lowered_parts
            for forbidden in FORBIDDEN_DECISION_TRIAGE_MODULE_PARTS
        ):
            violations.append(imported)

    assert violations == []


def test_governed_decision_does_not_call_ambient_discovery_primitives() -> None:
    path = PRODUCTION_ROOT / "governed_decision.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_names = {
        "open",
        "getenv",
        "getcwd",
        "time",
        "uuid1",
        "uuid4",
        "urandom",
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    calls.update(
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    assert calls.isdisjoint(forbidden_names)
