"""Human-edited Obsidian notes survive partial updates."""
import unittest
import test_obia as base

obia, payload = base.obia, base.payload


class EditingTests(unittest.TestCase):
    setUp = base.MemoryTests.setUp
    invoke = base.MemoryTests.invoke

    def human_note(self):
        saved = obia.save(self.root, payload())
        path = self.root / saved['path']
        text = path.read_text(encoding='utf-8')
        text = text.replace('obia: 1', 'obia: 1 # keep this comment\ntags:\n  - important\nowner: Enzo\ncustom_date: 2026-11-12')
        text = text.replace('project: "sample"', 'project: sample')
        text += '\n## Human notes\n\nKeep **exactly** this.\n\n```md\n## Not a section\n```\n'
        path.write_text(text, encoding='utf-8')
        return obia.note(self.root, saved['path'])

    def test_yaml_and_patch_preserve_properties_comments_and_untouched_sections(self):
        old = self.human_note()
        self.assertEqual(len(obia.search(self.root, 'sample', 'offline')), 1)
        result = self.invoke('patch', '--project', 'sample', '--task', 'cache', '--expect-sha', old['sha256'], '--input', '-', input_data={'properties': {'status': 'complete', 'summary': 'Inspection complete.'}, 'append': {'Facts': '- Schema inspected. [S1]'}})
        new = obia.note(self.root, result['path'])
        self.assertIn('owner: Enzo', new['content'])
        self.assertIn('# keep this comment', new['content'])
        self.assertIn('custom_date: 2026-11-12', new['content'])
        self.assertEqual(new['content'].split('## Human notes')[1].split('## Facts')[0].rstrip(), old['content'].split('## Human notes')[1].rstrip())
        self.assertIn('**Current state:** Inspection complete.', new['content'])
        self.assertEqual(obia.check(self.root, 'sample')['problems'], [])
        snapshot = self.root / f"OBIA/.history/sample/cache/{old['sha256']}.md"
        self.assertEqual(snapshot.read_text(encoding='utf-8'), old['content'])

    def test_full_replacement_requires_explicit_opt_in_and_preserves_extra_metadata(self):
        old = self.human_note()
        data = payload()
        data['summary'] = 'New summary.'
        with self.assertRaisesRegex(obia.ObiaError, '--replace'):
            obia.save(self.root, data, old['sha256'])
        new = obia.save(self.root, data, old['sha256'], replace_existing=True)
        self.assertIn('owner: Enzo', obia.note(self.root, new['path'])['content'])

    def test_stale_patch_identity_changes_and_missing_sources_are_rejected(self):
        old = self.human_note()
        for changes, sha in [({'properties': {'status': 'complete'}}, 'stale'), ({'properties': {'project': 'other'}}, old['sha256']), ({'sections': {'Facts': '- Unsupported. [S99]'}}, old['sha256'])]:
            with self.assertRaises(obia.ObiaError):
                obia.patch(self.root, 'sample', 'cache', changes, sha)
            self.assertEqual(obia.note(self.root, old['path'])['sha256'], old['sha256'])

    def test_yaml_duplicate_keys_and_python_tags_are_rejected_without_execution(self):
        saved = obia.save(self.root, payload())
        path = self.root / saved['path']
        original = path.read_text(encoding='utf-8')
        for extra in ['project: duplicate\n', 'evil: !!python/object/apply:os.system ["echo forbidden"]\n']:
            path.write_text(original.replace('obia: 1\n', 'obia: 1\n' + extra), encoding='utf-8')
            with self.assertRaises(obia.ObiaError):
                obia.note(self.root, saved['path'])

    def test_fenced_headings_and_ambiguous_duplicates(self):
        old = self.human_note()
        section = self.invoke('read', '--project', 'sample', '--task', 'cache', '--section', 'Human notes')
        self.assertIn('## Not a section', section['content'])
        path = self.root / old['path']
        path.write_text(old['content'] + '\n## Resume\nDuplicate.\n', encoding='utf-8')
        with self.assertRaisesRegex(obia.ObiaError, 'Duplicate section'):
            obia.patch(self.root, 'sample', 'cache', {'properties': {'status': 'complete'}}, obia.digest(path.read_text(encoding='utf-8')))

    def test_manually_rewritten_resume_requires_reconciliation(self):
        old = self.human_note()
        path = self.root / old['path']
        path.write_text(old['content'].replace('**Current state:** Schema inspection remains.', 'Human current state: different.'), encoding='utf-8')
        with self.assertRaisesRegex(obia.ObiaError, 'Resume was edited'):
            obia.patch(self.root, 'sample', 'cache', {'properties': {'summary': 'New state.'}}, obia.digest(path.read_text(encoding='utf-8')))
