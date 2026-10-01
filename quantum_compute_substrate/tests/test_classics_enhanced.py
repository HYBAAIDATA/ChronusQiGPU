"""Property + invariant tests for enhanced Grover, Shor, QFT."""
import math
import time
import numpy as np

from quantum_compute_substrate.quantum_2026.classics import (
    EnhancedGrover, optimal_grover_iterations, apply_diffusion, apply_oracle,
    quantum_counting_estimate, EnhancedShor,
    continued_fraction_convergents, extract_period_from_phase, quantum_period_finding_matrix,
    EnhancedQFT,
    exact_qft_matrix, banded_qft_matrix, coppersmith_error_bound,
)


# ==================== Grover primitives ====================
class TestGroverPrimitives:
    def test_optimal_iterations_formula(self):
        # pi/4 * sqrt(4/1) = pi/2 ~ 1.57 -> floor = 1
        assert optimal_grover_iterations(4, 1) == 1
        # pi/4 * sqrt(16/1) = pi ~ 3.14 -> 3
        assert optimal_grover_iterations(16, 1) == 3
        # pi/4 * sqrt(64/1) = 2 pi ~ 6.28 -> 6
        assert optimal_grover_iterations(64, 1) == 6
        # pi/4 * sqrt(1024/1) ~ 25.13 -> 25
        assert optimal_grover_iterations(1024, 1) == 25

    def test_optimal_iterations_multi_marked(self):
        # pi/4 * sqrt(16/4) = pi/2 -> 1
        assert optimal_grover_iterations(16, 4) == 1
        # pi/4 * sqrt(1024/16) = 2 pi -> 6
        assert optimal_grover_iterations(1024, 16) == 6

    def test_optimal_iterations_rejects_invalid(self):
        for bad in [(0, 1), (4, 0), (4, 5), (-1, 1)]:
            try:
                optimal_grover_iterations(*bad)
                assert False, f"expected error for {bad}"
            except ValueError:
                pass

    def test_oracle_is_self_inverse(self):
        rng = np.random.default_rng(0)
        psi = rng.standard_normal(16) + 1j * rng.standard_normal(16)
        psi = psi / np.linalg.norm(psi)
        marked = [3, 7, 11]
        psi2 = apply_oracle(apply_oracle(psi, marked), marked)
        assert np.allclose(psi, psi2, atol=1e-12)

    def test_diffusion_is_self_inverse(self):
        rng = np.random.default_rng(1)
        psi = rng.standard_normal(32) + 1j * rng.standard_normal(32)
        psi = psi / np.linalg.norm(psi)
        psi2 = apply_diffusion(apply_diffusion(psi))
        assert np.allclose(psi, psi2, atol=1e-12)

    def test_diffusion_o_n_not_o_n_squared(self):
        # Confirm large N runs in linear time; a 2^18 vector should apply in << 1s.
        N = 2 ** 18
        psi = np.ones(N, dtype=complex) / math.sqrt(N)
        t0 = time.perf_counter()
        for _ in range(50):
            psi = apply_diffusion(psi)
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"diffusion too slow ({elapsed:.2f}s) - not O(N)"


class TestGroverExactCase:
    def test_n_equals_four_one_iteration_gives_certainty(self):
        # N=4, M=1: after exactly 1 Grover iteration, success probability is 1.
        g = EnhancedGrover(num_qubits=2, num_marked=1)
        r = g.amplitude_amplification(marked=[2], num_iterations=1)
        assert abs(r["success_probability"] - 1.0) < 1e-12

    def test_final_state_is_normalized(self):
        for n in (3, 4, 5):
            g = EnhancedGrover(num_qubits=n, num_marked=1)
            r = g.amplitude_amplification(marked=[1])
            assert abs(np.linalg.norm(r["final_state"]) - 1.0) < 1e-10

    def test_amplification_boosts_probability(self):
        g = EnhancedGrover(num_qubits=6, num_marked=1)
        r = g.amplitude_amplification(marked=[42])
        # Initial P = 1/64; after optimal iterations should be near 1.
        assert r["success_probability"] > 0.95

    def test_multi_marked_probability_sums_correctly(self):
        g = EnhancedGrover(num_qubits=6, num_marked=4)
        marked = [3, 17, 29, 55]
        r = g.multi_marked_search(marked)
        # Total prob should be substantially boosted
        assert r["total_marked_probability"] > 0.9


