#!/usr/bin/env python3
"""Export numeric real-agent results without prompts, chats or private paths."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics

from evaluate_real_agents import usage_totals


def read_events(path):
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            result.append(json.loads(line))
        except ValueError:
            pass
    return result


def compact_stage(stage, path, manual_audit):
    events = read_events(path / "events.jsonl")
    usages = [event["usage"] for event in events if event.get("type") == "turn.completed"]
    observed = usage_totals(usages) if usages else None
    assert observed == stage["usage"], "Saved metrics do not match raw usage events"
    assert hashlib.sha256((path / "events.jsonl").read_bytes()).hexdigest() == stage["event_sha256"]
    keys = ("elapsed_seconds", "exit_code", "timed_out", "completed_turns", "usage", "command_count",
            "failed_commands", "other_tool_types", "event_sha256", "protected_files_unchanged", "quality")
    result = {key: stage[key] for key in keys if key in stage}
    result["tool_action_count"] = sum(event.get("type") == "item.completed" and
        event.get("item", {}).get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search", "collab_tool_call")
        for event in events)
    commands = [event["item"] for event in events if event.get("type") == "item.completed"
                and event.get("item", {}).get("type") == "command_execution"]
    workspace = path.parent / path.name.rsplit("-", 1)[0]
    outside_temp = []
    for item in commands:
        paths = re.findall(r"/(?:private/tmp|tmp)(?:/[^\s\"'\\;]*)?", item.get("command", ""))
        outside_temp.append(any(not (Path(value.rstrip(")],}")).resolve() == workspace.resolve()
                                    or workspace.resolve() in Path(value.rstrip(")],}")).resolve().parents)
                                for value in paths))
    # These are audit indicators, not a claim to prove every command safe.
    result["audit"] = {
        "hook_or_router_command_mentions": sum("hooks.py" in item.get("command", "") or "projects.py" in item.get("command", "") for item in commands),
        "completed_successful_commands": sum(item.get("exit_code") == 0 for item in commands),
        "test_output_observed": any("Ran " in item.get("aggregated_output", "") and "OK" in item.get("aggregated_output", "") and item.get("exit_code") == 0 for item in commands),
        "outside_workspace_temp_probe_commands": sum(outside_temp),
    }
    reviewed = manual_audit.get(path.parent.name + "/" + path.name)
    result["manual_review"] = reviewed
    result["protocol_deviation"] = (reviewed["scope"] == "deviation") if reviewed else None
    return result


def reduction(before, after):
    return round(100 * (before - after) / before, 3) if before else None


def summarize(root, manual_audit=None):
    manual_audit = manual_audit or {}
    original = json.loads((root / "report.json").read_text(encoding="utf-8"))
    report = {key: original[key] for key in ("schema", "model_requested", "reasoning_effort", "codex_version", "source_commit", "repeats", "workers")}
    report["workflow"] = original.get("workflow", "legacy")
    report["measurement"] = "actual_codex_turn_completed_usage"
    report["scope"] = "One fresh-context handoff, including initial checkpoint creation and final checkpoint maintenance."
    if original.get("workflow") == "reconciled_replay":
        for key in ("scope", "reused_source_commit", "planned_agent_executions", "new_agent_executions", "completed_agent_turns", "reused_agent_executions"):
            report[key] = original[key]
    report["exclusions"] = ["earlier common task work", "parent chat and evaluation development", "monetary billing", "human time", "native compaction comparison"]
    report["pairs"] = []
    for pair in sorted(original["pairs"], key=lambda p: (p["case"], p["repeat"])):
        if "infrastructure_error" in pair:
            report["pairs"].append({"case": pair["case"], "repeat": pair["repeat"], "infrastructure_error": True})
            continue
        folder = root / f"{pair['case']}-{pair['repeat']}"
        sample = {key: pair[key] for key in ("case", "repeat", "order", "history_characters")}
        creation = pair["checkpoint_creation"]
        sample["checkpoint_creation"] = compact_stage(creation, folder / "obia-checkpoint", manual_audit)
        sample["arms"] = {}
        for arm in ("baseline", "obia"):
            stage = pair["arms"][arm]
            result = compact_stage(stage, folder / (arm + "-resume"), manual_audit)
            result["inclusive_usage"] = stage["inclusive_usage"]
            sample["arms"][arm] = result
        initial = creation["checkpoint"]
        final = pair["arms"]["obia"]["final_checkpoint"]
        initial_sha = initial.get("sha256", "missing")
        sample["checkpoint_audit"] = {
            "initial_valid": initial.get("exists", False) and not initial.get("problems"),
            "initial_status": initial.get("status"),
            "initial_implementation_untouched": creation["implementation_unchanged"],
            "initial_policy_untouched": creation["policy_unchanged"],
            "initial_history_untouched": creation["history_unchanged"],
            "final_valid": final.get("exists", False) and not final.get("problems"),
            "final_status": final.get("status"),
            "checkpoint_changed": initial.get("sha256") != final.get("sha256"),
            "previous_version_retained": (folder / "obia/vault/OBIA/.history/benchmark/queue" / (initial_sha + ".md")).is_file(),
        }
        for label, path in (("initial", folder / "obia/vault/OBIA/.history/benchmark/queue" / (initial_sha + ".md")),
                            ("final", folder / "obia/vault/OBIA/projects/benchmark/tasks/queue.md")):
            sample["checkpoint_audit"][label + "_note_bytes"] = path.stat().st_size if path.is_file() else None
        a, b = (sample["arms"][arm]["inclusive_usage"] for arm in ("baseline", "obia"))
        assert a == sample["arms"]["baseline"]["usage"]
        if creation["usage"] is not None and sample["arms"]["obia"]["usage"] is not None:
            assert b == usage_totals([creation["usage"], sample["arms"]["obia"]["usage"]])
        sample["net_token_reduction_percent"] = reduction(a["total_tokens"], b["total_tokens"]) if a and b else None
        report["pairs"].append(sample)
    report["by_case"] = {}
    for size in ("short", "long"):
        pairs = [pair for pair in report["pairs"] if pair["case"] == size and "arms" in pair]
        complete = [pair for pair in pairs if all(pair["arms"][arm].get("inclusive_usage") for arm in ("baseline", "obia"))]
        group = {"planned_pairs": original["repeats"], "recorded_pairs": len(pairs), "complete_metered_pairs": len(complete), "arms": {}}
        for arm in ("baseline", "obia"):
            stages = [pair["arms"][arm] for pair in complete]
            quality_stages = [pair["arms"][arm] for pair in pairs]
            totals = usage_totals([stage["inclusive_usage"] for stage in stages])
            total_list = [stage["inclusive_usage"]["total_tokens"] for stage in stages]
            group["arms"][arm] = {"usage": totals, "median_total_tokens": statistics.median(total_list) if total_list else None,
                "min_total_tokens": min(total_list) if total_list else None, "max_total_tokens": max(total_list) if total_list else None,
                "quality_evaluated": sum("functional_total" in stage.get("quality", {}) for stage in quality_stages),
                "quality_all_pass": sum(stage.get("quality", {}).get("all_quality_checks_passed", False) for stage in quality_stages),
                "protocol_deviations": sum(stage["protocol_deviation"] is True for stage in quality_stages),
                "scope_unreviewed": sum(stage["protocol_deviation"] is None for stage in quality_stages),
                "functional_passed": sum(stage.get("quality", {}).get("functional_passed", 0) for stage in quality_stages),
                "functional_total": sum(stage.get("quality", {}).get("functional_total", 0) for stage in quality_stages),
                "retention_passed": sum(stage.get("quality", {}).get("retention_passed", 0) for stage in quality_stages),
                "retention_total": sum(stage.get("quality", {}).get("retention_total", 0) for stage in quality_stages)}
        creation = usage_totals([pair["checkpoint_creation"]["usage"] for pair in complete])
        resumes = usage_totals([pair["arms"]["obia"]["usage"] for pair in complete])
        group["checkpoint_creation_usage"] = creation
        group["obia_resume_and_maintenance_usage"] = resumes
        before = group["arms"]["baseline"]["usage"]["total_tokens"]
        after = group["arms"]["obia"]["usage"]["total_tokens"]
        group["net_token_reduction_percent"] = reduction(before, after)
        group["resume_only_token_reduction_percent"] = reduction(before, resumes["total_tokens"])
        group["median_paired_net_reduction_percent"] = statistics.median([p["net_token_reduction_percent"] for p in complete]) if complete else None
        report["by_case"][size] = group
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--invalid-run-dir", type=Path)
    parser.add_argument("--probe-events", type=Path)
    parser.add_argument("--manual-audit", type=Path, help="Reviewed trace annotations keyed by case/stage; no private paths")
    args = parser.parse_args()
    manual_audit = json.loads(args.manual_audit.read_text(encoding="utf-8")) if args.manual_audit else None
    report = summarize(args.run_dir.expanduser().resolve(), manual_audit)
    setup = []
    if args.invalid_run_dir:
        for path in sorted(args.invalid_run_dir.glob("*/*/events.jsonl")):
            usages = [event["usage"] for event in read_events(path) if event.get("type") == "turn.completed"]
            setup.append({"kind": "invalid_fixture_setup", "stage": str(path.relative_to(args.invalid_run_dir).parent),
                          "usage": usage_totals(usages) if usages else None,
                          "interrupted_usage_unknown": not bool(usages)})
    if args.probe_events:
        usages = [event["usage"] for event in read_events(args.probe_events) if event.get("type") == "turn.completed"]
        setup.append({"kind": "connectivity_probe", "usage": usage_totals(usages) if usages else None})
    if setup:
        report["setup_attempts_outside_comparison"] = setup
        report["setup_known_usage_lower_bound"] = usage_totals([stage["usage"] for stage in setup if stage.get("usage")])
        report["setup_executions_without_final_usage"] = sum(stage.get("usage") is None for stage in setup)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report["by_case"], indent=2))


if __name__ == "__main__":
    main()
