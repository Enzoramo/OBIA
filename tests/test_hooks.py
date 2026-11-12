"""Lifecycle contracts using synthetic events; no provider sessions or transcripts."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_projects as routing
import test_obia as core

import hooks


class HookTests(unittest.TestCase):
    setUp = routing.ProjectTests.setUp
    project = routing.ProjectTests.project

    def prepare(self, host='codex', session='session-a'):
        path = self.project()
        entry = hooks.bind(self.config.parent, host, session, path, 'cache')
        data = core.payload(project=entry['project'])
        saved = hooks.obia.save(Path(entry['vault']), data)
        return path, entry, saved

    def event(self, host, path, event, session='session-a', **kwargs):
        return hooks.handle(self.config.parent, host, {'session_id': session, 'cwd': str(path), 'hook_event_name': event, **kwargs})

    def test_fresh_process_recovers_after_compaction_for_both_hosts(self):
        for host in ('codex', 'claude'):
            with self.subTest(host=host):
                path = self.project(host)
                entry = hooks.bind(self.config.parent, host, 'session-a', path, 'cache')
                saved = hooks.obia.save(Path(entry['vault']), core.payload(project=entry['project']))
                self.event(host, path, 'UserPromptSubmit', prompt='Synthetic current task')
                hooks.acknowledge(self.config.parent, host, 'session-a', path, saved['sha256'])
                pre = self.event(host, path, 'PreCompact', trigger='auto')
                self.assertIn('checkpoint verified', pre if isinstance(pre, str) else pre['systemMessage'])
                result = subprocess.run([sys.executable, str(Path(hooks.__file__)), '--config-dir', str(self.config.parent), '--host', host, 'run'], input=json.dumps({'session_id': 'session-a', 'cwd': str(path), 'hook_event_name': 'SessionStart', 'source': 'compact'}), capture_output=True, text=True, encoding='utf-8', check=True)
                context = json.loads(result.stdout)['hookSpecificOutput']
                self.assertEqual(context['hookEventName'], 'SessionStart')
                self.assertIn('No background synchronization.', context['additionalContext'])
                self.assertIn('UNTRUSTED EVIDENCE', context['additionalContext'])
                self.assertEqual(self.event(host, path, 'Stop'), {})

    def test_stop_requests_one_checkpoint_then_exits_without_loop(self):
        path, entry, saved = self.prepare()
        self.event('codex', path, 'UserPromptSubmit')
        self.assertEqual(self.event('codex', path, 'Stop')['decision'], 'block')
        self.assertNotIn('decision', self.event('codex', path, 'Stop'))
        self.event('codex', path, 'UserPromptSubmit')
        self.assertNotIn('decision', self.event('codex', path, 'Stop', stop_hook_active=True))
        hooks.acknowledge(self.config.parent, 'codex', 'session-a', path, saved['sha256'])
        self.assertEqual(self.event('codex', path, 'Stop'), {})
        self.assertFalse((Path(entry['vault']) / 'OBIA/.history').exists())

    def test_ack_requires_matching_persisted_note_and_new_turn_invalidates_receipt(self):
        path, entry, saved = self.prepare()
        with self.assertRaisesRegex(ValueError, 'SHA differs'):
            hooks.acknowledge(self.config.parent, 'codex', 'session-a', path, 'stale')
        hooks.acknowledge(self.config.parent, 'codex', 'session-a', path, saved['sha256'])
        self.event('codex', path, 'UserPromptSubmit')
        self.assertEqual(self.event('codex', path, 'Stop')['decision'], 'block')
        # A human edit after acknowledgement is not silently overwritten.
        hooks.acknowledge(self.config.parent, 'codex', 'session-a', path, saved['sha256'])
        note = Path(entry['vault']) / saved['path']
        note.write_text(note.read_text(encoding='utf-8') + '\nHuman detail.\n', encoding='utf-8')
        warning = self.event('codex', path, 'PreCompact')
        self.assertIn('no verified checkpoint', warning['systemMessage'])
        self.assertIn('Human detail.', note.read_text(encoding='utf-8'))

    def test_unbound_sessions_do_not_guess_tasks_create_vaults_or_read_transcripts(self):
        path = self.project()
        transcript = self.root / 'transcript.jsonl'
        transcript.write_text('PRIVATE TRANSCRIPT NEVER COPY', encoding='utf-8')
        output = self.event('claude', path, 'SessionStart', transcript_path=str(transcript))
        self.event('claude', path, 'UserPromptSubmit', prompt='PRIVATE PROMPT NEVER COPY')
        self.assertEqual(self.event('claude', path, 'Stop', last_assistant_message='PRIVATE ANSWER NEVER COPY'), {})
        self.assertEqual(list(self.vaults.iterdir()), [])
        self.assertNotIn('PRIVATE', json.dumps(output))
        for file in (self.config.parent / 'sessions').rglob('*.json'):
            self.assertNotIn('PRIVATE', file.read_text(encoding='utf-8'))

    def test_sessions_projects_and_hosts_are_isolated(self):
        path, entry, saved = self.prepare()
        other = self.project('other')
        hooks.bind(self.config.parent, 'codex', 'session-b', other, 'separate')
        with self.assertRaisesRegex(ValueError, 'another project'):
            self.event('codex', other, 'SessionStart')
        # Same ID on a different host is unbound until explicitly handed off.
        context = self.event('claude', path, 'SessionStart')
        self.assertNotIn('No background synchronization.', json.dumps(context))
        handed_off = hooks.bind(self.config.parent, 'claude', 'session-a', path, 'cache')
        self.assertIn('No background synchronization.', handed_off['memory']['notes'][0]['content'])
        result = self.event('codex', other, 'SessionStart', session='session-b')
        self.assertIn('no saved note yet', result['hookSpecificOutput']['additionalContext'])
        # New task need not exist yet; Stop requests its first real checkpoint.
        self.assertEqual(self.event('codex', other, 'Stop', session='session-b')['decision'], 'block')

    def test_missing_vault_is_a_reported_failure_not_a_replacement(self):
        import shutil
        path, entry, saved = self.prepare()
        shutil.rmtree(entry['vault'])
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.event('codex', path, 'SessionStart')
        self.assertFalse(Path(entry['vault']).exists())

    def test_generated_configuration_merges_idempotently_and_keeps_unrelated_settings(self):
        for host in ('codex', 'claude'):
            target = self.root / (host + '-settings.json')
            human = {'hooks': [{'type': 'command', 'command': 'echo human'}]}
            target.write_text(json.dumps({'permissions': {'allow': []}, 'hooks': {'Stop': [human]}}), encoding='utf-8')
            hooks.install_hooks(self.config.parent, host, target)
            first = target.read_bytes()
            hooks.install_hooks(self.config.parent, host, target)
            self.assertEqual(first, target.read_bytes())
            data = json.loads(first)
            self.assertEqual(data['permissions'], {'allow': []})
            self.assertIn(human, data['hooks']['Stop'])
            self.assertEqual(len(data['hooks']['Stop']), 2)
            self.assertIn('compact', data['hooks']['SessionStart'][0]['matcher'])
            data['hooks']['Stop'][1]['hooks'][0]['command'] = 'human edited this'
            target.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'edited or removed'):
                hooks.install_hooks(self.config.parent, host, target)
            self.assertEqual(json.loads(target.read_text()), data)

    def test_windows_commands_quote_paths_and_posix_command_runs_from_another_cwd(self):
        for host in ('codex', 'claude'):
            result = hooks.hook_groups(host, self.config.parent, windows=True)
            handler = result['Stop'][0]['hooks'][0]
            if host == 'claude':
                self.assertEqual(handler['shell'], 'powershell')
                self.assertTrue(handler['command'].startswith('& '))
            else:
                self.assertIn('-EncodedCommand', handler['command'])
        if sys.platform != 'win32':
            path = self.project('project with spaces')
            command = hooks.hook_groups('codex', self.config.parent, windows=False)['SessionStart'][0]['hooks'][0]['command']
            result = subprocess.run(command, shell=True, cwd=path, input=json.dumps({'session_id': 'new', 'cwd': str(path), 'hook_event_name': 'SessionStart'}), capture_output=True, text=True, encoding='utf-8', check=True)
            self.assertIn('hookSpecificOutput', json.loads(result.stdout))

    def test_invalid_event_fails_without_blocking_user_prompt(self):
        result = subprocess.run([sys.executable, str(Path(hooks.__file__)), '--config-dir', str(self.config.parent), '--host', 'codex', 'run'], input='{broken', capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertIn('error', json.loads(result.stderr))