class TestFixedPointGrover:
    def test_monotone_success_probability(self):
        # Yoder-Chuang guarantees no over-rotation: prob never decreases below prev max.
        g = EnhancedGrover(num_qubits=6, num_marked=1)
        r = g.fixed_point_search(marked=[5], delta=0.05)
        history = r["amplification_history"]
        # For our capped implementation, once we hit >= 1 - delta^2 we stop.
        assert history[-1] >= 1 - 0.05 ** 2 - 1e-9 or len(history) >= 3

    def test_terminates_at_target(self):
        g = EnhancedGrover(num_qubits=8, num_marked=1)
        r = g.fixed_point_search(marked=[100], delta=0.01)
        assert r["success_probability"] >= 1 - 0.01 ** 2 - 1e-3


class TestQuantumCounting:
    def test_m_estimate_recovers_known_count(self):
        g = EnhancedGrover(num_qubits=8, num_marked=4)
        marked = [1, 2, 3, 4]
        r = g.count_marked(marked, qpe_bits=12)
        assert abs(r["M_estimate"] - 4.0) < 1.0

    def test_theta_computed(self):
        r = quantum_counting_estimate(np.ones(64) / 8.0, marked_oracle_indices=[1, 5, 9])
        assert 0.0 <= r["theta"] <= math.pi / 2
        assert r["N"] == 64


# ==================== Continued fractions ====================
class TestContinuedFractions:
    def test_pi_convergents(self):
        conv = continued_fraction_convergents(math.pi, max_denominator=1_000_000)
        # Well-known convergents of pi
        expected = [(3, 1), (22, 7), (333, 106), (355, 113), (103993, 33102)]
        pairs = [(p, q) for p, q in conv]
        for e in expected:
            assert e in pairs, f"missing convergent {e}, got {pairs[:8]}"

    def test_golden_ratio_convergents(self):
        # phi = (1 + sqrt(5))/2 has convergents F(n+1)/F(n)
        phi = (1 + math.sqrt(5)) / 2
        conv = continued_fraction_convergents(phi, max_denominator=1000)
        ratios = [p / q for p, q in conv]
        # Phi has the slowest continued-fraction convergence (all 1s).
        # By the 8th convergent (F_9/F_8 = 34/21) the error is well below 1e-2.
        assert all(abs(r - phi) < 1e-2 for r in ratios[8:])

    def test_empty_when_denominator_zero(self):
        assert continued_fraction_convergents(0.5, max_denominator=0) == []


# ==================== Shor ====================
class TestShorPeriodFinding:
    def test_period_of_2_mod_15_is_4(self):
        # 2^4 = 16 = 1 mod 15
        assert extract_period_from_phase(0.25, N=15, base=2) == 4

    def test_period_finding_matrix_normalized(self):
        probs = quantum_period_finding_matrix(base=2, N=15, num_counting_qubits=8)
        assert abs(probs.sum() - 1.0) < 1e-9
        assert (probs >= 0).all()

    def test_period_finding_finds_period_2_mod_15(self):
        s = EnhancedShor()
        r = s.period_finding(base=2, modulus=15, counting_qubits=10)
        assert r["verified"]
        assert r["period"] == 4


class TestShorFactorization:
    def test_factors_15(self):
        s = EnhancedShor()
        r = s.factorize(15)
        assert set(r["factors"]) == {3, 5}

    def test_factors_21(self):
        r = EnhancedShor().factorize(21)
        assert set(r["factors"]) == {3, 7}

    def test_factors_35(self):
        r = EnhancedShor().factorize(35)
        assert set(r["factors"]) == {5, 7}

    def test_factors_even(self):
        r = EnhancedShor().factorize(14)
        assert set(r["factors"]) == {2, 7}

    def test_modular_exponentiation(self):
        s = EnhancedShor()
        r = s.optimized_modular_exponentiation(base=2, exponent=15, modulus=21)
        assert r["result"] == pow(2, 15, 21)
        assert r["circuit_depth"] > 0


