"""PULVINI: reversible golden-ratio folding and honest spectral reduction.

PULVINI is a deterministic numerical operator.  It provides a reversible
coordinate transform when its complement is retained, and a separately
reported, lossy projection for Hamiltonians.  It does not claim physical
quantum acceleration, topology preservation for arbitrary truncations, or
information recovery after the complement is discarded.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0


@dataclass(frozen=True)
class PulviniAuditEnvelope:
    """Evidence returned by a Hamiltonian reduction."""

    original_dimension: int
    folded_dimension: int
    reconstruction_error_bound: float
    spectral_gap_delta: float
    topology_preserved: bool
    is_reversible: bool
    original_spectral_gap: float = 0.0
    reduced_spectral_gap: float = 0.0
    adaptive_tolerance: float = 0.0
    condition_number: float = 0.0
    method: str = "hermitian_eigenspace_projection"


class PulviniOperator:
    """Deterministic Phi-recursive folding operator.

    ``fold`` is invertible only when the returned projection kernel is retained.
    ``hamiltonian_reduction`` is a dimension-reducing projection and therefore
    explicitly reports ``is_reversible=False``.
    """

    def __init__(self, tolerance: float = 1e-6, require_hermitian: bool = True):
        if tolerance < 0 or not np.isfinite(tolerance):
            raise ValueError("tolerance must be a finite non-negative number")
        self.tolerance = float(tolerance)
        self.require_hermitian = require_hermitian

    @staticmethod
    def _get_fibonacci_split(dim: int) -> Tuple[int, int]:
        if not isinstance(dim, (int, np.integer)) or dim < 1:
            raise ValueError("dim must be a positive integer")
        if dim == 1:
            return 1, 0
        dim_n2 = max(1, int(np.rint(dim / (PHI + 1.0))))
        return dim - dim_n2, dim_n2

    def fold(self, tensor: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Fold a one-dimensional array and return its retained complement."""
        value = np.asarray(tensor)
        if value.ndim != 1:
            raise ValueError("fold expects a one-dimensional array")
        dim = value.size
        if dim <= 1:
            return value.copy(), np.zeros(0, dtype=value.dtype)

        dim_n1, dim_n2 = self._get_fibonacci_split(dim)
        x_n1 = value[:dim_n1]
        x_n2 = value[dim_n1:]
        padded = np.zeros(dim_n1, dtype=value.dtype)
        padded[:dim_n2] = x_n2

        w1 = 1.0 / PHI
        w2 = 1.0 / (PHI * PHI)
        folded = w1 * x_n1 + w2 * padded
        kernel = w2 * x_n1 - w1 * padded
        return folded, kernel

    def unfold(
        self,
        folded_tensor: np.ndarray,
        projection_kernel: np.ndarray,
        original_dim: int,
    ) -> np.ndarray:
        """Recover the exact input (within floating-point roundoff)."""
        dim_n1, dim_n2 = self._get_fibonacci_split(original_dim)
        folded = np.asarray(folded_tensor)
        kernel = np.asarray(projection_kernel)
        if folded.ndim != 1 or kernel.ndim != 1:
            raise ValueError("folded_tensor and projection_kernel must be vectors")
        if folded.size != dim_n1 or kernel.size != dim_n1:
            raise ValueError("folded and kernel dimensions do not match original_dim")

        w1 = 1.0 / PHI
        w2 = 1.0 / (PHI * PHI)
        norm_sq = w1 * w1 + w2 * w2
        x_n1 = (w1 * folded + w2 * kernel) / norm_sq
        padded = (w2 * folded - w1 * kernel) / norm_sq
        return np.concatenate((x_n1, padded[:dim_n2]))

    def round_trip_error(self, tensor: np.ndarray) -> float:
        value = np.asarray(tensor)
        folded, kernel = self.fold(value)
        restored = self.unfold(folded, kernel, value.size)
        denom = max(1.0, float(np.linalg.norm(value)))
        return float(np.linalg.norm(value - restored) / denom)

    def hamiltonian_reduction(
        self, hamiltonian: np.ndarray
    ) -> Tuple[np.ndarray, PulviniAuditEnvelope]:
        """Project a Hermitian matrix onto its lowest Phi-sized eigenspace.

        The low-energy eigenspace is used rather than an arbitrary SVD basis so
        that the reported spectral gap is the gap of the selected spectrum. A
        reduction is marked as topology-preserving only when the measured gap
        change is within the documented adaptive numerical tolerance.
        """
        h = np.asarray(hamiltonian)
        if h.ndim != 2 or h.shape[0] != h.shape[1] or h.shape[0] < 1:
            raise ValueError("hamiltonian must be a non-empty square matrix")
        hermitian = np.allclose(h, h.conj().T, atol=self.tolerance, rtol=0)
        if self.require_hermitian and not hermitian:
            raise ValueError("hamiltonian must be Hermitian")

        eigenvalues, eigenvectors = np.linalg.eigh(h)
        keep, _ = self._get_fibonacci_split(h.shape[0])
        keep = min(max(1, keep), h.shape[0])
        basis = eigenvectors[:, :keep]
        reduced = basis.conj().T @ h @ basis
        reduced_values = np.linalg.eigvalsh(reduced)

        original_gap = float(eigenvalues[1] - eigenvalues[0]) if h.shape[0] > 1 else 0.0
        reduced_gap = float(reduced_values[1] - reduced_values[0]) if keep > 1 else 0.0
        gap_delta = abs(original_gap - reduced_gap)
        norm_h = max(float(np.linalg.norm(h, ord="fro")), np.finfo(float).eps)
        reconstruction_error = float(
            np.linalg.norm(h - basis @ reduced @ basis.conj().T, ord="fro") / norm_h
        )
        condition = float(np.linalg.cond(h)) if h.size else 1.0
        if not np.isfinite(condition):
            condition = float("inf")
        adaptive = self.tolerance * max(1.0, np.log10(condition) if np.isfinite(condition) else 1.0)

        envelope = PulviniAuditEnvelope(
            original_dimension=h.shape[0],
            folded_dimension=keep,
            reconstruction_error_bound=reconstruction_error,
            spectral_gap_delta=float(gap_delta),
            topology_preserved=bool(gap_delta <= adaptive),
            is_reversible=False,
            original_spectral_gap=original_gap,
            reduced_spectral_gap=reduced_gap,
            adaptive_tolerance=float(adaptive),
            condition_number=condition,
        )
        return reduced, envelope
