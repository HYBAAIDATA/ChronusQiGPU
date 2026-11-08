import random
import unittest
from pathlib import Path
from chronus.hw.zeckendorf import fold_to_zeckendorf, unfold, add, FIBONACCI_TABLE


class TestZeckendorf(unittest.TestCase):
    def test_round_trip_basic(self):
        test_values = [0, 1, 2, 3, 5, 8, 13, 21, 34, 100, 123456, 9999999]
        for val in test_values:
            rep = fold_to_zeckendorf(val)
            res = unfold(rep)
            self.assertEqual(res, val)

    def test_non_adjacent_invariant(self):
        for val in range(1, 2000):
            bits = fold_to_zeckendorf(val)
            for i in range(len(bits) - 1):
                self.assertFalse(bits[i] == 1 and bits[i + 1] == 1, f"Consecutive 1s for val={val}")

    def test_fibonacci_boundary_round_trips(self):
        """B2.8: Test F_k - 1, F_k, F_k + 1 boundaries for all available Fibonacci numbers."""
        for fib in FIBONACCI_TABLE[:30]:
            if fib > 1:
                rep_prev = fold_to_zeckendorf(fib - 1)
                self.assertEqual(unfold(rep_prev), fib - 1)

            rep_exact = fold_to_zeckendorf(fib)
            self.assertEqual(unfold(rep_exact), fib)

            rep_next = fold_to_zeckendorf(fib + 1)
            self.assertEqual(unfold(rep_next), fib + 1)

    def test_random_round_trip_property(self):
        """B2.8: Round-trip 50,000 random 32-bit integers."""
        rng = random.Random(12345)
        for _ in range(50000):
            val = rng.randint(0, (1 << 32) - 1)
            rep = fold_to_zeckendorf(val)
            self.assertEqual(unfold(rep), val)

    def test_zeckendorf_addition(self):
        a = 1234
        b = 5678
        rep_a = fold_to_zeckendorf(a)
        rep_b = fold_to_zeckendorf(b)
        sum_rep = add(rep_a, rep_b)
        self.assertEqual(unfold(sum_rep), a + b)

    def test_negative_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            fold_to_zeckendorf(-5)

    def test_unfold_invalid_bits(self):
        with self.assertRaises(ValueError):
            unfold([0, 1, 2])  # 2 is not a valid Zeckendorf bit

    def test_sv_hardware_file_contract_inspection(self):
        """B2.1 - B2.5: Verifies RTL source contract compliance."""
        sv_path = Path(__file__).resolve().parent.parent / "hw" / "zeckendorf_alu_32lane.sv"
        self.assertTrue(sv_path.exists(), "zeckendorf_alu_32lane.sv must exist")
        content = sv_path.read_text(encoding="utf-8")

        # B2.1: Ports check
        for port in ["clk", "rst_n", "lane_en", "a", "b", "op", "y", "valid", "nf_valid"]:
            self.assertIn(port, content)

        # B2.2: Invariant check
        self.assertIn("~|(y_next[k] & (y_next[k] >> 1))", content)

        # B2.3: No MUL op
        self.assertNotIn("OP_MUL", content)
        self.assertNotIn("* b[k]", content)

        # B2.5: 2-FF reset synchronizer
        self.assertIn("rst_sync1", content)
        self.assertIn("rst_sync2", content)


if __name__ == "__main__":
    unittest.main()
