# Memory format, v1

One task has one stable current Markdown note. Separate tasks live under separate
project slugs. Content may be written in any language; field names stay stable.

```text
your-vault/
└── OBIA/
    ├── .obia.json
    ├── index.md
    ├── projects/
    │   └── my-app/
    │       ├── index.md
    │       └── tasks/
    │           ├── storage-choice.md
    │           └── offline-cache.md
    └── .history/
        └── my-app/offline-cache/<previous-sha>.md
```

The following JSON is the helper's **input**, not an extra permanent memory file.
It renders flat YAML frontmatter and human-readable Markdown. Save temporary
payloads outside public repositories and remove them according to user policy.

```json
{
  "project": "my-app",
  "id": "offline-cache",
  "title": "Implement an offline cache",
  "status": "active",
  "summary": "Storage choice agreed; implementation and verification remain.",
  "objective": "Allow previously loaded items to be read without a connection.",
  "sources": [
    {
      "id": "S1",
      "kind": "user",
      "ref": "Task request: cached items must remain readable offline; no background sync.",
      "observed_at": "2026-11-12"
    }
  ],
  "constraints": [{"text": "Do not introduce background synchronization.", "sources": ["S1"]}],
  "facts": [],
  "decisions": [],
  "hypotheses": [{"text": "The existing storage layer may be reusable.", "verify": "Inspect its schema and read path before changing code."}],
  "open_questions": ["How should expired cached data be presented?"],
  "next_actions": ["Inspect the current storage implementation."],
  "artifacts": [],
  "corrections": [],
  "links": []
}
```

## Fields

Required: `project`, `id`, `title`, `status`, `summary`, `objective`, `sources`.
All other fields are optional lists. Unknown fields are refused to catch typos.
Strings are single-line text. Keep claims concise and put long evidence in its
source artifact. The overall payload/note limit is 128 KiB.

| Field | Shape / meaning |
|---|---|
| `project`, `id` | Lowercase ASCII letters/digits separated by hyphens, 1–64 characters. |
| `title` | Human-readable task title, at most 160 characters. |
| `summary` | Current state for discovery, at most 240 characters. |
| `objective` | User's intended result, at most 1,500 characters. |
| `status` | `active`, `blocked`, `complete`, or `archived`. Complete means the requested outcome was actually verified. |
| `sources` | Nonempty list of `{id, kind, ref, observed_at}`. Unique IDs `S1`, `S2`, etc. |
| `facts`, `constraints`, `corrections` | Lists of `{text, sources: ["S1"]}`. |
| `decisions` | List of `{text, reason, sources: ["S1"]}`. A short decision rationale is sufficient. |
| `hypotheses` | List of `{text, verify}`. Hypotheses remain unverified until new evidence supports them. |
| `open_questions`, `next_actions` | Lists of strings. Next actions do not imply authorization. |
| `artifacts` | List of `{path, description, sources: ["S1"]}`. State the relevant revision/verification in the description or evidence locator. |
| `links` | List of `{target, relation}`. Target is an existing vault-relative `.md` file. |

Source kinds: `user`, `file`, `url`, `tool`, `memory`. Use `ref` for a useful
locator: message identifier if available, project-relative file and commit,
URL plus section, or command and stored result. Do not invent unavailable
identifiers, line numbers, timestamps or successful test results. `observed_at`
is an ISO date or timezone-aware ISO timestamp of actual observation. Synthetic
examples in this repository are explicitly labeled as such.

A `memory` source means a derived claim. Follow it to primary evidence before
relying on it for a consequential action. Do not reclassify it as a fresh tool
observation. No source field is an automatic credibility score.

## Links

```json
{"target": "OBIA/projects/my-app/tasks/storage-choice.md", "relation": "Implements the storage decision recorded in this task."}
```

The helper validates existence and renders
`[[OBIA/projects/my-app/tasks/storage-choice]]`. It rejects traversal, symlinks,
anchors and ambiguous special characters. Links may point to an existing personal
note when the user has authorized that scope, but automatic recall stays within
managed task notes of the selected project. Adding a link never edits its target.

## Corrections and bounded current state

When a remembered fact is disproved, replace the current fact and add a sourced
`corrections` entry explaining what changed. Do not keep an obsolete claim among
current facts. The old Markdown remains in `.history`. For genuinely conflicting
sources, record the disagreement and a next verification step instead of choosing
whichever source is newer by default.

Do not add a separate note for every observation. Extract another task only for a
distinct objective or a substantive decision that is actually reused. Current
notes summarize state; sources retain detail and history retains prior versions.

## Editing in Obsidian

The note body is ordinary Markdown. Frontmatter uses JSON-quoted scalar values
(valid YAML). The helper intentionally parses this small format, not arbitrary
YAML; preserve the generated quoting, keys and IDs when editing frontmatter.
Human body edits are preserved as snapshots on the next replacement. Reread and
merge useful edits into the checkpoint first. `index` refreshes discovery after
manual summary/status edits. Renaming managed task files by hand changes their
identity; use a new task and a documented relationship instead.
