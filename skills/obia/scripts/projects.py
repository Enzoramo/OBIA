#!/usr/bin/env python3
"""Portable project-to-vault routing. Private configuration stays outside the skill."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obia as memory

STATE = Path(os.environ.get("OBIA_HOME", Path.home() / ".config/obia")).expanduser()
CONFIG = STATE / "projects.json"
HELPER = Path(__file__).resolve().with_name("obia.py")


@contextmanager
def locked(config_path):
    lock = memory.safe_path(config_path.parent, ".projects.lock")
    try:
        import fcntl
    except ImportError:
        fcntl = None
    if fcntl is not None:
        # Interoperate with the original local router, whose advisory lock file
        # remains on disk after release. Existence is not a live POSIX lock.
        with lock.open("a", encoding="utf-8") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("Project registry is locked by another writer.")
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
        return
    # Windows fallback needs no third-party locking package. Stale exclusive
    # files require inspection; do not mistake an old PID for permission to delete.
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Project registry is locked. Check for a live writer before removing a stale .projects.lock.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"pid={os.getpid()}\n")
        yield
    finally:
        lock.unlink()


def configure(vaults_root, config_path=CONFIG):
    base = Path(vaults_root).expanduser().resolve()
    if not base.is_dir():
        raise ValueError("Choose an existing private parent directory for the project vaults.")
    config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with locked(config_path):
        if config_path.is_symlink():
            raise ValueError("Registry must not be a symlink.")
        if config_path.exists():
            data = load(config_path)
            if Path(data["vaults_root"]).expanduser().resolve() != base:
                raise ValueError("Existing vault parent differs. Migrate it explicitly; installation does not relocate memories.")
            return {"status": "existing", "config": str(config_path)}
        data = {"schema": 1, "vaults_root": str(base), "projects": []}
        memory.atomic_write(config_path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return {"status": "created", "config": str(config_path)}


def load(config_path=CONFIG):
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("projects"), list):
        raise ValueError("Unsupported local project registry.")
    root = Path(data["vaults_root"]).expanduser()
    if not root.is_dir():
        raise ValueError("Configured vault parent is unavailable. Do not create a replacement location.")
    return data


def key_for(name):
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:48].rstrip("-") or "project"


def git_root(path):
    if not shutil.which("git"):
        return path
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        text=True, encoding="utf-8", capture_output=True,
    )
    if result.returncode:
        return path
    common = Path(result.stdout.strip()).resolve()
    if common.name == ".git":
        return common.parent
    top = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                         text=True, encoding="utf-8", capture_output=True)
    return Path(top.stdout.strip()).resolve() if top.returncode == 0 else path


def match(path, projects):
    candidates = [p for p in projects if path.is_relative_to(Path(p["root"]))]
    return max(candidates, key=lambda p: len(Path(p["root"]).parts)) if candidates else None


def selection(path, projects):
    path = Path(path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError("Project directory does not exist.")
    existing = match(path, projects)
    if existing:
        return path, existing
    canonical = git_root(path)
    return canonical, match(canonical, projects)


def validate_vault(entry, data):
    vault = Path(entry["vault"])
    base = Path(data["vaults_root"]).expanduser().resolve()
    if vault.parent.resolve() != base or vault.is_symlink():
        raise ValueError("Vault must be a direct, non-symlink child of the configured parent.")
    return vault


def provision(entry, data):
    vault = validate_vault(entry, data)
    marker = memory.safe_path(vault, ".obia-project.json")
    identity = {"schema": 1, "project": entry["project"], "root": entry["root"]}
    if vault.exists():
        if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8")) != identity:
            raise ValueError(f"Refusing to claim an unrelated existing folder: {vault}")
    else:
        vault.mkdir(mode=0o700)
        memory.atomic_write(marker, json.dumps(identity, ensure_ascii=False, indent=2) + "\n")
    if (vault / ".obsidian").is_symlink():
        raise ValueError("Vault configuration directory must not be a symlink.")
    (vault / ".obsidian").mkdir(exist_ok=True)
    memory.initialize(vault)
    home = memory.safe_path(vault, "Home.md")
    if not home.exists():
        body = (
            f"# {entry['label']} · OBIA\n\n"
            f"- [[OBIA/projects/{entry['project']}/index|Project tasks]]\n"
            "- [[OBIA/index|Memory index]]\n\n"
            "Private task memory. Verify remembered claims against current evidence.\n"
            "The public skill repository does not contain this vault.\n"
        )
        memory.atomic_write(home, body)
    # A project index is useful before its first task; do not overwrite it later.
    index = memory.safe_path(vault, f"OBIA/projects/{entry['project']}/index.md")
    if not index.exists():
        memory.atomic_write(index, memory.index_content([], entry["project"]))
    return vault


def ensure(path, name=None, config_path=CONFIG):
    with locked(config_path):
        data = load(config_path)
        canonical, entry = selection(path, data["projects"])
        new = entry is None
        if new:
            label = (name or canonical.name).strip()
            if not label or any(ord(c) < 32 or c in '/\\:*?"<>|' for c in label):
                raise ValueError("Choose a simple project name without path separators or control characters.")
            label = label[:100]
            slug = key_for(label)
            base = Path(data["vaults_root"]).expanduser().resolve()
            vault = base / ("OBIA - " + label)
            used = {p["project"] for p in data["projects"]}
            if slug in used or vault.exists():
                suffix = hashlib.sha256(str(canonical).encode()).hexdigest()[:8]
                slug = slug[:48].rstrip("-") + "-" + suffix
                vault = base / ("OBIA - " + label + " - " + suffix)
            entry = {"root": str(canonical), "label": label, "project": slug,
                     "vault": str(vault), "ready": False}
            # Save the reservation first. A retry can finish provisioning this same vault.
            data["projects"].append(entry)
            memory.atomic_write(config_path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        if not new and entry.get("ready", True) and not Path(entry["vault"]).is_dir():
            raise ValueError("Registered vault is missing. Check sync or relocation; do not replace it.")
        vault = provision(entry, data)
        if not entry.get("ready", False):
            entry["ready"] = True
            memory.atomic_write(config_path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return {**entry, "created": new, "helper": str(HELPER), "home": str(vault / "Home.md")}


def resolve(path, config_path=CONFIG):
    data = load(config_path)
    _, entry = selection(path, data["projects"])
    if entry is None:
        raise ValueError("No vault registered yet. Run ensure for this project's root.")
    vault = validate_vault(entry, data)
    if not vault.is_dir():
        raise ValueError("Registered vault is missing. Check sync or relocation before creating anything.")
    identity = {"schema": 1, "project": entry["project"], "root": entry["root"]}
    marker = memory.safe_path(vault, ".obia-project.json")
    if not marker.is_file() or json.loads(memory.read_text(marker)) != identity:
        raise ValueError("Registered vault identity differs; check the configuration.")
    memory.initialized(vault)
    return {**entry, "helper": str(HELPER), "home": str(vault / "Home.md")}


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    for action in ("ensure", "resolve"):
        child = commands.add_parser(action)
        child.add_argument("--path", required=True)
        if action == "ensure":
            child.add_argument("--name")

    commands.add_parser("list")
    child = commands.add_parser("configure")
    child.add_argument("--vaults-root", required=True)
    args = parser.parse_args()
    config_path = args.config_dir.expanduser().resolve() / "projects.json"
    try:
        if args.command == "ensure":
            result = ensure(args.path, args.name, config_path)
        elif args.command == "resolve":
            result = resolve(args.path, config_path)
        elif args.command == "configure":
            result = configure(args.vaults_root, config_path)
        else:
            result = load(config_path)["projects"]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
