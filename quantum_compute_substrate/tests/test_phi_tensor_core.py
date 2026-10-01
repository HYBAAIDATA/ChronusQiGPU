"""Tests for the φ-resonance tensor core."""

import numpy as np
from quantum_compute_substrate.phi_tensor_core import PhiTensorCore, FoldState


class TestFoldState:
    def test_initialization(self):
        data = np.ones(64, dtype=np.complex128) / 8
        state = FoldState(data, 0, 64)
        assert state.dim == 64
        assert abs(state.norm - 1.0) < 1e-10
        assert state.is_normalized

    def test_normalize(self):
        data = np.random.randn(64) + 1j * np.random.randn(64)
        state = FoldState(data, 0, 64)
        normalized = state.normalize()
        assert abs(normalized.norm - 1.0) < 1e-10

    def test_fold_reduces_dimension(self):
        data = np.random.randn(1024) + 1j * np.random.randn(1024)
        state = FoldState(data, 0, 1024)
        folded = state.fold(1)
        assert folded.dim < state.dim
        assert folded.depth == 1

    def test_fold_then_unfold_restores_dimension(self):
        data = np.random.randn(1024) + 1j * np.random.randn(1024)
        state = FoldState(data, 0, 1024)
        folded = state.fold(1)
        unfolded = folded.unfold()
        assert unfolded.dim == 1024
        assert unfolded.depth == 0

    def test_reconstruction_error_nonzero_for_folded(self):
        data = np.random.default_rng(42).standard_normal(1024)
        state = FoldState(data, 0, 1024)
        folded = state.fold(1)
        error = folded.reconstruction_error(state)
        assert error > 0  # fold is lossy

    def test_no_fold_at_depth_zero(self):
        data = np.ones(64, dtype=np.complex128)
        state = FoldState(data, 0, 64)
        folded = state.fold(0)
        assert folded is state


class TestPhiTensorCore:
    def test_initial_state_is_uniform_superposition(self):
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        state = core.state
        assert state.dim == 64
        assert abs(state.norm - 1.0) < 1e-10
        # All amplitudes should be equal (uniform superposition)
        assert np.allclose(np.abs(state.data), 1.0 / np.sqrt(64))

    def test_amplitude_amplification_preserves_norm(self):
        """The Grover diffusion operator is unitary — it must preserve norm."""
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        state = core._initialize_state()
        amplified = core.amplitude_amplification(state)
        assert abs(amplified.norm - 1.0) < 1e-10

    def test_amplitude_amplification_correct_formula(self):
        """Verify the implementation matches D|φ⟩ = 2⟨ψ|φ⟩|ψ⟩ - |φ⟩."""
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        rng = np.random.default_rng(42)
        state = FoldState(rng.standard_normal(64) + 1j * rng.standard_normal(64), 0, 64)
        state = state.normalize()

        amplified = core.amplitude_amplification(state)

        # Manually compute the correct Grover diffusion
        n = 64
        psi = np.ones(n, dtype=np.complex128) / np.sqrt(n)
        inner = np.vdot(psi, state.data)
        expected = 2.0 * inner * psi - state.data

        assert np.allclose(amplified.data, expected)
        assert abs(amplified.norm - 1.0) < 1e-10  # unitary

    def test_grover_oracle_flips_target_phase(self):
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        state = core._initialize_state()
        target = 10
        oracled = core.grover_oracle(state, target)
        # Target amplitude should be negated
        assert oracled.data[target] == -state.data[target]
        # All others unchanged
        for i in range(64):
            if i != target:
                assert oracled.data[i] == state.data[i]

    def test_grover_iteration_preserves_norm(self):
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        state = core._initialize_state()
        for _ in range(5):
            state = core.grover_iteration(state, target=10)
        assert abs(state.norm - 1.0) < 1e-10

    def test_tensor_product(self):
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        a = FoldState(np.ones(4, dtype=np.complex128), 0, 4)
        b = FoldState(np.ones(4, dtype=np.complex128), 0, 4)
        result = core.tensor_product(a, b)
        assert result.dim == 16

    def test_fma(self):
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        a = FoldState(np.ones(4, dtype=np.complex128), 0, 4)
        b = FoldState(np.ones(4, dtype=np.complex128) * 2, 0, 4)
        c = FoldState(np.ones(4, dtype=np.complex128) * 3, 0, 4)
        result = core.fma(a, b, c)
        assert np.allclose(result.data, np.ones(4) * 5)  # 1*2+3=5

    def test_measured_flops_positive_after_operations(self):
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        core.reset_counters()
        a = FoldState(np.ones(32, dtype=np.complex128), 0, 32)
        b = FoldState(np.ones(32, dtype=np.complex128), 0, 32)
        core.tensor_product(a, b)
        assert core.measured_flops() > 0

    def test_integrity_check(self):
        core = PhiTensorCore(core_id=0, dim=64, seed=42)
        state = core._initialize_state()
        assert PhiTensorCore.integrity_check(state)
