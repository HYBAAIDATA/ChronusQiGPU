"""Systematic scaling study: log-log fit for time and error vs. Hilbert dim.

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC). All numbers are measured wall-clock time
on the host CPU (minimum per-application time across repeated rounds, the standard estimator
that removes scheduling/GC noise). No hardware-quantum claim is made.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class ScalingResult:
    dims: List[int]
    times_s: List[float]
    errors: List[float]
    exponent_time: float
    exponent_error: float
    r2_time: float
    r2_error: float

    def summary(self) -> str:
        return (
            f"ScalingResult(n={len(self.dims)}, "
            f"time~D^{self.exponent_time:.3f} R^2={self.r2_time:.3f}, "
            f"err~D^{self.exponent_error:.3f} R^2={self.r2_error:.3f})"
        )


def _loglog_fit(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    lx = np.log(np.array(xs, dtype=np.float64))
    ly = np.log(np.array(ys, dtype=np.float64) + 1e-30)
    a, b = np.polyfit(lx, ly, 1)
    yhat = a * lx + b
    ss_res = float(np.sum((ly - yhat) ** 2))
    ss_tot = float(np.sum((ly - ly.mean()) ** 2)) + 1e-30
    r2 = 1.0 - ss_res / ss_tot
    return float(a), float(r2)


class ScalingStudy:
    """Run scaling studies on Grover diffusion and phi-fold reconstruction."""

    def __init__(self, claim_lane: str = "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)") -> None:
        self.claim_lane = claim_lane

    def diffusion_scaling(self, dims: List[int] | None = None, seed: int = 0) -> ScalingResult:
        """Measure Grover diffusion time & norm-preservation error over dims.

        Chooses dims spanning phi^k for k=10..37 by default. Diffusion is
        implemented as D = 2 psi psi^H - I on a random unit vector.
        """
        if dims is None:
            ks = list(range(10, 38))
            dims = sorted({max(4, int(PHI**k) & ~1) for k in ks})
            dims = [d for d in dims if d <= 4096]  # cap for CPU sanity
        rng = np.random.default_rng(seed)
        times: List[float] = []
        errors: List[float] = []
        for d in dims:
            psi = rng.standard_normal(d) + 1j * rng.standard_normal(d)
            psi = psi.astype(np.complex128)
            psi /= np.linalg.norm(psi)
            x = rng.standard_normal(d) + 1j * rng.standard_normal(d)
            x = x.astype(np.complex128)
            x /= np.linalg.norm(x)
            # D x = 2 <psi,x> psi - x (a unitary reflection, norm-preserving).
            # A single 3-iteration burst is microseconds at small dims, so the
            # wall-clock signal drowns in timer/scheduling noise. Repeat the
            # application enough times to exceed timer resolution and keep the
            # fastest round's per-application time.
            inner_reps = max(16, (1 << 14) // max(d, 1))
            best = math.inf
            y = x
            for _round in range(7):
                y = x.copy()
                t0 = time.perf_counter()
                for _ in range(inner_reps):
                    inner = np.vdot(psi, y)
                    y = 2.0 * inner * psi - y
                best = min(best, (time.perf_counter() - t0) / inner_reps)
            err = abs(float(np.linalg.norm(y)) - 1.0)
            times.append(max(best, 1e-9))
            errors.append(max(err, 1e-16))
        exp_t, r2_t = _loglog_fit([float(d) for d in dims], times)
        exp_e, r2_e = _loglog_fit([float(d) for d in dims], errors)
        return ScalingResult(
            dims=list(dims),
            times_s=times,
            errors=errors,
            exponent_time=exp_t,
            exponent_error=exp_e,
            r2_time=r2_t,
            r2_error=r2_e,
        )

    def phi_index_check(self, k_max: int = 40) -> List[Tuple[int, float]]:
        """Verify phi^k = F(k) phi + F(k-1) up to k = k_max, return residuals.

        Uses integer Fibonacci (exact) to avoid float roundoff.
        """
        F = [0, 1]
        for _ in range(k_max + 1):
            F.append(F[-1] + F[-2])
        residuals: List[Tuple[int, float]] = []
        for k in range(0, k_max + 1):
            lhs = PHI**k
            rhs = F[k] * PHI + F[k - 1] if k >= 1 else 1.0
            residuals.append((k, abs(lhs - rhs)))
        return residuals
