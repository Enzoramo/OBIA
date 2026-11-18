# Helper commands

Python 3.10+; install `requirements.txt` for YAML edits. Runtime is local, without
API keys, embeddings or plugins. Examples run from the skill directory; resolve
that directory from the installed skill, quote paths, and use the actual vault.

```sh
python3 scripts/obia.py init --vault '/path/to/vault'
python3 scripts/obia.py save --vault '/path/to/vault' --input checkpoint.json
python3 scripts/obia.py search --vault '/path/to/vault' --project my-app --query 'login offline'
python3 scripts/obia.py recall --vault '/path/to/vault' --project my-app --task login --view brief --with-sources
python3 scripts/obia.py read --vault '/path/to/vault' --project my-app --task login --section Sources
python3 scripts/obia.py check --vault '/path/to/vault' --project my-app
```

`save --input -` accepts JSON stdin. Use input files or structured arguments;
never interpolate task text into shell commands. See [the format](memory-format.md)
for checkpoint fields.

## Update

Use the task/SHA already recovered in this context, then apply only changed
properties and level-two sections. Read an omitted section before replacing it:

```sh
python3 scripts/obia.py patch --vault '/path/to/vault' --project my-app --task login --input patch.json --expect-sha SHA
```

```json
{
  "properties": {"status": "complete", "summary": "Login tested offline."},
  "append": {"Facts": "- Offline login passed. [S1]"},
  "sections": {"Next steps": "No remaining implementation work."}
}
```

Supply referenced sources if absent. `sections` replaces named section bodies;
`append` adds text. Unmentioned sections and custom YAML properties/comments
survive; fenced headings are ignored. Duplicate headings/keys and custom YAML tags
are rejected. Identity fields (`obia`, `project`, `task_id`) are immutable;
`updated` is automatic. Generated title/current-state text is synchronized only
when it still matches; reconcile human rewrites through `sections.Resume`.

For a deliberate whole-body replacement use complete checkpoint JSON with
`save --input checkpoint.json --expect-sha SHA --replace`. Extra YAML properties
survive, but the body is replaced. Without `--replace`, changed notes are refused.
Conflicts require rereading/reconciliation, not blind retries. Identical writes
return `unchanged`; changes snapshot the previous Markdown under
`OBIA/.history/<project>/<task>/<sha>.md`. Removing current text does not erase
history or external backups.

`save` and `patch`, including `unchanged`, return `verified: true` only after
rereading the persisted note and validating its identity, sources and links under
the write lock. `project_index_current` separately compares this project's index
with current notes. A rebuild failure remains a warning: a saved note does not
imply repaired indexes. A readback mismatch fails without a positive receipt.
SHA follows the helper's existing UTF-8 text contract (CRLF normalized to LF),
not an OS-level hash of arbitrary newline bytes. No repeated read/check is needed when verified/index fields are true and there is
no warning. This is a local structural receipt, not source verification, a
project-wide audit, synchronization proof or hook acknowledgement. Use `check`
for project-wide audits; keep the separate exact-SHA `hooks.py ack` when bound.

## Retrieve

`search` requires a project and uses accent-insensitive lexical matching, with
title/summary boosts. It returns metadata/SHA, not note bodies. `--limit` is 1–10
(default 5). Archived tasks need `--include-archived` or a known task ID.

`recall` accepts exactly one of `--task` or `--query`. A known task can include
one-hop, same-project, nonarchived links up to `--limit` (default 3, maximum 10).
No recursive, personal-note or cross-project traversal occurs. `--max-chars`
bounds serialized JSON including its final newline: 1,024–64,000 Unicode
characters, default 12,000. This is not a token budget.

- `--view full` (CLI/API default): whole notes or explicit omissions.
- `--view brief`: whole Resume, Constraints, Decisions, Corrections and preamble,
  status/time, full-note SHA, omitted section names and referenced source IDs.
  `--with-sources` includes a `source_definitions` mapping for IDs cited in that
  projection, taken from the same in-memory snapshot. `available_source_ids`
  lists all defined IDs so an update can choose an unused ID without another read. Other definitions remain
  omitted; it does not read linked files or URLs. Without the flag, expand source
  definitions when needed. The budget includes the mapping; oversized projections
  remain deferred, never truncated. Full views already include all definitions. Known-task links become locators with
  titles/summaries; query matches each get a projection.
- Adaptive exception: if the complete packet fits without omissions and is no
  larger in serialized characters, return it with root `view: full`. Small notes
  can cost less whole than projected with bookkeeping and later source reads.
- Missing Resume/custom frontmatter triggers whole-note fallback. Custom body
  sections are listed as omitted. Essential text is never truncated: oversized
  entries become `deferred` with `read_required: full`, or counted omissions if
  even a locator cannot fit. Read a deferred/omitted main note in full before
  acting; read linked locators before relying on their evidence.

`omitted_count` counts selected candidate notes, not all unselected vault notes;
`omitted` lists their paths where space permits. Source IDs and section names
are discovery aids, not proof of source truth or completeness.

`read` has no recall budget; notes are limited to 128 KiB on disk. Repeat
`--section` for multiple sections or `--source S1` for multiple source definitions.
The selectors are mutually exclusive. Multiline source records are preserved;
fenced examples and IDs outside Sources are not definitions. Missing/duplicate
source IDs fail. Every read SHA identifies the complete persisted note.

Use `--expect-sha SHA` to expand the same snapshot; a mismatch fails before content
is returned. Recover changed state before combining evidence. `--if-changed SHA`
returns only path/SHA and `status: unchanged` on a match, otherwise the requested
content. Use it only for content already available; it neither loads newly needed
sections nor saves/acknowledges a checkpoint.

## Ownership and recovery

`init` refuses an existing OBIA folder without its `.obia.json` identity marker;
it leaves other notes and `.obsidian/` untouched. Writers use exclusive local
locks, SHA checks and atomic replacement, not a distributed synchronization lock.
Use one writer across synchronized devices. Inspect a stale lock and confirm its
writer stopped before removing it.

`index` rebuilds generated indexes and refuses unmarked files. Indexes are caches.
A write may succeed before index failure: for `Note saved; indexes need repair`,
read the current note before retrying, then repair indexes separately.

`check` validates metadata, source references, linked targets, the project index
and some credential patterns; it cannot verify truth or detect every secret.
Exit codes: 0 success, 1 check problems, 2 invalid input/I/O. JSON is UTF-8 on
stdout; errors use stderr. No deletion, automatic sync, shell execution or external
API commands are provided.
