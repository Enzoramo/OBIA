#!/usr/bin/env python3
"""Read usage metadata from one explicitly supplied Codex rollout snapshot.

No discovery, model calls, transcript export or hook execution. Usage is
cumulative: repeated snapshots are never added. A damaged or unfinished run
retains its largest valid observed snapshot as a conservative lower bound.
Completed means the snapshot has consistent usage and turn-terminal evidence;
it does not establish task quality, billing, checkpoint persistence or hooks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


COUNTERS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
            'output_tokens', 'reasoning_output_tokens', 'total_tokens')
MODEL_EVENTS = frozenset(('agent_message', 'agent_reasoning',
                          'agent_reasoning_raw_content'))


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON property')
        result[key] = value
    return result


def invalid_constant(_):
    raise ValueError('Non-JSON numeric constant')


def metadata_text(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and not any(ord(c) < 32 for c in value)


def usage_problem(value):
    if not isinstance(value, dict):
        return 'missing_usage', []
    missing = [key for key in COUNTERS if key not in value]
    if missing:
        return 'missing_usage_fields', missing
    invalid = [key for key in COUNTERS if type(value[key]) is not int or value[key] < 0]
    if invalid:
        return 'invalid_usage_fields', invalid
    if value['total_tokens'] != value['input_tokens'] + value['output_tokens']:
        return 'inconsistent_usage_total', ['total_tokens']
    invalid = [key for key in ('cached_input_tokens', 'cache_write_input_tokens')
               if value[key] > value['input_tokens']]
    if value['reasoning_output_tokens'] > value['output_tokens']:
        invalid.append('reasoning_output_tokens')
    if invalid:
        return 'invalid_usage_subsets', invalid
    return None, []


def summarize_bytes(raw, session):
    """Analyze one immutable byte snapshot; only allowlisted metadata is returned."""
    if not metadata_text(session):
        raise ValueError('A nonempty session ID is required')
    errors, metadata, sessions, turns = [], {}, [], {}
    active = set()
    last = lower = None
    snapshot_count = 0
    last_work = {}
    last_valid_line = {}

    def error(code, line=None, fields=None):
        item = {'code': code}
        if line is not None:
            item['line'] = line
        if fields:
            item['fields'] = fields
        errors.append(item)

    def collect(key, value, line):
        if value is None:
            return
        if not metadata_text(value):
            error('invalid_metadata', line, [key])
        elif value not in metadata.setdefault(key, []):
            metadata[key].append(value)

    rows = raw.splitlines(keepends=True)
    for line_number, row in enumerate(rows, 1):
        try:
            text = row.decode('utf-8')
        except UnicodeDecodeError as exc:
            tail = line_number == len(rows) and exc.end == len(row) and exc.reason == 'unexpected end of data'
            error('incomplete_utf8_tail' if tail else 'invalid_utf8', line_number)
            continue
        if not text.strip():
            continue
        try:
            event = json.loads(text, object_pairs_hook=strict_object, parse_constant=invalid_constant)
        except (ValueError, RecursionError):
            tail = line_number == len(rows) and not row.endswith((b'\n', b'\r'))
            error('incomplete_or_invalid_json_tail' if tail else 'invalid_json', line_number)
            continue
        if not isinstance(event, dict):
            error('invalid_event', line_number)
            continue
        kind, payload = event.get('type'), event.get('payload')
        if kind not in ('session_meta', 'turn_context', 'event_msg', 'response_item'):
            continue
        if not isinstance(payload, dict):
            error('invalid_event_payload', line_number)
            continue
        if kind == 'session_meta':
            sessions.append(payload.get('id'))
            for field in ('originator', 'model_provider', 'cli_version'):
                collect(field, payload.get(field), line_number)
            # Source may contain parent paths, names or arbitrary nested data;
            # export only its coarse kind, never its original object.
            source = payload.get('source')
            if isinstance(source, str):
                collect('source', source, line_number)
            elif isinstance(source, dict):
                for name in ('subagent', 'cli', 'vscode', 'exec', 'appServer'):
                    if name in source:
                        collect('source', name, line_number)
            for target, field in (('model', 'model'), ('effort', 'effort'), ('effort', 'reasoning_effort')):
                collect(target, payload.get(field), line_number)
            continue
        if kind == 'turn_context':
            for target, field in (('model', 'model'), ('effort', 'effort'), ('effort', 'reasoning_effort')):
                collect(target, payload.get(field), line_number)
            continue
        if kind == 'response_item':
            # Looking only at the item's existence is enough to refuse a stale
            # counter followed by more model work. Never return its content.
            for turn in active:
                last_work[turn] = line_number
            if turns and not active:
                error('model_activity_after_terminal', line_number)
            continue
        subtype = payload.get('type')
        if subtype in MODEL_EVENTS:
            for turn in active:
                last_work[turn] = line_number
            if turns and not active:
                error('model_activity_after_terminal', line_number)
        elif subtype == 'error':
            error('execution_error', line_number)
        elif subtype == 'task_started':
            turn = payload.get('turn_id')
            if not metadata_text(turn):
                error('missing_or_invalid_turn_id', line_number)
            elif turn in turns:
                error('duplicate_turn_start', line_number)
            else:
                turns[turn] = {'turn_id': turn, 'started_line': line_number,
                               'terminal': None, 'terminal_line': None,
                               'terminal_usage_observed': False}
                active.add(turn)
                last_work[turn] = line_number
        elif subtype in ('task_complete', 'turn_aborted'):
            turn = payload.get('turn_id')
            if not metadata_text(turn):
                error('missing_or_invalid_turn_id', line_number)
            elif turn not in turns:
                error('terminal_without_start', line_number)
            elif turn not in active:
                error('duplicate_turn_terminal', line_number)
            else:
                record = turns[turn]
                record.update(terminal=subtype, terminal_line=line_number,
                              terminal_usage_observed=last_valid_line.get(turn, -1) > last_work[turn])
                active.remove(turn)
                if not record['terminal_usage_observed']:
                    error('missing_terminal_usage', line_number)
        elif subtype == 'token_count':
            info = payload.get('info')
            value = info.get('total_token_usage') if isinstance(info, dict) else None
            problem, fields = usage_problem(value)
            if problem:
                error(problem, line_number, fields)
                continue
            current = {key: value[key] for key in COUNTERS}
            current['uncached_input_tokens'] = current['input_tokens'] - current['cached_input_tokens']
            snapshot_count += 1
            if last:
                decreasing = [key for key in COUNTERS if current[key] < last[key]]
                if decreasing:
                    error('decreasing_usage_counters', line_number, decreasing)
            last = current
            if lower is None or current['total_tokens'] > lower['total_tokens']:
                lower = current
            if len(active) == 1:
                turn = next(iter(active))
                last_valid_line[turn] = line_number
            elif len(active) > 1:
                error('ambiguous_usage_turn', line_number)
            else:
                error('usage_outside_started_turn', line_number)

    identity_ok = len(sessions) == 1 and sessions[0] == session
    if not sessions:
        error('missing_session_metadata')
    elif len(sessions) != 1:
        error('multiple_session_metadata')
    elif sessions[0] != session:
        error('session_identity_mismatch')
    if not turns:
        error('missing_turn_start')
    if active:
        error('missing_terminal_evidence')
    if last is None:
        error('no_valid_usage')
    aborted = any(turn['terminal'] == 'turn_aborted' for turn in turns.values())
    if aborted:
        error('turn_aborted')
    complete = identity_ok and bool(turns) and not errors and all(
        turn['terminal'] == 'task_complete' and turn['terminal_usage_observed'] for turn in turns.values())
    structural_errors = [e for e in errors if e['code'] not in
                         ('missing_terminal_evidence', 'missing_terminal_usage', 'no_valid_usage', 'turn_aborted')]
    status = 'completed' if complete else ('invalid' if structural_errors else 'aborted' if aborted else 'incomplete')
    # A different or ambiguous session must never have its costs attributed to
    # the requested ID, even when the supplied file contains valid counters.
    return {'schema': 1, 'measurement': 'codex_rollout_cumulative_token_usage',
            'session_id': session, 'session_verified': identity_ok,
            'trace_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
            'status': status, 'complete_metering': complete,
            'metadata': metadata if identity_ok else {},
            'last_cumulative_usage': last if identity_ok else None,
            'known_usage_lower_bound': lower if identity_ok else None,
            'usage_snapshots': snapshot_count if identity_ok else None,
            'turns': list(turns.values()) if identity_ok else [], 'errors': errors}


def read_usage(trace, session):
    """Read exactly this path once; hashing and parsing share the same bytes."""
    return summarize_bytes(Path(trace).expanduser().read_bytes(), session)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--session', required=True)
    args = parser.parse_args(argv)
    try:
        result = read_usage(args.trace, args.session)
    except (OSError, ValueError):
        # Avoid exception text: filesystem paths and JSON snippets are private.
        result = {'schema': 1, 'status': 'unavailable', 'complete_metering': False,
                  'last_cumulative_usage': None, 'known_usage_lower_bound': None,
                  'errors': [{'code': 'trace_unavailable_or_invalid_session'}]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['complete_metering'] else 2


if __name__ == '__main__':
    sys.exit(main())
