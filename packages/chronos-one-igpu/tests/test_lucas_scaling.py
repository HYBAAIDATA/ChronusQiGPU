import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from chronos.lucas_scaling import plan, tier

class LucasScalingTests(unittest.TestCase):
    def test_requested_tiers_are_exact_and_plannable(self):
        rows = plan((10, 12, 15, 18, 20, 31, 50, 76))
        self.assertEqual([r.exponent for r in rows], [10,12,15,18,20,31,50,76])
        self.assertEqual([r.lucas_value for r in rows[:5]], [123, 322, 1364, 5778, 15127])
        self.assertEqual(rows[-1].lucas_value.bit_length(), 53)
        self.assertEqual(rows[-1].status, 'PLANNER_ONLY')

    def test_dense_limit_is_explicit(self):
        self.assertEqual(tier(10, dense_face_limit=123).status, 'DENSE_REFERENCE_ELIGIBLE')
        self.assertEqual(tier(10, dense_face_limit=122).status, 'PLANNER_ONLY')

if __name__ == '__main__': unittest.main()
