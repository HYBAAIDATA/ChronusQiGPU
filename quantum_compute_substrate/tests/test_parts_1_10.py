"""Tests for Parts 1-10: Complete quantum GPU architecture."""

import numpy as np
from quantum_compute_substrate.hilbert_space import QuantumComputeState, HilbertSpaceProcessor
from quantum_compute_substrate.unitary_transforms import UnitaryHashTransform
from quantum_compute_substrate.density_operators import DensityMatrixProcessor
from quantum_compute_substrate.natural_gradient import QuantumNaturalGradientOptimizer
from quantum_compute_substrate.tensor_networks import MatrixProductStateProcessor
from quantum_compute_substrate.amplitude_amplification import AmplitudeAmplificationProcessor
from quantum_compute_substrate.quantum_fourier import QuantumFourierProcessor
from quantum_compute_substrate.topological_protection import TopologicalProtector
from quantum_compute_substrate.quantum_kernel import QuantumKernelProcessor
from quantum_compute_substrate.variational_eigensolver import VQEOptimizer


class TestPart1HilbertSpace:
    def test_state_initialization(self):
        processor = HilbertSpaceProcessor(n_bits=4, num_workers=8)
        assert processor.dim == 16
        assert np.isclose(np.linalg.norm(processor.state.amplitudes), 1.0)

    def test_uniform_superposition(self):
        processor = HilbertSpaceProcessor(n_bits=4, num_workers=8)
        probs = np.abs(processor.state.amplitudes) ** 2
        assert np.allclose(probs, 1.0 / 16)

    def test_probability_measure(self):
        state = QuantumComputeState(np.array([0, 1, 0, 0], dtype=np.complex128), 4, 100.0)
        assert state.probability_measure(1) == 1.0
        assert state.probability_measure(0) == 0.0

    def test_expectation(self):
        state = QuantumComputeState(np.array([1, 0], dtype=np.complex128), 2, 100.0)
        Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)
        assert np.isclose(state.expectation(Z), 1.0)

    def test_grover_search(self):
        processor = HilbertSpaceProcessor(n_bits=8, num_workers=8)
        result = processor.grover_search(target=42)
        assert result["found"]
        assert result["probability"] > 0.5

    def test_coherence_time(self):
        state = QuantumComputeState(np.array([1, 0], dtype=np.complex128), 2, 250.0)
        assert state.coherence_time == 250.0


class TestPart2UnitaryTransforms:
    def test_hadamard_single(self):
        transform = UnitaryHashTransform(num_qubits=2)
        state = QuantumComputeState(np.array([1, 0, 0, 0], dtype=np.complex128), 4, 100.0)
        result = transform.hadamard_single(state, 0)
        assert np.isclose(np.linalg.norm(result.amplitudes), 1.0)

    def test_phase_shift(self):
        transform = UnitaryHashTransform(num_qubits=2)
        state = QuantumComputeState(np.array([1, 0, 0, 0], dtype=np.complex128), 4, 100.0)
        result = transform.phase_shift(state, np.pi)
        assert np.isclose(np.linalg.norm(result.amplitudes), 1.0)

    def test_qft_transform(self):
        transform = UnitaryHashTransform(num_qubits=3)
        state = QuantumComputeState(np.ones(8, dtype=np.complex128) / np.sqrt(8), 8, 100.0)
        result = transform.qft_transform(state)
        assert np.isclose(np.linalg.norm(result.amplitudes), 1.0)

    def test_inverse_qft(self):
        transform = UnitaryHashTransform(num_qubits=3)
        state = QuantumComputeState(np.ones(8, dtype=np.complex128) / np.sqrt(8), 8, 100.0)
        forward = transform.qft_transform(state)
        backward = transform.inverse_qft(forward)
        assert np.allclose(backward.amplitudes, state.amplitudes, atol=1e-10)

    def test_hash_unitary(self):
        transform = UnitaryHashTransform(num_qubits=3)
        state = QuantumComputeState(np.ones(8, dtype=np.complex128) / np.sqrt(8), 8, 100.0)
        op = transform.compute_hash_unitary(b"test_header")
        result = op(state)
        assert np.isclose(np.linalg.norm(result.amplitudes), 1.0)


class TestPart3DensityOperators:
    def test_initial_state(self):
        processor = DensityMatrixProcessor(num_workers=8, dim=4)
        assert processor.rho.shape == (4, 4)
        assert np.isclose(np.trace(processor.rho), 1.0)

    def test_entropy_maximally_mixed(self):
        processor = DensityMatrixProcessor(num_workers=8, dim=4)
        entropy = processor.measure_entropy()
        assert np.isclose(entropy, np.log(4), atol=1e-6)

    def test_purity_mixed(self):
        processor = DensityMatrixProcessor(num_workers=8, dim=4)
        purity = processor.compute_purity()
        assert np.isclose(purity, 1.0 / 4, atol=1e-6)

    def test_apply_operation(self):
        processor = DensityMatrixProcessor(num_workers=8, dim=4)
        K = np.eye(4, dtype=np.complex128) / 2
        processor.apply_quantum_operation([K])
        assert np.isclose(np.trace(processor.rho), 1.0, atol=1e-6)

    def test_partial_trace(self):
        processor = DensityMatrixProcessor(num_workers=8, dim=4)
        reduced = processor.partial_trace(2)
        assert reduced.shape[0] > 0


