"""Focused recall with synthetic notes; no lifecycle events."""
import json
import unittest
import test_obia as core

obia = core.obia


class FocusedTests(unittest.TestCase):
    setUp = core.MemoryTests.setUp
    invoke = core.MemoryTests.invoke

    def prepare(self):
        data = core.payload()
        saved = obia.save(self.root, data)
        return obia.patch(self.root, 'sample', 'cache', {
            'sections': {'Renderer accounting': 'Ledger totals retain unknown costs. [S1]',
                         'Deferred diagnostics': 'Unrelated trace research. ' * 100,
                         'Open questions': 'Storage reliability remains uncertain. [S1]',
                         'Corrections': 'Never use old stored totals. [S1]'}}, saved['sha256'])

    def test_selects_complete_relevant_sections_with_atomic_core_and_sources(self):
        saved = self.prepare()
        before = (self.root / saved['path']).read_bytes()
        packet = obia.recall(self.root, 'sample', task='cache', focus='renderer ledger')
        item = packet['notes'][0]
        self.assertEqual(item['sha256'], saved['sha256'])
        for name in ('Resume', 'Constraints', 'Corrections', 'Open questions', 'Renderer accounting'):
            self.assertIn(name, item['included_sections'])
            self.assertIn(obia.read_note(self.root,'sample','cache',section_names=[name])['content'].strip(), item['content'])
        self.assertIn('Deferred diagnostics', item['omitted_sections'])
        self.assertNotIn('Unrelated trace research', item['content'])
        self.assertIn('S1', item['source_definitions'])
        self.assertEqual(before, (self.root / saved['path']).read_bytes())
        self.assertEqual(packet, obia.recall(self.root, 'sample', task='cache', focus='renderer ledger'))

    def test_hypothesis_without_focus_match_and_selected_sources(self):
        data = core.payload()
        data['sources'].extend([
            {'id': 'S2', 'kind': 'file', 'ref': 'Synthetic renderer specification.', 'observed_at': '2026-11-20'},
            {'id': 'S3', 'kind': 'file', 'ref': 'Synthetic unrelated future work.', 'observed_at': '2026-11-20'}])
        saved = obia.save(self.root, data)
        saved = obia.patch(self.root, 'sample', 'cache', {'sections': {
            'Renderer accounting': 'Ledger sums are derived from observed usage. [S2]',
            'Deferred diagnostics': 'Future trace research. [S3]',
            'Hypotheses': 'Storage reliability might depend on local synchronization. [S1]',
            'Hipóteses': 'Uma hipótese ainda sem confirmação. [S1]'}}, saved['sha256'])
        result = obia.recall(self.root, 'sample', task='cache', focus='renderer ledger')['notes'][0]
        self.assertIn('Hypotheses', result['included_sections'])
        self.assertIn('Hipóteses', result['included_sections'])
        self.assertIn('Storage reliability might depend on local synchronization.', result['content'])
        self.assertIn('S2', result['source_definitions'])
        self.assertIn('Synthetic renderer specification.', result['source_definitions']['S2'])
        self.assertNotIn('S3', result['source_definitions'])
        self.assertIn('Deferred diagnostics', result['omitted_sections'])
        self.assertEqual(result['sha256'], saved['sha256'])
        other = obia.recall(self.root, 'sample', task='cache', focus='zzzz')['notes'][0]
        self.assertNotIn('S2', other['source_definitions'])
        self.assertIn('Renderer accounting', other['omitted_sections'])
        self.assertIn('Hypotheses', other['included_sections'])

    def test_budget_defers_core_never_truncates_and_reports_relevant_omissions(self):
        saved = self.prepare()
        saved = obia.patch(self.root,'sample','cache',{'sections':{'Renderer accounting':'Ledger ' * 3000}},saved['sha256'])
        for budget in (1024,2048,4000,12000):
            result=obia.recall(self.root,'sample',task='cache',focus='ledger',budget=budget)
            self.assertLessEqual(len(json.dumps(result,ensure_ascii=False,indent=2))+1,budget)
            if result['notes'][0]['view']=='focused':
                self.assertIn('Renderer accounting',result['notes'][0]['matched_sections'])
                self.assertIn('Renderer accounting',result['notes'][0]['omitted_sections'])
                self.assertEqual(result['notes'][0]['omission_reasons']['Renderer accounting'],'matched but exceeds packet budget')
            else:
                self.assertEqual(result['notes'][0]['read_required'],'full')
        obia.patch(self.root,'sample','cache',{'sections':{'Constraints':'Critical boundary ' * 1000}},saved['sha256'])
        result=obia.recall(self.root,'sample',task='cache',focus='ledger',budget=4000)
        self.assertEqual(result['notes'][0]['view'],'deferred')
        self.assertNotIn('content',result['notes'][0])

    def test_no_match_and_invalid_focus_and_cli(self):
        self.prepare()
        item=obia.recall(self.root,'sample',task='cache',focus='zzzzz')['notes'][0]
        self.assertEqual(item['matched_sections'],[])
        self.assertIn('Renderer accounting',item['omitted_sections'])
        for focus in ('','???','x'*2001,12):
            with self.assertRaises(obia.ObiaError):obia.recall(self.root,'sample',task='cache',focus=focus)
        with self.assertRaises(obia.ObiaError):obia.recall(self.root,'sample',query='cache',focus='ledger')
        result=self.invoke('recall','--project','sample','--task','cache','--focus','ledger')
        self.assertIn('Renderer accounting',result['notes'][0]['included_sections'])

    def test_nonstandard_note_full_fallback_and_stale_evidence_rejected(self):
        saved=self.prepare();path=self.root/saved['path']
        original=path.read_text();path.write_text(original.replace('obia: 1','obia: 1\nhuman_limit: preserve'))
        result=obia.recall(self.root,'sample',task='cache',focus='ledger')
        self.assertEqual(result['notes'][0]['view'],'full')
        self.assertIn('human_limit',result['notes'][0]['content'])
        with self.assertRaises(obia.ObiaError):obia.read_note(self.root,'sample','cache',expected=saved['sha256'])
