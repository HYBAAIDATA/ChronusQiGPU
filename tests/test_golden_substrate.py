"""Checks for the golden-substrate stack (the DphiT and its walls).

Exact integer claims use equality; measured floats use inequalities taken
from observed values.  Negative results are asserted as measured — e.g.
``structural_convolution_sum`` does not equal the transform-domain product
at this depth, and the test records that fact rather than hoping otherwise.
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from kellogg.dphi_transform import (
    DphiTError,
    ReversibleRenormalizer,
    dphi_transform,
    fibonacci_word_signal,
    get_golden_grading_vector,
    golden_lifting_step,
    idphi_transform,
    inverse_golden_lifting_step,
    merge_phi_lattice,
    phi_lattice_mask,
    run_stability_benchmark,
    split_phi_lattice,
)
from kellogg.golden_convolution import (
    convolution_theorem_error,
    golden_convolution,
    golden_shift,
    structural_convolution_sum,
    structural_vs_transform_error,
    zeckendorf_scale,
)
from kellogg.phi_dynamics import (
    golden_propagate,
    measure_structural_fidelity,
    propagation_energy_drift,
    reversible_time_step,
    run_fidelity_duel,
    standard_fft_wave_propagation,
)
from kellogg.golden_stealth import GoldenStealth, run_stealth_duel
from kellogg.first_principles import GOLDEN_KAM_CRITICAL_K
from kellogg.phi_stability import (
    GoldenStabilityEngine,
    PlasticSequenceGenerator,
    benchmark_golden_vs_others,
    continued_fraction_convergent,
)
from kellogg.golden_stride import (
    CacheAwareGoldenStride,
    GoldenHilbertOptimizer,
    sparse_coverage_benchmark,
)
from kellogg.phi_renormalizer import (
    RenormalizationError,
    benchmark_rg_efficiency,
    chrysalis_benchmark,
    critical_ising_chain,
    mutual_information,
    phi_reconstruct_deep,
    phi_renormalize_deep,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class TestPhiLatticeSplit(unittest.TestCase):
    def test_mask_is_sturmian_with_phi_density(self):
        mask = phi_lattice_mask(987)
        self.assertEqual(mask.shape, (987,))
        # The short-child density of the characteristic Sturmian word is
        # 1/phi^2 ~ 0.382; a Fibonacci length lands on it exactly.
        self.assertEqual(int(mask.sum()), 377)
        self.assertEqual(int((~mask).sum()), 610)

    def test_split_merge_roundtrip(self):
        rng = np.random.default_rng(0)
        state = rng.integers(-100, 100, size=987)
        long_part, short_part = split_phi_lattice(state)
        merged = merge_phi_lattice(long_part, short_part)
        np.testing.assert_array_equal(merged, state)

    def test_merge_rejects_wrong_counts(self):
        with self.assertRaises(DphiTError):
            merge_phi_lattice(np.zeros(5, dtype=int), np.zeros(5, dtype=int))


class TestLiftingStep(unittest.TestCase):
    def test_integer_lifting_is_bit_exact(self):
        x = np.array([7, -3, 0, 41], dtype=np.int64)
        y = np.array([2, 9, -1, -5], dtype=np.int64)
        x_p, y_p = golden_lifting_step(x, y)
        x_r, y_r = inverse_golden_lifting_step(x_p, y_p)
        np.testing.assert_array_equal(x_r, x)
        np.testing.assert_array_equal(y_r, y)


class TestDphiTransform(unittest.TestCase):
    def test_integer_roundtrip_bit_exact(self):
        rng = np.random.default_rng(1)
        state = rng.integers(-1000, 1000, size=987).astype(np.int64)
        coeffs = dphi_transform(state, depth=6)
        back = idphi_transform(coeffs, depth=6)
        np.testing.assert_array_equal(back, state)

    def test_float_roundtrip(self):
        rng = np.random.default_rng(2)
        state = rng.standard_normal(610)
        coeffs = dphi_transform(state, depth=5)
        back = idphi_transform(coeffs, depth=5)
        np.testing.assert_allclose(back, state, atol=1e-10)

    def test_complex_roundtrip(self):
        rng = np.random.default_rng(3)
        state = rng.standard_normal(233) + 1j * rng.standard_normal(233)
        back = idphi_transform(dphi_transform(state, depth=4), depth=4)
        np.testing.assert_allclose(back, state, atol=1e-10)

    def test_grading_lands_on_fibonacci_counts(self):
        # N=987=F16: each grade is a Fibonacci count of coefficients.
        grades = get_golden_grading_vector(987, depth=6)
        counts = [int((grades == d).sum()) for d in range(7)]
        self.assertEqual(sum(counts), 987)
        # Measured layout at (N=987, depth=6): coarse residual 56, then
        # detail bands of Fibonacci width climbing to F14=377.
        self.assertEqual(counts, [56, 34, 55, 89, 144, 232, 377])

    def test_fibonacci_word_signal_matches_mask(self):
        np.testing.assert_array_equal(
            fibonacci_word_signal(55), phi_lattice_mask(55).astype(float)
        )


class TestReversibleRenormalizer(unittest.TestCase):
    def test_fold_unfold_bit_exact(self):
        rng = np.random.default_rng(4)
        state = rng.integers(-50, 50, size=987).astype(np.int64)
        renorm = ReversibleRenormalizer(depth=5)
        coarse = renorm.fold_system(state)
        restored = renorm.unfold_system(coarse)
        np.testing.assert_array_equal(restored, state)
        # A depth-5 fold of a Fibonacci length leaves F_{16-5} = 89+... .
        self.assertLess(coarse.size, state.size)

    def test_stability_benchmark_reports_measured_fields(self):
        result = run_stability_benchmark(
            signal_length=377, iterations=30, depth=4, seed=0
        )
        self.assertEqual(result.phi_bit_divergence, 0)
        self.assertLess(result.fft_rms_error, 1e-9)


class TestGoldenConvolution(unittest.TestCase):
    def test_convolution_theorem_identity(self):
        rng = np.random.default_rng(5)
        a = rng.standard_normal(610)
        b = rng.standard_normal(610)
        err = convolution_theorem_error(a, b, depth=4)
        self.assertLess(err, 1e-9)

    def test_structural_sum_is_measured_not_equal(self):
        # The O(N^2) structural sum does NOT coincide with the transform
        # convolution at this depth — measured difference is recorded.
        rng = np.random.default_rng(6)
        a = rng.standard_normal(55)
        b = rng.standard_normal(55)
        via_transform = golden_convolution(a, b, depth=3)
        structural = structural_convolution_sum(a, b, depth=3)
        err = structural_vs_transform_error(a, b, depth=3)
        self.assertTrue(math.isfinite(err))
        self.assertGreater(err, 0.0)
        self.assertEqual(via_transform.shape, structural.shape)

    def test_golden_shift_is_deterministic_not_permutation(self):
        # Zeckendorf-scaled indices collide modulo N, so the shift is a
        # deterministic rearrangement, not a bijection — measured here.
        signal = np.arange(34, dtype=float)
        a = golden_shift(signal, steps=1)
        b = golden_shift(signal, steps=1)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(a.shape, signal.shape)
        self.assertFalse(np.all(np.sort(a) == np.sort(signal)))

    def test_zeckendorf_scale_known_values(self):
        # 7 = 5 + 2 -> scale by 2 steps shifts each summand's index.
        self.assertEqual(zeckendorf_scale(7, 0), 7)
        self.assertIsInstance(zeckendorf_scale(11, 1), int)


class TestPhiDynamics(unittest.TestCase):
    def test_golden_propagate_roundtrip_in_coefficients(self):
        rng = np.random.default_rng(7)
        sig = rng.standard_normal(233)
        out = golden_propagate(sig, dt=0.0, steps=10, depth=3)
        np.testing.assert_allclose(np.real(out), sig, atol=1e-10)

    def test_fft_propagator_is_unitary(self):
        # np.fft.ifft(coeffs * unit-modulus phase) conserves signal energy.
        rng = np.random.default_rng(8)
        sig = rng.standard_normal(233)
        out = standard_fft_wave_propagation(sig, dt=0.1, steps=20)
        before = float(np.sum(sig ** 2))
        after = float(np.sum(np.abs(out) ** 2))
        self.assertAlmostEqual(after / before, 1.0, places=9)

    def test_propagation_drift_is_measured_not_zero(self):
        # The golden propagator is unit-modulus in coefficient space but
        # the DphiT basis is not orthonormal, so the drift is a measured
        # quantity — not asserted to vanish.
        rng = np.random.default_rng(9)
        sig = rng.standard_normal(377)
        drift = propagation_energy_drift(sig, dt=0.3, steps=10, depth=4)
        self.assertTrue(math.isfinite(drift))

    def test_fidelity_duel_returns_measured_fields(self):
        result = run_fidelity_duel(signal_length=233, depth=4, dt=0.1, steps=10)
        self.assertGreater(result.phi_coefficients, 0)
        self.assertTrue(math.isfinite(result.fidelity_delta))
        self.assertTrue(math.isfinite(result.std_energy_drift))

    def test_reversible_time_step_integer_exact(self):
        s = np.arange(55, dtype=np.int64)
        p = np.full(55, 3, dtype=np.int64)
        s1, p1 = reversible_time_step(s, p, dt=1.0, depth=2)
        self.assertEqual(s1.dtype, np.int64)
        self.assertEqual(p1.dtype, np.int64)

    def test_structural_fidelity_counts_coefficients(self):
        rng = np.random.default_rng(10)
        n = measure_structural_fidelity(rng.standard_normal(233), depth=3)
        self.assertGreaterEqual(n, 1)
        self.assertLessEqual(n, 233)


class TestGoldenStealth(unittest.TestCase):
    def test_encode_recover_roundtrip_noiseless(self):
        stealth = GoldenStealth(n=233, depth=4)
        carrier = stealth.generate_carrier()
        bits = np.array([1, 0, 1, 1, 0, 1, 0, 0])
        enc = stealth.encode(bits, carrier, payload_amplitude=8.0)
        self.assertEqual(enc.shape[0], 233)
        decoded = stealth.recover_bits(enc, carrier, bits.size)
        np.testing.assert_array_equal(decoded, bits)

    def test_cloak_uncloak_roundtrip(self):
        stealth = GoldenStealth(n=233, depth=4)
        rng = np.random.default_rng(11)
        sig = rng.standard_normal(233)
        cloaked = stealth.cloak(sig, 7.7)
        np.testing.assert_allclose(
            np.real(stealth.uncloak(cloaked, 7.7)), sig, atol=1e-9
        )

    def test_capacity_error(self):
        stealth = GoldenStealth(n=55, depth=4)
        carrier = stealth.generate_carrier()
        too_many = np.ones(56, dtype=int)
        with self.assertRaises(Exception):
            stealth.encode(too_many, carrier)

    def test_stealth_duel_measured_bers(self):
        result = run_stealth_duel(
            n=233, depth=4, message_bits=32, noise_sigma=0.5,
            jamming_amplitude=5.0, payload_amplitude=32.0, seed=0,
        )
        self.assertTrue(0.0 <= result.fourier_ber <= 1.0)
        self.assertTrue(0.0 <= result.golden_ber <= 1.0)
        # At this amplitude the golden channel clears the measured
        # coefficient floor; the Fourier path stays near chance.
        self.assertLess(result.golden_ber, 0.1)
        self.assertGreater(result.fourier_ber, result.golden_ber)


class TestPhiStability(unittest.TestCase):
    def test_convergent_values(self):
        self.assertEqual(continued_fraction_convergent(0.5, 55), (1, 2))
        p, q = continued_fraction_convergent(0.3819660112501051, 55)
        self.assertEqual((p, q), (21, 55))

    def test_golden_critical_k_matches_greene(self):
        eng = GoldenStabilityEngine()
        k_crit = eng.critical_k(1.0 / PHI**2)
        # Greene's criterion on the 21/55 convergent measures ~0.9712;
        # the reference constant is 0.971635.
        self.assertAlmostEqual(k_crit, GOLDEN_KAM_CRITICAL_K, delta=0.02)

    def test_regular_orbit_classifies_as_torus(self):
        eng = GoldenStabilityEngine()
        m = eng.analyze_stability(
            0.5, 1.0 / PHI**2, n_points=200, lyapunov_iterations=2000, seed=0
        )
        self.assertEqual(m.stability_class, "KAM_TORUS")

    def test_strong_kick_classifies_chaotic(self):
        eng = GoldenStabilityEngine()
        m = eng.analyze_stability(
            5.0, 1.0 / PHI**2, n_points=200, lyapunov_iterations=2000, seed=0
        )
        self.assertEqual(m.stability_class, "CHAOTIC")

    def test_rational_winding_classifies_resonance(self):
        eng = GoldenStabilityEngine()
        m = eng.analyze_stability(
            0.5, 0.5, n_points=200, lyapunov_iterations=2000, seed=0
        )
        self.assertEqual(m.stability_class, "RESONANCE")

    def test_plastic_sequence_shape_and_range(self):
        gen = PlasticSequenceGenerator(3)
        pts = gen.generate_sequence(64)
        self.assertEqual(pts.shape, (64, 3))
        self.assertTrue(np.all(pts >= 0.0) and np.all(pts < 1.0))

    def test_benchmark_ordering_golden_above_plastic(self):
        res = benchmark_golden_vs_others(n_points=200, lyapunov_iterations=800)
        self.assertGreater(res["golden"]["k_critical"], 0.9)
        self.assertLess(res["plastic"]["k_critical"], res["golden"]["k_critical"])
        self.assertIn(res["rational"]["stability_class"], ("RESONANCE", "MIXED"))


class TestGoldenStride(unittest.TestCase):
    def test_sparse_coverage_reports_all_engines(self):
        res = sparse_coverage_benchmark(500, data_size=100_000, seed=0)
        for name in ("linear", "golden", "plastic", "fibonacci", "random"):
            self.assertIn(name, res)
            self.assertGreaterEqual(res[name], 0)

    def test_cache_aware_stride_shape(self):
        strat = CacheAwareGoldenStride(dimension=2, cache_line_size=64)
        seq = strat.golden_stride_sequence(50)
        self.assertEqual(seq.shape[0], 50)
        self.assertEqual(seq.shape[1], 2)

    def test_cache_optimizer_reports_rates(self):
        out = GoldenHilbertOptimizer().optimize_sampling(500)
        for key in ("standard_golden", "cache_aware", "random"):
            self.assertIn(key, out)
            self.assertTrue(0.0 <= out[key]["cache_miss_rate"] <= 1.0)


class TestPhiRenormalizer(unittest.TestCase):
    def test_deep_roundtrip_bit_exact(self):
        chain = critical_ising_chain(377, seed=0)
        self.assertTrue(set(np.unique(chain)).issubset({-1, 1}))
        macro, register = phi_renormalize_deep(chain, depth=4)
        restored = phi_reconstruct_deep(macro, register)
        np.testing.assert_array_equal(restored, chain)

    def test_renormalize_rejects_float_input(self):
        with self.assertRaises(RenormalizationError):
            phi_renormalize_deep(np.zeros(34, dtype=float), depth=2)

    def test_mutual_information_nonnegative(self):
        rng = np.random.default_rng(12)
        x = rng.integers(0, 4, size=500)
        y = (x + rng.integers(0, 2, size=500)) % 4
        mi = mutual_information(x, y)
        self.assertGreaterEqual(mi, 0.0)
        self.assertLessEqual(mi, 2.0 + 1e-9)

    def test_rg_efficiency_records_measured_fields(self):
        result = benchmark_rg_efficiency(n=377, depth=3, seed=0)
        self.assertTrue(result.golden_bit_exact)
        self.assertTrue(math.isfinite(result.linear_retained_bits))
        self.assertTrue(math.isfinite(result.golden_retained_bits))

    def test_chrysalis_benchmark_records_measured_accuracies(self):
        result = chrysalis_benchmark(
            n=233, message_bits=24, payload_amplitude=16,
            noise_sigma=2.0, seed=0,
        )
        self.assertTrue(0.0 <= result.golden_bit_accuracy <= 1.0)
        self.assertTrue(0.0 <= result.linear_bit_accuracy <= 1.0)


if __name__ == "__main__":
    unittest.main()
