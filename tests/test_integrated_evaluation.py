"""Accounting tests with synthetic usage fixtures; no real models or hooks run."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import evaluate_integrated_agents as integrated


class IntegratedEvaluationTests(unittest.TestCase):
    def test_paid_creation_is_retained_after_capture_failure_in_both_orders(self):
        for repeat, tamper_smoke in ((0, False), (1, False), (0, True), (1, True)):
            with self.subTest(repeat=repeat, tamper_smoke=tamper_smoke), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                calls = []
                def local_fixture_agent(folder, phase, prompt, model, effort, timeout, schema):
                    calls.append((folder.name, phase))
                    if tamper_smoke and phase == 'checkpoint':
                        (folder / 'smoke_test.py').write_text('Altered synthetic smoke fixture')
                    artifacts = folder.parent / (folder.name + '-' + phase)
                    artifacts.mkdir()
                    usage = {'input_tokens': 200 if phase == 'checkpoint' else 100, 'output_tokens': 5}
                    (artifacts / 'events.jsonl').write_text(json.dumps({'type': 'turn.completed', 'usage': usage}) + '\n')
                    return {'usage': integrated.usage_totals([usage]), 'answer': {'invalid_checkpoint': True}}, artifacts
                with patch.object(integrated, 'run_agent', side_effect=local_fixture_agent), patch.object(integrated, 'prepare_skill'), patch.object(integrated, 'grade_result'):
                    result = integrated.run_pair(root, 'short', repeat, 'synthetic-model', 'test', 1)
                self.assertEqual(set(calls), {('baseline', 'resume'), ('obia', 'checkpoint')})
                self.assertEqual(result['checkpoint_creation']['usage']['total_tokens'], 205)
                self.assertEqual(result['failures'][0]['arm'], 'obia')
                if tamper_smoke:
                    self.assertFalse(result['checkpoint_creation']['smoke_unchanged'])
                    self.assertEqual([op['operation'] for op in result['adapter_operations']], ['prepare'])
                else:
                    self.assertFalse(result['adapter_operations'][-1]['success'])
                ledger = integrated.execution_ledger(root)
                self.assertEqual(len(ledger), 2)
                self.assertEqual(sum(item['usage']['total_tokens'] for item in ledger), 310)
                persisted = json.loads((root / f'short-{repeat}/result.json').read_text())
                self.assertEqual(persisted['checkpoint_creation']['usage']['total_tokens'], 205)

    def test_missing_final_usage_remains_unknown_in_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            phase = root / 'case/obia-resume'
            phase.mkdir(parents=True)
            (phase / 'events.jsonl').write_text('{"type":"thread.started"}\npartial invalid line\n')
            entry = integrated.execution_ledger(root)[0]
            self.assertIsNone(entry['usage'])
            self.assertEqual(entry['completed_turns'], 0)

    def test_incremental_utf8_tail_does_not_lose_preceding_paid_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            phase = root / 'case/obia-resume'
            phase.mkdir(parents=True)
            raw = b'{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":5}}\n' + b'\xe2\x82'
            (phase / 'events.jsonl').write_bytes(raw)
            item = integrated.execution_ledger(root)[0]
            self.assertEqual(item['usage']['total_tokens'], 105)
            self.assertTrue(item['incomplete_utf8_tail'])
            self.assertFalse(item['encoding_error'])
            self.assertEqual(item['event_sha256'], hashlib.sha256(raw).hexdigest())

    def test_independent_grader_receives_only_answer_not_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifacts = root / 'artifacts'
            artifacts.mkdir()
            answer = {'observed_max_attempts': 2}
            result = {'answer': {'answer': answer, 'checkpoint': {'private_memory': 'synthetic'}}}
            def grade(args, **kwargs):
                self.assertEqual(json.loads(Path(args[-1]).read_text()), answer)
                return SimpleNamespace(returncode=0, stdout='{"synthetic_grade":true}')
            with patch.object(integrated.subprocess, 'run', side_effect=grade):
                integrated.grade_result(root, artifacts, result, wrapped=True)
            self.assertEqual(result['quality'], {'synthetic_grade': True})
