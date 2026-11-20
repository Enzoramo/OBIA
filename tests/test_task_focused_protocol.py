"""Check prospective grader failure behavior without running any model."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / 'tools/task_focused_eval_cases.py'
spec = importlib.util.spec_from_file_location('task_focused_cases', PATH)
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)

METADATA_CHECKS = (
    'missing_schema_rejected', 'missing_workflow_rejected',
    'unsupported_schema_rejected', 'boolean_schema_rejected',
    'float_schema_rejected', 'unsupported_workflow_rejected',
)


class TaskFocusedProtocolTests(unittest.TestCase):
    def evaluate(self, source):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            (root / 'tools/render_measurements.py').write_text(source)
            return cases.grade(root)

    def test_permissive_renderer_cannot_pass_metadata_contract(self):
        result = self.evaluate('def summarize(report): return {}\n'
                               'def render_markdown(report): return ""\n')
        self.assertEqual(result['total'], 29)
        self.assertFalse(result['all_pass'])
        for name in METADATA_CHECKS:
            self.assertFalse(result['checks'][name], name)

    def test_reject_everything_cannot_pass_functional_acceptance(self):
        result = self.evaluate('def summarize(report): raise ValueError("invalid")\n'
                               'def render_markdown(report): raise ValueError("invalid")\n')
        self.assertTrue(all(result['checks'][name] for name in METADATA_CHECKS))
        self.assertFalse(result['checks']['derived_totals_subsets_and_no_mutation'])
        self.assertFalse(result['checks']['real_final_study'])
        self.assertFalse(result['all_pass'])

    def test_wrong_exception_is_not_valid_input_rejection(self):
        result = self.evaluate('def summarize(report): raise RuntimeError("broken")\n'
                               'def render_markdown(report): return ""\n')
        for name in METADATA_CHECKS:
            self.assertFalse(result['checks'][name], name)
        self.assertFalse(result['all_pass'])


if __name__ == '__main__':
    unittest.main()
