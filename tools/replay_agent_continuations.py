#!/usr/bin/env python3
"""Replay all six observed initial checkpoints with fresh continuation agents.

Creation and baseline events are reused, explicitly labeled, never re-metered.
Only new OBIA continuation usage is added to the experiment's unique-run ledger.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys

from agent_eval_cases import setup
from evaluate_real_agents import (REPO, ANSWER_SCHEMA, obia, prepare_skill,
                                  run_agent, check_memory, usage_totals)


def replay_pair(source, base, original, model, effort, timeout):
    name = f"{original['case']}-{original['repeat']}"
    previous, pair = source / name, base / name
    pair.mkdir()
    folder = pair / 'obia'
    setup(folder, original['case'])
    prepare_skill(folder)
    (folder / 'vault').mkdir()
    obia.initialize(folder / 'vault')
    initial_sha = original['checkpoint_creation']['checkpoint']['sha256']
    snapshot = previous / 'obia/vault/OBIA/.history/benchmark/queue' / (initial_sha + '.md')
    content = snapshot.read_bytes().decode('utf-8')
    if obia.digest(content) != initial_sha:
        raise ValueError('Original checkpoint snapshot digest differs')
    # This is a fixture restore of an actual saved note, not a new model checkpoint.
    with obia.locked(folder / 'vault'):
        obia.atomic_write(folder / 'vault' / obia.task_relative('benchmark', 'queue'), content)
        obia.rebuild(folder / 'vault')
    initial = check_memory(folder)
    if initial.get('sha256') != initial_sha or initial.get('status') != 'active' or initial.get('problems'):
        raise ValueError('Restored checkpoint does not match the observed initial state')
    (folder / 'queue_rules.json').write_text('{"max_attempts": 2}\n', encoding='utf-8')
    protected = {name: (folder / name).read_bytes() for name in ('queue_rules.json', 'history.md', 'smoke_test.py')}
    prompt = (previous / 'obia-resume/prompt.txt').read_text(encoding='utf-8')
    result, artifacts = run_agent(folder, 'resume', prompt, model, effort, timeout, ANSWER_SCHEMA)
    result['protected_files_unchanged'] = all((folder / name).is_file() and
        (folder / name).read_bytes() == data for name, data in protected.items())
    if result.get('answer') is not None:
        try:
            grade = subprocess.run([sys.executable, str(REPO / 'tools/agent_eval_cases.py'),
                                    str(folder), str(artifacts / 'answer.json')],
                                   cwd=folder, capture_output=True, text=True, timeout=15)
            result['quality'] = json.loads(grade.stdout) if grade.returncode == 0 else {'grading_error': True}
        except (ValueError, subprocess.TimeoutExpired):
            result['quality'] = {'grading_error': True}
    result['final_checkpoint'] = check_memory(folder)
    # Add reused evidence only after the new agent exits: no prior solution or
    # answer is placed beside its workspace during the continuation.
    for name in ('baseline', 'baseline-resume', 'obia-checkpoint'):
        shutil.copytree(previous / name, pair / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    creation = original['checkpoint_creation']['usage']
    result['inclusive_usage'] = usage_totals([creation, result['usage']]) if creation and result.get('usage') else None
    output = copy.deepcopy(original)
    output['order'] = 'replay_obia_only'
    output['reused_stages'] = ['baseline-resume', 'obia-checkpoint']
    output['arms']['obia'] = result
    (pair / 'result.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2, choices=(1, 2))
    parser.add_argument('--timeout', type=int, default=480)
    args = parser.parse_args()
    source, base = args.source_run.resolve(), args.run_dir.resolve()
    original = json.loads((source / 'report.json').read_text(encoding='utf-8'))
    if base == REPO or REPO in base.parents or base == source or source in base.parents:
        parser.error('Replay output must be a new private directory outside source/repository')
    if len(original['pairs']) != 6 or any('infrastructure_error' in p for p in original['pairs']):
        parser.error('This protocol replays all six completed pairs, never an outcome-selected subset')
    base.mkdir(parents=True, exist_ok=False)
    report = {key: original[key] for key in ('schema', 'model_requested', 'reasoning_effort', 'repeats')}
    report.update(workflow='reconciled_replay', workers=args.workers, pairs=[],
                  codex_version=subprocess.check_output(['codex', '--version'], text=True).strip(),
                  source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                  reused_source_commit=original['source_commit'], planned_agent_executions=6,
                  new_agent_executions=0, completed_agent_turns=0, reused_agent_executions=0,
                  scope='Six new continuations of the same real initial notes; creation/baseline events reused, not independent new pairs.')
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(replay_pair, source, base, p, report['model_requested'],
                               report['reasoning_effort'], args.timeout): p
                   for p in sorted(original['pairs'], key=lambda p: (p['repeat'], p['case']))}
        for future in as_completed(futures):
            previous = futures[future]
            try:
                report['pairs'].append(future.result())
            except Exception as error:
                report['pairs'].append({'case': previous['case'], 'repeat': previous['repeat'],
                                       'infrastructure_error': type(error).__name__ + ': ' + str(error)})
            metrics = [json.loads(path.read_text(encoding='utf-8'))
                       for path in base.glob('*/obia-resume/metrics.json')]
            report['new_agent_executions'] = len(metrics)
            report['completed_agent_turns'] = sum(item['completed_turns'] for item in metrics)
            report['reused_agent_executions'] = 2 * sum('arms' in pair for pair in report['pairs'])
            (base / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'event': 'replay_finished', 'new_executions': report['new_agent_executions'], 'pairs': len(report['pairs'])}))


if __name__ == '__main__':
    main()
