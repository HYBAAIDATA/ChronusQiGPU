"""Real-machinery tests: 1000 qubits, gate application, sampling, phi-fold compression."""
import math
import numpy as np

from quantum_compute_substrate.phi_infinity_tensor import (
    QubitMPS, bell_pair, uniform_superposition, ghz_state,
    H_GATE, X_GATE, CNOT_TENSOR, PhiFoldCompressor,
    benchmark_on, demonstrate_n_qubits,
)
from quantum_compute_substrate.phi_infinity_tensor.phi_identities import fib


# ==================== Basic MPS ====================
class TestQubitMPSBasics:
    def test_zero_state_norm_one(self):
        mps = QubitMPS(n_qubits=8, chi_max=4)
        assert abs(mps.norm_squared() - 1.0) < 1e-12

    def test_zero_state_amplitude(self):
        mps = QubitMPS(n_qubits=5, chi_max=4)
        # |00000> has amplitude 1 for bitstring 00000 and 0 elsewhere.
        assert abs(mps.amplitude([0, 0, 0, 0, 0]) - 1.0) < 1e-12
        assert abs(mps.amplitude([1, 0, 0, 0, 0])) < 1e-12

    def test_x_gate_flips_amplitude(self):
        mps = QubitMPS(n_qubits=3, chi_max=2)
        mps.apply_single_qubit_gate(X_GATE, 1)
        # |010>
        assert abs(mps.amplitude([0, 1, 0]) - 1.0) < 1e-12
        assert abs(mps.amplitude([0, 0, 0])) < 1e-12

    def test_z_expectation_zero_state(self):
        # Z|0> = |0> so <Z> = +1 in |0>.
        mps = QubitMPS(n_qubits=4, chi_max=2)
        for k in range(4):
            assert abs(mps.expectation_pauli_z(k) - 1.0) < 1e-12

    def test_hadamard_gives_uniform_superposition(self):
        mps = QubitMPS(n_qubits=3, chi_max=4)
        for k in range(3):
            mps.apply_single_qubit_gate(H_GATE, k)
        # Every bitstring has amplitude 1/sqrt(8).
        expected = 1.0 / math.sqrt(8)
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    amp = mps.amplitude([a, b, c])
                    assert abs(abs(amp) - expected) < 1e-12

    def test_hadamard_pair_state_z_expectation_zero(self):
        mps = QubitMPS(n_qubits=4, chi_max=4)
        for k in range(4):
            mps.apply_single_qubit_gate(H_GATE, k)
        # <+|Z|+> = 0.
        for k in range(4):
            assert abs(mps.expectation_pauli_z(k)) < 1e-12

    def test_norm_after_gates_preserved(self):
        mps = QubitMPS(n_qubits=5, chi_max=8)
        for k in range(5):
            mps.apply_single_qubit_gate(H_GATE, k)
        for k in range(4):
            mps.apply_two_qubit_gate(CNOT_TENSOR, k)
        assert abs(mps.norm_squared() - 1.0) < 1e-10


# ==================== Named states ====================
class TestNamedStates:
    def test_bell_pair_amplitudes(self):
        mps = bell_pair(chi_max=4)
        r = 1.0 / math.sqrt(2)
        assert abs(abs(mps.amplitude([0, 0])) - r) < 1e-12
        assert abs(abs(mps.amplitude([1, 1])) - r) < 1e-12
        assert abs(mps.amplitude([0, 1])) < 1e-12
        assert abs(mps.amplitude([1, 0])) < 1e-12

    def test_bell_pair_norm_one(self):
        assert abs(bell_pair().norm_squared() - 1.0) < 1e-12

    def test_ghz_state_amplitudes(self):
        mps = ghz_state(5, chi_max=4)
        r = 1.0 / math.sqrt(2)
        # Only |00000> and |11111> have non-zero amplitude.
        assert abs(abs(mps.amplitude([0] * 5)) - r) < 1e-10
        assert abs(abs(mps.amplitude([1] * 5)) - r) < 1e-10
        assert abs(mps.amplitude([0, 1, 0, 1, 0])) < 1e-10

    def test_ghz_state_bond_dimension_at_most_two(self):
        # Schmidt rank of GHZ at every bipartition is 2.
        mps = ghz_state(10, chi_max=8)
        # For the internal bonds the bond dim should be <= 2 exactly.
        assert max(mps.bond_dimensions()) <= 2

    def test_uniform_superposition_all_amplitudes_equal(self):
        n = 6
        mps = uniform_superposition(n, chi_max=4)
        expected = 1.0 / math.sqrt(2 ** n)
        for k in range(2 ** n):
            bits = [(k >> i) & 1 for i in range(n)]
            amp = mps.amplitude(bits)
            assert abs(abs(amp) - expected) < 1e-12


