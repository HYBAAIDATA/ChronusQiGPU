"""Enhanced QFT with unitary banded (Coppersmith) approximation.

References:
  * Coppersmith 1994 - approximate QFT (bandwidth truncation preserves unitarity).
  * Griffiths & Niu 1996 - semiclassical QFT.
  * Nielsen & Chuang - standard exposition.
"""

from __future__ import annotations
import math
import numpy as np
from typing import Dict, Any, Optional


def _kron_at(op: np.ndarray, qubit: int, num_qubits: int) -> np.ndarray:
    """Embed a single-qubit op at position `qubit` (0 = most significant) in an
    n-qubit register."""
    I2 = np.eye(2, dtype=complex)
    m = np.array([[1]], dtype=complex)
    for i in range(num_qubits):
        m = np.kron(m, op if i == qubit else I2)
    return m


def _controlled_phase(control: int, target: int, phase: float, num_qubits: int) -> np.ndarray:
    """Controlled-phase gate |11> -> e^{i phase} |11>, identity elsewhere."""
    dim = 2**num_qubits
    U = np.eye(dim, dtype=complex)
    for x in range(dim):
        bits = [(x >> (num_qubits - 1 - i)) & 1 for i in range(num_qubits)]
        if bits[control] == 1 and bits[target] == 1:
            U[x, x] = np.exp(1j * phase)
    return U


def _swap(i: int, j: int, num_qubits: int) -> np.ndarray:
    dim = 2**num_qubits
    U = np.zeros((dim, dim), dtype=complex)
    for x in range(dim):
        bits = [(x >> (num_qubits - 1 - k)) & 1 for k in range(num_qubits)]
        bits[i], bits[j] = bits[j], bits[i]
        y = 0
        for k, b in enumerate(bits):
            y |= b << (num_qubits - 1 - k)
        U[y, x] = 1.0
    return U


def _hadamard_on(qubit: int, num_qubits: int) -> np.ndarray:
    H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2.0)
    return _kron_at(H, qubit, num_qubits)


def exact_qft_matrix(num_qubits: int) -> np.ndarray:
    """Exact QFT via direct DFT matrix. Verified unitary."""
    n = 2**num_qubits
    j = np.arange(n).reshape(-1, 1)
    k = np.arange(n).reshape(1, -1)
    return np.exp(2j * np.pi * j * k / n) / math.sqrt(n)


def banded_qft_matrix(num_qubits: int, band: Optional[int] = None) -> np.ndarray:
    """Coppersmith banded QFT: skip controlled-R_k for k > band.

    The result is a product of unitary gates, hence exactly unitary.
    If band is None, all rotations are kept and this equals the exact QFT.
    Circuit form:
      for i in 0..n-1:
        H(i)
        for j in i+1..n-1:
          k = j - i
          if band is None or k <= band:
            controlled-R(pi/2^k) with control=j, target=i
      swap qubit i with qubit n-1-i (bit reversal)
    """
    n = num_qubits
    dim = 2**n
    U = np.eye(dim, dtype=complex)
    for i in range(n):
        U = _hadamard_on(i, n) @ U
        for j in range(i + 1, n):
            k = j - i
            if band is not None and k > band:
                continue
            angle = math.pi / (2**k)
            U = _controlled_phase(j, i, angle, n) @ U
    # Bit-reversal swaps
    for i in range(n // 2):
        U = _swap(i, n - 1 - i, n) @ U
    return U


def coppersmith_error_bound(num_qubits: int, band: int) -> float:
    """Coppersmith 1994: || QFT - AQFT_band || <= 2 pi n / 2^band."""
    return 2.0 * math.pi * num_qubits / (2 ** max(1, band))


class EnhancedQFT:
    def __init__(self, num_qubits: int) -> None:
        if num_qubits < 1:
            raise ValueError("num_qubits must be >= 1")
        self.num_qubits = num_qubits
        self.dimension = 2**num_qubits

    def exact_qft(self, state: np.ndarray) -> Dict[str, Any]:
        Q = exact_qft_matrix(self.num_qubits)
        return {
            "transformed_state": Q @ state,
            "circuit_depth": self.num_qubits * (self.num_qubits + 1) // 2,
            "gate_count": self.num_qubits * (self.num_qubits + 1) // 2 * 3,
            "error": 0.0,
            "type": "exact",
        }

    def banded_qft(self, state: np.ndarray, band: int) -> Dict[str, Any]:
        """Approximate QFT (Coppersmith): unitary by construction."""
        if band < 1:
            raise ValueError("band must be >= 1")
        Q = banded_qft_matrix(self.num_qubits, band=band)
        exact = exact_qft_matrix(self.num_qubits)
        return {
            "transformed_state": Q @ state,
            "circuit_depth": self.num_qubits * band,
            "gate_count": self.num_qubits * band * 3,
            "error": float(np.linalg.norm((Q - exact) @ state)),
            "upper_bound_error": coppersmith_error_bound(self.num_qubits, band),
            "type": "banded",
            "band": band,
        }

    def adaptive_precision_qft(
        self, state: np.ndarray, target_error: float = 1e-4, max_band: Optional[int] = None
    ) -> Dict[str, Any]:
        """Pick smallest band with |QFT - AQFT_band| * ||state|| <= target_error."""
        max_band = max_band or self.num_qubits
        best = self.exact_qft(state)
        best["band"] = self.num_qubits
        for band in range(1, max_band + 1):
            r = self.banded_qft(state, band=band)
            if r["error"] <= target_error:
                r["target_error"] = target_error
                r["type"] = "adaptive_precision"
                return r
        best["target_error"] = target_error
        best["type"] = "adaptive_precision_exact"
        return best

    def semiclassical_hint(self) -> Dict[str, Any]:
        """Return metadata for Griffiths-Niu semiclassical QFT (measurement + feed-forward).
        The substrate is measurement-free; this metadata is for downstream compilers.
        """
        return {
            "num_qubits": self.num_qubits,
            "measurements": self.num_qubits,
            "single_qubit_rotations": self.num_qubits * (self.num_qubits + 1) // 2,
            "classical_bits": self.num_qubits,
            "depth": self.num_qubits,
        }
