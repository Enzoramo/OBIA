import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from export_desktop_history import export


class DesktopHistoryTests(unittest.TestCase):
    def test_only_plaintext_task_and_tool_evidence_is_exported(self):
        def item(kind, **kwargs):
            return {'type': 'response_item', 'payload': {'type': kind, **kwargs}}
        rows = [
            {'type': 'session_meta', 'payload': {'id': 'test-session'}},
            item('message', role='developer', content=[{'type': 'input_text', 'text': 'PRIVATE-BOOTSTRAP'}]),
            item('message', role='user', content=[{'type': 'input_text', 'text': 'COMMON-ENVIRONMENT'}]),
            item('reasoning', encrypted_content='PRIVATE-REASONING'),
            item('message', role='assistant', phase='analysis', content=[{'type': 'output_text', 'text': 'PRIVATE-ANALYSIS'}]),
            item('agent_message', content=[{'type': 'input_text', 'text': 'task header'}, {'type': 'encrypted_content', 'encrypted_content': 'OPAQUE'}]),
            item('custom_tool_call', call_id='c', name='exec', input='read task file'),
            item('custom_tool_call_output', call_id='c', output=[{'type': 'input_text', 'text': 'actual request and source output'}]),
            item('message', role='assistant', phase='final_answer', content=[{'type': 'output_text', 'text': 'observed result'}]),
        ]
        raw = ('\n'.join(json.dumps(r) for r in rows) + '\n').encode()
        result = export(raw, 'test-session'); text = json.dumps(result)
        for forbidden in ('PRIVATE-', 'COMMON-ENVIRONMENT', 'OPAQUE'):
            self.assertNotIn(forbidden, text)
        self.assertIn('actual request and source output', text)
        self.assertIn('observed result', text)
        self.assertEqual(result['excluded'], {'encrypted_blocks': 1, 'encrypted_characters': 6})
        self.assertEqual(len(result['items']), 4)

    def test_wrong_session_and_unsupported_content_fail_without_export(self):
        raw = b'{"type":"session_meta","payload":{"id":"other"}}\n'
        with self.assertRaises(ValueError): export(raw, 'test-session')
        raw = b'{"type":"session_meta","payload":{"id":"test-session"}}\n' + b'{"type":"response_item","payload":{"type":"agent_message","content":[{"type":"image"}]}}\n'
        with self.assertRaises(ValueError): export(raw, 'test-session')
