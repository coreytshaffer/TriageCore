# Checklist review fixture provenance (CR-138)

Every document, identifier, date, and role in these fixtures is synthetic. They
come from the development packet `triagecore-revision-audition` v0.2-draft and
its R01 run. They are test inputs for the `checklist-review` workflow, not
evidence about real documents or model quality.

## Sources

| Complete source | SHA-256 |
| --- | --- |
| `30_run_card.md` (prompt wrapper and parsing rule) | `4acb630d54271dc28f44331d935c9b630764f1986eb0d1af788f479aa88de4a2` |
| `10_candidate_pack.md` (case blocks) | `7a8ce3c3bb9e185a18f743607ae8dddc410d71ff5be5594e045742a96a36cf60` |
| `slm_raw_R01_DC-02.txt` (sealed R01 model reply) | `7fca096c058a6998ae18699a3ae271447a230403721092502141db76db76d6c8` |

No answer key, change note, policy check, scoring file, or other
evaluator-only material was used to make these fixtures.

## Extraction rules

For each text excerpt, line endings are normalized to LF, the text is encoded
as UTF-8 without a BOM, and the newline after the last extracted line is
excluded. Those bytes are canonical on every platform. Tests normalize CRLF to
LF before checking a text fixture, because a Windows checkout may add CR
characters.

The recorded reply is copied byte for byte. It is checked against its original
seal without newline normalization.

| Fixture | Extraction | SHA-256 |
| --- | --- | --- |
| `workflow_docrev_v1/system.txt` | Run card's exact system-text fenced block, excluding fences | `69d17c5d1de85bddf0ddd321af7d1471ece6abb9ca60f04dbeb7dd03676df316` |
| `workflow_docrev_v1/user_template.txt` | Run card's exact user-text fenced block with placeholders intact | `4038f3e9de8bb33f58f1da1803951b510176b9f3caa8e3d6dd99f8ee30475176` |
| `cases/DC-02.txt` | Candidate pack from `BEGIN CASE DC-02` through `END CASE DC-02` inclusive | `bd28ba046465e68390a13200de61f3e46168d232ea51834cda0f7f74bb96ed79` |
| `cases/DC-03.txt` | Candidate pack from `BEGIN CASE DC-03` through `END CASE DC-03` inclusive | `ff0d555e3ce5845c20ee746aea44f1922dec4c883375373ad379e7a9772a861f` |
| `recorded/R01_DC-02_slm.txt` | Sealed R01 file `slm_raw_R01_DC-02.txt`, byte for byte | `7fca096c058a6998ae18699a3ae271447a230403721092502141db76db76d6c8` |

Substituting each case and its ID into the user template reproduces both
messages of the sealed R01 request for DC-02 and DC-03. The rendered user
messages have these SHA-256 digests:

| Case | Rendered user message SHA-256 |
| --- | --- |
| DC-02 | `424b0fbae5bc6fbec2ea1a024b60add88815579f64484f76145b5e23a18524fc` |
| DC-03 | `9a9360446cbb1b5917a71d4932ee4760f8f927d9a0106959f0dbfec0808ae46e` |

## Use

- The packaged system text and user template in
  `triage_core/checklist_review.py` must match the two workflow fixtures. The
  fixtures test that identity. The runtime never reads them.
- `cases/DC-02.txt` and `cases/DC-03.txt` are the candidate inputs. For live
  checks, the operator supplies copies of them separately from this directory.
- `recorded/R01_DC-02_slm.txt` is used only by the test harness, to replay the
  historical R01 reply through the runner without a model service. It is never
  a live model input.

R01 used `qwen3.5:4b` at digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` with
Ollama 0.40.16. The R01 request also carried `keep_alive: "5m"`, which the
CR-138 request settings omit. The installed model supplied `top_k 20` and
`presence_penalty 1.5`. The repeat penalty was not reported.
