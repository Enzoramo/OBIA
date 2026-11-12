# Helper commands

Python 3.10+; no packages, API keys, network calls, embeddings or Obsidian plugins.
Resolve the helper from the installed skill directory. Examples below run from
the OBIA repository root. Quote paths, including vault paths containing spaces.
Replace `/path/to/vault` with the user's existing vault directory.

```sh
python3 skills/obia/scripts/obia.py init --vault '/path/to/vault'
python3 skills/obia/scripts/obia.py save --vault '/path/to/vault' --input checkpoint.json
python3 skills/obia/scripts/obia.py search --vault '/path/to/vault' --project my-app --query 'login offline'
python3 skills/obia/scripts/obia.py recall --vault '/path/to/vault' --project my-app --task login --max-chars 12000
python3 skills/obia/scripts/obia.py read --vault '/path/to/vault' --project my-app --task login --section Sources
python3 skills/obia/scripts/obia.py check --vault '/path/to/vault' --project my-app
```

`save --input -` reads JSON from stdin. Prefer a structured tool or an input file
when composing payloads; do not interpolate task text into shell commands.

## Updating an existing task

1. `read` the task. The result contains a `sha256` of the complete Markdown note,
   including when reading one section.
2. Build a **complete replacement checkpoint**, preserving all still-relevant
   state, evidence and constraints. Omitted optional lists become empty; `save`
   is not a partial patch or automatic merge.
3. Run `save --input checkpoint.json --expect-sha ACTUAL_SHA_FROM_READ`.
4. Check the returned status and any warning. A stale or absent SHA refuses the
   replacement. Reconcile any concurrent edit before retrying.

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
- Notes are included whole or omitted. `omitted_count` counts candidate notes that
  do not fit the character budget, not every unselected note in the vault. `omitted`
  lists their paths where space permits. `read --section Resume`, followed by
  relevant evidence sections and `Sources`, handles an oversized note.
- `read` has no recall budget; one note is limited to 128 KiB on disk. It supports
  a level-2 section name such as `Facts`, `Decisions`, or `Sources`.
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
failure. Results are JSON on stdout; errors are JSON on stderr. No deletion,
automatic sync, arbitrary shell execution, or external API commands are provided.
