"""Accounting/acceptance regression fixtures; no agents or hook events run."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import summarize_integrated_evaluation as summary


class IntegratedSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manual = {}
        self.report = dict(schema=1, workflow='test', model_requested='synthetic',
                           reasoning_effort='test', codex_version='test',
                           source_commit='test', repeats=1, workers=1,
                           planned_executions=6, pairs=[])
        for size in ('short', 'long'):
            name = size + '-0'
            pair = dict(case=size, repeat=0, arms={})
            for phase, cost in (('baseline-resume', 100), ('obia-checkpoint', 10), ('obia-resume', 50)):
                path = self.root / name / phase
                path.mkdir(parents=True)
                raw = (json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': cost, 'output_tokens': 1}}) + '\n').encode()
                (path / 'events.jsonl').write_bytes(raw)
                stage = dict(usage=summary.usage_totals([{'input_tokens': cost, 'output_tokens': 1}]),
                             event_sha256=hashlib.sha256(raw).hexdigest(),
                             exit_code=0, timed_out=False, protected_files_unchanged=True,
                             quality={'all_quality_checks_passed': True})
                if phase == 'obia-checkpoint':
                    pair['checkpoint_creation'] = stage
                    stage.update(implementation_unchanged=True, policy_unchanged=True,
                                 history_unchanged=True, smoke_unchanged=True)
                else:
                    pair['arms'][phase.split('-')[0]] = stage
                self.manual[name + '/' + phase] = dict(scope='pass', memory_quality='pass',
                    test_claims='consistent_with_observed_execution')
            vault = self.root / name / 'obia/vault/OBIA'
            for label, content in (('initial', b'Initial checkpoint'), ('final', b'Final checkpoint')):
                sha = hashlib.sha256(content).hexdigest()
                path = vault / ('.history/benchmark/queue/' + sha + '.md' if label == 'initial' else 'projects/benchmark/tasks/queue.md')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                stage = pair['checkpoint_creation'] if label == 'initial' else pair['arms']['obia']
                stage['receipt'] = dict(sha256=sha, verified=True, project_index_current=True, handoff_owned=True)
                stage['checkpoint' if label == 'initial' else 'final_checkpoint'] = dict(
                    sha256=sha, exists=True, status='active' if label == 'initial' else 'complete', problems=[])
            owner = vault / '.handoff/benchmark/queue.json'
            owner.parent.mkdir(parents=True)
            owner.write_text(json.dumps({'version': 1, 'sha256': sha}))
            self.report['pairs'].append(pair)
        self.persist_report()

    def persist_report(self):
        self.report['execution_ledger'] = summary.execution_ledger(self.root)
        (self.root / 'report.json').write_text(json.dumps(self.report))

    def test_complete_sample_and_post_run_note_edit(self):
        result = summary.summarize(self.root, self.manual)
        self.assertTrue(result['primary_success'])
        self.assertEqual(result['aggregate']['usage_known']['obia']['total_tokens'], 124)
        current = self.root / 'short-0/obia/vault/OBIA/projects/benchmark/tasks/queue.md'
        current.write_text('Edited after the observed receipt')
        changed = summary.summarize(self.root, self.manual)
        self.assertFalse(changed['primary_success'])
        self.assertFalse(changed['pairs'][0]['checkpoint_audit']['current_bytes_match_receipt'])
        self.assertEqual(changed['known_usage_lower_bound']['total_tokens'], 326)

    def test_failed_capture_keeps_paid_usage_and_fails_acceptance(self):
        self.report['pairs'][0]['failures'] = [{'arm': 'obia', 'type': 'HandoffError', 'error': 'private details'}]
        self.report['pairs'][0]['arms']['obia']['receipt']['verified'] = False
        self.persist_report()
        result = summary.summarize(self.root, self.manual)
        self.assertFalse(result['primary_success'])
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 326)
        self.assertNotIn('private details', json.dumps(result))

    def test_missing_audit_and_missing_stage_cannot_be_success(self):
        self.assertFalse(summary.summarize(self.root, {})['primary_success'])
        (self.root / 'short-0/obia-resume/events.jsonl').unlink()
        self.persist_report()
        result = summary.summarize(self.root, self.manual)
        self.assertFalse(result['complete_metering'])
        self.assertFalse(result['primary_success'])
        self.assertIsNone(result['aggregate']['net_token_reduction_percent'])
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 275)

    def test_changed_usage_rejected_before_export(self):
        path = self.root / 'short-0/obia-resume/events.jsonl'
        path.write_text(path.read_text() + '{}\n')
        with self.assertRaisesRegex(ValueError, 'Raw usage changed'):
            summary.summarize(self.root, self.manual)

    def test_incomplete_utf8_preserves_known_cost_without_passing(self):
        path = self.root / 'short-0/obia-resume/events.jsonl'
        path.write_bytes(path.read_bytes() + b'\xe2\x82')
        self.persist_report()
        result = summary.summarize(self.root, self.manual)
        self.assertFalse(result['primary_success'])
        self.assertFalse(result['complete_metering'])
        self.assertEqual(result['known_usage_lower_bound']['total_tokens'], 326)
