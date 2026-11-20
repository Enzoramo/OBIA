# Codex desktop: synchronous checkpoints

Use this workflow in a Codex chat that already has OBIA lifecycle context and a
known session ID. It uses the app's existing shell tool. No schema override,
callback, plugin registration, configuration or hook-trust change is required.
`desktop.py` delegates to the installed OBIA storage and hook helpers; it does
not read transcripts, run a model, fabricate events or infer another chat's task.

## Recover and bind once

```sh
python3 scripts/desktop.py --config-dir CONFIG recover \
  --session SESSION --path PROJECT_ROOT --task TASK
```

This explicitly binds the session, resolves the registered project vault, and
returns brief task context with cited sources in one response. It also performs
the project-router ensure step. Inspect omissions and expand relevant sections
through ordinary `obia.py read`; deferred context still needs recovery.
`--known-sha SHA` suppresses repeated content only when that exact context is
already visible. A stored acknowledgement never substitutes for recovery.

For a specific next task, add `--focus "renderer ledger accounting"`. This
selects whole sections of the bound task by deterministic lexical matching,
keeps the core/uncertainties and cited source definitions, and lists omitted
sections. No linked-note bodies are loaded in focused mode. Expand needed
omissions with `read --section` and the returned SHA; matching is not semantic
understanding. If the core cannot fit, the response requires a full read.
`--known-sha` does not suppress focused recovery, since the requested need may
have changed even when the note has not.

## Save and acknowledge before the final response

```sh
python3 scripts/desktop.py --config-dir CONFIG checkpoint \
  --session SESSION --path PROJECT_ROOT --task TASK --input -
```

For a new note, stdin is the ordinary OBIA creation payload. `project` and `id`
can be omitted because the explicit binding supplies them; supplied values must
match. Title defaults to the task slug with spaces. Required source attribution,
status, summary and objective follow the normal skill format.

For an existing note, add `--expect-sha READ_SHA` and supply a normal partial
patch (`properties`, `sections`, `append`). Reconcile every affected current-state
claim. Unmentioned human sections/metadata survive. There is no automatic full
replacement, migration or adoption of a legacy note.

The command returns a storage receipt and an acknowledgement separately, within
one synchronous shell call. Do not issue a redundant read/check/ack after a valid
receipt with no warning. Storage success does not establish semantic truth or
cross-device synchronization.

With no useful change and the context already recovered, use one read/ack call:

```sh
python3 scripts/desktop.py --config-dir CONFIG verify \
  --session SESSION --path PROJECT_ROOT --task TASK --sha READ_SHA
```

A changed SHA fails; reread/reconcile, never blindly substitute a new SHA.

## Turn identity and partial failures

The acknowledgement covers only the last turn actually observed by lifecycle
events. A delegated turn may skip UserPromptSubmit; its first real Stop may still
request verification. Follow that continuation with `verify` (or a sourced patch
if work changed). Never fabricate a turn ID, suppress Stop, or reuse a prior
turn's receipt to bypass the requirement. Existing hook validation is unchanged.

Storage and session acknowledgement are not one filesystem transaction. If the
note was saved but the index/ack failed, the error includes `saved_checkpoint` and
`acknowledged: false`. Report the partial result, investigate, and retry only the
needed acknowledgement after recovery. Do not regenerate/rewrite the checkpoint
just to retry ack. A storage warning prevents automatic acknowledgement.

Keep task progress in the note; persistence status belongs in the receipt, not
in checkpoint prose. Reuse supplied historical evidence without reopening it
only for citation. Recover gaps/conflicts and verify volatile files and tests.

This is the supported synchronous adaptation for the existing app. Unlike the
optional host-controlled structured-output adapter, it requires a model tool
call to submit the checkpoint. Measurements must include this call, initial
creation, updates, recovery and any actual Stop continuations; do not transfer
token percentages from a different host workflow.
