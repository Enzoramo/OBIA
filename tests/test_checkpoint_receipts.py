"""Storage receipts must replace redundant calls, not weaken persistence checks."""
import hashlib
from unittest.mock import patch
import unittest

import test_obia as core

obia = core.obia


class ReceiptTests(unittest.TestCase):
    setUp = core.MemoryTests.setUp
    invoke = core.MemoryTests.invoke

    def assert_receipt(self, result):
        self.assertTrue(result['verified'])
        self.assertTrue(result['project_index_current'])
        self.assertEqual(result['sha256'], hashlib.sha256((self.root / result['path']).read_bytes()).hexdigest())
        self.assertNotIn('content', result)

    def test_create_patch_and_noop_verify_stored_bytes_and_keep_history(self):
        saved = self.invoke('save', '--input', '-', input_data=core.payload())
        self.assert_receipt(saved)
        changes = {'properties': {'summary': 'Inspected storage. [S1]'}}
        new = self.invoke('patch', '--project', 'sample', '--task', 'cache', '--input', '-',
                          '--expect-sha', saved['sha256'], input_data=changes)
        self.assert_receipt(new)
        unchanged = obia.patch(self.root, 'sample', 'cache', changes, new['sha256'])
        self.assert_receipt(unchanged)
        self.assertEqual(unchanged['status'], 'unchanged')
        history = list((self.root / 'OBIA/.history/sample/cache').glob('*.md'))
        self.assertEqual(len(history), 1)
        self.assertEqual(hashlib.sha256(history[0].read_bytes()).hexdigest(), saved['sha256'])
        with self.assertRaises(obia.ObiaError):
            obia.patch(self.root, 'sample', 'cache', changes, saved['sha256'])

    def test_readback_detects_changed_or_missing_file_after_write(self):
        original_write = obia.atomic_write
        relative = obia.task_relative('sample', 'cache')
        for missing in (False, True):
            def interfere(path, content):
                original_write(path, content)
                if path == self.root / relative:
                    if missing:
                        path.unlink()
                    else:
                        path.write_text(content + '\nConcurrent human change.\n', encoding='utf-8')
            with self.subTest(missing=missing), patch.object(obia, 'atomic_write', side_effect=interfere):
                with self.assertRaises((obia.ObiaError, OSError)):
                    obia.save(self.root, core.payload())
            path = self.root / relative
            if path.exists():
                self.assertIn('Concurrent human change', path.read_text())
                path.unlink()

    def test_index_failure_and_stale_noop_are_not_reported_as_repaired(self):
        saved = obia.save(self.root, core.payload())
        index = self.root / 'OBIA/projects/sample/index.md'
        index.write_text('Human index', encoding='utf-8')
        unchanged = obia.save(self.root, core.payload(), saved['sha256'])
        self.assertTrue(unchanged['verified'])
        self.assertFalse(unchanged['project_index_current'])
        new = obia.patch(self.root, 'sample', 'cache', {'properties': {'status': 'complete'}}, saved['sha256'])
        self.assertTrue(new['verified'])
        self.assertFalse(new['project_index_current'])
        self.assertIn('Note saved', new['warning'])
        self.assertEqual(index.read_text(), 'Human index')

    def test_rendered_missing_citation_and_duplicate_source_fail_before_write(self):
        data = core.payload()
        data['objective'] += ' [S99]'
        with self.assertRaises(obia.ObiaError):
            obia.save(self.root, data)
        self.assertEqual(obia.list_notes(self.root), [])
        saved = obia.save(self.root, core.payload())
        changes = {'append': {'Sources': '- **S1** (file; observed 2026-11-18): Duplicate.'}}
        with self.assertRaises(obia.ObiaError):
            obia.patch(self.root, 'sample', 'cache', changes, saved['sha256'])
        self.assertEqual(obia.note(self.root, saved['path'])['sha256'], saved['sha256'])

    def test_invalid_neighbor_does_not_hide_successfully_saved_note(self):
        saved = obia.save(self.root, core.payload())
        other = obia.save(self.root, core.payload(task='other'))
        (self.root / other['path']).write_text('Broken metadata', encoding='utf-8')
        changes = {'properties': {'status': 'complete'}}
        result = obia.patch(self.root, 'sample', 'cache', changes, saved['sha256'])
        self.assertTrue(result['verified'])
        self.assertFalse(result['project_index_current'])
        self.assertIn('Note saved', result['warning'])
        self.assertEqual(obia.note(self.root, saved['path'])['sha256'], result['sha256'])
        noop = obia.patch(self.root, 'sample', 'cache', changes, result['sha256'])
        self.assertEqual(noop['status'], 'unchanged')
        self.assertTrue(noop['verified'])
        self.assertFalse(noop['project_index_current'])
        self.assertIn('could not be verified', noop['warning'])
