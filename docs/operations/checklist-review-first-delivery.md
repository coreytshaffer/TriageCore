# `tc checklist-review`: first delivery (CR-138)

`tc checklist-review` runs one saved document-revision review procedure on a
case file with a local model, keeps the evidence in a private review store,
and records a human decision that survives reopening the review.

## Boundary

- Rule `R-DOCREV v0.1`, the model reply, and policy `C-AGREE v0.1` are
  advisory. Only `review` records a decision. That decision confers no
  authority outside the review store.
- The only network destination is `127.0.0.1:11434`, with exactly
  `GET /api/tags` (preflight) and `POST /api/chat`. No host name, environment
  variable, setting, or option can change it. There is no proxy, redirect,
  fallback, retry, model pull, or load or unload request.
- The review store is the only write destination. The standard ledger
  (`.triagecore/ledger.jsonl`) is not used.
- The two synthetic cases show whether the workflow runs end to end. They say
  nothing about model quality or real documents.

## Before you start

1. **Choose a private store.** Pick a local directory outside shared, synced
   (OneDrive, Dropbox, and similar), and version-controlled folders, for
   example `%LOCALAPPDATA%\TriageCore\checklist-review`. `save` creates it if
   its parent exists. It refuses a non-empty directory that is not already a
   store. Do not put the store path in handbacks.
2. **Supply case files separately.** Copy the pinned synthetic cases out of
   the test directory and keep their bytes exact: UTF-8, LF line endings, and
   no BOM. A Windows checkout may have converted the fixtures to CRLF, which
   the parser rejects with `case_line_ending_invalid`. This writes LF copies:

   ```powershell
   python -c "import sys, pathlib; [pathlib.Path(sys.argv[1], pathlib.Path(p).name).write_bytes(pathlib.Path(p).read_bytes().replace(b'\r\n', b'\n')) for p in sys.argv[2:]]" <case-dir> tests\fixtures\checklist_review\cases\DC-03.txt tests\fixtures\checklist_review\cases\DC-02.txt
   Get-FileHash -Algorithm SHA256 <case-dir>\DC-03.txt, <case-dir>\DC-02.txt
   ```

   Expected digests: DC-03
   `ff0d555e3ce5845c20ee746aea44f1922dec4c883375373ad379e7a9772a861f`, DC-02
   `bd28ba046465e68390a13200de61f3e46168d232ea51834cda0f7f74bb96ed79`.
