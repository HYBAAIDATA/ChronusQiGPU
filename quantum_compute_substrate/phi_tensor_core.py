"""
φ-Resonance Quantum-Inspired Tensor Core
========================================

Implements quantum-mathematical tensor processing using the golden ratio (φ)
compression framework. All operations use real linear algebra — no hardcoded
performance numbers. Performance is measured by timing actual operations.

Mathematical basis:
    - FoldState: φ-compressed state vector with invertible reconstruction
    - Amplitude amplification: Real Grover diffusion operator D = 2|ψ⟩⟨ψ| - I
    - Tensor operations: Kronecker product, contraction, FMA on complex vectors

Claim lane: INTERNAL — demonstrates quantum algebraic structure on classical
substrate via linear algebra emulation. This is NOT a physical quantum computer;
it is a quantum-mathematical classical algorithm. The Grover diffusion operator
D = 2|ψ⟩⟨ψ| - I is implemented correctly mathematically on NumPy arrays.
No quantum advantage is claimed. Performance is measured, not projected.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional
import time

# Golden ratio — fundamental constant of the φ-resonance framework
PHI = (1.0 + np.sqrt(5.0)) / 2.0


@dataclass
class FoldState:
    """
    A φ-compressed state vector with reconstruction metadata.

    The fold operation compresses a state vector by averaging adjacent
    elements at a rate determined by φ. The unfold operation reconstructs
    via linear interpolation. Reconstruction is approximate (not lossless)
    at depth > 0, with error tracked for integrity verification.
    """

    data: np.ndarray  # Complex state vector
    depth: int = 0  # Compression depth (0 = unfolded)
    original_dim: int = 0  # Dimension before folding (for reconstruction)
    _reconstruction_error: float = 0.0

    @property
    def dim(self) -> int:
        return len(self.data)

    @property
    def norm(self) -> float:
        return float(np.linalg.norm(self.data))

    @property
    def is_normalized(self) -> bool:
        return abs(self.norm - 1.0) < 1e-10

    def normalize(self) -> "FoldState":
        """Return a normalised copy."""
        n = self.norm
        if n > 0:
            return FoldState(self.data / n, self.depth, self.original_dim or self.dim)
        return self

    def fold(self, target_depth: int = 1) -> "FoldState":
        """
        Compress state by φ^depth factor via block averaging.
        Information-preserving in the sense that statistical structure is
        retained; exact reconstruction requires depth 0.
        """
        if target_depth <= self.depth:
            return self
        src = self.data
        src_dim = len(src)
        factor = PHI ** (target_depth - self.depth)
        target_dim = max(2, int(src_dim / factor))
        if target_dim >= src_dim:
            return self
        trim = target_dim * (src_dim // target_dim)
        reshaped = src[:trim].reshape(target_dim, src_dim // target_dim)
        folded = np.mean(reshaped, axis=1)
        return FoldState(folded, target_depth, self.original_dim or src_dim)

    def unfold(self) -> "FoldState":
        """Reconstruct from folded state via interpolation."""
        if self.depth == 0 or self.original_dim == 0:
            return self
        orig = self.original_dim
        src = self.data
        idx_src = np.arange(len(src), dtype=float)
        idx_dst = np.linspace(0, len(src) - 1, orig)
        if np.iscomplexobj(src):
            real = np.interp(idx_dst, idx_src, src.real)
            imag = np.interp(idx_dst, idx_src, src.imag)
            unfolded = real + 1j * imag
        else:
            unfolded = np.interp(idx_dst, idx_src, src)
        return FoldState(unfolded, 0, orig)

    def reconstruction_error(self, original: Optional["FoldState"] = None) -> float:
        """Compute L2 reconstruction error after fold → unfold cycle."""
        if original is not None:
            unfolded = self.unfold()
            if len(unfolded.data) != len(original.data):
                return float("inf")
            return float(np.linalg.norm(unfolded.data - original.data))
        return self._reconstruction_error


class QuantumFoldTensorCore:
    """
    Quantum-mathematical tensor processing unit operating on FoldState objects.

    Performs tensor operations with φ-resonance amplitude amplification.
    All performance is MEASURED by timing actual operations — no hardcoded
    FLOPS, no projected throughput.

    Claim lane: INTERNAL — demonstrates quantum algebraic structure on
    classical hardware. No quantum advantage claim.
    """

    def __init__(self, core_id: int, dim: int = 4096, seed: Optional[int] = None):
        self.core_id = core_id
        self.dim = dim
        self._rng = np.random.default_rng(seed if seed is not None else core_id)
        self.state = self._initialize_state()
        self._ops_count = 0
        self._compute_time = 0.0

    def _initialize_state(self) -> FoldState:
        """Initialise uniform superposition: |ψ⟩ = (1/√N) Σ|x⟩."""
        data = np.ones(self.dim, dtype=np.complex128) / np.sqrt(self.dim)
        return FoldState(data, 0, self.dim)

    # ── Tensor operations ──────────────────────────────────────────────

    def tensor_product(self, a: FoldState, b: FoldState) -> FoldState:
        """Kronecker product A ⊗ B in tensor space."""
        t0 = time.perf_counter()
        result = np.kron(a.data, b.data)
        self._compute_time += time.perf_counter() - t0
        self._ops_count += len(a.data) * len(b.data)
        return FoldState(result, max(a.depth, b.depth), len(result))

    def tensor_contraction(self, a: FoldState, b: FoldState) -> FoldState:
        """Contract two tensors via inner product."""
        t0 = time.perf_counter()
        result = np.dot(a.data, b.data)
        self._compute_time += time.perf_counter() - t0
        self._ops_count += len(a.data)
        return FoldState(np.array([result]), 0, 1)

    def fma(self, a: FoldState, b: FoldState, c: FoldState) -> FoldState:
        """Fused multiply-add: a * b + c (elementwise)."""
        t0 = time.perf_counter()
        result = a.data * b.data + c.data
        self._compute_time += time.perf_counter() - t0
        self._ops_count += 2 * len(a.data)
        return FoldState(result, max(a.depth, b.depth, c.depth), len(result))

    def matmul(self, a: FoldState, b: np.ndarray) -> FoldState:
        """Matrix-vector product: A @ |ψ⟩."""
        t0 = time.perf_counter()
        result = a.data @ b
        self._compute_time += time.perf_counter() - t0
        self._ops_count += len(a.data) * b.shape[-1] if b.ndim > 1 else len(a.data)
        return FoldState(result, a.depth, len(result))

    # ── Quantum-mathematical operations ────────────────────────────────────

    def amplitude_amplification(self, state: FoldState) -> FoldState:
        """
        Real Grover diffusion operator: D = 2|ψ⟩⟨ψ| - I

        D|φ⟩ = 2⟨ψ|φ⟩|ψ⟩ - |φ⟩

        where |ψ⟩ is the uniform superposition (1/√N) Σ|x⟩.

        This is the mathematically correct amplitude amplification. It is
        NOT 2*mean(x) - x, which is a scalar subtraction with no quantum
        mechanical meaning.
        """
        t0 = time.perf_counter()
        s = state.data
        n = len(s)
        psi = np.ones(n, dtype=np.complex128) / np.sqrt(n)
        inner = np.vdot(psi, s)  # ⟨ψ|φ⟩ — complex inner product
        result = 2.0 * inner * psi - s  # D|φ⟩ = 2⟨ψ|φ⟩|ψ⟩ - |φ⟩
        self._compute_time += time.perf_counter() - t0
        self._ops_count += 3 * n
        return FoldState(result, state.depth, state.original_dim or n)

    def grover_oracle(self, state: FoldState, target: int) -> FoldState:
        """
        Grover oracle: flip the phase of the target basis state.
        O|x⟩ = (-1)^f(x) |x⟩  where f(x) = 1 if x == target, else 0.
        """
        s = state.data.copy()
        s[target] *= -1.0
        return FoldState(s, state.depth, state.original_dim or len(s))

    def grover_iteration(self, state: FoldState, target: int) -> FoldState:
        """One complete Grover iteration: oracle followed by diffusion."""
        state = self.grover_oracle(state, target)
        state = self.amplitude_amplification(state)
        return state

    def measure(self, state: FoldState) -> int:
        """Measure: return the index of the highest-probability basis state."""
        probs = np.abs(state.data) ** 2
        return int(np.argmax(probs))

    def measure_probability(self, state: FoldState, target: int) -> float:
        """Return the probability of measuring the target state."""
        probs = np.abs(state.data) ** 2
        return float(probs[target])

    # ── Performance measurement ───────────────────────────────────────

    def measured_flops(self) -> float:
        """Return MEASURED FLOPS from actual computation time."""
        if self._compute_time > 0:
            return self._ops_count / self._compute_time
        return 0.0

    def reset_counters(self):
        """Reset operation and timing counters."""
        self._ops_count = 0
        self._compute_time = 0.0

    # ── Integrity ──────────────────────────────────────────────────────

    @staticmethod
    def integrity_check(state: FoldState, tolerance: float = 1e-10) -> bool:
        """Verify state norm is preserved (unitarity check)."""
        return abs(state.norm - 1.0) < tolerance or state.norm < 1e-12
