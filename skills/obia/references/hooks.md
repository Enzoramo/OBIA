# Hook workflow for agents

`hooks.py` is beside `obia.py`. Use the exact host, config directory and session
ID provided by the hook's startup context. Example commands below are relative
to the skill root; quote values using the actual shell or use structured argv.

```sh
python scripts/hooks.py --host codex --config-dir '/private/obia-config' bind --session 'HOST_SESSION_ID' --path '/work/my-app' --task offline-cache
```

Binding resolves or creates this project's vault and returns its location and
project ID. For an existing task, it also returns bounded recall immediately.
Reuse that task ID for the same objective. A different chat or host has a separate
binding; explicitly bind the same task to hand off. Never automatically load the
last task worked on by an unrelated chat.

Save using `obia.py save` for a new task or `obia.py patch --expect-sha ...` for an
existing one, following the command and memory-format references. Then verify the
actual persisted note through:

```sh
python scripts/hooks.py --host codex --config-dir '/private/obia-config' ack --session 'HOST_SESSION_ID' --path '/work/my-app' --sha ACTUAL_SHA
```

For Claude Code change `--host codex` to `--host claude`. `ack` only verifies an
existing persisted note against that SHA. It does **not** generate or save a
checkpoint. If nothing materially changed, read the current note and acknowledge
its SHA without rewriting it. If work or constraints changed, save them first.

SessionStart restores the bound task and its limited same-project links. A
UserPromptSubmit event advances the private prompt counter without storing the
prompt. In Codex, a valid receipt also needs the `turn_id` supplied by the host
to match the ID recorded by `ack`. PreCompact and Stop observe this ID too:
delegated turns can skip UserPromptSubmit but cannot reuse an earlier turn's ack.
The counter remains a count of prompt events, not all host turns.

Codex `ack` returns the last observed `turn_id` (or null if none is known). It
verifies the persisted note against that observed turn, never an unseen future
turn. If the first event for a delegated turn is Stop, an earlier ack cannot
identify that turn; reread and ack during the requested continuation. Legacy
receipts without an ID require a new ack after a real lifecycle event supplies
one. A missing Codex `turn_id` is reported as unverified, never accepted using
only the counter. Claude Code retains its prompt-counter receipt workflow.

Stop asks for a checkpoint when its receipt is missing/stale, at most once per
observed turn/cycle, and respects `stop_hook_active` even if the continuation has
a new turn ID. After that it reports the missing receipt without looping. A
failed write or failed acknowledgement is not a successful checkpoint; report it.
Hooks never archive a task or mark it complete themselves.

PreCompact records whether the current checkpoint was verified. It cannot compel
the model to produce a fresh summary before an automatic compaction, and does not
read the transcript or last assistant message. Save meaningful progress during
work, before the context is exhausted. SessionEnd is deliberately not used as a
last-chance writer: it may be too late for the agent to produce a checkpoint.

Runtime files live under the private config directory: `sessions/<host>/...json`
contains task bindings, turn counters and SHA receipts, with no copied prompts
or transcripts. A missing vault fails visibly. Locks coordinate local writers;
inspect a stale lock only after confirming its writer stopped.
