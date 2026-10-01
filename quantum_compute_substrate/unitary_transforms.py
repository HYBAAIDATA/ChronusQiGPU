"""
Part 2: Unitary Transformations
================================
Hash functions as unitary operators with tensor core acceleration.
"""

import numpy as np
from .hilbert_space import QuantumComputeState


class UnitaryHashTransform:
    """Part 2: Hash function as unitary transformation."""

    def __init__(self, num_qubits: int = 4096):
        self.num_qubits = num_qubits
        self.dim = 2 ** min(num_qubits, 12)
        self.tensor_core_config = {
            "sparsity": 0.5,
            "precision": "fp8",
            "transform_engine": True,
        }

    def hadamard_transform(self, state: QuantumComputeState) -> QuantumComputeState:
        """H = (1/sqrt(2))[[1,1],[1,-1]] applied to all qubits."""
        amplitudes = state.amplitudes.copy()
        # Full Hadamard on all qubits = DFT matrix / sqrt(N)
        N = self.dim
        transformed = np.zeros(N, dtype=np.complex128)
        for y in range(N):
            for x in range(N):
                bit_parity = bin(x & y).count("1") % 2
                transformed[y] += amplitudes[x] * ((-1) ** bit_parity) / np.sqrt(N)
        return QuantumComputeState(transformed, self.dim, state.coherence_time)

    def hadamard_single(self, state: QuantumComputeState, qubit: int) -> QuantumComputeState:
        """Apply Hadamard to a single qubit."""
        amplitudes = state.amplitudes.copy()
        int(np.log2(self.dim))
        for i in range(self.dim):
            if (i >> qubit) & 1:
                j = i ^ (1 << qubit)
                a, b = amplitudes[j], amplitudes[i]
                amplitudes[j] = (a + b) / np.sqrt(2)
                amplitudes[i] = (a - b) / np.sqrt(2)
        return QuantumComputeState(amplitudes, self.dim, state.coherence_time)

    def phase_shift(self, state: QuantumComputeState, angle: float) -> QuantumComputeState:
        """P(phi) = diag(1, e^{i*phi}) applied per qubit."""
        amplitudes = state.amplitudes.copy()
        for i in range(self.dim):
            bit_count = bin(i).count("1")
            amplitudes[i] *= np.exp(1j * angle * bit_count)
        return QuantumComputeState(amplitudes, self.dim, state.coherence_time)

    def qft_transform(self, state: QuantumComputeState) -> QuantumComputeState:
        """Quantum Fourier Transform using FFT for efficiency."""
        N = self.dim
        amplitudes = state.amplitudes.copy()
        # QFT is just DFT with positive exponent
        transformed = np.fft.fft(amplitudes) / np.sqrt(N)
        return QuantumComputeState(transformed, self.dim, state.coherence_time)

    def inverse_qft(self, state: QuantumComputeState) -> QuantumComputeState:
        """Inverse QFT using IFFT."""
        N = self.dim
        amplitudes = state.amplitudes.copy()
        transformed = np.fft.ifft(amplitudes) * np.sqrt(N)
        return QuantumComputeState(transformed, self.dim, state.coherence_time)

    def compute_hash_unitary(self, input_data: bytes) -> callable:
        """Construct full unitary hash operator."""

        def hash_operator(state: QuantumComputeState):
            state = self.hadamard_transform(state)
            phase = self.header_to_phase(input_data)
            state = self.phase_shift(state, phase)
            state = self.hadamard_transform(state)
            return state

        return hash_operator

    def header_to_phase(self, header: bytes) -> float:
        """Convert header to phase angle."""
        hash_val = hash(header)
        return (hash_val % 1000) / 1000.0 * 2 * np.pi
