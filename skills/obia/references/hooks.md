# Hook workflow

Use `hooks.py` beside `obia.py`, with the host/config directory/session ID supplied
by startup context. Examples are relative to the skill directory:

```sh
python scripts/hooks.py --host codex --config-dir '/private/obia-config' bind --session 'HOST_SESSION_ID' --path '/work/my-app' --task offline-cache
```

Binding resolves/creates the project vault and returns its location/project ID
and adaptive brief recall for an existing task. Reuse IDs for the same objective.
Explicitly bind every new chat/host; never infer its task from another chat.
Use `--known-sha SHA` only when that note context is already available: matching
bytes return `memory: {status: unchanged, path, sha256}`, otherwise fresh recall.
This does not acknowledge a checkpoint. An earlier receipt cannot establish what
context the model currently holds.

SessionStart always restores bound context, including after compaction. Recall
preserves whole essential sections, exposes omissions, and selects complete notes
when smaller; see [retrieval](commands.md#retrieve) for expansion/fallback rules.
There is no persistent suppression flag after an ack.

Save useful changes with `obia.py`, then verify persistence:

```sh
python scripts/hooks.py --host codex --config-dir '/private/obia-config' ack --session 'HOST_SESSION_ID' --path '/work/my-app' --sha ACTUAL_SHA
```

For Claude Code use `--host claude`. Ack verifies the existing note against the
exact SHA; it does not write a checkpoint or verify its meaning. With no useful
change, read and ack the existing SHA without rewriting. `read --if-changed` may
check freshness of context already read; neither a brief view nor a receipt proves
that deferred evidence was read. Save changed work/constraints before ack.

UserPromptSubmit advances a private prompt-event counter without storing prompts.
Codex receipts also require a non-null host `turn_id` matching the ack and current
note SHA. PreCompact/Stop observe this ID: delegated turns may skip prompt events
but cannot reuse a previous turn's ack. The counter does not count all host turns.
Ack reports the last observed ID, never an unseen future turn. If a delegated turn
is first observed at Stop, reread/ack during its requested continuation. Legacy
or missing-ID receipts remain unverified until a real event supplies the ID and a
new ack is made. Claude retains prompt-counter/SHA receipt validation.

Stop requests one checkpoint pass for a stale/missing receipt per observed
turn/cycle. It honors `stop_hook_active` even with a new continuation ID, then
reports missing verification without looping. Report failed writes/acks; hooks
do not archive or complete tasks. PreCompact records verification without blocking
compaction or summarizing unsaved context. No transcript/last-message inspection
or SessionEnd rescue writer exists. Save progress before the context is exhausted.

Private `sessions/<host>/...json` files hold bindings, counters, turn IDs and SHA
receipts, never copied prompts/transcripts. Missing vaults fail visibly. Local
locks require checking that a writer stopped before stale-lock removal.
