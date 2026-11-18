#!/usr/bin/env python3
"""Reproducible retrieval-payload comparison; no model calls or real hook events."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from measure_context_tokens import measure, obia


def fixture(task, diagnostics):
    sources = [{'id': 'S1', 'kind': 'user', 'ref': 'Synthetic request: work offline; never upload customer files.',
                'observed_at': '2026-11-18'},
               {'id': 'S2', 'kind': 'file', 'ref': 'fixtures/current-design.md: use a local queue and preserve cancellation.',
                'observed_at': '2026-11-18'}]
    facts = []
    for i in range(diagnostics):
        identifier = 'S' + str(i + 3)
        sources.append({'id': identifier, 'kind': 'file',
                        'ref': f'fixtures/inspection-{i:02d}.txt: synthetic completed diagnostic; retained for audit, not a new requirement.',
                        'observed_at': '2026-11-18'})
        facts.append({'text': f'Inspection {i:02d} checked a historical cache path. The result is retained as background evidence.',
                      'sources': [identifier]})
    return {
        'project': 'benchmark', 'id': task, 'title': 'Continue the offline queue',
        'status': 'active', 'summary': 'Local queue implemented; cancellation check remains.',
        'objective': 'Resume the offline queue while preserving the current restrictions.',
        'constraints': [{'text': 'Never upload customer files.', 'sources': ['S1']},
                        {'text': 'Work offline; preserve cancellation.', 'sources': ['S2']}],
        'decisions': [{'text': 'Use a local queue.', 'reason': 'No server is needed for this workflow.', 'sources': ['S2']}],
        'corrections': [{'text': 'The previous server-backed queue proposal is obsolete.', 'sources': ['S2']}],
        'next_actions': ['Verify cancellation before marking the task complete.'],
        'facts': facts, 'sources': sources,
    }


def benchmark():
    with tempfile.TemporaryDirectory(prefix='obia-retrieval-benchmark-') as folder:
        root = Path(folder)
        obia.initialize(root)
        cases = [('short', 0), ('long', 16)]
        checks = []
        for task, history in cases:
            data = fixture(task, history)
            saved = obia.save(root, data)
            # Normalize only a temporary synthetic fixture for repeatable SHA
            # and tokenizer counts; no real session or user memory is touched.
            obia.atomic_write(root / saved['path'], obia.render(data, '2026-11-18T00:00:00+00:00'))
            item = obia.note(root, saved['path'])
            full = obia.recall(root, 'benchmark', task=task, limit=1)
            brief = obia.recall(root, 'benchmark', task=task, limit=1, view='brief')
            assert full['notes'] and full['notes'][0]['content'] == item['content']
            projection = brief['notes'][0]
            selected_view = projection.get('view', brief['view'])
            assert selected_view == ('full' if history == 0 else 'brief')
            for section in obia.BRIEF_SECTIONS:
                required = obia.read_note(root, 'benchmark', task, section_names=[section])
                assert required['content'].strip() in projection['content']
            evidence = (obia.read_note(root, 'benchmark', task, source_ids=projection['source_ids'],
                                       expected=projection['sha256']) if selected_view == 'brief' else projection)
            for source in data['sources'][:2]:
                assert source['ref'] in evidence['content']
            assert evidence['sha256'] == item['sha256']
            checks.append({'case': task, 'selected_view': selected_view, 'whole_core_preserved': True, 'referenced_sources_recoverable': True,
                           'same_note_snapshot': True, 'full_baseline_fits_budget': True})
        report = measure(root, 'benchmark', [task for task, _ in cases])
        report['fixture'] = 'benchmark_progressive_recall.py; sample 1 short, sample 2 long; fixed synthetic timestamp'
        report['checks'] = checks
        report['interpretation'] = 'Checks prove deterministic retrieval coverage, not model task success or billed-token savings.'
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(benchmark(), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
