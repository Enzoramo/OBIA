"""Checks for the metering and independent grader; never calls a model in CI."""
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import agent_eval_cases as cases
import evaluate_real_agents as evaluation


CORRECT = '''import json
from pathlib import Path

def select_ready(records, now, limit):
    maximum = json.loads((Path(__file__).parent / "queue_rules.json").read_text())["max_attempts"]
    result = []
    seen = set()
    if limit <= 0:
        return result
    for r in records:
        if r["cancelled"] or r["state"] not in ("pending", "retry"):
            continue
        if r["ready_at"] > now or (r["expires_at"] is not None and r["expires_at"] <= now):
            continue
        if r["attempts"] >= maximum or r["id"] in seen:
            continue
        result.append(r["id"])
        seen.add(r["id"])
        if len(result) == limit:
            break
    return result
'''


class AgentEvaluationTests(unittest.TestCase):
    def test_usage_sums_cache_as_subset_and_never_double_counts_reasoning(self):
        a = dict(input_tokens=100, cached_input_tokens=60, output_tokens=30, reasoning_output_tokens=20)
        b = dict(input_tokens=200, cached_input_tokens=80, output_tokens=40, reasoning_output_tokens=30)
        total = evaluation.usage_totals([a, b])
        self.assertEqual(total['total_tokens'], 370)
        self.assertEqual(total['uncached_input_tokens'], 160)
        self.assertEqual(total['reasoning_output_tokens'], 50)

    def test_grader_accepts_reference_and_catches_stale_retry_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases.setup(root, 'short', attempts=2)
            (root / 'queue_logic.py').write_text(CORRECT)
            answer = {'observed_max_attempts': 2, 'latency_claim_status': 'unverified',
                      'evidence_files': ['queue_rules.json']}
            grade = cases.grade(root, answer)
            self.assertEqual((grade['functional_passed'], grade['retention_passed']), (13, 3))
            (root / 'queue_logic.py').write_text(CORRECT.replace('>= maximum', '>= 3'))
            wrong = cases.grade(root, answer)
            self.assertFalse(wrong['functional']['live_retry_policy'])

    def test_grader_detects_mutation_and_unsupported_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cases.setup(root, 'short', attempts=2)
            (root / 'queue_logic.py').write_text(CORRECT.replace('    result = []', '    records.reverse()\n    result = []'))
            grade = cases.grade(root, {'observed_max_attempts': 3, 'latency_claim_status': 'verified'})
            self.assertFalse(grade['functional']['input_unchanged'])
            self.assertEqual(grade['retention_passed'], 0)

    def test_cases_have_identical_requirements_and_different_history_lengths(self):
        short, long = cases.history('short'), cases.history('long')
        self.assertGreater(len(long), len(short) * 10)
        self.assertEqual(short.split('[D000')[0], long.split('[D000')[0])
        self.assertEqual(short.split('[H06')[1], long.split('[H06')[1])
