# Context-Aware Review Prompt (Example)

Purpose: run the review with a curated reviewer context bundle so the model has
artifacts to cite. After this pass, the reviewer sorts each claim using the
protocol's claim taxonomy.

---

You are reviewing an open-source project called **TriageCore**.

Below the line I am giving you a curated reviewer context bundle: selected
repository files, documentation, and command output. Review the project **using
only what is in that bundle.** If a statement is not backed by something in the
bundle, do not present it as established fact.

For every substantive claim, do the following:

1. State the claim as one discrete, numbered point.
2. Cite the specific artifact in the bundle that backs it (file name, doc
   section, or command output). If you cannot cite one, say so explicitly.
3. Separate claims you can support from inferences you are guessing at.
4. List any concrete next actions as bounded, scoped steps a human could choose
   to authorize — not as work you have done or should do automatically.

Do not claim the project is safe, certified, compliant, or production-ready. Do
not describe files, commands, or capabilities that are not present in the bundle.

---

CONTEXT BUNDLE:

<paste the curated reviewer context bundle here, e.g. the concatenated
README / pyproject / selected docs and tests used for the run>
