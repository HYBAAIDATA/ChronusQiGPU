import unittest
from scripts.ci.determinism_check import run_pipeline_deterministic


class TestDeterminism(unittest.TestCase):
    def test_bit_identical_seeded_runs(self):
        h1 = run_pipeline_deterministic(42)
        h2 = run_pipeline_deterministic(42)
        h3 = run_pipeline_deterministic(42)
        self.assertEqual(h1, h2)
        self.assertEqual(h2, h3)


if __name__ == "__main__":
    unittest.main()
