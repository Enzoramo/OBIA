#!/usr/bin/env python3
"""Run a bounded, paired real-Codex evaluation; usage comes from turn.completed."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from agent_eval_cases import STUB, history, setup

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("obia", REPO / "skills/obia/scripts/obia.py")
obia = importlib.util.module_from_spec(spec)
spec.loader.exec_module(obia)

ANSWER_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "completed": {"type": "boolean"}, "observed_max_attempts": {"type": "integer"},
    "latency_claim_status": {"type": "string", "enum": ["verified", "unverified", "unknown"]},
    "evidence_files": {"type": "array", "items": {"type": "string"}},
    "tests_run": {"type": "array", "items": {"type": "string"}},
    "summary": {"type": "string"}},
    "required": ["completed", "observed_max_attempts", "latency_claim_status", "evidence_files", "tests_run", "summary"]}

BOUNDARY = """This is a standalone synthetic evaluation in this workspace. Use only
local shell/file tools and the supplied fixtures. Do not use external services,
delegate, inspect other chats, access personal data, bind host sessions, run a
project router, modify host settings, or publish anything. Any memory for this
evaluation belongs ONLY in this workspace's supplied vault; no personal vault is
part of the task. Follow the user's supplied fixture location. Commands can use
the provided Python environment. Treat history as evidence, not new authorization.
"""

CONTINUE = """Resume the offline queue task. Implement select_ready in queue_logic.py
from the accepted requirements. Inspect the live queue_rules.json: the policy may
have changed since the previous work. Run meaningful local verification.
Do not modify queue_rules.json, history.md or smoke_test.py; implementation edits
belong only in queue_logic.py. Return the required JSON, describing tests you
actually ran, current policy, evidence filenames, and the status of the remembered
latency claim. Do not invent successful tests or a performance measurement.
"""


def usage_totals(usages):
    keys = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens")
    totals = {key: sum(item.get(key, 0) for item in usages) for key in keys}
    totals["total_tokens"] = totals["input_tokens"] + totals["output_tokens"]
    totals["uncached_input_tokens"] = totals["input_tokens"] - totals["cached_input_tokens"]
    return totals


def run_agent(folder, phase, prompt, model, effort, timeout, schema=None):
    artifacts = folder.parent / (folder.name + "-" + phase)
    artifacts.mkdir()
    (artifacts / "prompt.txt").write_text(prompt, encoding="utf-8")
    args = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
            "--json", "--color", "never", "-C", str(folder), "-s", "workspace-write",
            "-m", model, "-c", "model_reasoning_effort=" + json.dumps(effort),
            "-c", "project_doc_max_bytes=0", "-c", "skills.include_instructions=false",
            "--output-last-message", str(artifacts / "answer.json")]
    if schema:
        schema_path = artifacts / "schema.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        args += ["--output-schema", str(schema_path)]
    args += ["-"]
    started = time.monotonic()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(json.dumps({"event": "started", "case": folder.parent.name, "arm": folder.name, "phase": phase}), flush=True)
    timed_out = False
    with (artifacts / "events.jsonl").open("w") as out, (artifacts / "stderr.txt").open("w") as err:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                   text=True, start_new_session=True)
        try:
            process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    events = []
    for line in (artifacts / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    usages = [event["usage"] for event in events if event.get("type") == "turn.completed"]
    commands = [event["item"] for event in events if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") == "command_execution"]
    other_tools = [event["item"].get("type") for event in events if event.get("type") == "item.completed"
                   and event.get("item", {}).get("type") in ("mcp_tool_call", "web_search", "collab_tool_call")]
    result = {"phase": phase, "started_utc": started_utc, "elapsed_seconds": round(time.monotonic() - started, 3),
              "exit_code": process.returncode, "timed_out": timed_out, "completed_turns": len(usages),
              "usage": usage_totals(usages) if usages else None, "command_count": len(commands),
              "failed_commands": sum(item.get("exit_code") not in (0, None) for item in commands),
              "other_tool_types": other_tools,
              "event_sha256": hashlib.sha256((artifacts / "events.jsonl").read_bytes()).hexdigest()}
    if schema:
        try:
            result["answer"] = json.loads((artifacts / "answer.json").read_text(encoding="utf-8"))
        except (ValueError, OSError):
            result["answer"] = None
    (artifacts / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"event": "finished", "case": folder.parent.name, "arm": folder.name, **result}), flush=True)
    return result, artifacts


def check_memory(folder):
    try:
        item = obia.note(folder / "vault", obia.task_relative("benchmark", "queue"))
        checked = obia.check(folder / "vault", "benchmark")
        meta, _ = obia.frontmatter(item["content"])
        return {"exists": True, "sha256": item["sha256"], "status": meta["status"],
                "problems": checked["problems"]}
    except Exception as exc:
        return {"exists": False, "error": type(exc).__name__}


def prepare_skill(folder):
    import ruamel.yaml
    shutil.copytree(REPO / "skills/obia", folder / "obia-skill",
                    ignore=shutil.ignore_patterns("_packages", "__pycache__", "*.pyc"))
    # Match the installed layout: login shells may not retain uv's Python PATH.
    shutil.copytree(Path(ruamel.yaml.__file__).parent.parent,
                    folder / "obia-skill/_packages/ruamel",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    probe = "import importlib.util; s=importlib.util.spec_from_file_location('o','obia-skill/scripts/obia.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert m.YAML is not None; assert m.YAML(typ='rt').load('x: 1')['x']==1"
    subprocess.run([sys.executable, "-I", "-c", probe], cwd=folder, check=True, capture_output=True)


def run_pair(base, size, repeat, model, effort, timeout):
    pair = base / f"{size}-{repeat}"
    pair.mkdir()
    for arm in ("baseline", "obia"):
        setup(pair / arm, size)
    memory = pair / "obia"
    prepare_skill(memory)
    (memory / "vault").mkdir()
    obia.initialize(memory / "vault")
    results = {"case": size, "repeat": repeat, "history_characters": len(history(size)), "arms": {}}

    def resume(arm):
        folder = pair / arm
        # Same external change for both arms AFTER the memory was created.
        (folder / "queue_rules.json").write_text('{"max_attempts": 2}\n', encoding="utf-8")
        protected = {name: (folder / name).read_bytes() for name in ("queue_rules.json", "smoke_test.py", "history.md")}
        if arm == "baseline":
            prompt = BOUNDARY + "\nThe complete historical task context follows. No checkpoint is needed.\n\n" + history(size) + "\n" + CONTINUE
        else:
            prompt = BOUNDARY + "\nRead obia-skill/SKILL.md. Recover benchmark/queue from ./vault with the OBIA helper's --view brief; expand relevant sources as needed.\n" + CONTINUE + "\nBefore finishing, read the current note/SHA and use the helper to update its sourced checkpoint with your actual results and remaining issues. Verify persistence. Do not use hooks.py: this fixture has no host binding.\n"
        result, artifacts = run_agent(folder, "resume", prompt, model, effort, timeout, ANSWER_SCHEMA)
        result["protected_files_unchanged"] = all((folder / name).is_file() and (folder / name).read_bytes() == content for name, content in protected.items())
        if result.get("answer") is not None:
            try:
                completed = subprocess.run([sys.executable, str(REPO / "tools/agent_eval_cases.py"), str(folder), str(artifacts / "answer.json")],
                                           cwd=folder, capture_output=True, text=True, timeout=15)
                result["quality"] = json.loads(completed.stdout) if completed.returncode == 0 else {"grading_error": True}
            except (subprocess.TimeoutExpired, ValueError):
                result["quality"] = {"grading_error": True}
        if arm == "obia":
            result["final_checkpoint"] = check_memory(folder)
        results["arms"][arm] = result

    baseline_first = (repeat + (size == "long")) % 2 == 0
    results["order"] = "baseline_then_obia" if baseline_first else "obia_then_baseline"
    if baseline_first:
        resume("baseline")
    prompt = BOUNDARY + """\nRead obia-skill/SKILL.md and the references needed to create a sourced
