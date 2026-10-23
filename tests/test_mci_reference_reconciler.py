"""Conformance tests for the test-only mci/0.1 reference reconciler (CR-136).

The oracle is the frozen, hand-derived corpus in
docs/research/monitoring-coverage-fixtures-v0.1/, pinned to contract and
fixture specification r5. These tests read it directly and never rewrite it.
A failure means the reconciler disagrees with the oracle; the oracle changes
only through a reviewed, synchronized specification revision. Passing tests
show conformance to fabricated synthetic cases only: no runtime monitoring,
census completeness, safety, authorization or inhibition is established.
"""
import ast
import hashlib
import importlib.util
import json
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "docs" / "research" / "monitoring-coverage-fixtures-v0.1"
MODULE_PATH = Path(__file__).with_name("mci_reference_reconciler.py")
REVISION = "r5"


def _load_reconciler():
    spec = importlib.util.spec_from_file_location("mci_reference_reconciler", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reconciler = _load_reconciler()
INDEX = json.loads((CORPUS / "index.json").read_bytes())
CASE_FILES = [entry["file"] for entry in INDEX["cases"]]
REPORTS = [(entry["file"], position) for entry in INDEX["cases"] for position in range(len(entry["report_ticks"]))]
RAW_DIRS = [entry["dir"] for entry in INDEX["raw"]]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> bytes:
    # Independent of the reconciler: contract section 8 canonical bytes.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _case(file: str) -> dict:
    return json.loads((CORPUS / file).read_bytes())


def _run(case: dict, envelopes: list, as_of: int) -> dict:
    return reconciler.reconcile(_canonical(case["manifest"]), [_canonical(e) for e in envelopes], as_of)


def test_pins_match_the_specification_files():
    pins = INDEX["pins"]
    for key in ("contract", "fixture_specification"):
        pin = pins[key]
        assert pin["revision"] == REVISION
        assert _sha256((ROOT / pin["path"]).read_bytes()) == pin["sha256"], f"{pin['path']} changed without re-pin"


def test_corpus_files_match_the_index():
    assert len(CASE_FILES) == 71 and len(REPORTS) == 85 and len(RAW_DIRS) == 6
    for entry in INDEX["cases"]:
        data = (CORPUS / entry["file"]).read_bytes()
        assert _sha256(data) == entry["sha256"], entry["file"]
        assert json.loads(data)["pins"] == INDEX["pins"], entry["file"]
    for entry in INDEX["raw"]:
        for name, digest in entry["files"].items():
            assert _sha256((CORPUS / entry["dir"] / name).read_bytes()) == digest, (entry["dir"], name)


@pytest.mark.parametrize("file,position", REPORTS, ids=[f"{f[6:-5]}@{p}" for f, p in REPORTS])
def test_report_matches_frozen_expectation(file, position):
    case = _case(file)
    frozen = case["reports"][position]
    assert _run(case, case["envelopes"], frozen["as_of"]) == frozen["expected"]


@pytest.mark.parametrize("directory", RAW_DIRS)
def test_raw_input_is_rejected_at_the_expected_index(directory):
    folder = CORPUS / directory
    data = (folder / "envelopes.jsonl").read_bytes()
    assert data.endswith(b"\n")
    lines = data[:-1].split(b"\n")
    expected = json.loads((folder / "expected.json").read_bytes())
    for as_of in (0, 5):
        assert reconciler.reconcile((folder / "manifest.json").read_bytes(), lines, as_of) == expected


@pytest.mark.parametrize("file", CASE_FILES, ids=[f[6:-5] for f in CASE_FILES])
def test_envelope_order_does_not_change_reports(file):
    case = _case(file)
    shuffled = list(case["envelopes"])
    random.Random(file).shuffle(shuffled)
    for frozen in case["reports"]:
        assert _run(case, list(reversed(case["envelopes"])), frozen["as_of"]) == frozen["expected"]
        assert _run(case, shuffled, frozen["as_of"]) == frozen["expected"]


@pytest.mark.parametrize("file", CASE_FILES, ids=[f[6:-5] for f in CASE_FILES])
def test_later_exact_retransmission_is_idempotent(file):
    case = _case(file)
    resent = [dict(e, visible_at=e["visible_at"] + 3) for e in case["envelopes"]]
    for frozen in case["reports"]:
        assert _run(case, case["envelopes"] + resent, frozen["as_of"]) == frozen["expected"]


def test_reports_never_claim_assurance_or_inhibition():
    for file, position in REPORTS:
        case = _case(file)
        report = _run(case, case["envelopes"], case["reports"][position]["as_of"])
        assert report["census_assurance"] == "unknown"
        assert report["inhibition"] == "not_implemented"


def test_reconciler_module_is_isolated():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    allowed = {"__future__", "hashlib", "json", "re", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert {alias.name.split(".")[0] for alias in node.names} <= allowed
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module.split(".")[0] in allowed
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "exec", "eval", "compile", "__import__", "input"}
        elif isinstance(node, ast.Attribute):
            assert node.attr not in {"system", "popen", "urlopen", "write_text", "write_bytes"}
    assert "triage_core" not in MODULE_PATH.read_text(encoding="utf-8")