3. **Confirm the local runtime before each live run.** The Ollama local API
   can invoke cloud models, so the client records your confirmation separately
   from the tag and digest it observes.
   - Disable cloud features with `OLLAMA_NO_CLOUD=1` (a Windows user
     environment variable) or `"disable_ollama_cloud": true` in
     `~/.ollama/server.json`, then restart Ollama. See
     [How do I disable Ollama's cloud features?](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).
   - Check that the server log (on Windows, under `%LOCALAPPDATA%\Ollama`)
     shows `Ollama cloud disabled: true` for the running instance.
   - Check that `ollama list` shows `qwen3.5:4b` as an installed model.
   - Only then pass `--confirm-local-runtime`. Without it, `run` saves the
     case and rule result and stops with `runtime_locality_unconfirmed` before
     any request.

## Commands

The installed `tc` command and `python -m triage_core.tc_cli` are equivalent.
On Windows, use the second form when `tc` is not on `PATH`.

```text
tc checklist-review --store <private-dir> save --workflow docrev-v1 --model qwen3.5:4b --model-digest d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04
tc checklist-review --store <private-dir> run --workflow docrev-v1 --case <DC-03.txt> --confirm-local-runtime
tc checklist-review --store <private-dir> run --workflow docrev-v1 --case <DC-02.txt> --confirm-local-runtime
tc checklist-review --store <private-dir> show --run <run-id>
tc checklist-review --store <private-dir> show --run <run-id> --item revision-approval --evidence
tc checklist-review --store <private-dir> review --run <run-id> --item revision-approval --target <result-event-id> --finding "<finding>" --disposition <accepted|revised> --label-assessment <correct|incorrect|unknown> --evidence-assessment <supported|unsupported|unknown> --cite <label> [--cite <label> ...] --reason-code <code> [--supersedes <human-event-id>] [--note-file <path>] [--active-seconds <n>]
```

Windows equivalents:

```powershell
python -m triage_core.tc_cli checklist-review --store <private-dir> save --workflow docrev-v1 --model qwen3.5:4b --model-digest d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04
python -m triage_core.tc_cli checklist-review --store <private-dir> run --workflow docrev-v1 --case <case-dir>\DC-03.txt --confirm-local-runtime
python -m triage_core.tc_cli checklist-review --store <private-dir> run --workflow docrev-v1 --case <case-dir>\DC-02.txt --confirm-local-runtime
python -m triage_core.tc_cli checklist-review --store <private-dir> show --run <run-id>
python -m triage_core.tc_cli checklist-review --store <private-dir> show --run <run-id> --item revision-approval --evidence
```

- `save` freezes the packaged system text and user template as verified
  private artifacts. Their digests must be
  `69d17c5d1de85bddf0ddd321af7d1471ece6abb9ca60f04dbeb7dd03676df316` and
  `4038f3e9de8bb33f58f1da1803951b510176b9f3caa8e3d6dd99f8ee30475176`. Saving
  the same reference again with identical content is a no-op. Different
  content fails with `definition_conflict`.
- `run` records the attempt start, case, and rule result before any network
  I/O. It then makes one preflight request and, only if that succeeds and the
  exact request body is stored as a verified artifact, one chat request. It
  prints the run view, including the event IDs that `review` targets.
- `show` opens the store read-only. It never starts a model, initializes a
  store, or appends an event. A missing or altered artifact appears as
  `evidence_missing` or `evidence_digest_mismatch`, while result IDs and human
  decisions stay visible. `--evidence` shows the work-product header lines,
  the whole controlling register, each component's citations, the model's own
  reason text, and any notes. The run and item IDs and the command back to the
  run view are printed with a `<store>` placeholder.
- `review` appends one human event linked to an earlier rule, model, or policy
  result of the same run and item. `--supersedes` must name an earlier human
  event of the same run and item. `--cite` accepts only labels in the recorded
  case. The note is stored as a private artifact. Unmeasured active time is
  recorded as `unknown`. A decision on a recorded (replayed) run is marked as
  a demonstration record.

Reason codes for `review` are `exact_entry_approved`, `no_matching_document`,
`other_revision_only`, `entry_field_missing`, `decision_not_approved`,
`approval_qualified`, `target_field_missing`, `controlling_source_absent`,
`citation_unsupported`, and `other`.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. For `run`, the model reply completed (`returned_valid` or `returned_invalid`). |
| `1` | Error, reported as a closed reason code on stderr. Nothing was appended. |
| `2` | Command-line usage error, such as a missing `--store`. |
| `3` | `run` recorded a stopped or failed attempt. The stop and its reason are saved. |

### Attempt outcomes

| Stage and condition | Status | Reason code |
| --- | --- | --- |
| Malformed or oversized case | `stopped` | `case_*` input code |
| Frozen template missing or changed | `stopped` | `definition_evidence_missing` or `definition_evidence_digest_mismatch` |
| No `--confirm-local-runtime` | `stopped` | `runtime_locality_unconfirmed` |
| Tags connection failed, or non-200 status other than a redirect | `stopped` | `runtime_unavailable` |
| Tags deadline (5 s) exceeded | `stopped` | `tags_timeout` |
| Tags redirect | `stopped` | `transport_refused` |
| Tags body over 256 KiB | `stopped` | `tags_response_too_large` |
| Malformed or truncated tags reply, missing identity, or duplicate tag | `stopped` | `tags_invalid_response` |
| Tag not in the list | `stopped` | `model_not_installed` |
| Tag reports another digest | `stopped` | `model_digest_mismatch` |
| Chat request over 32 KiB | `stopped` | `request_too_large` |
| Chat redirect | `failed` | `transport_refused` |
| Chat connection failed, or non-200 status other than a redirect | `failed` | `completion_failed` |
| Chat deadline (240 s) exceeded, or body over 64 KiB | `failed` | `timeout` or `response_too_large` |
| Truncated or invalid chat envelope | `failed` | `chat_invalid_response` |
| Completed reply that the R01 parser rejects | `returned_invalid` | `model_*` parser code |
| Completed reply that the R01 parser accepts | `returned_valid` | none |

## Verification

### Recorded (no model service)

The recorded DC-02 check replays the sealed R01 reply through the same runner
and store, with no network call. It checks inspection, the correction of the
unsupported explanation, and reopening in a new process.

```powershell
python -m pytest tests/test_checklist_review.py tests/test_checklist_review_store.py tests/test_checklist_review_local.py tests/test_checklist_review_cli.py -q
python -m pytest -q
```

### Live (operator-run)

Run these two checks once each, after the runtime confirmation above:

1. `save` once, as above.
2. `run` DC-03 with `--confirm-local-runtime`. Expect the rule's `match`
   citing `S1.L04`. Inspect the run with `show --evidence`, then record an
   explicit decision with `review` and `--cite` labels.
3. `run` DC-02 with `--confirm-local-runtime`, reusing the same definition and
   model. Expect the rule's `insufficient evidence` citing `S1.L03` to
   `S1.L05`. Inspect it, then record an explicit decision with citations.

Each run records the runtime confirmation, the observed model tag and digest,
the settings sent, its own case digest, the model outcome, and the human
decision. An unavailable runtime or unconfirmed locality saves a stop and
leaves the live check pending. For the handback, use run and event IDs, and
leave out the store path and raw records.
