"""Regression expectations for the frozen baseline, not acceptance tests for a future solver."""
import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('arc_regression_runner', HERE / 'arc_agi_runner.py')
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)
runner.DATA_DIR = HERE.parent / 'data' / 'training'


class FrozenRunnerRegression(unittest.TestCase):
    def test_original_known_solve(self):
        self.assertTrue(runner.evaluate_arc_task('007bbfb7')['all_passed'])

    def test_second_training_solve(self):
        self.assertTrue(runner.evaluate_arc_task('c59eb873')['all_passed'])

    def test_recorded_wrong_transform(self):
        self.assertFalse(runner.evaluate_arc_task('00d62c1b')['all_passed'])

    def test_recorded_unsupported_fallback(self):
        result = runner.evaluate_arc_task('017c7c7b')
        self.assertEqual(result['rule_discovered'], 'component_recolor')
        self.assertFalse(result['all_passed'])


if __name__ == '__main__':
    unittest.main()