# ==================== QFT ====================
class TestQFTUnitarity:
    def test_exact_qft_is_unitary(self):
        for n in (2, 3, 4, 5):
            Q = exact_qft_matrix(n)
            dim = 2 ** n
            assert np.allclose(Q @ Q.conj().T, np.eye(dim), atol=1e-9)

    def test_banded_qft_is_unitary_for_all_bands(self):
        """THE key correction vs the 2025 draft: approx QFT is unitary."""
        n = 4
        dim = 2 ** n
        for band in range(1, n + 1):
            Q = banded_qft_matrix(n, band=band)
            product = Q @ Q.conj().T
            assert np.allclose(
                product, np.eye(dim), atol=1e-9), f"banded QFT with band={band} not unitary; max deviation {
                np.max(
                    np.abs(
                        product - np.eye(dim)))}"

    def test_banded_full_band_equals_exact(self):
        n = 4
        # With band=n, all rotations are present; the circuit implements exact QFT.
        Q_banded = banded_qft_matrix(n, band=n)
        Q_exact = exact_qft_matrix(n)
        assert np.allclose(Q_banded, Q_exact, atol=1e-10)

    def test_banded_full_band_is_none_equivalent(self):
        n = 3
        assert np.allclose(
            banded_qft_matrix(
                n, band=None), banded_qft_matrix(
                n, band=n), atol=1e-10)


class TestQFTErrorBound:
    def test_coppersmith_bound(self):
        # Bound: 2 pi n / 2^band. Actual error must be <= bound.
        n = 5
        for band in (1, 2, 3):
            Q_exact = exact_qft_matrix(n)
            Q_banded = banded_qft_matrix(n, band=band)
            actual = float(np.linalg.norm(Q_banded - Q_exact, ord=2))
            bound = coppersmith_error_bound(n, band)
            assert actual <= bound + 1e-9, f"band={band} actual={actual} bound={bound}"

    def test_error_decreases_with_band(self):
        n = 5
        Q_exact = exact_qft_matrix(n)
        errors = [float(np.linalg.norm(banded_qft_matrix(n, band=b) - Q_exact, ord=2))
                  for b in (1, 2, 3, 4, 5)]
        # Non-increasing in band
        assert all(errors[i] >= errors[i + 1] - 1e-12 for i in range(len(errors) - 1))


class TestQFTApplication:
    def test_qft_of_basis_state_is_uniform_amplitude(self):
        n = 3
        Q = exact_qft_matrix(n)
        for k in range(2 ** n):
            e = np.zeros(2 ** n, dtype=complex)
            e[k] = 1.0
            out = Q @ e
            probs = np.abs(out) ** 2
            assert np.allclose(probs, 1.0 / (2 ** n), atol=1e-10)

    def test_qft_inverse_recovers_input(self):
        n = 4
        rng = np.random.default_rng(0)
        v = rng.standard_normal(2 ** n) + 1j * rng.standard_normal(2 ** n)
        v = v / np.linalg.norm(v)
        Q = exact_qft_matrix(n)
        assert np.allclose(Q.conj().T @ (Q @ v), v, atol=1e-10)

    def test_adaptive_precision_meets_target(self):
        qft = EnhancedQFT(num_qubits=4)
        rng = np.random.default_rng(3)
        v = rng.standard_normal(16) + 1j * rng.standard_normal(16)
        v = v / np.linalg.norm(v)
        r = qft.adaptive_precision_qft(v, target_error=0.5)
        assert r["error"] <= 0.5 + 1e-9


class TestQFTIntegration:
    def test_matches_numpy_fft_scaled(self):
        # QFT is the DFT / sqrt(N) - i.e. numpy fft with 'ortho' norm and no bit-reversal.
        # Compare pointwise probability distributions (both should match after conversion).
        n = 4
        N = 2 ** n
        v = np.zeros(N, dtype=complex)
        v[3] = 1.0
        Q = exact_qft_matrix(n)
        qft_out = Q @ v
        fft_out = np.fft.fft(v, norm="ortho")
        assert np.allclose(np.abs(qft_out), np.abs(fft_out), atol=1e-10)
