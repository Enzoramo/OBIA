#!/usr/bin/env python3
"""Count OBIA text locally; emit aggregates, never note text or task identifiers.

This is a payload-size measurement, not an agent or billing benchmark.
Optional evaluation dependencies: tiktoken==0.12.0, ruamel.yaml==0.18.17.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import tiktoken

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'skills/obia/scripts'))
import obia


def measure(vault, project, tasks):
    encodings = {name: tiktoken.get_encoding(name) for name in ('o200k_base', 'cl100k_base')}

    def count(text):
        return {'characters': len(text), **{
            name: len(encoder.encode(text, disallowed_special=()))
            for name, encoder in encodings.items()
        }}

    def json_text(value):
        # Match the helper CLI serialization, including its final newline.
        return json.dumps(value, ensure_ascii=False, indent=2) + '\n'

    static = {}
    for relative in ('SKILL.md', 'references/commands.md', 'references/memory-format.md', 'references/hooks.md'):
        static[relative] = count((REPO / 'skills/obia' / relative).read_text(encoding='utf-8'))

    samples = []
    for index, task in enumerate(tasks, 1):
        item = obia.note(vault, obia.task_relative(project, task))
        content = item['content']
        payload = {key: item[key] for key in ('path', 'sha256', 'content')}
        metrics = {'note_markdown': count(content), 'read_full_json': count(json_text(payload))}
        for section, (start, _, end) in obia.sections(content).items():
            if section in ('Resume', 'Constraints', 'Facts', 'Decisions', 'Sources'):
                part = content[start:end].rstrip() + '\n'
                metrics['read_' + section.lower() + '_json'] = count(json_text({**payload, 'content': part}))
                metrics['section_' + section.lower() + '_text'] = count(part)
        packet = obia.recall(vault, project, task=task, budget=12000)
        metrics['recall_12000_json'] = count(json_text(packet))
        samples.append({
            'sample': index,
            'metrics': metrics,
            'recall_included_notes': len(packet['notes']),
            'recall_omitted_notes': packet['omitted_count'],
        })
    return {
        'schema': 1,
        'measurement': 'local_text_tokenization_not_model_usage',
        'tiktoken_version': tiktoken.__version__,
        'encodings': list(encodings),
        'scope': 'Explicit task notes, their read-only recall packets and public skill instructions. No transcripts or hooks executed.',
        'exclusions': ['model message framing', 'reasoning and output tokens', 'cache billing',
                       'checkpoint authoring', 'source verification', 'repeated context across model requests',
                       'human time', 'task quality equivalence'],
        'static_instructions': static,
        'samples': samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--task', action='append', required=True, help='Repeat for explicitly selected samples.')
    parser.add_argument('--output', type=Path, help='Write aggregate JSON, otherwise print to stdout.')
    args = parser.parse_args()
    report = measure(args.vault.expanduser().resolve(), args.project, args.task)
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        # Refuse to overwrite an existing report or any memory/configuration file.
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
