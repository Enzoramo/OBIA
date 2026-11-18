# Helper commands

Python 3.10+; install `skills/obia/requirements.txt` for round-trip YAML edits.
No API keys, network calls at runtime, embeddings or Obsidian plugins.
Resolve the helper from the installed skill directory. Examples below run from
the OBIA repository root. Quote paths, including vault paths containing spaces.
Replace `/path/to/vault` with the user's existing vault directory.

```sh
python3 skills/obia/scripts/obia.py init --vault '/path/to/vault'
python3 skills/obia/scripts/obia.py save --vault '/path/to/vault' --input checkpoint.json
python3 skills/obia/scripts/obia.py search --vault '/path/to/vault' --project my-app --query 'login offline'
python3 skills/obia/scripts/obia.py recall --vault '/path/to/vault' --project my-app --task login --max-chars 12000
python3 skills/obia/scripts/obia.py recall --vault '/path/to/vault' --project my-app --task login --view brief
python3 skills/obia/scripts/obia.py read --vault '/path/to/vault' --project my-app --task login --section Sources
python3 skills/obia/scripts/obia.py check --vault '/path/to/vault' --project my-app
```

`save --input -` reads JSON from stdin. Prefer a structured tool or an input file
when composing payloads; do not interpolate task text into shell commands.

## Updating an existing task

1. `read` the task. The result contains a `sha256` of the complete Markdown note,
   including when reading one section.
2. Prefer a partial JSON patch containing `properties`, `sections` and/or `append`.
   `sections` replaces only the named level-two section body; `append` adds to it.
   Headings inside fenced code are ignored. Unmentioned sections are retained.
3. Run `patch --project my-app --task login --input patch.json --expect-sha SHA`.
4. Check the returned status and warning. Reconcile concurrent edits before retrying.

Example `patch.json` (sources must already exist or be supplied in `sections.Sources`):

```json
{
  "properties": {"status": "complete", "summary": "Login tested offline."},
  "append": {"Facts": "- Offline login passed. [S1]"},
  "sections": {"Next steps": "No remaining implementation work."}
}
```

Plain YAML strings, lists, dates, custom properties and comments are supported.
Identity fields (`obia`, `project`, `task_id`) are immutable; `updated` is automatic.
The generated title/current-state line is synchronized when its old text matches.
If a human rewrote the current-state line, supply a reconciled `sections.Resume`.
Duplicate YAML keys, custom YAML tags and duplicate section headings are rejected.

For a deliberate complete body rewrite, use a complete checkpoint JSON with
`save --input checkpoint.json --expect-sha SHA --replace`. Extra frontmatter
properties are preserved when YAML support is installed; the body is replaced.
Without `--replace`, a changed existing note is refused even with the correct SHA.

Identical replacements return `unchanged` and create no history. Changed notes
save the previous version in `OBIA/.history/<project>/<task>/<sha>.md` before
replacing current state. History is local and never searched by default. It may
contain information later removed from current state; deleting sensitive data
from a current note does not erase historical copies or external backups.

## Retrieval

- `search` requires a project. It uses accent-insensitive lexical matching over
  current task notes, with title and summary boosts; it is not semantic search.
  Results contain metadata and SHA, not complete notes. `--limit` is 1–10 (default 5).
- `recall` accepts exactly one of `--task` or `--query`. A known task may add its
  directly linked, nonarchived tasks from the same project, up to `--limit`
  (default 3). It does not traverse recursively or open personal/cross-project links.
- `--max-chars` limits the serialized JSON output, including its trailing newline,
  to 1,024–64,000 Unicode characters (default 12,000). This is **not** a token count.
- `recall --view full` (the CLI/API default) includes notes whole or omits them.
  `omitted_count` counts candidate notes that
  do not fit the character budget, not every unselected note in the vault. `omitted`
  lists their paths where space permits. `read --section Resume`, followed by
  relevant evidence sections and `Sources`, handles an oversized note.
- `recall --view brief` includes the main note's complete `Resume`, `Constraints`,
  `Decisions` and `Corrections` sections when present, its preamble, status and
  updated time. The SHA always identifies the full persisted note. It lists
  omitted sections and referenced source IDs; source definitions are deferred.
  Known-task links return only locators, titles and summaries, not recovered
  context. Query matches each receive a brief projection.
- Brief views never truncate essential sections to make them fit. A `deferred`
  entry has `read_required: full` and no content; if even its locator cannot fit,
  the note is counted as omitted. Read a deferred/omitted main note in full before
  acting. Linked locators need a read before relying on their evidence. Notes
  without `Resume` or with custom frontmatter use a full fallback to preserve
  nonstandard context. Custom body sections remain explicitly listed as omitted.
- `read` has no recall budget; one note is limited to 128 KiB on disk. Repeat
  `--section` to fetch several level-two sections in one response, or repeat
  `--source S1` to fetch selected definitions from `Sources`, including multiline
  records. The two selectors are mutually exclusive. Fenced examples and source
  IDs outside `Sources` are not definitions; missing or duplicate IDs fail.
- Use `read --expect-sha SHA` when expanding a retrieved snapshot. If the note
  changed, recover its new state instead of combining old claims with new sources.
- `read --if-changed SHA` returns only path/SHA and `status: unchanged` when the
  persisted note matches. Use this only for context already available to the
  agent, not as a substitute for reading a newly needed section or source. If the
  SHA differs, the requested content is returned normally. It neither saves a
  checkpoint nor acknowledges a receipt.
- Archived tasks are absent from normal search and linked recall; use
  `search --include-archived` or an explicitly known task ID to recover them.

## Ownership and failure recovery

`init` claims a new `OBIA/` namespace. It refuses an existing folder without the
matching `.obia.json` marker. It leaves `.obsidian/` and all other vault notes alone.
Task files are Markdown; the tiny marker is a JSON format-version identifier.

Writers use an exclusive local lock, SHA checks and atomic file replacement.
These coordinate helper processes on one filesystem; they are **not** a distributed
lock for iCloud/Dropbox/Git, and cannot coordinate editors that ignore the lock.
Use one writer at a time across synchronized devices. A stale `.write.lock` needs
manual inspection: confirm the writer is stopped before removing it.

`index` rebuilds the generated vault/project indexes from current notes. It
refuses to overwrite an index without OBIA's generated marker. Indexes are caches,
not authoritative memories. If `save` reports `Note saved; indexes need repair`,
read the note before retrying and repair the index separately.

`check` checks project metadata, source references, related targets, the project
index, and a limited set of credential patterns. It cannot establish source truth,
detect every secret, or enforce the agent's reasoning behavior. Do not store secrets.

Exit codes: `0` success, `1` structural check problems, `2` invalid input or I/O
failure. Results are UTF-8 JSON on stdout; errors are UTF-8 JSON on stderr. No deletion,
automatic sync, arbitrary shell execution, or external API commands are provided.
