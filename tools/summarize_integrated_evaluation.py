#!/usr/bin/env python3
"""Export all integrated-handoff costs and quality, including failed paid stages."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics

from evaluate_integrated_agents import execution_ledger
from evaluate_real_agents import usage_totals
from summarize_agent_evaluation import compact_stage, reduction

PHASES = ('baseline-resume', 'obia-checkpoint', 'obia-resume')


def valid_receipt(value):
    return all(value.get(key) is True for key in ('verified', 'project_index_current', 'handoff_owned')) and not value.get('warning')


def summarize(root, manual):
    original = json.loads((root / 'report.json').read_text(encoding='utf-8'))
    ledger = execution_ledger(root)
    if ledger != original['execution_ledger']:
        raise ValueError('Raw usage changed or run is still active; reconcile before exporting')
    keyed = {entry['stage']: entry for entry in ledger}
    planned = {f'{size}-{repeat}/{phase}' for repeat in range(original['repeats'])
               for size in ('short', 'long') for phase in PHASES}
    complete_metering = (set(keyed) == planned and all(entry['usage'] is not None and
        not entry['encoding_error'] and not entry['incomplete_utf8_tail'] for entry in ledger))
    report = {key: original[key] for key in ('schema', 'workflow', 'model_requested', 'reasoning_effort',
                                            'codex_version', 'source_commit', 'repeats', 'workers', 'planned_executions')}
    report.update(measurement='actual_codex_turn_completed_usage',
                  scope='Six fresh paired scenarios; full initial model generation, injected context/schema and final checkpoint maintenance included.',
                  exclusions=['parent orchestration and review agents', 'earlier common work', 'monetary billing', 'human hours'],
                  execution_ledger=ledger, complete_metering=complete_metering,
                  known_usage_lower_bound=usage_totals([entry['usage'] for entry in ledger if entry['usage']]),
                  executions_without_final_usage=sum(entry['usage'] is None for entry in ledger),
                  missing_planned_stages=sorted(planned - set(keyed)), unexpected_stages=sorted(set(keyed) - planned), pairs=[])
    pairs = {(p['case'], p['repeat']): p for p in original['pairs']}
    for size in ('short', 'long'):
        for repeat in range(original['repeats']):
            name = f'{size}-{repeat}'
            pair = pairs.get((size, repeat), {})
            stages = {}
            for phase in PHASES:
                key = name + '/' + phase
                if key not in keyed:
                    stages[phase] = {'not_recorded': True}
                    continue
                path = root / key
                saved = (pair.get('checkpoint_creation') if phase == 'obia-checkpoint' else
                         pair.get('arms', {}).get(phase.split('-')[0]))
                if saved is None:
                    saved = json.loads((path / 'metrics.json').read_text(encoding='utf-8')) if (path / 'metrics.json').is_file() else keyed[key]
                if keyed[key]['encoding_error'] or keyed[key]['incomplete_utf8_tail']:
                    # Damaged/incomplete traces cannot pass quality gates, but
                    # their known paid usage must remain in the exported ledger.
                    stages[phase] = {**keyed[key], 'trace_unreadable': True}
                else:
                    stages[phase] = compact_stage(saved, path, manual)
            initial = pair.get('checkpoint_creation', {})
            resumed = pair.get('arms', {}).get('obia', {})
            initial_note, final_note = initial.get('checkpoint', {}), resumed.get('final_checkpoint', {})
            old_sha = initial_note.get('sha256', 'missing')
            previous = root / name / 'obia/vault/OBIA/.history/benchmark/queue' / (old_sha + '.md')
            current = root / name / 'obia/vault/OBIA/projects/benchmark/tasks/queue.md'
            owner = root / name / 'obia/vault/OBIA/.handoff/benchmark/queue.json'
            try:
                ownership = json.loads(owner.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                ownership = None
            note_audit = {
                'initial_valid': bool(initial_note.get('exists')) and not initial_note.get('problems'),
                'initial_active': initial_note.get('status') == 'active',
                'initial_fixtures_unchanged': all(initial.get(k) is True for k in
                    ('implementation_unchanged', 'policy_unchanged', 'history_unchanged', 'smoke_unchanged')),
                'initial_receipt_valid': valid_receipt(initial.get('receipt', {})),
                'final_valid': bool(final_note.get('exists')) and not final_note.get('problems'),
                'final_complete': final_note.get('status') == 'complete',
                'final_receipt_valid': valid_receipt(resumed.get('receipt', {})),
                'checkpoint_changed': bool(final_note.get('sha256')) and final_note.get('sha256') != old_sha,
                'previous_version_retained': previous.is_file(),
                'previous_bytes_match_receipt': previous.is_file() and hashlib.sha256(previous.read_bytes()).hexdigest() == old_sha == initial.get('receipt', {}).get('sha256'),
                'current_bytes_match_receipt': current.is_file() and hashlib.sha256(current.read_bytes()).hexdigest() == final_note.get('sha256') == resumed.get('receipt', {}).get('sha256'),
                'current_ownership_matches': ownership == {'version': 1, 'sha256': final_note.get('sha256')} and bool(final_note.get('sha256')),
            }
            note_audit['initial_note_bytes'] = previous.stat().st_size if previous.is_file() else None
            note_audit['final_note_bytes'] = current.stat().st_size if current.is_file() else None
            storage_ok = all(note_audit[k] is True for k in note_audit if not k.endswith('_bytes'))
            quality_ok = all(stages[phase].get('quality', {}).get('all_quality_checks_passed') is True
                             and stages[phase].get('protected_files_unchanged') is True
                             for phase in ('baseline-resume', 'obia-resume'))
            audit_ok = all((stages[phase].get('manual_review') or {}).get('scope') == 'pass' and
                           (stages[phase].get('manual_review') or {}).get('test_claims') in
                               ('consistent_with_observed_execution', 'not_applicable') and
                           (phase == 'baseline-resume' or (stages[phase].get('manual_review') or {}).get('memory_quality') == 'pass')
                           for phase in PHASES)
            execution_ok = all(stages[phase].get('exit_code') == 0 and not stages[phase].get('timed_out') and
                               stages[phase].get('usage') is not None for phase in PHASES)
            usage = {}
            for arm, phases in (('baseline', ['baseline-resume']), ('obia', ['obia-checkpoint', 'obia-resume'])):
                values = [keyed.get(name + '/' + phase, {}).get('usage') for phase in phases]
                usage[arm] = usage_totals(values) if all(value is not None for value in values) else None
            a, b = usage['baseline'], usage['obia']
            report['pairs'].append({'case': size, 'repeat': repeat, 'order': pair.get('order'),
                'history_characters': pair.get('history_characters'), 'stages': stages,
                'inclusive_usage': usage, 'checkpoint_audit': note_audit,
                'failures': [{'arm': error.get('arm'), 'type': error.get('type')} for error in pair.get('failures', [])],
                'infrastructure_error': 'infrastructure_error' in pair or not bool(pair),
                'storage_pass': storage_ok, 'task_quality_pass': quality_ok, 'manual_audit_pass': audit_ok,
                'execution_pass': execution_ok,
                'adapter_operations': [{k: op[k] for k in ('operation', 'elapsed_seconds', 'success', 'error_type') if k in op}
                                       for op in pair.get('adapter_operations', [])],
                'net_token_reduction_percent': reduction(a['total_tokens'], b['total_tokens']) if a and b else None})
    report['by_case'] = {}
    for size in ('short', 'long'):
        group = [p for p in report['pairs'] if p['case'] == size]
        totals = {}
        for arm, phases in (('baseline', ['baseline-resume']), ('obia', ['obia-checkpoint', 'obia-resume'])):
            values = [entry['usage'] for entry in ledger if entry['stage'].startswith(size + '-') and
                      entry['stage'].split('/')[1] in phases and entry['usage'] is not None]
            totals[arm] = usage_totals(values)
        a, b = totals['baseline']['total_tokens'], totals['obia']['total_tokens']
        deltas = [p['net_token_reduction_percent'] for p in group if p['net_token_reduction_percent'] is not None]
        report['by_case'][size] = {'planned_pairs': original['repeats'], 'usage_known': totals,
            'net_token_reduction_percent': reduction(a, b) if complete_metering else None,
            'median_paired_reduction_percent': statistics.median(deltas) if len(deltas) == len(group) else None,
            'all_quality_and_storage_pass': all(p['storage_pass'] and p['task_quality_pass'] and p['manual_audit_pass'] for p in group)}
    totals = {arm: usage_totals([group['usage_known'][arm] for group in report['by_case'].values()])
              for arm in ('baseline', 'obia')}
    a, b = totals['baseline']['total_tokens'], totals['obia']['total_tokens']
    report['aggregate'] = {'usage_known': totals,
        'net_token_reduction_percent': reduction(a, b) if complete_metering else None,
        'quality_and_persistence_pass': all(p['storage_pass'] and p['task_quality_pass'] and
            p['manual_audit_pass'] and p['execution_pass'] and not p['failures'] and not p['infrastructure_error'] for p in report['pairs'])}
    report['primary_success'] = (complete_metering and b < a and report['aggregate']['quality_and_persistence_pass'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--manual-audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.run_dir.resolve(), json.loads(args.manual_audit.read_text(encoding='utf-8')))
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'primary_success': report['primary_success'], 'aggregate': report['aggregate'],
                      'complete_metering': report['complete_metering']}, indent=2))


if __name__ == '__main__':
    main()
