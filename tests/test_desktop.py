"""Desktop helper contracts, using temporary state fixtures, never hook events."""
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_obia as core
import test_projects as routing
import desktop

obia, hooks = desktop.obia, desktop.hooks
HELPER = Path(desktop.__file__)


class DesktopTests(unittest.TestCase):
    project = routing.ProjectTests.project

    def setUp(self):
        routing.ProjectTests.setUp(self)
        self.cwd = self.project('Workspace')
        self.session = 'synthetic-desktop-session'
        self.entry = desktop.recover(self.config.parent, self.session, self.cwd, 'cache')
        self.vault = Path(self.entry['vault'])
        # This is an on-disk unit-test fixture, not a fabricated lifecycle event.
        self.state_path = hooks.session_file(self.config.parent, 'codex', self.session)
        self.fixture_state(turn=7, turn_id='previously-observed-turn')
        forbidden = patch.object(hooks, 'handle', side_effect=AssertionError('No hook events in desktop tests'))
        forbidden.start()
        self.addCleanup(forbidden.stop)

    def fixture_state(self, **fields):
        state = json.loads(self.state_path.read_text(encoding='utf-8'))
        state.update(fields)
        self.state_path.write_text(json.dumps(state), encoding='utf-8')
        return state

    def state(self):
        return json.loads(self.state_path.read_text(encoding='utf-8'))

    def value(self):
        data = core.payload(project=self.entry['project'])
        data.pop('project')
        data.pop('id')
        return data

    def save(self, value=None, expected=None, **overrides):
        args = {'config': self.config.parent, 'session': self.session, 'cwd': self.cwd,
                'task': 'cache', 'value': self.value() if value is None else value,
                'expected': expected, **overrides}
        return desktop.checkpoint(**args)

    def note(self):
        return obia.note(self.vault, obia.task_relative(self.entry['project'], 'cache'))

    def files(self, root=None):
        root = root or self.root
        return {str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def invoke(self, command, *args, value=None, code=0):
        result = subprocess.run(
            [sys.executable, '-B', str(HELPER), '--config-dir', str(self.config.parent), command,
             '--session', self.session, '--path', str(self.cwd), '--task', 'cache', *args],
            input=json.dumps(value, ensure_ascii=False) if value is not None else None,
            text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertEqual(result.stderr if code == 0 else result.stdout, '')
        return json.loads(result.stdout if code == 0 else result.stderr)

    def test_recover_bundles_sources_and_known_sha_does_not_ack(self):
        data = core.payload(project=self.entry['project'])
        data['facts'] = [{'text': 'Historical diagnostic. ' * 90, 'sources': ['S1']} for _ in range(8)]
        saved = obia.save(self.vault, data)
        recovered = desktop.recover(self.config.parent, self.session, self.cwd, 'cache')
        memory = recovered['memory']['notes'][0]
        self.assertEqual(memory['sha256'], saved['sha256'])
        self.assertIn('No background synchronization.', memory['content'])
        self.assertEqual(memory['source_ids'], ['S1'])
        self.assertIn('Synthetic user request', memory['source_definitions']['S1'])
        self.assertNotIn('Historical diagnostic.', memory['content'])
        self.assertIsNone(self.state()['checkpoint_turn'])
        with patch.object(obia, 'recall', side_effect=AssertionError('Known context must not be repeated')):
            known = desktop.recover(self.config.parent, self.session, self.cwd, 'cache', saved['sha256'])
        self.assertEqual(known['memory'], {'status': 'unchanged', 'path': saved['path'], 'sha256': saved['sha256']})
        self.assertIsNone(self.state()['checkpoint_turn'])

    def test_creation_has_distinct_storage_and_observed_turn_receipts(self):
        registry = self.config.read_bytes()
        result = self.save()
        saved, ack = result['checkpoint'], result['ack']
        self.assertEqual(saved['status'], 'created')
        self.assertTrue(saved['verified'])
        self.assertTrue(saved['project_index_current'])
        self.assertEqual(self.note()['sha256'], saved['sha256'])
        self.assertEqual(ack['sha256'], saved['sha256'])
        self.assertEqual(ack['task'], 'cache')
        self.assertEqual(ack['turn'], 7)
        self.assertEqual(ack['turn_id'], 'previously-observed-turn')
        self.assertEqual(result['ack_scope'], 'last_observed_host_turn')
        self.assertEqual(result['current_turn_validated_by'], 'the next real lifecycle event')
        self.assertTrue(result['turn_identity_observed'])
        self.assertEqual(self.state()['checkpoint_turn_id'], 'previously-observed-turn')
        self.assertEqual(self.config.read_bytes(), registry)
        self.assertFalse((self.vault / 'OBIA/.handoff').exists())

    def test_partial_update_preserves_human_metadata_sections_and_history(self):
        self.save()
        original = self.note()
        text = original['content'].replace('obia: 1', 'obia: 1 # human comment\nowner: Human')
        human = '\n## Human notes\n\nKeep **exactly** this.\n\n```md\n## Not a section\n```\n'
        (self.vault / original['path']).write_text(text + human, encoding='utf-8')
        before = self.note()
        result = self.save({'properties': {'status': 'complete', 'summary': 'Inspection complete.'},
                            'append': {'Facts': '- Schema inspected. [S1]'}}, before['sha256'])
        current = self.note()
        self.assertIn('owner: Human', current['content'])
        self.assertIn('# human comment', current['content'])
        self.assertIn(human.strip(), current['content'])
        self.assertIn('**Current state:** Inspection complete.', current['content'])
        self.assertIn('Schema inspected. [S1]', current['content'])
        self.assertEqual(current['status'], 'complete')
        self.assertEqual(result['ack']['sha256'], current['sha256'])
        history = self.vault / 'OBIA/.history' / self.entry['project'] / 'cache' / (before['sha256'] + '.md')
        self.assertEqual(history.read_text(encoding='utf-8'), before['content'])

    def test_stale_sha_preserves_newer_note_and_ack(self):
        first = self.save()['checkpoint']
        second = self.save({'properties': {'summary': 'Another writer finished inspection.'}}, first['sha256'])
        before = self.files()
        with patch.object(hooks, 'acknowledge', wraps=hooks.acknowledge) as ack:
            with self.assertRaisesRegex(obia.ObiaError, 'Write conflict'):
                self.save({'properties': {'summary': 'Stale overwrite.'}}, first['sha256'])
        ack.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertEqual(self.state()['sha256'], second['checkpoint']['sha256'])

    def test_unbound_wrong_task_and_wrong_project_fail_before_writing(self):
        other = self.project('Other')
        routing.projects.ensure(other, config_path=self.config)
        for override in ({'session': 'unbound'}, {'task': 'different'}, {'cwd': other}):
            with self.subTest(override=override):
                before = self.files()
                with patch.object(obia, 'save', wraps=obia.save) as write:
                    with self.assertRaises((obia.ObiaError, ValueError)):
                        self.save(**override)
                write.assert_not_called()
                self.assertEqual(self.files(), before)

    def test_wrong_payload_or_note_identity_is_rejected_without_ack(self):
        for key in ('project', 'id'):
            with self.subTest(key=key):
                before = self.files()
                with self.assertRaisesRegex(desktop.DesktopError, 'identity differs'):
                    self.save({**self.value(), key: 'unrelated'})
                self.assertEqual(self.files(), before)
        first = self.save()['checkpoint']
        for changes in ({'properties': {'project': 'unrelated'}},
                        {'properties': {'task_id': 'unrelated'}},
                        {'sections': {'Facts': '- Unsupported assertion. [S99]'}}):
            with self.subTest(changes=changes):
                before = self.files()
                with patch.object(hooks, 'acknowledge', wraps=hooks.acknowledge) as ack:
                    with self.assertRaises(obia.ObiaError):
                        self.save(changes, first['sha256'])
                ack.assert_not_called()
                self.assertEqual(self.files(), before)

    def test_path_traversal_and_vault_identity_substitution_fail_before_writing(self):
        with self.assertRaises(obia.ObiaError):
            self.save(task='../elsewhere')
        marker = self.vault / '.obia-project.json'
        marker.write_text('{}', encoding='utf-8')
        before = self.files()
        with patch.object(obia, 'save', wraps=obia.save) as write:
            with self.assertRaises(ValueError):
                self.save()
        write.assert_not_called()
        self.assertEqual(self.files(), before)

    def test_creation_cannot_replace_an_existing_note_without_sha(self):
        self.save()
        before = self.files()
        with self.assertRaisesRegex(obia.ObiaError, 'Write conflict'):
            self.save({**self.value(), 'summary': 'Implicit replacement forbidden.'})
        self.assertEqual(self.files(), before)

    def test_ack_failure_after_save_returns_receipt_of_actual_persistence(self):
        before_state = self.state()
        with patch.object(hooks, 'acknowledge', side_effect=OSError('Synthetic ack storage failure')):
            with self.assertRaisesRegex(desktop.DesktopError, 'acknowledgement failed') as caught:
                self.save()
        saved = caught.exception.saved
        self.assertTrue(saved['verified'])
        self.assertEqual(saved['sha256'], self.note()['sha256'])
        self.assertEqual(self.state(), before_state)

    def test_concurrent_binding_change_after_save_is_reported_without_ack(self):
        actual_save = obia.save
        def switch_binding(*args, **kwargs):
            saved = actual_save(*args, **kwargs)
            hooks.bind(self.config.parent, 'codex', self.session, self.cwd, 'different')
            return saved
        with patch.object(obia, 'save', side_effect=switch_binding), \
                patch.object(hooks, 'acknowledge', wraps=hooks.acknowledge) as ack:
            with self.assertRaises(desktop.DesktopError) as caught:
                self.save()
        ack.assert_not_called()
        self.assertEqual(self.note()['sha256'], caught.exception.saved['sha256'])
        self.assertEqual(self.state()['task'], 'different')
        self.assertIsNone(self.state()['checkpoint_turn'])

    def test_later_note_change_before_ack_preserves_human_edit_and_reports_failure(self):
        actual_save = obia.save
        def human_edit(*args, **kwargs):
            saved = actual_save(*args, **kwargs)
            path = self.vault / saved['path']
            path.write_text(path.read_text(encoding='utf-8') + '\nHuman change after save.\n', encoding='utf-8')
            return saved
        with patch.object(obia, 'save', side_effect=human_edit):
            with self.assertRaisesRegex(desktop.DesktopError, 'SHA differs') as caught:
                self.save()
        self.assertNotEqual(caught.exception.saved['sha256'], self.note()['sha256'])
        self.assertIn('Human change after save.', self.note()['content'])
        self.assertIsNone(self.state()['checkpoint_turn'])

    def test_real_index_warning_preserves_saved_note_without_attempting_ack(self):
        index = self.vault / 'OBIA/projects' / self.entry['project'] / 'index.md'
        index.write_text('Human index: do not replace.\n', encoding='utf-8')
        with patch.object(hooks, 'acknowledge', wraps=hooks.acknowledge) as ack:
            with self.assertRaisesRegex(desktop.DesktopError, 'acknowledgement was not attempted') as caught:
                self.save()
        saved = caught.exception.saved
        self.assertTrue(saved['verified'])
        self.assertFalse(saved['project_index_current'])
        self.assertIn('warning', saved)
        self.assertEqual(self.note()['sha256'], saved['sha256'])
        self.assertEqual(index.read_text(), 'Human index: do not replace.\n')
        self.assertIsNone(self.state()['checkpoint_turn'])
        ack.assert_not_called()

    def test_any_incomplete_storage_receipt_blocks_ack(self):
        for issue in ({'verified': False}, {'project_index_current': False}, {'warning': 'Investigate storage.'}):
            with self.subTest(issue=issue):
                receipt = {'status': 'created', 'sha256': 'fixture-sha', 'verified': True,
                           'project_index_current': True, **issue}
                with patch.object(obia, 'save', return_value=receipt), \
                        patch.object(hooks, 'acknowledge', wraps=hooks.acknowledge) as ack:
                    with self.assertRaises(desktop.DesktopError) as caught:
                        self.save()
                self.assertEqual(caught.exception.saved, receipt)
                ack.assert_not_called()

    def test_verify_is_storage_noop_and_stale_verify_cannot_ack(self):
        saved = self.save()['checkpoint']
        self.fixture_state(checkpoint_turn=None, checkpoint_turn_id=None, sha256=None)
        before = self.files(self.vault)
        with patch.object(obia, 'save', side_effect=AssertionError('verify must not save')), \
                patch.object(obia, 'patch', side_effect=AssertionError('verify must not patch')):
            result = desktop.verify(self.config.parent, self.session, self.cwd, 'cache', saved['sha256'])
        self.assertEqual(result['checkpoint'], {'status': 'unchanged', 'path': saved['path'], 'sha256': saved['sha256']})
        self.assertEqual(result['ack']['sha256'], saved['sha256'])
        self.assertEqual(self.files(self.vault), before)
        before = self.files()
        with patch.object(hooks, 'acknowledge', wraps=hooks.acknowledge) as ack:
            with self.assertRaisesRegex(obia.ObiaError, 'Read conflict'):
                desktop.verify(self.config.parent, self.session, self.cwd, 'cache', 'stale-sha')
        ack.assert_not_called()
        self.assertEqual(self.files(), before)

    def test_missing_or_old_turn_identity_is_never_upgraded_to_current(self):
        saved = self.save()['checkpoint']
        for identity in (None, 'an-older-observed-turn'):
            with self.subTest(identity=identity):
                self.fixture_state(turn_id=identity, checkpoint_turn_id=None, checkpoint_turn=None)
                result = desktop.verify(self.config.parent, self.session, self.cwd, 'cache', saved['sha256'])
                self.assertEqual(result['ack']['turn_id'], identity)
                self.assertEqual(self.state()['turn_id'], identity)
                self.assertEqual(self.state()['checkpoint_turn_id'], identity)
                self.assertEqual(result['turn_identity_observed'], identity is not None)
                self.assertEqual(result['ack_scope'], 'last_observed_host_turn')
                self.assertEqual(result['current_turn_validated_by'], 'the next real lifecycle event')

    def test_cli_create_recover_patch_verify_and_stale_failure(self):
        created = self.invoke('checkpoint', '--input', '-', value={**self.value(), 'title': 'Conexão 日本語'})
        sha = created['checkpoint']['sha256']
        known = self.invoke('recover', '--known-sha', sha)
        self.assertEqual(known['memory']['status'], 'unchanged')
        input_file = self.root / 'patch.json'
        input_file.write_text(json.dumps({'properties': {'summary': 'Inspeção concluída.'}}), encoding='utf-8')
        changed = self.invoke('checkpoint', '--input', str(input_file), '--expect-sha', sha)
        current = changed['checkpoint']['sha256']
        self.assertEqual(self.invoke('verify', '--sha', current)['ack']['sha256'], current)
        self.assertIn('Conexão 日本語', self.note()['content'])
        self.assertIn('Inspeção concluída.', self.note()['content'])
        before = self.files()
        failed = self.invoke('verify', '--sha', sha, code=2)
        self.assertIn('Read conflict', failed['error'])
        self.assertNotIn('saved_checkpoint', failed)
        self.assertEqual(self.files(), before)

    def test_cli_ack_failure_exposes_saved_receipt_and_nonzero_exit(self):
        stdin, stdout, stderr = io.StringIO(json.dumps(self.value())), io.StringIO(), io.StringIO()
        with patch.object(hooks, 'acknowledge', side_effect=OSError('Synthetic ack failure')), \
                patch.object(sys, 'stdin', stdin), patch.object(sys, 'stdout', stdout), \
                patch.object(sys, 'stderr', stderr):
            code = desktop.main(['--config-dir', str(self.config.parent), 'checkpoint',
                                 '--session', self.session, '--path', str(self.cwd), '--task', 'cache', '--input', '-'])
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), '')
        failure = json.loads(stderr.getvalue())
        self.assertFalse(failure['acknowledged'])
        self.assertTrue(failure['saved_checkpoint']['verified'])
        self.assertEqual(failure['saved_checkpoint']['sha256'], self.note()['sha256'])


    def test_changed_focus_recovers_even_when_note_sha_is_known(self):
        receipt=self.save();sha=receipt['checkpoint']['sha256']
        import desktop
        result=desktop.recover(self.config.parent,self.session,self.cwd,'cache',sha,focus='offline')
        self.assertNotEqual(result['memory'].get('status'),'unchanged')
        self.assertEqual(result['memory']['notes'][0]['sha256'],sha)
        self.assertEqual(self.invoke('recover','--known-sha',sha,'--focus','offline')['memory']['view'],'focused')

if __name__ == '__main__':
    unittest.main()
