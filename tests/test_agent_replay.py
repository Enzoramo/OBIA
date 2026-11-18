"""Fixture replay provenance checks; never invokes a model or fabricates hook events."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_agent_evaluation import CORRECT
import agent_eval_cases as cases
import replay_agent_continuations as replay
from test_obia import payload


class ReplayTests(unittest.TestCase):
    def test_restores_initial_snapshot_reuses_usage_and_measures_only_continuation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / 'source', root / 'output'
            previous = source / 'short-0'
            memory = previous / 'obia/vault'
            memory.mkdir(parents=True)
            replay.obia.initialize(memory)
            data = payload(task='queue', project='benchmark')
            initial = replay.obia.save(memory, data)
            replay.obia.patch(memory, 'benchmark', 'queue', {'properties': {'status': 'complete'}}, initial['sha256'])
            for name in ('baseline', 'baseline-resume', 'obia-checkpoint', 'obia-resume'):
                (previous / name).mkdir(exist_ok=True)
            prompt = 'Synthetic unchanged continuation prompt'
            (previous / 'obia-resume/prompt.txt').write_text(prompt, encoding='utf-8')
            original = {'case': 'short', 'repeat': 0, 'order': 'baseline_then_obia',
                        'checkpoint_creation': {'checkpoint': initial, 'usage': {'input_tokens': 10, 'output_tokens': 2}},
                        'arms': {'baseline': {'inclusive_usage': {'total_tokens': 30}}, 'obia': {}}}
            output.mkdir()
            calls = []

            def local_test_agent(folder, phase, received_prompt, model, effort, timeout, schema):
                calls.append((phase, model, effort))
                for hidden in ('baseline', 'baseline-resume', 'obia-checkpoint'):
                    self.assertFalse((folder.parent / hidden).exists())
                self.assertEqual(received_prompt, prompt)
                self.assertEqual((folder / 'queue_logic.py').read_text(), cases.STUB)
                self.assertEqual(json.loads((folder / 'queue_rules.json').read_text()), {'max_attempts': 2})
                note = replay.obia.note(folder / 'vault', initial['path'])
                self.assertEqual(note['sha256'], initial['sha256'])
                self.assertEqual(note['status'], 'active')
                (folder / 'queue_logic.py').write_text(CORRECT, encoding='utf-8')
                replay.obia.patch(folder / 'vault', 'benchmark', 'queue', {'properties': {'status': 'complete'}}, initial['sha256'])
                artifacts = folder.parent / 'obia-resume'
                artifacts.mkdir()
                answer = {'observed_max_attempts': 2, 'latency_claim_status': 'unverified',
                          'evidence_files': ['queue_rules.json']}
                (artifacts / 'answer.json').write_text(json.dumps(answer), encoding='utf-8')
                return {'answer': answer, 'usage': {'input_tokens': 20, 'output_tokens': 3}}, artifacts

            with patch.object(replay, 'prepare_skill'), patch.object(replay, 'run_agent', side_effect=local_test_agent):
                result = replay.replay_pair(source, output, original, 'test-model', 'test-effort', 1)
            self.assertEqual(calls, [('resume', 'test-model', 'test-effort')])
            self.assertEqual(result['checkpoint_creation'], original['checkpoint_creation'])
            self.assertEqual(result['arms']['baseline'], original['arms']['baseline'])
            self.assertEqual(result['arms']['obia']['inclusive_usage']['total_tokens'], 35)
            self.assertTrue(result['arms']['obia']['quality']['all_quality_checks_passed'])
            self.assertTrue(result['arms']['obia']['protected_files_unchanged'])
            self.assertEqual(result['reused_stages'], ['baseline-resume', 'obia-checkpoint'])
            self.assertEqual(replay.obia.note(memory, initial['path'])['status'], 'complete')