class TestPart4NaturalGradient:
    def test_initialization(self):
        ng = QuantumNaturalGradientOptimizer(num_params=8)
        assert ng.theta.shape == (8,)
        assert ng.fisher_matrix.shape == (8, 8)

    def test_update_parameters(self):
        ng = QuantumNaturalGradientOptimizer(num_params=4)
        grad = np.ones(4)
        old_theta = ng.theta.copy()
        ng.update_parameters(grad)
        assert not np.allclose(old_theta, ng.theta)

    def test_optimize(self):
        ng = QuantumNaturalGradientOptimizer(num_params=4)

        def loss_fn(theta):
            return float(np.sum(theta**2))

        result = ng.optimize(loss_fn, max_iterations=10)
        assert result["iterations"] > 0
        assert result["final_loss"] <= result["initial_loss"]

    def test_state_from_params(self):
        ng = QuantumNaturalGradientOptimizer(num_params=4)
        rho = ng.state_from_params(ng.theta)
        assert rho.shape[0] > 0
        assert np.isclose(np.trace(rho), 1.0, atol=1e-6)


class TestPart5TensorNetworks:
    def test_initialization(self):
        mps = MatrixProductStateProcessor(num_sites=4, bond_dim=4)
        assert len(mps.tensors) == 4

    def test_compress_state(self):
        mps = MatrixProductStateProcessor(num_sites=4, bond_dim=4)
        state = np.random.randn(16) + 1j * np.random.randn(16)
        state = state / np.linalg.norm(state)
        tensors = mps.compress_state(state)
        assert len(tensors) > 0

    def test_contract_mps(self):
        mps = MatrixProductStateProcessor(num_sites=4, bond_dim=4)
        result = mps.contract_mps()
        assert len(result) > 0

    def test_apply_local_operator(self):
        mps = MatrixProductStateProcessor(num_sites=4, bond_dim=4)
        X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
        mps.apply_local_operator(X, 0)
        assert len(mps.tensors) == 4

    def test_memory_savings(self):
        mps = MatrixProductStateProcessor(num_sites=4096, bond_dim=128)
        savings = mps.memory_savings()
        # For 4096 sites, compression is so extreme it underflows to 0.0
        # This is correct: MPS uses exponentially less memory than full state
        assert savings >= 0.0
        assert savings < 1.0  # MPS uses less memory than full state

    def test_memory_savings_small(self):
        # Use 20 sites so MPS compression is meaningful (2^20 >> 20*4^2*2)
        mps = MatrixProductStateProcessor(num_sites=20, bond_dim=4)
        savings = mps.memory_savings()
        assert savings > 0  # For 20 sites, ratio is representable and < 1
        assert savings < 1.0

    def test_get_specs(self):
        mps = MatrixProductStateProcessor(num_sites=8, bond_dim=8)
        specs = mps.get_specs()
        assert "num_sites" in specs
        assert "bond_dim" in specs


class TestPart6AmplitudeAmplification:
    def test_grover_search(self):
        processor = AmplitudeAmplificationProcessor(search_space=2**10)
        result = processor.grover_search(target=42)
        assert result is not None
        assert result == 42

    def test_apply_oracle(self):
        processor = AmplitudeAmplificationProcessor(search_space=2**8)
        state = np.ones(256, dtype=np.complex128) / np.sqrt(256)
        result = processor.apply_oracle(state, 42)
        assert result[42] == -state[42]

    def test_apply_diffusion(self):
        processor = AmplitudeAmplificationProcessor(search_space=2**8)
        state = np.ones(256, dtype=np.complex128) / np.sqrt(256)
        result = processor.apply_diffusion(state)
        assert np.isclose(np.linalg.norm(result), np.linalg.norm(state), atol=1e-6)

    def test_amplitude_estimation(self):
        processor = AmplitudeAmplificationProcessor(search_space=2**8)
        amp = processor.quantum_amplitude_estimation(target=42)
        assert amp > 0

    def test_get_specs(self):
        processor = AmplitudeAmplificationProcessor(search_space=2**8)
        specs = processor.get_specs()
        assert "search_space" in specs
        assert "theoretical_speedup" in specs