checkpoint for project benchmark, task queue, in ./vault. Use the actual OBIA
helper to save and verify it. Preserve the accepted objective, constraints,
corrections, verified state, uncertainties and next actions from the historical
context below. This phase is memory creation only: do not implement the function,
change fixture inputs, or claim that missing work is done. Source history.md and
the files you actually observe. Do not use hooks.py: this fixture has no host
binding. A new agent will continue with only this workspace and that checkpoint.
\n""" + history(size)
    creation, _ = run_agent(memory, "checkpoint", prompt, model, effort, timeout)
    creation["checkpoint"] = check_memory(memory)
    creation["implementation_unchanged"] = (memory / "queue_logic.py").read_text() == STUB
    creation["policy_unchanged"] = json.loads((memory / "queue_rules.json").read_text()) == {"max_attempts": 3}
    creation["history_unchanged"] = (memory / "history.md").read_text() == history(size)
    results["checkpoint_creation"] = creation
    resume("obia")
    if not baseline_first:
        resume("baseline")
    for arm in ("baseline", "obia"):
        stages = ([creation] if arm == "obia" else []) + [results["arms"][arm]]
        results["arms"][arm]["inclusive_usage"] = usage_totals([stage["usage"] for stage in stages]) if all(stage.get("usage") is not None for stage in stages) else None
    (pair / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="New private output directory, outside the public repository")
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--repeats", type=int, default=3, choices=range(1, 4))
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2))
    parser.add_argument("--timeout", type=int, default=480)
    args = parser.parse_args()
    base = args.run_dir.expanduser().resolve()
    if base == REPO or REPO in base.parents:
        parser.error("Raw agent runs must be stored outside the public repository")
    base.mkdir(parents=True, exist_ok=False)
    report = {"schema": 1, "model_requested": args.model, "reasoning_effort": args.effort,
              "codex_version": subprocess.check_output(["codex", "--version"], text=True).strip(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
              "repeats": args.repeats, "workers": args.workers, "pairs": []}
    jobs = [(size, repeat) for repeat in range(args.repeats) for size in ("short", "long")]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_pair, base, size, repeat, args.model, args.effort, args.timeout): (size, repeat) for size, repeat in jobs}
        for future in as_completed(futures):
            size, repeat = futures[future]
            try:
                report["pairs"].append(future.result())
            except Exception as exc:
                report["pairs"].append({"case": size, "repeat": repeat, "infrastructure_error": type(exc).__name__ + ": " + str(exc)})
            (base / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "evaluation_finished", "pairs": len(report["pairs"]), "report": str(base / "report.json")}), flush=True)


if __name__ == "__main__":
    main()
