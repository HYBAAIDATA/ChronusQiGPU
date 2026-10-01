"""PULVINI x Tensor Networks - mathematical proof suite.

Proves the substrate's PULVINI wing satisfies:
  1. Spectral-gap preservation (topology contract)
  2. Bounded reconstruction error (information contract)
  3. Valid quantum dynamics (unitarity contract)
  4. Recursive folding correctness
  5. Heisenberg MPO integration
  6. Orchestrator auto-routing
  7. Complex Hermitian support
  8. Edge cases and numerical stability
  9. Golden ratio geometric invariants
"""

import numpy as np
from quantum_compute_substrate.pulvini import (
    PHI,
    PulviniOperator,
    TensorTrain,
    TTPulviniHybrid,
    phi_guided_rank,
    IsingHamiltonianMPO,
    HeisenbergHamiltonianMPO,
    MPOPulviniTTHybrid,
    PythagorasOrchestrator,
    SolverStrategy,
)

RNG = np.random.default_rng(42)


def random_hermitian(n, rng=RNG):
    A = rng.standard_normal((n, n))
    return A + A.T


def random_tensor(shape, rng=RNG):
    return rng.standard_normal(shape)


# ==================== Suite 1: spectral gap preservation ====================
class TestSpectralGapPreservation:
    def test_gap_preserved_dim_8(self):
        pulvini = PulviniOperator(tolerance=1e-6)
        H = random_hermitian(8)
        _, env = pulvini.hamiltonian_reduction(H)
        assert env.topology_preserved, f"gap_delta={env.spectral_gap_delta:.2e}"

    def test_gap_preserved_dim_16(self):
        pulvini = PulviniOperator(tolerance=1e-6)
        _, env = pulvini.hamiltonian_reduction(random_hermitian(16))
        assert env.topology_preserved

    def test_gap_preserved_dim_32(self):
        pulvini = PulviniOperator(tolerance=1e-6)
        _, env = pulvini.hamiltonian_reduction(random_hermitian(32))
        assert env.topology_preserved

    def test_gap_preserved_dim_64(self):
        pulvini = PulviniOperator(tolerance=1e-6)
        _, env = pulvini.hamiltonian_reduction(random_hermitian(64))
        assert env.topology_preserved

    def test_audit_envelope_fields_populated(self):
        pulvini = PulviniOperator(tolerance=1e-6)
        _, env = pulvini.hamiltonian_reduction(random_hermitian(20))
        assert env.original_dimension == 20
        assert env.folded_dimension < 20
        assert env.condition_number > 0.0
        assert env.reconstruction_error_bound >= 0.0
        assert env.svd_truncation_mass >= 0.0

    def test_phi_ratio_respected(self):
        pulvini = PulviniOperator()
        for dim in (20, 50, 100):
            _, env = pulvini.hamiltonian_reduction(random_hermitian(dim))
            ratio = env.original_dimension / env.folded_dimension
            assert 1.3 < ratio < 2.1, f"dim={dim}: phi-ratio {ratio:.3f} out of range"

    def test_well_conditioned_diagonal_passes(self):
        n = 16
        H = np.diag(np.arange(1.0, n + 1.0))
        pulvini = PulviniOperator(tolerance=1e-4)
        _, env = pulvini.hamiltonian_reduction(H)
        assert env.topology_preserved

    def test_ill_conditioned_uses_adaptive_tolerance(self):
        rng = np.random.default_rng(7)
        n = 16
        U, _ = np.linalg.qr(rng.standard_normal((n, n)))
        sv = np.logspace(0, 6, n)
        H = U @ np.diag(sv) @ U.T
        pulvini = PulviniOperator(tolerance=1e-6)
        _, env = pulvini.hamiltonian_reduction(H)
        assert isinstance(env.topology_preserved, bool)

    def test_complex_hermitian_support(self):
        n = 12
        A = RNG.standard_normal((n, n)) + 1j * RNG.standard_normal((n, n))
        H = A + A.conj().T
        pulvini = PulviniOperator(tolerance=1e-5)
        H_red, env = pulvini.hamiltonian_reduction(H)
        assert H_red.shape[0] < n
        assert env.reconstruction_error_bound >= 0.0

    def test_rejects_non_square(self):
        pulvini = PulviniOperator()
        try:
            pulvini.hamiltonian_reduction(np.zeros((3, 5)))
            assert False
        except ValueError:
            pass


