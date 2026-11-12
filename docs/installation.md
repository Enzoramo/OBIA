# Public installer and one vault per project

Requires Python 3.10+ and pip. Git is optional, but needed to recognize worktrees.
Choose an **existing private parent folder** for the vaults. Keep it outside the
public skill checkout. The installer downloads the pinned pure-Python YAML package
into the skill's `_packages/`; runtime memory operations do not use the network.

```sh
python3 install.py --host codex --vaults-root '/private/Obsidian' --project '/work/my-app'
python3 install.py --host claude --vaults-root '/private/Obsidian' --project '/work/my-app'
```

On Windows, use `python` and quoted absolute Windows paths. No shell script,
Unix-only file locking, or administrator access is required for installation.

Defaults:

| Setting | Location |
| --- | --- |
| Codex skill | `~/.agents/skills/obia` |
| Claude Code skill | `~/.claude/skills/obia` |
| Private registry | `~/.config/obia/projects.json` (`OBIA_HOME` overrides the directory) |
| Codex instructions | `$CODEX_HOME/AGENTS.md`, default `~/.codex/AGENTS.md` |
| Claude instructions | `~/.claude/CLAUDE.md` |
| New vault | `<vaults-root>/OBIA - <project name>` |

Use `--skills-dir`, `--config-dir` and `--instructions` to override these paths.
For existing Codex desktop installations under `~/.codex/skills`, explicitly pass
`--skills-dir ~/.codex/skills`. Do not keep duplicate copies in both skill locations.
For another host, use its skill directory with `--no-instructions`, then configure
its own instruction mechanism. The installed package contains its own installer
at `scripts/setup_obia.py` as well as the project router.

The installer adds a clearly delimited OBIA block to host instructions, preserving
other text and backing up changed files. `--no-instructions` opts out. This is an
instruction to use memory for project work, not a guarantee of host activation.
Open the new folder using Obsidian's **Open folder as vault** command. OBIA does
not modify Obsidian's running application's private vault registry.

Add `--hooks` to merge optional lifecycle adapters; see [hooks and activation](hooks.md).

## Resolving projects

```sh
python3 skills/obia/scripts/projects.py --config-dir '/private/obia-config' configure --vaults-root '/private/Obsidian'
python3 skills/obia/scripts/projects.py --config-dir '/private/obia-config' ensure --path '/work/my-app'
python3 skills/obia/scripts/projects.py --config-dir '/private/obia-config' resolve --path '/work/my-app/src'
```

Use the returned `vault` and `project` values with `obia.py`. `ensure` creates a
new vault only for an unregistered project. `resolve` is read-only. Both match a
registered parent folder first, then use Git's common directory to map worktrees
to the original project. Register separate nested projects by running `ensure`
for each **before** registering an enclosing workspace, or use separate registries.
Name collisions get a stable path-derived suffix. A missing registered vault or
parent folder is an error; it is never silently replaced. Check sync or relocation.

Vault creation reserves an identity in the registry before provisioning. If an
interrupted creation left an unowned folder with no identity marker, inspect it
before retrying; OBIA refuses to claim arbitrary existing content.

Registry locks are exclusive on one filesystem. A stale `.projects.lock` requires
checking that its writer stopped before removal. These locks do not coordinate
multiple computers through iCloud or other sync systems.

## Updates and migration

```sh
python3 install.py --host codex --vaults-root '/private/Obsidian' --update
```

Use the same directory overrides as the original installation. Dependencies are
installed and checked in a staging directory before replacing code. The previous
skill is kept in a `.obia-backup-...` sibling folder. Private registry entries and
vault contents are retained. Existing instruction files also get local backups.
Never put these backups or runtime configuration in the public repository.

Existing schema-1 `projects.json` registries are supported, including the original
local Codex router. Pass their directory via `--config-dir`; the installer refuses
to change their vault parent. It does not silently migrate absolute paths to
another computer. Configure that computer's accessible locations explicitly.

For development:

```sh
python3 -m venv .venv
# Activate .venv using your platform's normal command, then:
python -m pip install -r skills/obia/requirements.txt
python -m unittest discover -s tests -v
python examples/demo.py
```
