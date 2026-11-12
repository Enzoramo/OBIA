#!/usr/bin/env python3
"""Run a synthetic cross-process save/recovery demo in an isolated temporary vault."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "skills/obia/scripts/obia.py"


def call(vault, command, *args):
    result = subprocess.run(
        [sys.executable, str(HELPER), command, "--vault", str(vault), *args],
        text=True, encoding="utf-8", capture_output=True, check=True,
    )
    return json.loads(result.stdout)


def main():
    with tempfile.TemporaryDirectory(prefix="obia-demo-") as folder:
        vault = Path(folder)
        call(vault, "init")
        for fixture in ("storage-choice.json", "offline-cache.json"):
            call(vault, "save", "--input", str(REPO / "examples" / fixture))
        # This new process receives only the vault/project/task, no conversation.
        packet = call(vault, "recall", "--project", "demo-app", "--task", "offline-cache")
        report = call(vault, "check", "--project", "demo-app")
        if len(packet["notes"]) != 2 or report["problems"]:
            raise RuntimeError("Synthetic recovery failed")
        output = {
            "demo": "Synthetic data only; temporary vault removed on exit.",
            "recovered_notes": [n["path"] for n in packet["notes"]],
            "retrieval_characters": len(json.dumps(packet, ensure_ascii=False, indent=2)) + 1,
            "character_budget": packet["max_chars"],
            "checks": report,
            "resume": call(vault, "read", "--project", "demo-app", "--task", "offline-cache", "--section", "Resume")["content"],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