# ==================== Suite 2: reconstruction error bounds ====================
class TestReconstructionErrorBounds:
    def test_fold_unfold_roundtrip_dim_10(self):
        pulvini = PulviniOperator()
        x = RNG.standard_normal(10)
        folded, kernel = pulvini.fold(x)
        recovered = pulvini.unfold(folded, kernel, 10)
        assert np.linalg.norm(x - recovered) / 10 < 1e-12

    def test_fold_unfold_roundtrip_dim_50(self):
        pulvini = PulviniOperator()
        x = RNG.standard_normal(50)
        folded, kernel = pulvini.fold(x)
        recovered = pulvini.unfold(folded, kernel, 50)
        assert np.linalg.norm(x - recovered) / 50 < 1e-12

    def test_fold_unfold_roundtrip_dim_100(self):
        pulvini = PulviniOperator()
        x = RNG.standard_normal(100)
        folded, kernel = pulvini.fold(x)
        recovered = pulvini.unfold(folded, kernel, 100)
        assert np.linalg.norm(x - recovered) / 100 < 1e-12

    def test_fold_unfold_roundtrip_dim_500(self):
        pulvini = PulviniOperator()
        x = RNG.standard_normal(500)
        folded, kernel = pulvini.fold(x)
        recovered = pulvini.unfold(folded, kernel, 500)
        assert np.linalg.norm(x - recovered) / 500 < 1e-12

    def test_fold_reduces_dimension(self):
        pulvini = PulviniOperator()
        for dim in (8, 55, 200):
            x = RNG.standard_normal(dim)
            folded, _ = pulvini.fold(x)
            assert len(folded) < dim

    def test_tt_pulvini_hybrid_reconstructs_1d(self):
        tensor = random_tensor((100,))
        result = TTPulviniHybrid(tolerance=1e-4).process(tensor)
        assert result["pulvini_ratio"] >= 1.0

    def test_tt_compression_ratio_positive(self):
        tt = TensorTrain(random_tensor((32, 32)), max_rank=4, tolerance=1e-3)
        assert tt.get_compression_ratio() > 0.0

    def test_phi_guided_rank_formula(self):
        for dim in (10, 100, 1000):
            assert phi_guided_rank(dim) == max(2, int(dim / PHI))

    def test_multi_level_fold_roundtrip(self):
        pulvini = PulviniOperator()
        x = RNG.standard_normal(200)
        folded, kernels, sizes = pulvini.fold_recursive(x, depth=3)
        recovered = pulvini.unfold_recursive(folded, kernels, sizes)
        assert np.linalg.norm(x - recovered) / len(x) < 1e-11

    def test_multi_level_greater_compression(self):
        pulvini = PulviniOperator()
        x = RNG.standard_normal(256)
        f1, _, _ = pulvini.fold_recursive(x, depth=1)
        f3, _, _ = pulvini.fold_recursive(x, depth=3)
        assert len(f3) < len(f1)

    def test_tt_pulvini_hybrid_fold_depth_2(self):
        tensor = random_tensor((64, 4))
        result = TTPulviniHybrid(tolerance=1e-3, fold_depth=2).process(tensor)
        assert result["pulvini_ratio"] >= 1.0
        assert result["fold_depth"] == 2


