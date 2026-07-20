# Contributing to TriageCore

TriageCore welcomes focused feedback, bug reports, documentation improvements, tests, and code changes. You do not need to write code to contribute.

## Give Feedback Without Writing Code

Use [GitHub Discussions](https://github.com/coreytshaffer/TriageCore/discussions) for questions, first impressions, workflow feedback, and open-ended ideas. Use [GitHub Issues](https://github.com/coreytshaffer/TriageCore/issues) for reproducible bugs or a specific proposed change.

Choose one bounded review capsule:

1. **Two-minute first impression (no install):** Read the README opening through **What It Does Today**. Reply with two or three sentences explaining what TriageCore does, who it is for, and what remains unclear.
2. **Ten-minute workflow check:** Install the project, then run only `tc doctor` and `tc demo --dry-run`. Report the first confusing instruction, unexpected output, failure, or missing prerequisite. Include your operating system and Python version.
3. **Design challenge (15–20 minutes):** Choose one privacy, authority, evidence, or governance claim. Identify where the repository supports it, where support is incomplete, or where the wording overstates the evidence.

Specific observations are more actionable than general ratings. Confusion, failed expectations, and uncertainty are valuable results.

## Privacy Before Posting

Public issues and discussions must not contain prompts, credentials, tokens, personal data, sensitive geospatial information, private project context, or any other local-only material. Replace sensitive values with clearly marked placeholders and share only the minimum reproducible example. If safe redaction is not possible, do not post the material publicly.

## Report a Bug

Before opening an [issue](https://github.com/coreytshaffer/TriageCore/issues), check for an existing report. Include:

- the command or bounded action you attempted;
- expected and actual behavior;
- minimal reproduction steps;
- operating system, Python version, and TriageCore version or commit;
- privacy-safe logs or error text, if relevant.

Bug reports identify observations; they do not establish evidence, approval, or authorization.

## Propose a Code Change

For a small, well-scoped fix, open a pull request with a concise description, related issue (if any), and tests. Discuss larger or behavior-changing proposals in [Discussions](https://github.com/coreytshaffer/TriageCore/discussions) or an issue before investing substantial effort.

Minimal local setup:

```bash
git clone https://github.com/coreytshaffer/TriageCore
cd TriageCore
python -m pip install -e .
python -m pytest -q
```

Keep changes bounded, preserve local-first and privacy boundaries, and update tests or documentation when behavior changes.

## Limitations and Uncertainty

TriageCore is an early research workbench, not a finished assurance or governance product. Behavior, interfaces, evidence quality, and documentation may change, and a passing test suite does not prove every safety or policy claim. Feedback from contributors and external reviewers is advisory: it is not automatically treated as validated evidence, approval, clearance, or authority to act. Maintainers and designated human decision-makers remain responsible for evaluating changes and recorded evidence within the applicable context.
