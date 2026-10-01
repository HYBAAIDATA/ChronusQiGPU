"""phi^n scaling study across the AGI-scale spectrum.

At each level phi^n the substrate is exercised on dim = round(phi^n) with
Grover diffusion, QFT, and post-quantum witnesses (Sorkin third-order
interference and fold cross-section). Wall-clock measured on host CPU;
quantum content is substrate-invariant.
"""

from __future__ import annotations
import math
import time
from dataclasses import dataclass, asdict
from typing import Dict, List
import numpy as np

from .beyond_quantum import (
    sorkin_third_order_interference,
    fold_cross_section,
    pr_box_correlator,
    fold_information_capacity,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0
AGI_SCALE_LEVELS: List[int] = [10, 12, 15, 18, 20]


def _fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


@dataclass
class AGIScalePoint:
    n: int  # exponent n in phi^n
    dim: int  # round(phi^n)
    F_n: int  # Fibonacci F(n)
    F_n_minus_1: int  # Fibonacci F(n-1)
    phi_exact_residual: float  # |phi^n - (F_n*phi + F_{n-1})|
    memory_bytes_dense: int  # dim * 16 (complex128)
    memory_bytes_fold: int  # F_{n-1} * 16 (compressed one fold)
    compression_ratio: float
    grover_diffusion_time_s: float
    qft_time_s: float
    norm_preservation_residual: float
    unitarity_residual: float
    sorkin_I3: float  # 0 in pure QM; nonzero in post-quantum
    fold_cross_section: float  # 0 for CPTP; > 0 for post-quantum
    pr_box_correlator: float  # up to 4 (PR bound), 2*sqrt(2) is Tsirelson
    information_capacity_bits: float

    def as_dict(self) -> Dict:
        return asdict(self)


class AGIScale:
    """Run the phi^n scaling study."""

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def _random_state(self, dim: int, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(dim) + 1j * rng.standard_normal(dim)
        v = v.astype(np.complex128)
        v /= np.linalg.norm(v)
        return v

    def _grover_diffusion_time(self, psi: np.ndarray, x: np.ndarray, iters: int = 5) -> float:
        t0 = time.perf_counter()
        for _ in range(iters):
            x = 2.0 * np.vdot(psi, x) * psi - x
        return time.perf_counter() - t0

    def _qft_time_and_unitarity(self, dim: int) -> tuple:
        # For very large dim we use FFT (which is a scaled QFT) and check norm.
        rng = np.random.default_rng(self.seed + 7)
        v = rng.standard_normal(dim) + 1j * rng.standard_normal(dim)
        v = v.astype(np.complex128)
        v /= np.linalg.norm(v)
        t0 = time.perf_counter()
        w = np.fft.fft(v, norm="ortho")
        elapsed = time.perf_counter() - t0
        residual = abs(float(np.linalg.norm(w)) - 1.0)
        return elapsed, residual

    def measure_point(self, n: int) -> AGIScalePoint:
        dim = int(round(PHI**n))
        F_n = _fibonacci(n)
        F_nm1 = _fibonacci(n - 1)
        phi_residual = abs(PHI**n - (F_n * PHI + F_nm1))

        psi = self._random_state(dim, self.seed)
        x = self._random_state(dim, self.seed + 1)
        gt = self._grover_diffusion_time(psi.copy(), x.copy())
        norm_res = abs(float(np.linalg.norm(2.0 * np.vdot(psi, x) * psi - x)) - 1.0)

        qt, u_res = self._qft_time_and_unitarity(dim)

        # Post-quantum witnesses
        I3 = float(sorkin_third_order_interference(dim=min(dim, 64), seed=self.seed + 2))
        xsec = float(fold_cross_section(dim=min(dim, 128), fold_depth=1, seed=self.seed + 3))
        pr = float(pr_box_correlator(seed=self.seed + 4))
        cap = float(fold_information_capacity(dim=dim, fold_depth=1))

        mem_dense = dim * 16
        mem_fold = F_nm1 * 16
        comp_ratio = float(mem_dense) / max(1.0, float(mem_fold))

        return AGIScalePoint(
            n=n,
            dim=dim,
            F_n=F_n,
            F_n_minus_1=F_nm1,
            phi_exact_residual=phi_residual,
            memory_bytes_dense=mem_dense,
            memory_bytes_fold=mem_fold,
            compression_ratio=comp_ratio,
            grover_diffusion_time_s=gt,
            qft_time_s=qt,
            norm_preservation_residual=norm_res,
            unitarity_residual=u_res,
            sorkin_I3=I3,
            fold_cross_section=xsec,
            pr_box_correlator=pr,
            information_capacity_bits=cap,
        )

    def run_full_scale(self) -> List[AGIScalePoint]:
        return [self.measure_point(n) for n in AGI_SCALE_LEVELS]