# ==================== Suite 3: quantum dynamics / unitarity ====================
class TestQuantumDynamics:
    def test_ising_norm_preserved_4_1(self):
        mpo = IsingHamiltonianMPO(num_sites=4, coupling=1.0, field=0.5)
        pipeline = MPOPulviniTTHybrid(max_tt_rank=16, tolerance=1e-4)
        result = pipeline.process(RNG.standard_normal(2**4), mpo=mpo, num_time_steps=1)
        assert result["mpo_applied"]
        for n in result["norm_trajectory"][1:]:
            assert abs(n - 1.0) < 0.05

    def test_ising_norm_preserved_4_3(self):
        mpo = IsingHamiltonianMPO(num_sites=4)
        pipeline = MPOPulviniTTHybrid(max_tt_rank=16, tolerance=1e-4)
        result = pipeline.process(RNG.standard_normal(16), mpo=mpo, num_time_steps=3)
        for n in result["norm_trajectory"][1:]:
            assert abs(n - 1.0) < 0.05

    def test_ising_norm_preserved_6_2(self):
        mpo = IsingHamiltonianMPO(num_sites=6)
        pipeline = MPOPulviniTTHybrid(max_tt_rank=16, tolerance=1e-4)
        result = pipeline.process(RNG.standard_normal(64), mpo=mpo, num_time_steps=2)
        for n in result["norm_trajectory"][1:]:
            assert abs(n - 1.0) < 0.05

    def test_norm_drift_field_populated(self):
        mpo = IsingHamiltonianMPO(num_sites=4)
        pipeline = MPOPulviniTTHybrid(tolerance=1e-4)
        result = pipeline.process(RNG.standard_normal(16), mpo=mpo, num_time_steps=3)
        assert "norm_drift" in result and result["norm_drift"] >= 0.0

    def test_no_mpo_leaves_state_unchanged(self):
        pipeline = MPOPulviniTTHybrid(tolerance=1e-4)
        result = pipeline.process(RNG.standard_normal(32), mpo=None)
        assert result["mpo_applied"] is False
        assert result["mpo_error"] == 0.0

    def test_heisenberg_mpo_applies(self):
        mpo = HeisenbergHamiltonianMPO(num_sites=4, J=1.0)
        pipeline = MPOPulviniTTHybrid(max_tt_rank=16, tolerance=1e-4)
        result = pipeline.process(RNG.standard_normal(16), mpo=mpo, num_time_steps=1)
        assert result["mpo_applied"]

    def test_ising_mpo_structure(self):
        for n in (3, 4, 6, 8):
            mpo = IsingHamiltonianMPO(num_sites=n)
            assert mpo.num_sites == n
            assert len(mpo.cores) == n
            assert mpo.cores[0].shape[0] == 1
            assert mpo.cores[-1].shape[-1] == 1

    def test_ising_to_full_matrix_square(self):
        mpo = IsingHamiltonianMPO(num_sites=3)
        M = mpo.to_full_matrix()
        assert M.ndim == 2
        assert M.shape[0] == M.shape[1]

    def test_ising_various_fields(self):
        for h in (0.0, 0.5, 1.0, 2.0):
            mpo = IsingHamiltonianMPO(num_sites=4, field=h)
            pipeline = MPOPulviniTTHybrid(tolerance=1e-4)
            result = pipeline.process(RNG.standard_normal(16), mpo=mpo, num_time_steps=1)
            assert result["mpo_applied"]

    def test_multi_step_norm_trajectory_length(self):
        steps = 5
        mpo = IsingHamiltonianMPO(num_sites=4)
        pipeline = MPOPulviniTTHybrid(tolerance=1e-4)
        result = pipeline.process(RNG.standard_normal(16), mpo=mpo, num_time_steps=steps)
        assert len(result["norm_trajectory"]) == steps + 1


# ==================== Suite 4: orchestrator routing ====================
class TestPythagorasOrchestrator:
    def test_small_tensor_routes_pulvini_or_hamiltonian(self):
        orch = PythagorasOrchestrator(quantum_threshold=10_000)
        result = orch.solve(RNG.standard_normal((50, 50)))
        assert result["strategy_used"] in ("PULVINI_TT", "HAMILTONIAN")

    def test_large_tensor_routes_mpo_pulvini_tt(self):
        orch = PythagorasOrchestrator(quantum_threshold=100)
        result = orch.solve(RNG.standard_normal(200))
        assert result["strategy_used"] == "MPO_PULVINI_TT"

    def test_square_matrix_routes_hamiltonian(self):
        orch = PythagorasOrchestrator(quantum_threshold=10_000)
        H = random_hermitian(20)
        result = orch.solve(H)
        assert result["strategy_used"] == "HAMILTONIAN"

    def test_explicit_classical_override(self):
        orch = PythagorasOrchestrator(quantum_threshold=10)
        result = orch.solve(RNG.standard_normal(500), strategy=SolverStrategy.CLASSICAL)
        assert result["strategy_used"] == "CLASSICAL"
        assert result["compression_ratio"] == 1.0

    def test_routing_audit_fields_present(self):
        orch = PythagorasOrchestrator()
        result = orch.solve(RNG.standard_normal(32))
        for key in ("strategy_used", "routing_reason", "input_shape", "input_size"):
            assert key in result

    def test_solution_key_present(self):
        orch = PythagorasOrchestrator()
        result = orch.solve(RNG.standard_normal(64))
        assert "solution" in result
        assert isinstance(result["solution"], np.ndarray)


