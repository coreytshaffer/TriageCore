from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = REPO_ROOT / "docs" / "evals" / "external_evaluator_adapter_contract.md"
CR_RECORD = (
    REPO_ROOT
    / "docs"
    / "change"
    / "requests"
    / "CR-129-external-evaluator-adapter-contract.md"
)
TC_CLI = REPO_ROOT / "triage_core" / "tc_cli.py"
ADAPTER_MODULE = REPO_ROOT / "triage_core" / "external_evaluator_adapter.py"


def _normalized(path):
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_adapter_contract_pins_future_closed_profile_boundary():
    doc = _normalized(CONTRACT)

    required = (
        "external_evaluator_adapter_contract.v0",
        "this command does not exist in cr-129",
        "--bundle <explicit-root>",
        "--evaluator-profile <closed-profile>",
        "--timeout-seconds <bounded-value>",
        "arbitrary `--executable`",
        "free-form evaluator arguments",
        "fixed argv-list template",
        "explicit working directory",
        "result/output contract",
        "network posture",
        "stdout/stderr encoding",
        "1 through 3600",
        "suggested default timeout is 300 seconds",
    )
    for phrase in required:
        assert phrase in doc


def test_adapter_contract_pins_process_safety_and_prelaunch_validation():
    doc = _normalized(CONTRACT)

    required = (
        "validate-handoff --bundle <bundle-root>",
        "argv list",
        "`shell=false`",
        "stdin to `devnull`",
        "allowlisted minimal environment",
        "exclude credentials",
        "proxy settings",
        "process tree",
        "windows and posix",
        "untrusted bytes",
        "environment stripping alone does not prove offline execution",
        "network_posture_unverified",
    )
    for phrase in required:
        assert phrase in doc


def test_adapter_contract_pins_wrapper_exits_reasons_and_external_ownership():
    doc = _normalized(CONTRACT)

    assert "raw evaluator exit codes must never be propagated" in doc
    assert "| `0` |" in CONTRACT.read_text(encoding="utf-8")
    assert "| `1` |" in CONTRACT.read_text(encoding="utf-8")
    assert "| `2` |" in CONTRACT.read_text(encoding="utf-8")
    for reason in (
        "bundle_invalid",
        "evaluator_profile_missing",
        "evaluator_profile_invalid",
        "evaluator_not_found",
        "evaluator_version_mismatch",
        "evaluator_launch_failed",
        "evaluator_timeout",
        "evaluator_nonzero_exit",
        "evaluator_output_invalid_encoding",
        "evaluator_output_limit_exceeded",
        "evaluator_interrupted",
        "network_posture_unverified",
    ):
        assert reason in doc
    assert "external evaluator" in doc
    assert "owns any scored result artifact" in doc
    assert "does not create evaluator output" in doc
    assert "does not create evaluator output, parse it, import it, render it, persist it" in doc


def test_cr129_remains_contract_only_without_generic_execution_surface():
    contract = _normalized(CONTRACT)
    cli_source = TC_CLI.read_text(encoding="utf-8")

    assert CR_RECORD.exists()
    assert "no subprocess or process-tree execution code" in contract
    assert "no cli parser or runtime adapter module" in contract
    assert "invoke-external" not in cli_source
    assert not ADAPTER_MODULE.exists()


def test_handoff_docs_link_to_adapter_contract_without_claiming_implementation():
    handoff = _normalized(
        REPO_ROOT / "docs" / "evals" / "evaluation_handoff_contract.md"
    )
    manifest = _normalized(
        REPO_ROOT / "docs" / "evals" / "evaluation_handoff_manifest.md"
    )

    assert "external_evaluator_adapter_contract.md" in handoff
    assert "does not exist in cr-129" in handoff
    assert "external_evaluator_adapter_contract.md" in manifest
    assert "required pre-launch gate" in manifest
