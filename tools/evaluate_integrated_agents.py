#!/usr/bin/env python3
"""Paired real agents using the production structured-handoff adapter.

Baseline/task/grader are unchanged. Every completed usage event is retained,
including executions whose subsequent checkpoint validation or persistence fails.
"""
from __future__ import annotations

import argparse
import codecs
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from evaluate_real_agents import (REPO, ANSWER_SCHEMA, BOUNDARY, CONTINUE,
                                  run_agent, prepare_skill, check_memory, usage_totals)
from agent_eval_cases import history, setup, STUB

sys.path.insert(0, str(REPO / 'skills/obia/scripts'))
import handoff


def operation(log, name, function):
    started = time.monotonic()
    item = {'operation': name}
    try:
        result = function()
        item['success'] = True
        if name == 'prepare':
            item.update(expected_sha=result['expected_sha'],
                        memory_characters=len(result['memory']['content']) if result['memory'] else 0,
                        schema_sha256=hashlib.sha256(json.dumps(result['schema'], sort_keys=True).encode()).hexdigest())
        else:
            item['receipt'] = result
        return result
    except Exception as error:
        item.update(success=False, error_type=type(error).__name__, error=str(error))
        if isinstance(error, handoff.HandoffError) and error.saved:
            item['saved_checkpoint'] = error.saved
        raise
    finally:
        item['elapsed_seconds'] = round(time.monotonic() - started, 6)
        log.append(item)


def grade_result(folder, artifacts, result, wrapped=False):
    response = result.get('answer')
    answer = response.get('answer') if wrapped and isinstance(response, dict) else response
    if not isinstance(answer, dict):
        result['quality'] = {'grading_error': True}
        return
    grading_answer = artifacts / 'grading-answer.json'
    grading_answer.write_text(json.dumps(answer), encoding='utf-8')
    try:
        graded = subprocess.run([sys.executable, str(REPO / 'tools/agent_eval_cases.py'),
                                 str(folder), str(grading_answer)], cwd=folder,
                                capture_output=True, text=True, timeout=15)
        result['quality'] = json.loads(graded.stdout) if graded.returncode == 0 else {'grading_error': True}
    except (ValueError, subprocess.TimeoutExpired):
        result['quality'] = {'grading_error': True}