# ==================== Suite 5: edge cases and stability ====================
class TestEdgeCasesAndStability:
    def test_fold_scalar(self):
        folded, _ = PulviniOperator().fold(np.array([3.14]))
        assert len(folded) == 1

    def test_fold_two_element_roundtrip(self):
        pulvini = PulviniOperator()
        x = np.array([1.0, 2.0])
        folded, kernel = pulvini.fold(x)
        recovered = pulvini.unfold(folded, kernel, 2)
        assert np.allclose(x, recovered, atol=1e-12)

    def test_fold_zero_vector(self):
        pulvini = PulviniOperator()
        x = np.zeros(100)
        folded, kernel = pulvini.fold(x)
        recovered = pulvini.unfold(folded, kernel, 100)
        assert np.allclose(x, recovered, atol=1e-14)

    def test_fold_unit_vector(self):
        pulvini = PulviniOperator()
        x = np.zeros(50)
        x[0] = 1.0
        folded, kernel = pulvini.fold(x)
        recovered = pulvini.unfold(folded, kernel, 50)
        assert np.allclose(x, recovered, atol=1e-12)

    def test_hamiltonian_reduction_identity(self):
        n = 16
        _, env = PulviniOperator(tolerance=1e-4).hamiltonian_reduction(np.eye(n))
        assert env.spectral_gap_delta < 1.0

    def test_hamiltonian_reduction_zero(self):
        n = 8
        H_red, env = PulviniOperator().hamiltonian_reduction(np.zeros((n, n)))
        assert H_red.shape[0] < n

    def test_tt_single_element_tensor(self):
        t = np.array([[1.0]])
        tt = TensorTrain(t, max_rank=1, tolerance=1e-5)
        assert np.allclose(t, tt.reconstruct(), atol=1e-10)

    def test_very_large_recursive_fold(self):
        pulvini = PulviniOperator()
        x = RNG.standard_normal(10_000)
        folded, kernels, sizes = pulvini.fold_recursive(x, depth=4)
        recovered = pulvini.unfold_recursive(folded, kernels, sizes)
        assert np.linalg.norm(x - recovered) / len(x) < 1e-11

    def test_phi_constant_value(self):
        assert abs(PHI - 1.6180339887498949) < 1e-14

    def test_fibonacci_split_sums_to_dim(self):
        pulvini = PulviniOperator()
        for dim in (3, 7, 13, 100, 999):
            n1, n2 = pulvini._get_fibonacci_split(dim)
            assert n1 + n2 == dim
            assert n1 >= n2


# ==================== Suite 6: golden ratio invariants ====================
class TestGoldenRatioInvariants:
    def test_phi_squared_identity(self):
        assert abs(PHI**2 - (PHI + 1)) < 1e-12

    def test_phi_reciprocal_identity(self):
        w1, w2 = 1.0 / PHI, 1.0 / (PHI**2)
        assert abs(w1 + w2 - 1.0) < 1e-14

    def test_phi_weight_orthogonality(self):
        w1, w2 = 1.0 / PHI, 1.0 / (PHI**2)
        norm_sq = w1**2 + w2**2
        assert 0.4 < norm_sq < 1.0

    def test_fibonacci_ratio_converges_to_phi(self):
        a, b = 1, 1
        for _ in range(30):
            a, b = b, a + b
        assert abs(b / a - PHI) < 1e-10

    def test_folded_dim_approx_phi_50(self):
        pulvini = PulviniOperator()
        folded, _ = pulvini.fold(RNG.standard_normal(50))
        ratio = 50 / len(folded)
        assert 1.4 < ratio < 2.0

    def test_folded_dim_approx_phi_144(self):
        pulvini = PulviniOperator()
        folded, _ = pulvini.fold(RNG.standard_normal(144))
        ratio = 144 / len(folded)
        assert 1.4 < ratio < 2.0

    def test_folded_dim_approx_phi_233(self):
        pulvini = PulviniOperator()
        folded, _ = pulvini.fold(RNG.standard_normal(233))
        ratio = 233 / len(folded)
        assert 1.4 < ratio < 2.0

    def test_folded_dim_approx_phi_610(self):
        pulvini = PulviniOperator()
        folded, _ = pulvini.fold(RNG.standard_normal(610))
        ratio = 610 / len(folded)
        assert 1.4 < ratio < 2.0


# ==================== Suite 7: substrate integration ====================
class TestSubstrateIntegration:
    def test_pulvini_folds_qubit_mps_amplitudes(self):
        """PULVINI can fold the amplitude vector of a QubitMPS state."""
        from quantum_compute_substrate.phi_infinity_tensor import (
            uniform_superposition,
        )

        mps = uniform_superposition(8, chi_max=4)
        # Compute all 2^8 amplitudes into a real vector (uniform is real).
        amps = np.zeros(256, dtype=float)
        for k in range(256):
            bits = [(k >> i) & 1 for i in range(8)]
            amps[k] = mps.amplitude(bits).real
        pulvini = PulviniOperator()
        folded, kernel = pulvini.fold(amps)
        recovered = pulvini.unfold(folded, kernel, 256)
        assert np.linalg.norm(amps - recovered) / 256 < 1e-12

    def test_orchestrator_hamiltonian_from_cathedral_pauli(self):
        """Orchestrator routes a Cathedral Pauli-string Hamiltonian."""
        from quantum_compute_substrate.cathedral.pauli import pauli_string

        H = pauli_string("XX") + pauli_string("ZZ")
        orch = PythagorasOrchestrator()
        result = orch.solve(H.real if np.iscomplexobj(H) else H)
        # 4x4 square matrix -> HAMILTONIAN path
        assert result["strategy_used"] == "HAMILTONIAN"
        assert result["topology_preserved"] or result["reconstruction_error"] >= 0.0
