# Zero-Context Review Prompt (Example)

Purpose: establish the model's prior. Supply **no** repository evidence. Every
substantive claim the model makes here is `unsupported` by construction, because
nothing was provided to support it. Keep this pass to compare against the
context-aware pass.

---

You are reviewing an open-source project called **TriageCore**.

I am not giving you the repository, its files, its documentation, or any command
output. Work only from the name and this prompt.

Produce a short review that answers:

1. What do you expect this project does?
2. What capabilities do you expect it has?
3. What files or commands do you expect to find?
4. What would you flag as risks or gaps?

State each point as a discrete, numbered claim. Do not hedge them into a single
paragraph — the reviewer needs to sort each claim individually afterward.

---

Reviewer note: do not paste any repository content into this pass. If the model
asks for files, decline and ask it to answer from its prior only. The value of
this pass is precisely what the model asserts *without* evidence.
