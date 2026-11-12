# Lifecycle hooks for Codex and Claude Code

Opt in during installation (use the same paths on updates):

```sh
python3 install.py --host codex --vaults-root '/private/Obsidian' --hooks
python3 install.py --host claude --vaults-root '/private/Obsidian' --hooks
# Add --update when the skill already exists.
```

The installer merges command hooks into `~/.codex/hooks.json` or
`~/.claude/settings.json`. `--hook-settings` overrides that destination.
Other settings/hooks are retained; previous files are backed up locally. Later
updates replace only exact previously managed entries. Human edits to those
entries require reconciliation rather than silent replacement. No trust records,
permission policies or host security settings are changed.

**Codex requires review of the exact hook definitions before they run.** Use its
`/hooks` interface or desktop hook review. Review again when the host requests it.
The installer only configures hooks; it never bypasses this review. This follows
[Codex's documented trust flow](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).
Use Claude Code's `/hooks` interface to inspect its installed configuration and
follow any host review/restart prompts.

| Event | OBIA behavior |
| --- | --- |
| SessionStart | Supplies the session ID and workflow; restores bounded memory when a task is bound. Includes restart after compaction. |
| UserPromptSubmit | Advances a private prompt counter and records the Codex turn ID when supplied. Does not store the prompt. |
| PreCompact | Observes the Codex turn ID and checks whether the current saved note has a verified receipt for that turn. Reports unsaved state; never blocks compaction. |
| Stop | Observes the Codex turn ID and requests one checkpoint pass if needed; accepts a verified current SHA for that turn and prevents repeated continuation loops. |

The agent uses `bind` to associate a session with a task, then saves through the
normal memory helper and uses `ack` to verify the note SHA. Existing task bindings
survive process restarts. A new chat must explicitly bind its intended task. See
[the agent workflow](../skills/obia/references/hooks.md).

Codex receipts match both the prompt counter and the host's `turn_id`, in addition
to the saved note SHA. Delegated tool-output turns may skip UserPromptSubmit;
PreCompact or Stop still observes their new ID and rejects an earlier turn's
receipt. The Stop loop guard resets for a new observed ID, while
`stop_hook_active` still prevents a repeated continuation. The ID comes from the
[documented lifecycle input](https://learn.chatgpt.com/docs/hooks#stop), without
reading transcripts or adding hook definitions.

An ack records the most recently observed turn; it cannot anticipate an ID the
host has not supplied yet. A delegated turn first observed at Stop therefore
needs an ack in that continuation even if the agent acknowledged earlier. Older
receipts without a turn ID require one new acknowledgement after an event
supplies it. If Codex omits the ID, the checkpoint is reported as unverified.
Claude Code continues to use its prompt counter and SHA. Updating the helper
requires no changes to hook configuration or trust records.

**Automatic recovery is for saved context.** These command hooks cannot generate
a semantic summary of unobserved model context. Checkpoints are authored by the
agent, with source references. PreCompact is a persistence check, not a promise
that every unsaved detail was captured. Hosts that do not load/run command hooks
still use the instruction-based skill workflow.

Codex uses JSON additional context at SessionStart and diagnostic output at
PreCompact; Claude Code accepts plain compaction guidance. Stop uses continuation
JSON in both adapters. The output choices follow the current
[Codex](https://learn.chatgpt.com/docs/hooks) and
[Claude Code](https://code.claude.com/docs/en/hooks) event contracts, checked
November 12, 2026. Test fixtures exercise these contracts in fresh Python processes;
they do not establish live compatibility with every product/version.

Commands use absolute Python/script/config paths and synchronous execution. On
Windows, generated handlers use PowerShell quoting; Claude sets its documented
PowerShell shell explicitly, and Codex launches an encoded PowerShell command.
Runtime Python tests run on Linux, macOS and Windows; Windows host integration
still needs an end-to-end check in the installed agent product.

## Inspect or disable

Inspect the generated host settings file and private `<config-dir>/<host>-hooks.json`
manifest. Disable the OBIA entries through the host's hook UI, or remove only those
exact entries from its settings, preserving other hooks. This does not delete
vaults or checkpoint history. If you later reinstall after manual removal,
reconcile/remove the private manifest after inspecting the current settings.

Hook errors exit with code 1 and report a diagnostic; they do not block prompts
or compaction. A `Stop` continuation is requested only through an explicit JSON
decision, once per cycle. Stop's `stop_hook_active` guard takes precedence.
