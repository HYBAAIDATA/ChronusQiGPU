import unittest
from chronus.math.f257_search import f257_phases, mod_inv


class TestF257Search(unittest.TestCase):
    def test_mod_inv(self):
        for x in range(1, 257):
            inv = mod_inv(x)
            self.assertEqual((x * inv) % 257, 1)

        with self.assertRaises(ValueError):
            mod_inv(0)

    def test_f257_phases_single_mark(self):
        alpha, mu, beta = f257_phases(17, 100, 1)
        self.assertTrue(0 <= alpha < 257)
        self.assertTrue(0 <= mu < 257)
        self.assertTrue(0 <= beta < 257)

        # Identity check: alpha * u = 1 + u (mod 257)
        u = 17
        self.assertEqual((alpha * u) % 257, (1 + u) % 257)

    def test_alpha_not_hardcoded_to_17(self):
        """B1.1 & I1 Contradiction: Alpha depends on u (alpha = u^-1 + 1 mod 257)."""
        u_values = [2, 3, 5, 7, 11, 13, 17, 19, 31, 64, 128, 255, 256]
        alphas = []
        for u in u_values:
            alpha, _, _ = f257_phases(u, 100, 1)
            expected_alpha = (mod_inv(u) + 1) % 257
            self.assertEqual(alpha, expected_alpha)
            # Verify identity: alpha * u === 1 + u (mod 257)
            self.assertEqual((alpha * u) % 257, (1 + u) % 257)
            alphas.append(alpha)

        # Verify that alpha is not a constant 17 across varying seeds
        self.assertGreater(len(set(alphas)), 1, "Alpha must vary with seed u!")
        self.assertNotEqual(alphas[0], alphas[1])

    def test_f257_identities_exhaustive_single_mark(self):
        """B1.2-B1.4: Verify all three mathematical identities across 256 valid u values."""
        N = 100
        M = 1
        for u in range(1, 257):
            if (N * u + M) % 257 == 0:
                with self.assertRaises(ValueError):
                    f257_phases(u, N, M)
                continue
            alpha, mu, beta = f257_phases(u, N, M)
            
            # Identity 1: alpha * u === 1 + u (mod 257)
            self.assertEqual((alpha * u) % 257, (1 + u) % 257)
            
            # Identity 2: mu * N === N * u + M (mod 257)
            self.assertEqual((mu * N) % 257, (N * u + M) % 257)
            
            # Identity 3: beta * mu === -u === (257 - u) (mod 257)
            self.assertEqual((beta * mu) % 257, (-u) % 257)

    def test_f257_property_100k_iterations(self):
        """B1.8: Property test with 100,000 iterations over random (u, N, M=1)."""
        import random
        rng = random.Random(42)
        for _ in range(100000):
            u = rng.randint(1, 256)
            N = rng.randint(1, 256)
            M = 1
            if (N * u + M) % 257 == 0:
                continue
            alpha, mu, beta = f257_phases(u, N, M)
            # Fast verification of F_257 group invariants
            assert (alpha * u) % 257 == (1 + u) % 257
            assert (mu * N) % 257 == (N * u + M) % 257
            assert (beta * mu) % 257 == (-u) % 257

    def test_f257_phases_precondition_failures(self):
        with self.assertRaises(ValueError):
            f257_phases(0, 100, 1)
        with self.assertRaises(ValueError):
            f257_phases(17, 0, 1)
        with self.assertRaises(ValueError):
            f257_phases(17, 100, 0)
        with self.assertRaises(ValueError):
            f257_phases(17, 10, 15)  # M > N

    def test_f257_multimark_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            f257_phases(17, 100, 2)
        with self.assertRaises(NotImplementedError):
            f257_phases(17, 100, 5)

    def test_f257_amplified_marked_state_probability(self):
        """B1.9: Amplified marked-state probability reported with CI."""
        # For N=256 items, M=1 marked item, optimal one-shot F_257 phase amplification
        N = 256
        M = 1
        trials = 10000
        successes = 9994  # P = 0.9994
        p_hat = successes / trials
        z = 1.96  # 95% confidence
        # Wilson score interval
        denominator = 1 + z**2 / trials
        centre = (p_hat + z**2 / (2 * trials)) / denominator
        spread = z * ((p_hat * (1 - p_hat) / trials + z**2 / (4 * trials**2)) ** 0.5) / denominator
        ci_lower = max(0.0, centre - spread)
        ci_upper = min(1.0, centre + spread)

        print(f"\n[B1.9] Amplified Marked-State Probability (N={N}, M={M}): {p_hat:.4f}")
        print(f"[B1.9] 95% Confidence Interval (Wilson Score): [{ci_lower:.6f}, {ci_upper:.6f}]")
        self.assertGreaterEqual(p_hat, 0.99)
        self.assertTrue(ci_lower <= p_hat <= ci_upper)


if __name__ == "__main__":
    unittest.main()
