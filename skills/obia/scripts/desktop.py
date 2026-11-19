#!/usr/bin/env python3
"""Synchronous OBIA checkpoints for the existing Codex desktop shell tool.

No model call, transcript access, hook event, configuration or trust change.
Storage and acknowledgement remain distinct receipts, returned in one tool call.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import obia
import hooks


class DesktopError(obia.ObiaError):
    def __init__(self, message, saved=None):
        super().__init__(message)
        self.saved = saved


def recover(config, session, cwd, task, known_sha=None):
    result = hooks.bind(config, 'codex', session, cwd, task, known_sha)
    memory = result.get('memory')
    if memory and memory.get('status') != 'unchanged':
        # bind performs project routing and explicit session ownership. Bundle
        # source definitions in the one model-visible recovery response.
        result['memory'] = obia.recall(Path(result['vault']), result['project'],
                                     task=task, view='brief', with_sources=True)
    return result


def bound_entry(config, session, cwd, task):
    obia.slug(task)
    path = hooks.session_file(config, 'codex', session)
    with hooks.state_lock(path):
        state = hooks.load_state(path)
        if state.get('task') != task:
            raise DesktopError('Explicitly recover/bind this session to the requested task first.')
        return hooks.entry_for(config, cwd, state)


def acknowledge(config, session, cwd, task, sha, saved=None):
    try:
        bound_entry(config, session, cwd, task)
        ack = hooks.acknowledge(config, 'codex', session, cwd, sha)
        if ack['task'] != task:
            raise DesktopError('Session binding changed during acknowledgement.')
    except (obia.ObiaError, OSError, ValueError, TypeError, KeyError) as error:
        raise DesktopError('Checkpoint acknowledgement failed; reconcile before retrying: ' + str(error), saved) from error
    return {'ack': ack, 'ack_scope': 'last_observed_host_turn',
            'turn_identity_observed': ack.get('turn_id') is not None,
            'current_turn_validated_by': 'the next real lifecycle event'}


def checkpoint(config, session, cwd, task, value, expected=None):
    entry = bound_entry(config, session, cwd, task)
    root = Path(entry['vault'])
    if expected is None:
        if not isinstance(value, dict):
            raise DesktopError('Creation requires an OBIA task object.')
        for key, actual in (('project', entry['project']), ('id', task)):
            if key in value and value[key] != actual:
                raise DesktopError('Checkpoint identity differs from the bound task.')
        data = {'title': task.replace('-', ' '), **value,
                'project': entry['project'], 'id': task}
        saved = obia.save(root, data)
    else:
        # Existing notes always use partial patches; never implicitly adopt
        # ownership or replace human/legacy sections with generated content.
        saved = obia.patch(root, entry['project'], task, value, expected)
    if not saved.get('verified') or not saved.get('project_index_current') or saved.get('warning'):
        raise DesktopError('Storage receipt needs investigation; acknowledgement was not attempted.', saved)
    acknowledged = acknowledge(config, session, cwd, task, saved['sha256'], saved)
    return {'checkpoint': saved, **acknowledged}


def verify(config, session, cwd, task, expected):
    entry = bound_entry(config, session, cwd, task)
    read = obia.read_note(Path(entry['vault']), entry['project'], task,
                          expected=expected, known_sha=expected)
    return {'checkpoint': read, **acknowledge(config, session, cwd, task, read['sha256'])}


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', newline='\n')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-dir', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('recover', 'checkpoint', 'verify'):
        command = commands.add_parser(name)
        for key in ('session', 'path', 'task'):
            command.add_argument('--' + key, required=True)
        if name == 'recover':
            command.add_argument('--known-sha')
        elif name == 'checkpoint':
            command.add_argument('--input', required=True)
            command.add_argument('--expect-sha')
        else:
            command.add_argument('--sha', required=True)
    args = parser.parse_args(argv)
    try:
        config = Path(args.config_dir).expanduser().resolve()
        if args.command == 'recover':
            result = recover(config, args.session, args.path, args.task, args.known_sha)
        elif args.command == 'verify':
            result = verify(config, args.session, args.path, args.task, args.sha)
        else:
            raw = sys.stdin.read(obia.MAX_BYTES + 1) if args.input == '-' else obia.read_text(Path(args.input))
            if len(raw.encode('utf-8')) > obia.MAX_BYTES:
                raise DesktopError('Input is too large.')
            result = checkpoint(config, args.session, args.path, args.task,
                                json.loads(raw), args.expect_sha)
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
        return 0
    except (obia.ObiaError, OSError, ValueError, TypeError, KeyError) as error:
        failure = {'error': str(error)}
        if isinstance(error, DesktopError) and error.saved:
            failure['saved_checkpoint'] = error.saved
            failure['acknowledged'] = False
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