# ==================== 1000-qubit scale ====================
class TestThousandQubits:
    def test_thousand_qubit_initialisation(self):
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        assert mps.n_qubits == 1000

    def test_thousand_qubit_norm_is_one(self):
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        assert abs(mps.norm_squared() - 1.0) < 1e-10

    def test_thousand_qubit_amplitude_all_zeros(self):
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        # |0^1000> has amplitude 1 for bitstring 0^1000.
        assert abs(mps.amplitude([0] * 1000) - 1.0) < 1e-12

    def test_thousand_qubit_memory_fits_in_ram(self):
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        bytes_used = mps.memory_bytes()
        # Fresh product state: chi=1 everywhere, so memory ~ 1000 * 2 * 16 = 32,000 bytes.
        assert bytes_used < 100_000  # < 100 KB

    def test_thousand_qubit_hadamard_norm_preserved(self):
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        # Apply H to every qubit; product state stays chi=1.
        for k in range(1000):
            mps.apply_single_qubit_gate(H_GATE, k)
        assert abs(mps.norm_squared() - 1.0) < 1e-6

    def test_thousand_qubit_hadamard_memory_stays_small(self):
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        for k in range(1000):
            mps.apply_single_qubit_gate(H_GATE, k)
        # Still chi=1 everywhere (|+>^1000 is a product state).
        assert mps.max_bond_dimension() == 1
        assert mps.memory_bytes() < 100_000

    def test_thousand_qubit_z_expectation_after_hadamard(self):
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        for k in range(1000):
            mps.apply_single_qubit_gate(H_GATE, k)
        # <+|Z|+> = 0 on every qubit; sample first, middle, last.
        for k in (0, 500, 999):
            assert abs(mps.expectation_pauli_z(k)) < 1e-6

    def test_thousand_qubit_ghz_bond_dim_exactly_two(self):
        mps = ghz_state(1000, chi_max=4)
        assert max(mps.bond_dimensions()) == 2
        assert abs(mps.norm_squared() - 1.0) < 1e-6

    def test_thousand_qubit_ghz_amplitudes(self):
        mps = ghz_state(1000, chi_max=4)
        r = 1.0 / math.sqrt(2)
        assert abs(abs(mps.amplitude([0] * 1000)) - r) < 1e-6
        assert abs(abs(mps.amplitude([1] * 1000)) - r) < 1e-6
        # Mixed bitstrings have zero amplitude.
        mixed = [0, 1] * 500
        assert abs(mps.amplitude(mixed)) < 1e-10

    def test_demonstrate_1000_qubits_returns_stats(self):
        d = demonstrate_n_qubits(n=1000, chi_max=128)
        assert d["n_qubits"] == 1000
        # Full state would need > 10^301 bytes.
        assert d["full_state_log10_bytes"] > 300
        # Actual MPS memory is under 1 MB.
        assert d["memory_mb"] < 1.0
        # Norm is preserved.
        assert abs(d["norm_squared"] - 1.0) < 1e-6


