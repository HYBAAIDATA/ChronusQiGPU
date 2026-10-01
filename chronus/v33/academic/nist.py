# nist.py -- NIST academic-review enhancement modules (audit-fixed, 3 Aug 2026)
#
# Real vs. flavor-text triage:
#   - NIST_Standards: quantum state fidelity is computed via a real Uhlmann
#     fidelity formula (matrix square roots via eigendecomposition, since no
#     scipy is available in this sandbox), applied to actual states produced
#     by this codebase's real render pipeline -- not fabricated "1.0
#     fidelity" reference constants.
#   - NIST_Benchmark: the pasted pseudocode's benchmark scores ("99.9%",
#     "Quantum_Volume: 128", etc.) are hardcoded literals, never computed --
#     exactly the kind of fabricated-result pattern already found and fixed
#     elsewhere in this audit (see AUDIT_NOTES.md defect #2). Every score
#     here is instead a real, measured number produced by actually running a
#     corresponding real computation.

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

import numpy as np


def _hermitian_sqrtm(matrix: np.ndarray) -> np.ndarray:
    # Matrix square root for a Hermitian PSD matrix via eigendecomposition
    # (no scipy available in this sandbox).
    matrix = (matrix + matrix.conj().T) / 2
    eigvals, eigvecs = np.linalg.eigh(matrix)
    eigvals = np.clip(eigvals, 0, None)
    return eigvecs @ np.diag(np.sqrt(eigvals)) @ eigvecs.conj().T


class NIST_Standards:
    def state_to_density_matrix(self, state_vector: np.ndarray) -> np.ndarray:
        v = state_vector.reshape(-1, 1)
        return v @ v.conj().T

    def fidelity(self, rho: np.ndarray, sigma: np.ndarray) -> float:
        # Real Uhlmann fidelity: F(rho, sigma) = [Tr(sqrt(sqrt(rho) sigma sqrt(rho)))]^2
        sqrt_rho = _hermitian_sqrtm(rho)
        inner = sqrt_rho @ sigma @ sqrt_rho
        sqrt_inner = _hermitian_sqrtm(inner)
        val = np.trace(sqrt_inner).real
        return float(np.clip(val**2, 0.0, 1.0))

    def validate_against_reference(self, state_vector: np.ndarray, reference: str) -> float:
        n = state_vector.shape[0]
        ref = np.zeros(n, dtype=complex)
        if reference == "ground":
            ref[int(np.argmax(np.abs(state_vector)))] = 1.0  # self-consistency check
        elif reference == "uniform":
            ref[:] = 1.0 / np.sqrt(n)
        else:
            raise ValueError(f"unknown reference '{reference}'")
        rho = self.state_to_density_matrix(state_vector)
        sigma = self.state_to_density_matrix(ref)
        return self.fidelity(rho, sigma)


@dataclass
class BenchmarkReport:
    scores: Dict[str, float]
    timings_s: Dict[str, float]
    average_score: float


class NIST_Benchmark:
    # Every score below is computed by actually running something on this
    # machine, not a hardcoded literal.

    def run_all(self, chronos_render_fn) -> BenchmarkReport:
        scores: Dict[str, float] = {}
        timings: Dict[str, float] = {}

        # "QASM_Simulator" stand-in: run the real render pipeline twice and
        # score by how close the two energies are (real determinism check).
        t0 = time.time()
        e1 = chronos_render_fn().energy
        e2 = chronos_render_fn().energy
        timings["determinism_check"] = time.time() - t0
        scores["determinism_check"] = 1.0 if abs(e1 - e2) < 1e-9 else 0.0

        # "Quantum_Volume" stand-in: largest random Hermitian matrix size
        # exactly diagonalized within a fixed real time budget on this
        # machine.
        t0 = time.time()
        max_dim = 0
        for dim in (16, 32, 64, 128, 256):
            m = np.random.default_rng(0).normal(size=(dim, dim))
            m = (m + m.T) / 2
            np.linalg.eigh(m)
            max_dim = dim
            if time.time() - t0 > 0.5:
                break
        timings["quantum_volume"] = time.time() - t0
        scores["quantum_volume"] = float(max_dim)

        # "QFT" stand-in: real numpy FFT round-trip reconstruction error.
        t0 = time.time()
        x = np.random.default_rng(1).normal(size=256)
        reconstructed = np.fft.ifft(np.fft.fft(x)).real
        timings["qft_roundtrip"] = time.time() - t0
        scores["qft_roundtrip_error"] = float(np.max(np.abs(x - reconstructed)))

        # p=1 QAOA for the two-vertex MaxCut instance.
        t0 = time.time()
        gamma, beta = np.pi / 2, np.pi / 8
        state = np.full(4, 0.5, dtype=complex)
        cost_values = np.array([0.0, 1.0, 1.0, 0.0])
        state *= np.exp(-1j * gamma * cost_values)
        mixer = np.array(
            [[np.cos(beta), -1j * np.sin(beta)], [-1j * np.sin(beta), np.cos(beta)]],
            dtype=complex,
        )
        state = np.kron(mixer, mixer) @ state
        cost0 = 0.5
        cost1 = float(np.sum(np.abs(state) ** 2 * cost_values))
        timings["qaoa_p1_maxcut"] = time.time() - t0
        scores["qaoa_cost_reduction"] = float(cost0 - cost1)

        return BenchmarkReport(scores=scores, timings_s=timings, average_score=float(np.mean(list(scores.values()))))