class TestPart7QuantumFourier:
    def test_qft(self):
        processor = QuantumFourierProcessor(num_qubits=3)
        state = np.ones(8, dtype=np.complex128) / np.sqrt(8)
        result = processor.qft(state)
        assert np.isclose(np.linalg.norm(result), 1.0, atol=1e-6)

    def test_inverse_qft(self):
        processor = QuantumFourierProcessor(num_qubits=3)
        state = np.random.randn(8) + 1j * np.random.randn(8)
        state = state / np.linalg.norm(state)
        forward = processor.qft(state)
        backward = processor.inverse_qft(forward)
        assert np.allclose(backward, state, atol=1e-10)

    def test_qft_hash_speedup(self):
        processor = QuantumFourierProcessor(num_qubits=3)
        result = processor.qft_frequency_analysis(b"test_header_data")
        assert isinstance(result, int)

    def test_frequency_domain_hash(self):
        processor = QuantumFourierProcessor(num_qubits=3)
        data = np.ones(8, dtype=np.complex128)
        result = processor.frequency_domain_transform(data)
        assert np.allclose(result, data)

    def test_get_specs(self):
        processor = QuantumFourierProcessor(num_qubits=3)
        specs = processor.get_specs()
        assert specs["dimension"] == 8


class TestPart8TopologicalProtection:
    def test_initialization(self):
        protector = TopologicalProtector(lattice_size=4)
        assert protector.lattice_size == 4
        assert len(protector.qubit_stabilizers) == 16

    def test_compute_homology(self):
        protector = TopologicalProtector(lattice_size=4)
        betti = protector.compute_homology()
        assert betti == [1, 0, 0]

    def test_validate_share(self):
        protector = TopologicalProtector(lattice_size=4)
        assert protector.validate_data(b"test_share")

    def test_correct_errors(self):
        protector = TopologicalProtector(lattice_size=4)
        state = np.ones(16, dtype=np.complex128) / 4
        corrected = protector.correct_quantum_errors(state)
        assert corrected.shape == state.shape

    def test_get_specs(self):
        protector = TopologicalProtector(lattice_size=4)
        specs = protector.get_specs()
        assert specs["lattice_size"] == 4
        assert specs["target_lattice_size"] == 4096


class TestPart9QuantumKernel:
    def test_encode_state(self):
        processor = QuantumKernelProcessor(num_qubits=4)
        x = np.array([1.0, 2.0, 3.0, 4.0])
        psi = processor.encode_state(x)
        assert np.isclose(np.linalg.norm(psi), 1.0)

    def test_quantum_feature_map(self):
        processor = QuantumKernelProcessor(num_qubits=4)
        x = np.array([1.0, 2.0, 3.0, 4.0])
        psi = processor.quantum_feature_map(x)
        assert np.isclose(np.linalg.norm(psi), 1.0)

    def test_compute_kernel(self):
        processor = QuantumKernelProcessor(num_qubits=4)
        x_i = np.array([1.0, 2.0])
        x_j = np.array([1.0, 2.0])
        k = processor.compute_quantum_kernel(x_i, x_j)
        assert 0 <= k <= 1.0

    def test_kernel_matrix(self):
        processor = QuantumKernelProcessor(num_qubits=4)
        data = [np.array([1.0, 2.0]), np.array([3.0, 4.0]), np.array([1.0, 2.0])]
        K = processor.compute_kernel_matrix(data)
        assert K.shape == (3, 3)
        assert np.allclose(K, K.T)  # Symmetric

    def test_adaptive_strategy(self):
        processor = QuantumKernelProcessor(num_qubits=4)
        conditions = {"difficulty": 100, "time": 0}
        result = processor.adaptive_compute_strategy(conditions)
        assert "nonce" in result
        assert "difficulty" in result

    def test_kernel_pca(self):
        processor = QuantumKernelProcessor(num_qubits=4)
        data = [
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
            np.array([5.0, 6.0]),
            np.array([7.0, 8.0]),
        ]
        components = processor.quantum_kernel_pca(data, n_components=2)
        assert components.shape[0] == 4
        assert components.shape[1] == 2


class TestPart10VQE:
    def test_initialization(self):
        vqe = VQEOptimizer(num_qubits=4, layers=3)
        assert vqe.num_qubits == 4
        assert vqe.dim == 16
        assert len(vqe.params) > 0

    def test_ansatz(self):
        vqe = VQEOptimizer(num_qubits=2, layers=2)
        state = vqe.ansatz(vqe.params)
        assert state.shape == (4,)
        assert np.isclose(np.linalg.norm(state), 1.0, atol=1e-6)

    def test_expectation_value(self):
        vqe = VQEOptimizer(num_qubits=2, layers=2)
        val = vqe.expectation_value(vqe.params)
        assert isinstance(val, float)

    def test_gradient_descent(self):
        vqe = VQEOptimizer(num_qubits=2, layers=2)
        params = vqe.gradient_descent(max_iterations=10)
        assert params.shape == vqe.params.shape

    def test_find_optimal_config(self):
        vqe = VQEOptimizer(num_qubits=2, layers=2)
        config = vqe.find_optimal_config()
        assert "optimal_config" in config
        assert "energy" in config

    def test_apply_cnot(self):
        vqe = VQEOptimizer(num_qubits=2, layers=1)
        state = np.array([1, 0, 0, 0], dtype=np.complex128)
        result = vqe.apply_cnot(state, 0, 1)
        assert result.shape == (4,)

    def test_get_specs(self):
        vqe = VQEOptimizer(num_qubits=4, layers=3)
        specs = vqe.get_specs()
        assert specs["num_qubits"] == 4
        assert specs["target_num_qubits"] == 4096