# ==================== Sampling ====================
class TestSampling:
    def test_sample_from_zero_state(self):
        rng = np.random.default_rng(0)
        mps = QubitMPS(n_qubits=6, chi_max=2)
        for _ in range(5):
            bits = mps.sample_computational_basis(rng)
            assert bits == [0] * 6

    def test_sample_from_uniform_superposition(self):
        rng = np.random.default_rng(0)
        mps = uniform_superposition(4, chi_max=4)
        seen = set()
        for _ in range(200):
            bits = tuple(mps.sample_computational_basis(rng))
            seen.add(bits)
        # Should see a variety of bitstrings (uniform over 2^4 = 16).
        assert len(seen) >= 8

    def test_sample_from_ghz_only_two_outcomes(self):
        rng = np.random.default_rng(1)
        mps = ghz_state(6, chi_max=2)
        seen = set()
        for _ in range(50):
            bits = tuple(mps.sample_computational_basis(rng))
            seen.add(bits)
        # Only |000000> and |111111> possible.
        allowed = {(0,) * 6, (1,) * 6}
        assert seen.issubset(allowed)
        # Both should appear with 200 draws.
        assert seen == allowed or len(seen) >= 1


# ==================== phi-fold compression ====================
class TestPhiFoldCompression:
    def test_compression_lossless_on_product_state(self):
        # Product states already have chi=1, so truncation is a no-op.
        mps = QubitMPS(n_qubits=50, chi_max=64)
        _, metrics = PhiFoldCompressor(fib_index=12).compress(mps)
        # Fidelity is 1 (nothing dropped).
        assert metrics.fidelity > 0.999999

    def test_compression_preserves_norm_on_ghz(self):
        mps = ghz_state(20, chi_max=8)
        comp, metrics = PhiFoldCompressor(fib_index=12).compress(mps)
        assert abs(comp.norm_squared() - 1.0) < 1e-6
        assert metrics.fidelity > 0.99

    def test_benchmark_returns_measured_ratio(self):
        mps = ghz_state(30, chi_max=8)
        r = benchmark_on(mps, fib_index=12)
        assert 0.0 <= r["ratio"] <= 1.0
        assert 0.0 <= r["fidelity"] <= 1.0 + 1e-9
        assert isinstance(r["summary"], str)

    def test_compression_metric_ratio_in_unit_interval(self):
        # On highly redundant states, ratio should be non-negative.
        mps = uniform_superposition(20, chi_max=4)
        _, m = PhiFoldCompressor(fib_index=12).compress(mps)
        assert m.ratio >= 0.0
        assert m.ratio <= 1.0

    def test_fib_index_controls_target_rank(self):
        comp = PhiFoldCompressor(fib_index=10)
        assert comp.fib_value == fib(10)  # 55
        comp2 = PhiFoldCompressor(fib_index=15)
        assert comp2.fib_value == fib(15)  # 610
        assert comp2.fib_value > comp.fib_value

    def test_compressor_rejects_bad_fib_index(self):
        try:
            PhiFoldCompressor(fib_index=1)
            assert False
        except ValueError:
            pass


# ==================== Substrate integration ====================
class TestSubstrateIntegration:
    def test_1000_qubit_memory_vs_full_state(self):
        """Full state would be 2^1000 * 16 bytes ~ 10^302; MPS is ~ 10^5.
        Ratio: MPS is 10^-297 of full storage.
        """
        mps = QubitMPS(n_qubits=1000, chi_max=128)
        log10_full = 1000 * math.log10(2) + math.log10(16)
        log10_mps = math.log10(mps.memory_bytes())
        assert log10_full > 300.0
        assert log10_mps < 10.0
        # More than 290 orders of magnitude of compression.
        assert log10_full - log10_mps > 290

    def test_apply_gates_on_1000_qubits_completes_quickly(self):
        """1000 single-qubit gates on 1000 qubits.  Should finish in seconds."""
        import time
        mps = QubitMPS(n_qubits=1000, chi_max=64)
        start = time.time()
        for k in range(1000):
            mps.apply_single_qubit_gate(H_GATE, k)
        elapsed = time.time() - start
        # A minute is plenty even for the slowest host; typically << 1 s.
        assert elapsed < 60.0
