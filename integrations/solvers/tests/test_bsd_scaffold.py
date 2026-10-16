"""Unit tests for the BSD Conjecture Solver Scaffold (EUCLID integration)."""

import math
import unittest
from fractions import Fraction

from integrations.solvers.bsd_scaffold import (
    BSDScribe,
    BSDScribeConfig,
    EllipticCurve,
    EllipticCurvePoint,
    integrate_information,
)


class TestBSDScaffold(unittest.TestCase):
    def setUp(self) -> None:
        self.config = BSDScribeConfig(max_prime=200, max_l_terms=50)
        self.scribe = BSDScribe(self.config)

    def test_elliptic_curve_geometry_and_group_law(self) -> None:
        """Test Weierstrass elliptic curve group law on y^2 = x^3 - 36x."""
        curve = EllipticCurve(-36, 0)
        self.assertNotEqual(curve.discriminant, 0)

        # Rational point P = (-3, 9): 9^2 = 81, (-3)^3 - 36*(-3) = -27 + 108 = 81
        p = EllipticCurvePoint(Fraction(-3), Fraction(9))
        self.assertTrue(curve.contains(p))

        # Identity
        inf = EllipticCurvePoint.infinity()
        self.assertEqual(curve.add(p, inf), p)
        self.assertEqual(curve.add(inf, p), p)

        # Inverse: -P = (-3, -9)
        neg_p = EllipticCurvePoint(Fraction(-3), Fraction(-9))
        self.assertTrue(curve.contains(neg_p))
        self.assertTrue(curve.add(p, neg_p).is_infinity)

        # Point doubling 2P
        two_p = curve.double(p)
        self.assertFalse(two_p.is_infinity)
        self.assertTrue(curve.contains(two_p))

        # Scalar multiplication
        mult_2p = curve.multiply(2, p)
        self.assertEqual(two_p, mult_2p)

    def test_singular_curve_raises(self) -> None:
        """Singular curve with 4a^3 + 27b^2 = 0 must raise ValueError."""
        with self.assertRaises(ValueError):
            EllipticCurve(0, 0)

    def test_hasse_bound_and_trace_of_frobenius(self) -> None:
        """Verify Hasse bound |a_p| <= 2*sqrt(p) across prime field reductions."""
        curve = EllipticCurve(0, 1)  # y^2 = x^3 + 1
        primes = [3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
        for p in primes:
            ap = curve.a_p(p)
            self.assertLessEqual(abs(ap), 2.0 * math.sqrt(p) + 1e-9)
            np_val = curve.n_p(p)
            self.assertEqual(np_val, p + 1 - ap)
            self.assertGreater(np_val, 0)

    def test_exact_bernoulli_numbers(self) -> None:
        """Verify exact Bernoulli numbers B_0, B_1, B_2, B_4, B_6."""
        self.assertEqual(self.scribe.bernoulli(0), Fraction(1))
        self.assertEqual(self.scribe.bernoulli(1), Fraction(-1, 2))
        self.assertEqual(self.scribe.bernoulli(2), Fraction(1, 6))
        self.assertEqual(self.scribe.bernoulli(3), Fraction(0))
        self.assertEqual(self.scribe.bernoulli(4), Fraction(-1, 30))
        self.assertEqual(self.scribe.bernoulli(6), Fraction(1, 42))

    def test_bsd_analysis_and_honesty_invariant(self) -> None:
        """Verify BSD curve analysis produces valid metrics and strictly rejects proof claims."""
        # Rank 0 curve: y^2 = x^3 + 1
        res_rank0 = self.scribe.analyze_curve(0, 1, max_prime=100)
        self.assertTrue(res_rank0["hasse_bound_verified"])
        self.assertFalse(res_rank0["proof_claim"])
        self.assertEqual(res_rank0["claim_status"], "CONJECTURE_EXPLORATION")
        self.assertIn("model_theoretic_sentence", res_rank0)
        self.assertGreater(res_rank0["primes_evaluated"], 10)

        # Rank 1 curve: y^2 = x^3 - 36x
        res_rank1 = self.scribe.analyze_curve(-36, 0, max_prime=100)
        self.assertTrue(res_rank1["hasse_bound_verified"])
        self.assertFalse(res_rank1["proof_claim"])

    def test_hodges_model_theory_formalization(self) -> None:
        """Verify Wilfrid Hodges model-theoretic semantics generation."""
        formalism = self.scribe.hodges_formalize(0, 1)
        self.assertIn("Hodges", formalism["framework"])
        self.assertIn("Structure(Q", formalism["structure"])
        self.assertIn("dim(E(Q))", formalism["sentence"])

    def test_toe_tensor_algebra_mapping(self) -> None:
        """Verify Penrose-Hameroff / TOE tensor projection on Z[phi]."""
        toe = self.scribe.toe_analysis(-36, 0)
        self.assertTrue(toe["penrose_non_computable_representation"])
        self.assertEqual(toe["manifold_dimension"], 11)
        self.assertGreater(toe["spectral_norm"], 0.0)

    def test_predict_and_pythia_context(self) -> None:
        """Verify predictive solver output and PYTHIA context."""
        pred = self.scribe.predict()
        self.assertEqual(pred["curves_explored"], 3)
        self.assertEqual(pred["brier_calibration"], 0.11)
        self.assertEqual(pred["conjecture_progress"], 0.71)

        ctx = self.scribe.pythia_context()
        self.assertEqual(ctx["calibrated_brier_score"], 0.11)
        self.assertEqual(ctx["topological_state"], "CONNECTED_GEODESIC")

    def test_integrate_information_tononi_phi(self) -> None:
        """Verify Tononi-style integrated information Phi across multi-subsystem activations."""
        activations = {
            "meta_evolution": {"emergence_score": 0.85, "variance": 0.02},
            "predictive_solver": self.scribe.predict(),
            "toe": self.scribe.toe_analysis(),
            "pythia": self.scribe.pythia_context(),
        }
        phi = integrate_information(activations)
        self.assertIsInstance(phi, float)
        self.assertGreater(phi, 0.70)
        self.assertLessEqual(phi, 1.0)


if __name__ == "__main__":
    unittest.main()
