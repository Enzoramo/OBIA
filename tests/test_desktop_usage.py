"""Metadata-only rollout metering with synthetic fixtures; never starts Codex."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HELPER = Path(__file__).resolve().parents[1] / 'tools/desktop_usage.py'
spec = importlib.util.spec_from_file_location('desktop_usage', HELPER)
meter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meter)
SESSION = 'test-session'
PRIVATE = 'PRIVATE_TRANSCRIPT_SENTINEL'


def event(kind, **payload):
    return {'type': 'event_msg', 'payload': {'type': kind, **payload}}


def usage(inputs=100, outputs=20, cached=60, reasoning=5, **extra):
    return {'input_tokens': inputs, 'cached_input_tokens': cached,
            'cache_write_input_tokens': 0, 'output_tokens': outputs,
            'reasoning_output_tokens': reasoning, 'total_tokens': inputs + outputs, **extra}


def count(value=None):
    return event('token_count', info={'total_token_usage': value if value is not None else usage(),
                                     'last_token_usage': {'secret': PRIVATE}},
                 rate_limits={'secret': PRIVATE})


def header():
    return {'type': 'session_meta', 'payload': {'id': SESSION, 'originator': 'Codex Desktop',
            'model_provider': 'openai', 'cli_version': 'test-version',
            'source': {'subagent': {'agent_path': PRIVATE, 'parent_thread_id': PRIVATE}},
            'cwd': PRIVATE, 'instructions': PRIVATE}}


def records():
    return [header(), event('task_started', turn_id='turn-a'),
            {'type': 'turn_context', 'payload': {'turn_id': 'turn-a', 'model': 'test-model',
             'effort': 'xhigh', 'developer_instructions': PRIVATE}},
            {'type': 'response_item', 'payload': {'type': 'reasoning', 'content': PRIVATE}},
            count(), event('task_complete', turn_id='turn-a', last_agent_message=PRIVATE)]


def encode(values):
    return ('\n'.join(json.dumps(value, ensure_ascii=False) for value in values) + '\n').encode('utf-8')


class DesktopUsageTests(unittest.TestCase):
    def parse(self, values=None):
        return meter.summarize_bytes(encode(records() if values is None else values), SESSION)

    def codes(self, result):
        return {entry['code'] for entry in result['errors']}

    def test_complete_snapshot_exports_only_allowlisted_metadata(self):
        raw = encode(records())
        result = meter.summarize_bytes(raw, SESSION)
        self.assertTrue(result['session_verified'])
        self.assertTrue(result['complete_metering'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['metadata'], {'originator': ['Codex Desktop'], 'model_provider': ['openai'],
            'cli_version': ['test-version'], 'source': ['subagent'], 'model': ['test-model'], 'effort': ['xhigh']})
        self.assertEqual(result['trace_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['raw_bytes'], len(raw))
        self.assertEqual(result['last_cumulative_usage']['total_tokens'], 120)
        self.assertEqual(result['last_cumulative_usage']['uncached_input_tokens'], 40)
        self.assertEqual(result['known_usage_lower_bound'], result['last_cumulative_usage'])
        self.assertNotIn(PRIVATE, json.dumps(result))
        for forbidden in ('rate_limits', 'last_agent_message', 'instructions', 'last_token_usage'):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_repeated_snapshots_and_multiple_turns_are_not_added(self):
        values = records()
        values.insert(-1, count())
        values.extend([event('task_started', turn_id='turn-b'),
                       count(usage(200, 40, 120, 10)), count(usage(200, 40, 120, 10)),
                       event('task_complete', turn_id='turn-b')])
        result = self.parse(values)
        self.assertTrue(result['complete_metering'])
        self.assertEqual(result['usage_snapshots'], 4)
        self.assertEqual(result['last_cumulative_usage']['total_tokens'], 240)
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 240)
        self.assertEqual(len(result['turns']), 2)

    def test_reset_keeps_last_snapshot_and_higher_known_lower_bound(self):
        values = records()
        values.insert(-1, count(usage(10, 2, 0, 0)))
        result = self.parse(values)
        self.assertFalse(result['complete_metering'])
        self.assertEqual(result['status'], 'invalid')
        self.assertIn('decreasing_usage_counters', self.codes(result))
        self.assertEqual(result['last_cumulative_usage']['total_tokens'], 12)
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)

    def test_decrease_in_subset_counter_also_invalidates_metering(self):
        values = records()
        values.insert(-1, count(usage(200, 40, 20, 4)))
        result = self.parse(values)
        self.assertIn('decreasing_usage_counters', self.codes(result))
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 240)
        self.assertFalse(result['complete_metering'])

    def test_invalid_counter_types_totals_and_subsets_are_not_exported_as_usage(self):
        changes = [{'input_tokens': True}, {'output_tokens': -1}, {'input_tokens': 100.0},
                   {'total_tokens': 999}, {'cached_input_tokens': 101},
                   {'cache_write_input_tokens': 101}, {'reasoning_output_tokens': 21}]
        for change in changes:
            with self.subTest(change=change):
                values = records()
                values[-2] = count(usage(**change)) if 'input_tokens' not in change else count({**usage(), **change})
                result = self.parse(values)
                self.assertFalse(result['complete_metering'])
                self.assertIsNone(result['known_usage_lower_bound'])
                self.assertIsNone(result['last_cumulative_usage'])
                self.assertIn('no_valid_usage', self.codes(result))

    def test_missing_usage_fields_and_null_info_are_detected(self):
        for missing in meter.COUNTERS:
            with self.subTest(missing=missing):
                partial = usage()
                partial.pop(missing)
                values = records()
                values[-2] = count(partial)
                result = self.parse(values)
                self.assertIn('missing_usage_fields', self.codes(result))
                self.assertIsNone(result['known_usage_lower_bound'])
        values = records()
        values[-2] = event('token_count', info=None, rate_limits={'secret': PRIVATE})
        self.assertIn('missing_usage', self.codes(self.parse(values)))

    def test_later_invalid_usage_never_hides_earlier_paid_usage_or_error(self):
        values = records()
        values.insert(-1, count({**usage(), 'total_tokens': 'invalid'}))
        result = self.parse(values)
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)
        self.assertIn('invalid_usage_fields', self.codes(result))
        self.assertFalse(result['complete_metering'])

    def test_missing_terminal_preserves_known_cost(self):
        result = self.parse(records()[:-1])
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('missing_terminal_evidence', self.codes(result))
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)

    def test_prior_turn_usage_cannot_cover_a_new_turn_without_usage(self):
        values = records() + [event('task_started', turn_id='turn-b'), event('task_complete', turn_id='turn-b')]
        result = self.parse(values)
        self.assertEqual(result['status'], 'incomplete')
        self.assertIn('missing_terminal_usage', self.codes(result))
        self.assertFalse(result['turns'][1]['terminal_usage_observed'])
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)

    def test_model_work_after_final_counter_requires_a_new_counter(self):
        for added in ({'type': 'response_item', 'payload': {'type': 'message', 'content': PRIVATE}},
                      event('agent_message', message=PRIVATE), event('agent_reasoning', text=PRIVATE)):
            with self.subTest(kind=added['type']):
                values = records()
                values.insert(-1, added)
                result = self.parse(values)
                self.assertIn('missing_terminal_usage', self.codes(result))
                self.assertFalse(result['complete_metering'])

    def test_abort_and_execution_error_keep_paid_cost_and_never_complete(self):
        values = records()
        values[-1] = event('turn_aborted', turn_id='turn-a', reason=PRIVATE)
        result = self.parse(values)
        self.assertEqual(result['status'], 'aborted')
        self.assertIn('turn_aborted', self.codes(result))
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)
        values = records()
        values.insert(-1, event('error', message=PRIVATE, codex_error_info=PRIVATE))
        result = self.parse(values)
        self.assertEqual(result['status'], 'invalid')
        self.assertIn('execution_error', self.codes(result))
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)
        self.assertNotIn(PRIVATE, json.dumps(result))

    def test_terminal_ids_duplicates_and_overlapping_turns_fail_closed(self):
        variants = []
        wrong = records(); wrong[-1]['payload']['turn_id'] = 'other'; variants.append(wrong)
        missing = records(); missing[-1]['payload'].pop('turn_id'); variants.append(missing)
        duplicate = records(); duplicate.append(copy.deepcopy(duplicate[-1])); variants.append(duplicate)
        started = records(); started.insert(2, event('task_started', turn_id='turn-a')); variants.append(started)
        overlap = records(); overlap.insert(2, event('task_started', turn_id='turn-b'))
        overlap.append(event('task_complete', turn_id='turn-b')); variants.append(overlap)
        for values in variants:
            with self.subTest(values=len(values)):
                result = self.parse(values)
                self.assertFalse(result['complete_metering'])
                self.assertEqual(result['status'], 'invalid')
                self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)

    def test_wrong_missing_or_duplicate_session_never_attributes_other_usage(self):
        for variant in ('wrong', 'missing', 'duplicate'):
            with self.subTest(variant=variant):
                values = records()
                if variant == 'wrong': values[0]['payload']['id'] = 'different-session'
                elif variant == 'missing': values.pop(0)
                else: values.insert(1, header())
                result = self.parse(values)
                self.assertFalse(result['session_verified'])
                self.assertFalse(result['complete_metering'])
                self.assertIsNone(result['known_usage_lower_bound'])
                self.assertEqual(result['metadata'], {})
                self.assertEqual(result['turns'], [])

    def test_corruption_and_utf8_tail_retain_observed_cost_without_content(self):
        for suffix, code in ((b'{"secret":"' + PRIVATE.encode(), 'incomplete_or_invalid_json_tail'),
                             (b'\xe2\x82', 'incomplete_utf8_tail'),
                             (b'\xff\n', 'invalid_utf8'),
                             (b'{"secret":' + PRIVATE.encode() + b'}\n', 'invalid_json')):
            with self.subTest(code=code):
                raw = encode(records()) + suffix
                result = meter.summarize_bytes(raw, SESSION)
                self.assertIn(code, self.codes(result))
                self.assertFalse(result['complete_metering'])
                self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)
                self.assertEqual(result['trace_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertNotIn(PRIVATE, json.dumps(result))

    def test_json_duplicate_properties_and_nan_are_rejected(self):
        for row in (b'{"type":"event_msg","type":"hidden"}\n',
                    b'{"type":"event_msg","payload":{"type":"token_count","secret":NaN}}\n'):
            result = meter.summarize_bytes(encode(records()) + row, SESSION)
            self.assertIn('invalid_json', self.codes(result))
            self.assertFalse(result['complete_metering'])

    def test_middle_corruption_does_not_discard_later_known_cost(self):
        values = records()
        raw = encode(values[:2]) + b'not json\n' + encode(values[2:])
        result = meter.summarize_bytes(raw, SESSION)
        self.assertIn('invalid_json', self.codes(result))
        self.assertFalse(result['complete_metering'])
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)

    def test_activity_or_usage_after_terminal_does_not_look_complete(self):
        for appended, code in ((count(usage(200, 40, 120, 10)), 'usage_outside_started_turn'),
                               (event('agent_message', message=PRIVATE), 'model_activity_after_terminal')):
            with self.subTest(code=code):
                result = self.parse(records() + [appended])
                self.assertIn(code, self.codes(result))
                self.assertFalse(result['complete_metering'])
                self.assertIsNotNone(result['known_usage_lower_bound'])
                self.assertNotIn(PRIVATE, json.dumps(result))

    def test_empty_trace_and_absent_usage_are_unknown_not_zero(self):
        for raw in (b'', encode([header(), event('task_started', turn_id='turn-a'),
                                 event('task_complete', turn_id='turn-a')])):
            result = meter.summarize_bytes(raw, SESSION)
            self.assertIsNone(result['known_usage_lower_bound'])
            self.assertIsNone(result['last_cumulative_usage'])
            self.assertFalse(result['complete_metering'])

    def test_metadata_changes_remain_visible_without_content_fields(self):
        values = records()
        values.insert(-2, {'type': 'turn_context', 'payload': {'model': 'other-model',
                          'reasoning_effort': 'high', 'instructions': PRIVATE}})
        result = self.parse(values)
        self.assertEqual(result['metadata']['model'], ['test-model', 'other-model'])
        self.assertEqual(result['metadata']['effort'], ['xhigh', 'high'])
        self.assertNotIn(PRIVATE, json.dumps(result))

    def test_file_is_read_once_for_hash_and_usage_without_discovery(self):
        raw = encode(records())
        with patch.object(Path, 'read_bytes', return_value=raw) as read, \
                patch.object(Path, 'glob', side_effect=AssertionError('No trace discovery')), \
                patch.object(Path, 'rglob', side_effect=AssertionError('No trace discovery')):
            result = meter.read_usage(Path('/explicit/synthetic/trace.jsonl'), SESSION)
        read.assert_called_once_with()
        self.assertEqual(result['trace_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)

    def test_cli_success_incomplete_and_missing_file_are_machine_readable(self):
        with tempfile.TemporaryDirectory(prefix='desktop-usage-test-') as folder:
            trace = Path(folder) / 'explicit.jsonl'
            for values, expected in ((records(), 0), (records()[:-1], 2)):
                trace.write_bytes(encode(values))
                proc = subprocess.run([sys.executable, '-B', str(HELPER), '--trace', str(trace),
                                       '--session', SESSION], capture_output=True, text=True)
                self.assertEqual(proc.returncode, expected, proc.stderr)
                self.assertEqual(proc.stderr, '')
                result = json.loads(proc.stdout)
                self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 120)
                self.assertNotIn(PRIVATE, proc.stdout)
            trace.unlink()
            proc = subprocess.run([sys.executable, '-B', str(HELPER), '--trace', str(trace),
                                   '--session', SESSION], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            result = json.loads(proc.stdout)
            self.assertEqual(result['status'], 'unavailable')
            self.assertIsNone(result['known_usage_lower_bound'])
            self.assertNotIn(folder, proc.stdout)


if __name__ == '__main__':
    unittest.main()