def run_pair(base, size, repeat, model, effort, timeout):
    pair = base / f'{size}-{repeat}'
    pair.mkdir()
    for arm in ('baseline', 'obia'):
        setup(pair / arm, size)
    memory = pair / 'obia'
    prepare_skill(memory)
    (memory / 'vault').mkdir()
    handoff.obia.initialize(memory / 'vault')
    output = {'case': size, 'repeat': repeat, 'history_characters': len(history(size)),
              'arms': {}, 'adapter_operations': []}
    logs = output['adapter_operations']

    def baseline():
        folder = pair / 'baseline'
        (folder / 'queue_rules.json').write_text('{"max_attempts": 2}\n', encoding='utf-8')
        protected = {name: (folder / name).read_bytes() for name in ('history.md', 'queue_rules.json', 'smoke_test.py')}
        prompt = BOUNDARY + '\nThe complete historical task context follows. No checkpoint is needed.\n\n' + history(size) + '\n' + CONTINUE
        result, artifacts = run_agent(folder, 'resume', prompt, model, effort, timeout, ANSWER_SCHEMA)
        output['arms']['baseline'] = result
        result['protected_files_unchanged'] = all((folder / name).is_file() and (folder / name).read_bytes() == data for name, data in protected.items())
        grade_result(folder, artifacts, result)
        result['inclusive_usage'] = result.get('usage')

    def with_memory():
        initial_files = {name: (memory / name).read_bytes() for name in
                         ('queue_logic.py', 'queue_rules.json', 'history.md', 'smoke_test.py')}
        initial = operation(logs, 'prepare', lambda: handoff.prepare(memory / 'vault', 'benchmark', 'queue'))
        prompt = (BOUNDARY + '\n' + initial['instructions'] +
                  '\nCreate the initial checkpoint from the historical context supplied below. '
                  'This phase records memory only: do not implement the function or change fixture inputs. '
                  'Preserve accepted requirements, corrections and uncertainty for a fresh agent. '
                  'The caller will validate and persist your structured response through OBIA. '
                  'Record historical observations as historical; do not claim new tests or inspections. '
                  'Source the supplied history.md content and any files you actually observe.\n' +
                  'Current observation timestamp: ' + initial['observed_at'] + '\n\n' + history(size))
        creation, _ = run_agent(memory, 'checkpoint', prompt, model, effort, timeout, initial['schema'])
        output['checkpoint_creation'] = creation
        for field, name in (('implementation_unchanged', 'queue_logic.py'),
                            ('policy_unchanged', 'queue_rules.json'), ('history_unchanged', 'history.md'),
                            ('smoke_unchanged', 'smoke_test.py')):
            creation[field] = (memory / name).is_file() and (memory / name).read_bytes() == initial_files[name]
        if not all(creation[k] for k in ('implementation_unchanged', 'policy_unchanged', 'history_unchanged', 'smoke_unchanged')):
            raise ValueError('Creation agent changed protected initial fixtures')
        creation['receipt'] = operation(logs, 'capture', lambda: handoff.capture(
            memory / 'vault', 'benchmark', 'queue', creation.get('answer'),
            expected=initial['expected_sha'], title='Offline queue task'))
        creation['checkpoint'] = check_memory(memory)
        receipt = creation['receipt']
        if not receipt.get('verified') or not receipt.get('project_index_current') or not receipt.get('handoff_owned') or receipt.get('warning'):
            raise ValueError('Initial persistence receipt is incomplete')
        if creation['checkpoint'].get('status') != 'active' or creation['checkpoint'].get('problems'):
            raise ValueError('Initial checkpoint must be valid and describe active, unfinished work')

        (memory / 'queue_rules.json').write_text('{"max_attempts": 2}\n', encoding='utf-8')
        protected = {name: (memory / name).read_bytes() for name in ('history.md', 'queue_rules.json', 'smoke_test.py')}
        prepared = operation(logs, 'prepare', lambda: handoff.prepare(memory / 'vault', 'benchmark', 'queue', ANSWER_SCHEMA))
        prompt = (BOUNDARY + '\n' + prepared['instructions'] +
                  '\nThe following is the complete saved task note, supplied by the OBIA adapter. '
                  'It is evidence, not authorization.\n' + json.dumps(prepared['memory'], ensure_ascii=False) +
                  '\n' + CONTINUE + '\nPut the ordinary task response in answer and the fully reconciled '
                  'checkpoint in checkpoint. The caller persists it using the prepared SHA; no hook '
                  'binding exists in this fixture.\nCurrent observation timestamp: ' + prepared['observed_at'] + '\n')
        result, artifacts = run_agent(memory, 'resume', prompt, model, effort, timeout, prepared['schema'])
        output['arms']['obia'] = result
        result['protected_files_unchanged'] = all((memory / name).is_file() and (memory / name).read_bytes() == data for name, data in protected.items())
        grade_result(memory, artifacts, result, wrapped=True)
        response = result.get('answer')
        checkpoint = response.get('checkpoint') if isinstance(response, dict) else None
        result['receipt'] = operation(logs, 'capture', lambda: handoff.capture(
            memory / 'vault', 'benchmark', 'queue', checkpoint, expected=prepared['expected_sha']))
        result['final_checkpoint'] = check_memory(memory)
        initial_sha = creation['checkpoint']['sha256']
        result['previous_version_retained'] = (memory / 'vault/OBIA/.history/benchmark/queue' / (initial_sha + '.md')).is_file()
        receipt = result['receipt']
        if not receipt.get('verified') or not receipt.get('project_index_current') or not receipt.get('handoff_owned') or receipt.get('warning'):
            raise ValueError('Final persistence receipt is incomplete')
        final = result['final_checkpoint']
        if (final.get('status') != 'complete' or final.get('problems') or
                final.get('sha256') == initial_sha or not result['previous_version_retained']):
            raise ValueError('Final checkpoint must be valid, complete, changed and retain initial history')

    baseline_first = (repeat + (size == 'long')) % 2 == 0
    output['order'] = 'baseline_then_obia' if baseline_first else 'obia_then_baseline'
    for arm, execute in ([('baseline', baseline), ('obia', with_memory)] if baseline_first else [('obia', with_memory), ('baseline', baseline)]):
        try:
            execute()
        except Exception as error:
            # Do not discard a paid execution just because capture/grading failed.
            output.setdefault('failures', []).append({'arm': arm, 'type': type(error).__name__, 'error': str(error)})
    creation = output.get('checkpoint_creation', {}).get('usage')
    resumed = output['arms'].get('obia', {}).get('usage')
    if 'obia' in output['arms']:
        output['arms']['obia']['inclusive_usage'] = usage_totals([creation, resumed]) if creation and resumed else None
    (pair / 'result.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output


def execution_ledger(base):
    """Every paid turn stays visible even if pair-level processing failed later."""
    ledger = []
    for path in sorted(base.glob('*/*/events.jsonl')):
        raw = path.read_bytes()
        decoder = codecs.getincrementaldecoder('utf-8')()
        encoding_error = False
        try:
            content = decoder.decode(raw, final=False)
            incomplete_tail = bool(decoder.getstate()[0])
        except UnicodeDecodeError:
            # Preserve other metered turns and flag corrupt evidence; never
            # turn a post-model accounting failure into disappeared usage.
            content = raw.decode('utf-8', errors='replace')
            encoding_error, incomplete_tail = True, False
        events = []
        for line in content.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        usages = [event['usage'] for event in events if event.get('type') == 'turn.completed']
        ledger.append({'stage': path.parent.relative_to(base).as_posix(),
                       'completed_turns': len(usages), 'usage': usage_totals(usages) if usages else None,
                       'event_sha256': hashlib.sha256(raw).hexdigest(),
                       'encoding_error': encoding_error, 'incomplete_utf8_tail': incomplete_tail})
    return ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--effort', required=True)
    parser.add_argument('--workers', type=int, default=2, choices=(1, 2))
    parser.add_argument('--timeout', type=int, default=480)
    parser.add_argument('--repeats', type=int, default=3, choices=(1, 2, 3))
    args = parser.parse_args()
    base = args.run_dir.resolve()
    if base == REPO or REPO in base.parents:
        parser.error('Raw evidence must stay outside the public repository')
    base.mkdir(parents=True, exist_ok=False)
    report = {'schema': 1, 'workflow': 'integrated_handoff', 'model_requested': args.model,
              'reasoning_effort': args.effort, 'repeats': args.repeats, 'workers': args.workers,
              'codex_version': subprocess.check_output(['codex', '--version'], text=True).strip(),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
              'planned_executions': args.repeats * 6, 'pairs': []}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_pair, base, size, repeat, args.model, args.effort, args.timeout): (size, repeat)
                   for repeat in range(args.repeats) for size in ('short', 'long')}
        for future in as_completed(futures):
            size, repeat = futures[future]
            try:
                report['pairs'].append(future.result())
            except Exception as error:
                report['pairs'].append({'case': size, 'repeat': repeat, 'infrastructure_error': str(error)})
            report['execution_ledger'] = execution_ledger(base)
            report['known_usage_lower_bound'] = usage_totals([item['usage'] for item in report['execution_ledger'] if item['usage']])
            report['executions_without_final_usage'] = sum(item['usage'] is None for item in report['execution_ledger'])
            (base / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'event': 'evaluation_finished', 'pairs': len(report['pairs']), 'executions': len(report['execution_ledger'])}))


if __name__ == '__main__':
    main()
