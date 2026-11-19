#!/usr/bin/env python3
"""Export plaintext task/tool history from one explicitly authorized test trace.

Never exports bootstrap messages, reasoning or opaque encrypted content. This is
evaluation tooling, not the OBIA production helper or an automatic chat reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def export(raw, session):
    events = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    identities = [e['payload'].get('id') for e in events if e.get('type') == 'session_meta']
    if identities != [session]:
        raise ValueError('Session identity mismatch or ambiguity')
    excluded = {'encrypted_blocks': 0, 'encrypted_characters': 0}

    def plaintext(value):
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
            raise ValueError('Unsupported content shape')
        result = []
        for block in value:
            kind = block.get('type') if isinstance(block, dict) else None
            if kind == 'encrypted_content':
                excluded['encrypted_blocks'] += 1
                excluded['encrypted_characters'] += sum(len(v) for k, v in block.items() if k != 'type' and isinstance(v, str))
            elif kind in ('input_text', 'output_text', 'text') and isinstance(block.get('text'), str):
                result.append({'type': kind, 'text': block['text']})
            else:
                raise ValueError('Unsupported non-text content; do not silently truncate it')
        return result

    items = []
    for event in events:
        if event.get('type') != 'response_item':
            continue
        p = event.get('payload', {}); kind = p.get('type')
        if kind == 'message' and p.get('role') == 'assistant' and p.get('phase') in (None, 'commentary', 'final_answer', 'final'):
            items.append({'type': kind, 'role': 'assistant', 'phase': p.get('phase'), 'content': plaintext(p.get('content'))})
        elif kind == 'agent_message':
            items.append({'type': kind, 'content': plaintext(p.get('content'))})
        elif kind in ('function_call', 'custom_tool_call'):
            items.append({k: p[k] for k in ('type', 'call_id', 'name', 'arguments', 'input') if k in p})
        elif kind in ('function_call_output', 'custom_tool_call_output'):
            items.append({'type': kind, 'call_id': p.get('call_id'), 'output': plaintext(p.get('output'))})
    return {'notice': 'Plaintext task/tool evidence from this authorized test only. Historical phase restrictions are superseded by the current request. Bootstrap, reasoning and opaque delegation blocks excluded; technical requests remain in observed request-file outputs.',
            'source_session': session, 'source_trace_sha256': hashlib.sha256(raw).hexdigest(),
            'excluded': excluded, 'items': items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.trace.read_bytes(), args.session)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'items': len(result['items']), 'excluded': result['excluded']}))


if __name__ == '__main__':
    main()
