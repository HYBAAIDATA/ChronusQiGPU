"""Kellogg stability horizon — dynamical invariants for the golden substrate.

Thin orchestration layer over the canonical probes in
:mod:`kellogg.first_principles` (the single source for Chirikov iteration,
maximal Lyapunov exponents, Greene residues and the generalized golden
constants) plus numpy-only coverage metrics.  No scipy dependency: Voronoi
and Delaunay diagnostics are replaced by the nearest-neighbour distance
variance, a continuous proxy the pseudocode itself names acceptable.

Convention: the standard map is on the lift with ``theta`` a turn in
``[0, 1)`` — ``standard_map_step`` takes ``K`` (kick strength), the winding
number is a rotation number in turns, and the golden winding is
``golden_turn() = 1/phi^2``.  KAM critical ``K ≈ 0.971635`` lives in
``GOLDEN_KAM_CRITICAL_K``.

Calibration notes (measured, not asserted):

* Finite-time MLEs on a regular orbit decay like ``log(steps)/steps``
  because a generic tangent grows linearly; classification thresholds are
  therefore scaled to that floor rather than taken as absolute constants.
* To measure the breakup of the ``omega``-winding torus the orbit is
  started on that torus — ``(theta, p) = (0, omega)`` — not at ``p = 0``,
  which sits inside the main ``p ~ 0`` resonance island and stays regular
  far above the golden KAM boundary.
* ``critical_k`` uses Greene's criterion on a continued-fraction
  convergent of ``omega``: the torus is broken once the convergent's
  residue magnitude passes the universal critical value ``R* ≈ 0.25``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Tuple

import numpy as np

from .first_principles import (
    ConvergenceError,
    additive_recurrence,
    generalized_golden,
    golden_ratio,
    golden_turn,
    greene_residue,
    maximal_lyapunov,
    plastic_number,
    standard_map_step,
)


class StabilityError(ValueError):
    """A stability-engine contract was violated."""


GREENE_CRITICAL_RESIDUE = 0.250088
"""Universal residue magnitude at the KAM breakup boundary."""


@dataclass(frozen=True)
class StabilityMetrics:
    """Measured invariants for one (K, omega) orbit sample."""

    lyapunov_exponent: float
    nearest_neighbor_variance: float
    discrepancy_score: float
    stability_class: str  # 'KAM_TORUS', 'RESONANCE', 'CHAOTIC', 'MIXED'


def _regular_mle_floor(iterations: int) -> float:
    """Finite-time MLE ceiling of a regular orbit over ``iterations`` steps.

    On a KAM torus a generic tangent grows ~linearly, so the renormalized
    average leaves a ``~log(steps)/steps`` residue; a margin of 4 clears
    the measured floor at the iteration counts used here.
    """
    return 4.0 * math.log(max(int(iterations), 2)) / max(int(iterations), 1)


def continued_fraction_convergent(
    omega: float, max_denominator: int
) -> Tuple[int, int]:
    """Best rational ``p/q`` approximating ``omega`` with ``q <= max_denominator``.

    Walks the continued fraction of the fractional part of ``omega`` and
    returns the last convergent inside the denominator cap.
    """
    omega = float(omega) % 1.0
    x = omega
    p_prev, p = 0, 1
    q_prev, q = 1, 0
    best = (0, 1)
    while x > 1e-12:
        a = int(math.floor(x))
        p_next, q_next = a * p + p_prev, a * q + q_prev
        if q_next > max_denominator:
            break
        p_prev, p = p, p_next
        q_prev, q = q, q_next
        if 0 < p < q:
            best = (p, q)
        if x - a <= 1e-12:
            break  # exact rational — convergent is already final
        x = 1.0 / (x - a)
    return best


class GoldenStabilityEngine:
    """Dynamical-invariant metrics on the standard map."""

    def __init__(self, dimension: int = 2):
        self.dimension = int(dimension)
        self.phi = golden_ratio()
        self.plastic = plastic_number()

    def standard_map_iterate(
        self, theta: float, momentum: float, k: float
    ) -> tuple[float, float]:
        """One Chirikov step on the lift (delegates to first_principles)."""
        return standard_map_step(k, theta, momentum)

    def calculate_max_lyapunov(
        self, k: float, omega: float, iterations: int = 5000
    ) -> float:
        """MLE of the orbit started on the ``omega``-winding torus ``(0, omega)``."""
        return maximal_lyapunov(k, 0.0, omega, iterations)

    def greene_residue(
        self, k: float, period: int, winding: int
    ) -> tuple[float, float]:
        """Greene residue ``(residue, closure)`` of the winding/period orbit.

        Newton-solved periodic orbit plus monodromy residue, delegated to
        :func:`kellogg.first_principles.greene_residue` — the elevated
        Wall-11 measurement (residue -> 0.25 at the KAM boundary).
        """
        return greene_residue(k, period, winding)

    def nearest_neighbor_variance(self, points: np.ndarray) -> float:
        """Continuous coverage proxy: variance of nearest-neighbour distances.

        The transcript's scipy Voronoi area variance is unavailable without
        scipy; the pseudocode itself notes NN-distance variance is a sound
        continuous stand-in.  Perfectly uniform coverage → variance → 0.
        """
        pts = np.asarray(points, dtype=float)
        n = pts.shape[0]
        if n < 2:
            return math.inf
        dists = np.sqrt(((pts[:, None, :] - pts[None, :, :]) ** 2).sum(axis=-1))
        np.fill_diagonal(dists, math.inf)
        nearest = dists.min(axis=1)
        return float(np.var(nearest))

    def discrepancy_score(
        self, points: np.ndarray, samples: int = 64, seed: int = 0
    ) -> float:
        """Monte-Carlo star-discrepancy proxy.  Lower is more uniform."""
        pts = np.asarray(points, dtype=float)
        n = pts.shape[0]
        if n == 0:
            return math.inf
        span = pts.max(axis=0) - pts.min(axis=0)
        span[span == 0.0] = 1.0
        normed = (pts - pts.min(axis=0)) / span
        rng = np.random.default_rng(seed)
        deviations = []
        for _ in range(int(samples)):
            corner = rng.random(pts.shape[1])
            actual = float(np.mean(np.all(normed <= corner, axis=1)))
            expected = float(np.prod(corner))
            deviations.append(abs(actual - expected))
        return float(np.mean(deviations))

    def analyze_stability(
        self,
        k: float,
        omega: float,
        n_points: int = 1000,
        lyapunov_iterations: int = 2000,
        seed: int = 0,
    ) -> StabilityMetrics:
        """Lyapunov + coverage invariants for the ``omega``-winding orbit at K.

        The orbit is started on the torus ``(theta, p) = (0, omega)``; the
        class thresholds are scaled to the finite-time regular floor
        ``~4*log(steps)/steps`` (see module docstring).
        """
        x, p = 0.0, float(omega)
        pts = np.empty((n_points, 2), dtype=float)
        for i in range(n_points):
            x, p = self.standard_map_iterate(x, p, k)
            pts[i] = (x, p)

        mle = self.calculate_max_lyapunov(k, omega, lyapunov_iterations)
        nn_var = self.nearest_neighbor_variance(pts)
        disc = self.discrepancy_score(pts, seed=seed)

        floor = _regular_mle_floor(lyapunov_iterations)
        near = Fraction(omega % 1.0).limit_denominator(1000)
        is_small_rational = (
            near.denominator > 0
            and abs(float(near) - (omega % 1.0)) < 1e-12
        )
        if mle < floor:
            # A stable resonant orbit is not a torus — say so.
            stability = "RESONANCE" if is_small_rational else "KAM_TORUS"
        elif mle > 5.0 * floor:
            stability = "CHAOTIC"
        else:
            stability = "MIXED"

        return StabilityMetrics(
            lyapunov_exponent=mle,
            nearest_neighbor_variance=nn_var,
            discrepancy_score=disc,
            stability_class=stability,
        )

    def critical_k(
        self,
        omega: float,
        k_low: float = 0.0,
        k_high: float = 4.0,
        iterations: int = 24,
        max_period: int = 55,
        lyapunov_iterations: int = 1500,
        method: str = "greene",
    ) -> float:
        """Largest K whose ``omega``-winding orbit is still stable.

        ``method="greene"`` bisects on Greene's criterion: the convergent
        ``p/q`` of ``omega`` with ``q <= max_period`` is tracked and the
        torus counts as broken once ``|R|`` exceeds
        :data:`GREENE_CRITICAL_RESIDUE`.  A rational ``omega`` (exact
        convergent) uses ``|R| = 1`` — the orbit's own instability boundary,
        since a resonance has no KAM torus.  If the Newton orbit solver
        fails to close at some ``k``, that point counts as broken — no
        smooth invariant curve exists there to close against.

        ``method="mle"`` bisects on the finite-time Lyapunov floor instead
        (slower, noisier, kept as a cross-check).
        """
        if method == "greene":
            p, q = continued_fraction_convergent(omega, max_period)
            if q == 0:
                raise StabilityError(
                    f"no convergent for omega={omega} within {max_period}"
                )
            boundary = (
                1.0
                if abs(p / q - (omega % 1.0)) < 1e-9
                else GREENE_CRITICAL_RESIDUE
            )
            for _ in range(iterations):
                k_mid = 0.5 * (k_low + k_high)
                try:
                    residue, _ = self.greene_residue(k_mid, q, p)
                    stable = abs(residue) < boundary
                except ConvergenceError:
                    stable = False
                if stable:
                    k_low = k_mid
                else:
                    k_high = k_mid
            return 0.5 * (k_low + k_high)
        if method == "mle":
            floor = _regular_mle_floor(lyapunov_iterations)
            for _ in range(iterations):
                k_mid = 0.5 * (k_low + k_high)
                mle = self.calculate_max_lyapunov(
                    k_mid, omega, lyapunov_iterations
                )
                if mle < floor:
                    k_low = k_mid
                else:
                    k_high = k_mid
            return 0.5 * (k_low + k_high)
        raise StabilityError(f"unknown critical_k method {method!r}")


class PlasticSequenceGenerator:
    """Generalized-golden low-discrepancy sequences for dimension ``d``.

    Delegates to :func:`kellogg.first_principles.additive_recurrence`, which
    uses the degree-``d+1`` Pisot root: d=1 golden, d=2 plastic, etc.
    """

    def __init__(self, dimension: int):
        if dimension < 1:
            raise StabilityError(f"dimension must be >= 1, got {dimension}")
        self.d = int(dimension)
        self.constant = generalized_golden(self.d)

    def generate_sequence(self, n: int) -> np.ndarray:
        """``n`` points in ``[0,1)^d`` on the additive golden recurrence."""
        return additive_recurrence(int(n), self.d)


def benchmark_golden_vs_others(
    n_points: int = 2000,
    lyapunov_iterations: int = 1500,
    seed: int = 0,
) -> Dict[str, Dict[str, float]]:
    """Measured critical-K and coverage duel across winding numbers.

    For each frequency the critical kick strength is bisected on Greene's
    criterion, then a subcritical orbit is sampled for coverage metrics.
    All numbers are measured by this run — the transcript's reference
    values (golden K_c ≈ 0.97 vs sqrt(2) K_c ≈ 0.70) are expectations,
    not asserts.
    """
    engine = GoldenStabilityEngine()
    frequencies = {
        "golden": golden_turn(),
        "plastic": engine.plastic - 1.0,  # fractional part ~ 0.3247
        "sqrt2": math.sqrt(2.0) - 1.0,
        "rational": 0.5,
    }
    results: Dict[str, Dict[str, float]] = {}
    for name, omega in frequencies.items():
        k_crit = engine.critical_k(omega)
        metrics = engine.analyze_stability(
            k_crit * 0.5, omega, n_points=n_points,
            lyapunov_iterations=lyapunov_iterations, seed=seed,
        )
        results[name] = {
            "k_critical": k_crit,
            "lyapunov_exponent": metrics.lyapunov_exponent,
            "nearest_neighbor_variance": metrics.nearest_neighbor_variance,
            "discrepancy": metrics.discrepancy_score,
            "stability_class": metrics.stability_class,
        }
    return results


__all__ = [
    "GREENE_CRITICAL_RESIDUE",
    "GoldenStabilityEngine",
    "PlasticSequenceGenerator",
    "StabilityError",
    "StabilityMetrics",
    "benchmark_golden_vs_others",
    "continued_fraction_convergent",
]
