"""Structured handoffs preserve real storage and human edits without model calls."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import unittest

import test_obia as core

obia = core.obia
HELPER = core.REPO / 'skills/obia/scripts/handoff.py'
spec = importlib.util.spec_from_file_location('obia_handoff_tests', HELPER)
handoff = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'obia': obia}):
    spec.loader.exec_module(handoff)


def checkpoint():
    original = core.payload()
    return {key: copy.deepcopy(original.get(key, []))
            for key in handoff.CHECKPOINT_SCHEMA['properties']}


class HandoffTests(unittest.TestCase):
    setUp = core.MemoryTests.setUp

    def capture(self, data=None, expected=None, task='cache', **kwargs):
        return handoff.capture(self.root, 'sample', task,
                               checkpoint() if data is None else data, expected, **kwargs)

    def prepare(self, task='cache', **kwargs):
        return handoff.prepare(self.root, 'sample', task, **kwargs)

    def tree(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def invoke(self, command, *args, value=None, code=0):
        result = subprocess.run(
            [sys.executable, str(HELPER), command, '--vault', str(self.root),
             '--project', 'sample', '--task', 'cache', *args],
            input=json.dumps(value) if value is not None else None,
            text=True, encoding='utf-8', capture_output=True,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout if code == 0 else result.stderr)

    def test_create_prepare_update_and_noop_preserve_snapshot_and_history(self):
        before = self.tree()
        initial = self.prepare()
        self.assertIsNone(initial['memory'])
        self.assertIsNone(initial['expected_sha'])
        self.assertEqual(self.tree(), before)

        saved = self.capture(expected=initial['expected_sha'], title='Offline cache')
        self.assertEqual(saved['status'], 'created')
        self.assertTrue(saved['verified'])
        self.assertTrue(saved['handoff_owned'])
        packet = self.prepare()
        original = obia.note(self.root, saved['path'])
        self.assertEqual(packet['expected_sha'], saved['sha256'])
        self.assertEqual(packet['memory'], {key: original[key]
                         for key in ('path', 'sha256', 'content')})
        self.assertIn('No background synchronization.', packet['memory']['content'])
        self.assertIn('Synthetic user request', packet['memory']['content'])

        changed = checkpoint()
        changed['summary'] = 'Inspected the storage schema.'
        changed['status'] = 'complete'
        changed['next_actions'] = []
        changed['facts'] = [{'text': 'Schema inspection completed.', 'sources': ['S1']}]
        result = self.capture(changed, packet['expected_sha'], title='Ignored replacement title')
        self.assertEqual(result['status'], 'updated')
        self.assertTrue(result['verified'])
        self.assertTrue(result['handoff_owned'])
        current = obia.note(self.root, result['path'])
        self.assertEqual(current['title'], 'Offline cache')
        self.assertEqual(current['status'], 'complete')
        self.assertNotIn('Schema inspection remains.', current['content'])
        history = self.root / 'OBIA/.history/sample/cache' / (saved['sha256'] + '.md')
        self.assertEqual(history.read_text(encoding='utf-8'), original['content'])

        before = self.tree()
        with patch.object(obia, 'atomic_write', wraps=obia.atomic_write) as writes:
            noop = self.capture(changed, result['sha256'])
        self.assertEqual(noop['status'], 'unchanged')
        self.assertTrue(noop['verified'])
        self.assertTrue(noop['handoff_owned'])
        self.assertEqual(noop['sha256'], result['sha256'])
        self.assertEqual(self.tree(), before)
        writes.assert_not_called()

    def test_stale_snapshot_does_not_replace_a_newer_managed_checkpoint(self):
        first = self.capture()
        stale = self.prepare()
        changed = checkpoint()
        changed['summary'] = 'Another writer inspected the schema.'
        second = self.capture(changed, first['sha256'])
        before = self.tree()
        with self.assertRaisesRegex(handoff.HandoffError, 'stale'):
            self.capture(checkpoint(), stale['expected_sha'])
        self.assertEqual(self.tree(), before)
        self.assertEqual(self.prepare()['expected_sha'], second['sha256'])

    def test_ordinary_note_is_refused_even_with_its_current_sha(self):
        saved = obia.save(self.root, core.payload())
        before = self.tree()
        with self.assertRaisesRegex(handoff.HandoffError, 'not owned'):
            self.prepare()
        with self.assertRaisesRegex(handoff.HandoffError, 'not owned'):
            self.capture(expected=saved['sha256'])
        self.assertEqual(self.tree(), before)

    def test_ordinary_note_created_after_empty_prepare_is_preserved(self):
        packet = self.prepare()
        obia.save(self.root, core.payload())
        before = self.tree()
        with self.assertRaisesRegex(handoff.HandoffError, 'not owned'):
            self.capture(expected=packet['expected_sha'])
        self.assertEqual(self.tree(), before)

    def test_manual_edits_before_or_after_prepare_are_preserved(self):
        for when in ('before', 'after'):
            with self.subTest(when=when):
                saved = self.capture(task=when)
                packet = self.prepare(task=when) if when == 'after' else None
                path = self.root / saved['path']
                path.write_text(path.read_text(encoding='utf-8') +
                                '\n## Human notes\n\nKeep this independently edited detail.\n',
                                encoding='utf-8')
                before = self.tree()
                with self.assertRaisesRegex(handoff.HandoffError, 'ownership changed'):
                    self.prepare(task=when)
                # Even explicitly passing the freshly read SHA must not grant ownership.
                expected = packet['expected_sha'] if packet else obia.note(self.root, saved['path'])['sha256']
                with self.assertRaisesRegex(handoff.HandoffError, 'ownership changed'):
                    self.capture(expected=expected, task=when)
                self.assertEqual(self.tree(), before)

    def test_manual_edit_between_ownership_check_and_save_hits_helper_cas(self):
        saved = self.capture()
        original_save = obia.save
        path = self.root / saved['path']

        def concurrent_edit(*args, **kwargs):
            path.write_text(path.read_text(encoding='utf-8') + '\nHuman edit during capture.\n',
                            encoding='utf-8')
            return original_save(*args, **kwargs)

        changed = checkpoint()
        changed['summary'] = 'Should not replace a concurrent human change.'
        with patch.object(obia, 'save', side_effect=concurrent_edit):
            with self.assertRaisesRegex(obia.ObiaError, 'Write conflict'):
                self.capture(changed, saved['sha256'])
        self.assertIn('Human edit during capture.', path.read_text(encoding='utf-8'))
        self.assertNotIn(changed['summary'], path.read_text(encoding='utf-8'))
        self.assertFalse((self.root / 'OBIA/.history').exists())

    def test_invalid_sources_and_extra_identity_fields_fail_without_writing(self):
        variants = []
        missing = checkpoint()
        missing['sources'] = []
        variants.append(missing)
        undefined = checkpoint()
        undefined['facts'] = [{'text': 'Unsupported assertion.', 'sources': ['S99']}]
        variants.append(undefined)
        missing_inline = checkpoint()
        missing_inline['objective'] += ' [S99]'
        variants.append(missing_inline)
        duplicate = checkpoint()
        duplicate['sources'].append(copy.deepcopy(duplicate['sources'][0]))
        variants.append(duplicate)
        for key in ('project', 'id', 'title', 'expected_sha'):
            extra = checkpoint()
            extra[key] = 'different-target'
            variants.append(extra)
        for index, data in enumerate(variants):
            with self.subTest(index=index):
                before = self.tree()
                with self.assertRaises(obia.ObiaError):
                    self.capture(data)
                self.assertEqual(self.tree(), before)

    def test_budget_uses_full_serialized_memory_and_never_truncates(self):
        data = checkpoint()
        data['objective'] = 'Read cached items offline. ' + ('日本語 é "quoted" ' * 50)
        saved = self.capture(data)
        full = self.prepare(max_memory_chars=obia.MAX_BYTES)
        size = len(json.dumps(full['memory'], ensure_ascii=False))
        self.assertGreater(size, 1024)
        exact = self.prepare(max_memory_chars=size)
        self.assertEqual(exact['memory'], full['memory'])
        self.assertEqual(exact['expected_sha'], saved['sha256'])
        before = self.tree()
        with self.assertRaisesRegex(handoff.HandoffError, 'Nothing was truncated'):
            self.prepare(max_memory_chars=size - 1)
        self.assertEqual(self.tree(), before)

    def test_missing_note_or_ownership_never_grants_recreation_permission(self):
        for removed in ('note', 'owner'):
            with self.subTest(removed=removed):
                saved = self.capture(task=removed)
                path = (self.root / saved['path'] if removed == 'note'
                        else handoff.owner_path(self.root, 'sample', removed))
                path.unlink()
                before = self.tree()
                with self.assertRaises(handoff.HandoffError):
                    self.prepare(task=removed)
                with self.assertRaises(handoff.HandoffError):
                    self.capture(expected=saved['sha256'], task=removed)
                self.assertEqual(self.tree(), before)

    def test_ownership_write_failure_reports_saved_note_without_owned_receipt(self):
        original_write = obia.atomic_write
        owner = handoff.owner_path(self.root, 'sample', 'cache')

        def fail_owner(path, content):
            if path == owner:
                raise OSError('Synthetic ownership storage failure')
            return original_write(path, content)

        with patch.object(obia, 'atomic_write', side_effect=fail_owner):
            with self.assertRaisesRegex(handoff.HandoffError, 'Note saved') as caught:
                self.capture()
        error = caught.exception
        self.assertIsNotNone(error.saved)
        self.assertTrue(error.saved['verified'])
        self.assertNotIn('handoff_owned', error.saved)
        self.assertEqual(obia.note(self.root, error.saved['path'])['sha256'], error.saved['sha256'])
        self.assertFalse(owner.exists())
        with self.assertRaisesRegex(handoff.HandoffError, 'not owned'):
            self.prepare()

    def test_failed_ownership_readback_is_not_reported_as_verified(self):
        original_write = obia.atomic_write
        owner = handoff.owner_path(self.root, 'sample', 'cache')

        def corrupt_owner(path, content):
            return original_write(path, '{}' if path == owner else content)

        with patch.object(obia, 'atomic_write', side_effect=corrupt_owner):
            with self.assertRaisesRegex(handoff.HandoffError, 'Ownership readback failed') as caught:
                self.capture()
        saved = caught.exception.saved
        self.assertTrue(saved['verified'])
        self.assertNotIn('handoff_owned', saved)
        self.assertEqual(obia.note(self.root, saved['path'])['sha256'], saved['sha256'])
        with self.assertRaises(handoff.HandoffError):
            self.prepare()

    def test_changed_note_after_save_is_reported_with_original_storage_receipt(self):
        original_save = obia.save

        def edit_after_save(*args, **kwargs):
            saved = original_save(*args, **kwargs)
            path = self.root / saved['path']
            path.write_text(path.read_text(encoding='utf-8') + '\nLater human change.\n', encoding='utf-8')
            return saved

        with patch.object(obia, 'save', side_effect=edit_after_save):
            with self.assertRaisesRegex(handoff.HandoffError, 'Note changed after persistence') as caught:
                self.capture()
        saved = caught.exception.saved
        current = obia.note(self.root, saved['path'])
        self.assertNotEqual(current['sha256'], saved['sha256'])
        self.assertIn('Later human change.', current['content'])
        self.assertNotIn('handoff_owned', saved)
        self.assertFalse(handoff.owner_path(self.root, 'sample', 'cache').exists())

    def test_changed_ownership_after_save_is_preserved_and_reported(self):
        original_save = obia.save
        owner = handoff.owner_path(self.root, 'sample', 'cache')
        concurrent_record = '{"version":1,"sha256":"another-owner"}\n'

        def change_ownership(*args, **kwargs):
            saved = original_save(*args, **kwargs)
            obia.atomic_write(owner, concurrent_record)
            return saved

        with patch.object(obia, 'save', side_effect=change_ownership):
            with self.assertRaisesRegex(handoff.HandoffError, 'Ownership changed after persistence') as caught:
                self.capture()
        saved = caught.exception.saved
        self.assertEqual(owner.read_text(encoding='utf-8'), concurrent_record)
        self.assertTrue(saved['verified'])
        self.assertNotIn('handoff_owned', saved)
        self.assertEqual(obia.note(self.root, saved['path'])['sha256'], saved['sha256'])
        with self.assertRaises(handoff.HandoffError):
            self.prepare()

    def test_cli_wraps_arbitrary_answer_and_captures_only_checkpoint(self):
        answer_schema = handoff.object_schema({'done': {'type': 'boolean'}, 'detail': {'type': 'string'}})
        schema_path = self.root / 'answer-schema.json'
        schema_path.write_text(json.dumps(answer_schema), encoding='utf-8')
        packet = self.invoke('prepare', '--answer-schema', str(schema_path))
        self.assertEqual(packet['schema']['properties']['answer'], answer_schema)
        self.assertEqual(set(packet['schema']['properties']), {'answer', 'checkpoint'})
        wrapped = {'answer': {'done': False, 'detail': 'Response content stays outside memory.'},
                   'checkpoint': checkpoint()}
        saved = self.invoke('capture', '--input', '-', '--wrapped', value=wrapped)
        self.assertTrue(saved['handoff_owned'])
        packet = self.invoke('prepare')
        self.assertEqual(packet['expected_sha'], saved['sha256'])
        self.assertNotIn(wrapped['answer']['detail'], packet['memory']['content'])
        malformed = {**wrapped, 'extra': 'must be refused'}
        before = self.tree()
        failure = self.invoke('capture', '--input', '-', '--wrapped',
                              '--expect-sha', saved['sha256'], value=malformed, code=2)
        self.assertIn('exactly answer and checkpoint', failure['error'])
        self.assertEqual(self.tree(), before)

    def test_cli_ownership_failure_exposes_saved_checkpoint_and_error_exit(self):
        original_write = obia.atomic_write
        owner = handoff.owner_path(self.root, 'sample', 'cache')

        def fail_owner(path, content):
            if path.resolve() == owner.resolve():
                raise OSError('Synthetic ownership storage failure')
            return original_write(path, content)

        stdin, stdout, stderr = io.StringIO(json.dumps(checkpoint())), io.StringIO(), io.StringIO()
        with patch.object(obia, 'atomic_write', side_effect=fail_owner), \
                patch.object(sys, 'stdin', stdin), patch.object(sys, 'stdout', stdout), \
                patch.object(sys, 'stderr', stderr):
            code = handoff.main(['capture', '--vault', str(self.root), '--project', 'sample',
                                 '--task', 'cache', '--input', '-'])
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), '')
        failure = json.loads(stderr.getvalue())
        self.assertIn('Note saved', failure['error'])
        saved = failure['saved_checkpoint']
        self.assertTrue(saved['verified'])
        self.assertNotIn('handoff_owned', saved)
        self.assertEqual(obia.note(self.root, saved['path'])['sha256'], saved['sha256'])


if __name__ == '__main__':
    unittest.main()
