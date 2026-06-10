# Operator Bootstrap & First-Run Setup

This document guides operators through setting up the TriageCore environment and resolving common execution issues so that the `tc` workflow operates seamlessly.

## 1. Initial Setup

Navigate to the repository root directory:
```powershell
cd C:\Users\corey\.gemini\antigravity-ide\scratch\field-aware\triagecore
```

Perform an editable installation so that the CLI and package metadata are registered with Python:
```powershell
python -m pip install -e .
```

## 2. Post-Install Verification

To verify that the installation succeeded and the entry points are registered, run:
```powershell
tc --help
```

## 3. Dealing with PATH Issues & Fallbacks

If you receive an error like `tc : The term 'tc' is not recognized as the name of a cmdlet, function, script file, or operable program`, it is likely because the Python Scripts folder is not in your system's `PATH`.

### Locating the Python Scripts Folder
You can find the directory where pip installs entry point executables by running:
```powershell
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```
To fix the issue permanently, add this path to your system's environment variables.

### Module Fallback Method
If you cannot or do not want to modify your `PATH`, you can always access the CLI using the Python module execution fallback:
```powershell
python -m triage_core.tc_cli --help
```

### Temporary PowerShell Shim
For a faster temporary workaround in your current PowerShell session, you can define a shim:
```powershell
function tc { python -m triage_core.tc_cli @args }
```

## 4. Canonical Smoke Test

To verify that context compression, handoff generation, and the `tc` workflow behave correctly, execute the canonical smoke test using `CR-006` artifacts:

1. Generate the preflight bundle:
   ```powershell
   tc preflight CR-006 --files docs/change/requests/CR-006-seamless-operator-workflow-integration.md triage_core/tc_cli.py tests/test_tc_cli.py
   ```
2. View the generated handoff (prints to console, bypassing clipboard):
   ```powershell
   tc handoff latest --print
   ```
3. Copy the handoff to your clipboard:
   ```powershell
   tc handoff latest
   ```

## 5. Expected Smoke Test Outputs & Safety Constraints

### Safety Notes
* **Non-Destructive**: The `tc preflight` and `tc handoff` commands are strictly read-only. No source files or project docs are modified by the smoke workflow.
* **Artifact Location**: They write operational artifacts only into the `.triagecore/handoffs/` directory. 
* **Authority**: Generated handoffs are orientation artifacts. They do **not** grant implementation authority.

### Expected Output Contents
The resulting `.triagecore/handoffs/latest.md` should include:
- The **source verification reminder** emphasizing that source code must not be autonomously modified without explicit approval.
- **File references and hashes** tracking the files you fed into the preflight step.
- An HTML comment containing **token metadata** estimates.
- **Warning**: A deterministic fallback warning will appear (`[DETERMINISTIC FALLBACK USED]`) if local LLM compression is unavailable or disabled.
