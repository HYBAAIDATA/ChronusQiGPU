"""Bounded classical state-vector simulation, not physical qubits."""
import numpy as np
MAX_DIMENSION = 4096
class MathematicalQuantumState:
    def __init__(self, amplitudes):
        a = np.asarray(amplitudes, dtype=np.complex128)
        if a.ndim != 1 or not 0 < a.size <= MAX_DIMENSION or not np.isfinite(a).all():
            raise ValueError("finite bounded 1-D state required")
        scale = np.max(np.abs(a))
        if scale == 0 or not np.isfinite(scale): raise ValueError("invalid state norm")
        a = a / scale
        self.amplitudes = a / np.linalg.norm(a)
    @property
    def probabilities(self): return np.abs(self.amplitudes) ** 2
class Operator:
    def __init__(self, matrix):
        a = np.asarray(matrix, dtype=np.complex128)
        if a.ndim != 2 or a.shape[0] != a.shape[1] or not 0 < a.shape[0] <= 512 or not np.isfinite(a).all():
            raise ValueError("finite bounded square operator required")
        self.matrix = a.copy()
    def apply(self, state):
        if self.matrix.shape[1] != state.amplitudes.size: raise ValueError("dimension mismatch")
        return MathematicalQuantumState(self.matrix @ state.amplitudes)
class HamiltonianEngine:
    def evolve(self, state, hamiltonian, time=1.0):
        h = Operator(hamiltonian).matrix
        if not np.allclose(h, h.conj().T, atol=1e-12, rtol=1e-12): raise ValueError("Hamiltonian must be Hermitian")
        if h.shape[0] != state.amplitudes.size or not np.isfinite(time): raise ValueError("dimension/time mismatch")
        values, vectors = np.linalg.eigh(h)
        phases = values * time
        if not np.isfinite(phases).all(): raise ValueError("phase overflow")
        return MathematicalQuantumState(vectors @ (np.exp(-1j * phases) * (vectors.conj().T @ state.amplitudes)))
