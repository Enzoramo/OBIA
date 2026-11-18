"""Progressive retrieval contracts with synthetic, temporary notes only."""
import json
import unittest

import test_obia as core

obia = core.obia


class ProgressiveTests(unittest.TestCase):
    setUp = core.MemoryTests.setUp
    invoke = core.MemoryTests.invoke

    def prepare(self):
        data = core.payload()
        data['sources'].append({'id': 'S2', 'kind': 'file', 'ref': 'Synthetic archived inspection log.',
                                'observed_at': '2026-11-12'})
        data['facts'] = [{'text': 'Historical diagnostic detail. ' * 90, 'sources': ['S2']} for _ in range(8)]
        data['decisions'] = [{'text': 'Cache remains local.', 'reason': 'Offline requirement.', 'sources': ['S1']}]
        data['corrections'] = [{'text': 'An earlier network-first proposal is obsolete.', 'sources': ['S1']}]
        saved = obia.save(self.root, data)
        return data, saved

    def test_brief_preserves_entire_core_and_defers_only_explicit_details(self):
        data, saved = self.prepare()
        before = (self.root / saved['path']).read_bytes()
        packet = obia.recall(self.root, 'sample', task='cache', view='brief')
        item = packet['notes'][0]
        self.assertEqual(item['view'], 'brief')
        self.assertEqual(item['sha256'], saved['sha256'])
        self.assertEqual(item['included_sections'], list(obia.BRIEF_SECTIONS))
        self.assertIn('Facts', item['omitted_sections'])
        self.assertIn('Sources', item['omitted_sections'])
        self.assertEqual(item['source_ids'], ['S1'])
        for section in obia.BRIEF_SECTIONS:
            part = obia.read_note(self.root, 'sample', 'cache', section_names=[section])
            self.assertIn(part['content'].strip(), item['content'])
        self.assertNotIn('Historical diagnostic', item['content'])
        evidence = self.invoke('read', '--project', 'sample', '--task', 'cache', '--source', 'S1',
                               '--expect-sha', saved['sha256'])
        self.assertIn(data['sources'][0]['ref'], evidence['content'])
        self.assertNotIn('archived inspection', evidence['content'])
        self.assertEqual(evidence['sha256'], saved['sha256'])
        self.assertEqual((self.root / saved['path']).read_bytes(), before)

    def test_budget_never_returns_a_truncated_constraint_or_incomplete_core(self):
        data = core.payload()
        data['constraints'][0]['text'] = 'Critical boundary é🙂 ' * 150
        saved = obia.save(self.root, data)
        for budget in (1024, 1200, 2048, 4096, 12000):
            with self.subTest(budget=budget):
                packet = obia.recall(self.root, 'sample', task='cache', budget=budget, view='brief')
                self.assertLessEqual(len(json.dumps(packet, ensure_ascii=False, indent=2)) + 1, budget)
                if packet['view'] == 'brief':
                    self.assertIn('before acting', packet['next'])
                if packet['notes'] and (packet['view'] == 'full' or packet['notes'][0]['view'] == 'brief'):
                    self.assertIn(data['constraints'][0]['text'], packet['notes'][0]['content'])
                elif packet['notes']:
                    self.assertEqual(packet['notes'][0]['read_required'], 'full')
                    self.assertNotIn('content', packet['notes'][0])
                    self.assertEqual(packet['notes'][0]['sha256'], saved['sha256'])
                else:
                    self.assertEqual(packet['omitted_count'], 1)

    def test_brief_falls_back_for_nonstandard_metadata_or_missing_resume(self):
        saved = obia.save(self.root, core.payload())
        path = self.root / saved['path']
        original = path.read_text(encoding='utf-8')
        for changed in (original.replace('## Resume', '## Human state'),
                        original.replace('obia: 1', 'obia: 1\nhuman_constraint: "Never contact a server"')):
            with self.subTest(changed=changed[:30]):
                path.write_text(changed, encoding='utf-8')
                packet = obia.recall(self.root, 'sample', task='cache', view='brief')
                item = packet['notes'][0]
                self.assertEqual(item.get('view', packet['view']), 'full')
                self.assertEqual(item['content'], changed)

    def test_brief_retains_human_preamble_and_lists_custom_sections(self):
        _, saved = self.prepare()
        path = self.root / saved['path']
        content = path.read_text(encoding='utf-8').replace('## Resume', 'Human boundary: do not delete drafts.\n\n## Resume')
        content += '\n## Human observations\n\nAn optional extra detail.\n'
        path.write_text(content, encoding='utf-8')
        item = obia.recall(self.root, 'sample', task='cache', view='brief')['notes'][0]
        self.assertIn('Human boundary: do not delete drafts.', item['content'])
        self.assertIn('Human observations', item['omitted_sections'])

    def test_related_notes_are_locators_and_remain_one_project_one_hop(self):
        other = obia.save(self.root, core.payload(task='other', project='private'))
        linked_data = core.payload(task='choice')
        linked_data['links'] = [{'target': other['path'], 'relation': 'Cross-project reference only.'}]
        linked = obia.save(self.root, linked_data)
        data = core.payload()
        data['links'] = [{'target': linked['path'], 'relation': 'Relevant implementation decision.'},
                         {'target': other['path'], 'relation': 'Explicit cross-project reference.'}]
        obia.save(self.root, data)
        packet = obia.recall(self.root, 'sample', task='cache', view='brief')
        self.assertEqual([item['view'] for item in packet['notes']], ['brief', 'locator'])
        self.assertNotIn('content', packet['notes'][1])
        self.assertEqual(packet['notes'][1]['path'], linked['path'])
        self.assertNotIn('/private/', json.dumps(packet))

    def test_query_results_are_brief_and_empty_search_is_explicit(self):
        self.prepare()
        result = self.invoke('recall', '--project', 'sample', '--query', 'offline', '--view', 'brief')
        self.assertEqual(result['notes'][0]['view'], 'brief')
        empty = self.invoke('recall', '--project', 'sample', '--query', 'not-present', '--view', 'brief')
        self.assertEqual(empty['notes'], [])
        self.assertIn('No lexical matches', empty['next'])

    def test_short_notes_use_complete_payload_when_it_is_smaller(self):
        obia.save(self.root, core.payload())
        full = obia.recall(self.root, 'sample', task='cache')
        adaptive = obia.recall(self.root, 'sample', task='cache', view='brief')
        self.assertEqual(adaptive['view'], 'full')
        self.assertEqual(adaptive['notes'], full['notes'])
        self.assertIn('## Sources', adaptive['notes'][0]['content'])

    def test_batch_sections_conditional_read_and_snapshot_guard(self):
        saved = obia.save(self.root, core.payload())
        selected = self.invoke('read', '--project', 'sample', '--task', 'cache',
                               '--section', 'Resume', '--section', 'Constraints', '--section', 'Resume')
        self.assertEqual(selected['content'].count('## Resume'), 1)
        self.assertIn('No background synchronization.', selected['content'])
        self.assertNotIn('## Sources', selected['content'])
        unchanged = self.invoke('read', '--project', 'sample', '--task', 'cache', '--if-changed', saved['sha256'])
        self.assertEqual(unchanged['status'], 'unchanged')
        self.assertNotIn('content', unchanged)
        path = self.root / saved['path']
        path.write_text(path.read_text(encoding='utf-8') + '\nHuman update.\n', encoding='utf-8')
        self.invoke('read', '--project', 'sample', '--task', 'cache', '--source', 'S1',
                    '--expect-sha', saved['sha256'], code=2)
        changed = self.invoke('read', '--project', 'sample', '--task', 'cache', '--if-changed', saved['sha256'])
        self.assertIn('Human update.', changed['content'])
        self.assertNotEqual(changed['sha256'], saved['sha256'])

    def test_source_reader_preserves_multiline_records_and_rejects_spoofed_ids(self):
        data, saved = self.prepare()
        path = self.root / saved['path']
        content = path.read_text(encoding='utf-8')
        content = content.replace('- **S2**', '  Continuation of source one.\n\n- **S2**')
        content += '\n```md\n- **S99** (file; observed 2026-11-12): Fenced fake.\n```\n'
        content += '\n## Human details\n- **S98** (file; observed 2026-11-12): Outside Sources.\n'
        path.write_text(content, encoding='utf-8')
        selected = self.invoke('read', '--project', 'sample', '--task', 'cache', '--source', 'S1')
        self.assertIn('Continuation of source one.', selected['content'])
        self.assertNotIn('S2', selected['content'])
        for identifier in ('S99', 'S98', 'bad'):
            self.invoke('read', '--project', 'sample', '--task', 'cache', '--source', identifier, code=2)
        both = self.invoke('read', '--project', 'sample', '--task', 'cache', '--source', 'S1', '--source', 'S2')
        self.assertIn(data['sources'][1]['ref'], both['content'])

    def test_duplicate_source_ids_fail_without_guessing(self):
        saved = obia.save(self.root, core.payload())
        path = self.root / saved['path']
        path.write_text(path.read_text(encoding='utf-8') + '\n- **S1** (file; observed 2026-11-12): Ambiguous.\n', encoding='utf-8')
        result = self.invoke('read', '--project', 'sample', '--task', 'cache', '--source', 'S1', code=2)
        self.assertIn('Duplicate source', result['error'])

    def test_brief_many_long_locators_stays_within_serialized_budget(self):
        targets = [obia.save(self.root, core.payload(task='linked-' + str(i) + 'x' * 45)) for i in range(9)]
        data = core.payload()
        data['links'] = [{'target': target['path'], 'relation': 'Synthetic related task.'} for target in targets]
        obia.save(self.root, data)
        for budget in (1024, 1200, 2000, 4000):
            packet = obia.recall(self.root, 'sample', task='cache', limit=10, budget=budget, view='brief')
            self.assertLessEqual(len(json.dumps(packet, ensure_ascii=False, indent=2)) + 1, budget)
        with self.assertRaises(ValueError):
            obia.recall(self.root, 'sample', task='cache', view='unknown')

    def test_bundled_sources_include_only_cited_records_and_inventory_all_ids(self):
        data, saved = self.prepare()
        packet = self.invoke('recall', '--project', 'sample', '--task', 'cache',
                             '--view', 'brief', '--with-sources')
        item = packet['notes'][0]
        self.assertEqual(item['sha256'], saved['sha256'])
        self.assertEqual(item['available_source_ids'], ['S1', 'S2'])
        self.assertEqual(list(item['source_definitions']), ['S1'])
        self.assertIn(data['sources'][0]['ref'], item['source_definitions']['S1'])
        self.assertIn('Sources', item['omitted_sections'])
        self.assertNotIn(data['sources'][1]['ref'], str(packet))
        for budget in (1024, 1500, 3000):
            result = obia.recall(self.root, 'sample', task='cache', view='brief',
                                 with_sources=True, budget=budget)
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False, indent=2)) + 1, budget)
            if result['notes'][0]['view'] == 'brief':
                self.assertEqual(result['notes'][0]['source_definitions'], item['source_definitions'])
            else:
                self.assertEqual(result['notes'][0]['read_required'], 'full')

    def test_bundled_sources_reject_duplicate_or_missing_definition(self):
        _, saved = self.prepare()
        path = self.root / saved['path']
        content = path.read_text(encoding='utf-8')
        for changed in (content.replace('- **S1**', '- **S3**'),
                        content + '\n- **S1** (file; observed 2026-11-18): Duplicate.\n'):
            path.write_text(changed, encoding='utf-8')
            with self.assertRaises(obia.ObiaError):
                obia.recall(self.root, 'sample', task='cache', view='brief', with_sources=True)

    def test_bundled_evidence_remains_in_the_loaded_snapshot(self):
        from unittest.mock import patch
        _, saved = self.prepare()
        path = self.root / saved['path']
        original = obia.source_records
        def edit_after_load(content):
            path.write_text(content.replace('Synthetic user request', 'Changed evidence'), encoding='utf-8')
            return original(content)
        with patch.object(obia, 'source_records', side_effect=edit_after_load):
            result = obia.recall(self.root, 'sample', task='cache', view='brief', with_sources=True)
        item = result['notes'][0]
        self.assertEqual(item['sha256'], saved['sha256'])
        self.assertIn('Synthetic user request', item['source_definitions']['S1'])
        self.assertNotEqual(obia.note(self.root, saved['path'])['sha256'], item['sha256'])
