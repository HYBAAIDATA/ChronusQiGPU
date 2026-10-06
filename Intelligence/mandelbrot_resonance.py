"""Mandelbrot boundary anchoring for candidate ordering (Phase 5).

The spec calls this "Fractal Resonance": search vectors are snapped toward
the boundary of the Mandelbrot set and the measured boundary affinity is
used as an ordering heuristic for nonce candidates.

HONEST SCOPE
------------
This module computes *real, deterministic mathematics*: Mandelbrot
escape-time iterations, exterior distance estimation, and boundary-edge
snapping. What it does NOT do is claim that boundary-anchored nonces are
more likely to satisfy the SHA-256d target. It is an ordering/prioritization
heuristic in the same truth class as the phi-resonance and Cassini
manifold orderings: it decides *where to look first*, never *what counts
as a valid share*. The resonance probe (mining/resonance_probe.py) is the
instrument that would detect any real enrichment; none has been measured.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Boundary interrogation constants. These are mathematical constants of the
# method, not unexplained magic values:
#   ESCAPE_RADIUS = 2: if |z| ever exceeds 2 the orbit diverges (proved).
#   MAX_ITER bounds the escape-time computation; higher values resolve the
#   boundary more finely at linear cost.
ESCAPE_RADIUS = 2.0
MAX_ITER = 64

# The classical main-cardioid/period-2-bulb region of interest for nonce
# anchoring: c in [-2.0, 0.47] x [-1.12i, 1.12i] covers the entire set.
C_RE_MIN, C_RE_MAX = -2.0, 0.47
C_IM_MIN, C_IM_MAX = -1.12, 1.12


def _escape_time(cre: float, cim: float, max_iter: int = MAX_ITER) -> Tuple[int, float]:
    """Escape iteration and final |z| for z0=0, z_{k+1} = z_k^2 + c.

    Returns (n, |z_n|) where n is the first iteration with |z| > 2, or
    (max_iter, |z|) if the orbit never escaped (interior or boundary).
    """
    zr = zi = 0.0
    for n in range(max_iter):
        zr, zi = zr * zr - zi * zi + cre, 2.0 * zr * zi + cim
        r2 = zr * zr + zi * zi
        if r2 > ESCAPE_RADIUS * ESCAPE_RADIUS:
            return n, math.sqrt(r2)
    return max_iter, math.sqrt(zr * zr + zi * zi)


def _exterior_distance(cre: float, cim: float, max_iter: int = MAX_ITER) -> float:
    """Hubbard-Douady exterior distance estimate to the boundary.

    d(c) ~ |z_n| * ln|z_n| / |z'_n|, evaluated after escape. 0.0 for
    interior/non-escaping orbits. Real analysis, not a heuristic score.
    """
    zr = zi = 0.0
    dr = di = 0.0
    for _ in range(max_iter):
        # derivative z'_{k+1} = 2 z_k z'_k + 1
        dr, di = 2.0 * (zr * dr - zi * di) + 1.0, 2.0 * (zr * di + zi * dr)
        zr, zi = zr * zr - zi * zi + cre, 2.0 * zr * zi + cim
        r2 = zr * zr + zi * zi
        if r2 > ESCAPE_RADIUS * ESCAPE_RADIUS:
            r = math.sqrt(r2)
            dmag = math.sqrt(dr * dr + di * di)
            if dmag == 0.0:
                return 0.0
            return (r * math.log(r)) / dmag
    return 0.0


def _snap_to_boundary(cre: float, cim: float, max_iter: int = MAX_ITER) -> Tuple[float, float]:
    """Snap a point toward the nearest boundary edge.

    One Newton step on the level set f(c) = |z_N(c)| - R = 0, where
    d|z|/dc = (z * conj(z'))/|z|. Interior orbits (|z_N| < R) step outward;
    escaped orbits (|z_N| > R) step inward — both toward the boundary.
    One step suffices for an ordering heuristic.
    """
    zr = zi = 0.0
    dr = di = 0.0
    for _ in range(max_iter):
        dr, di = 2.0 * (zr * dr - zi * di) + 1.0, 2.0 * (zr * di + zi * dr)
        zr, zi = zr * zr - zi * zi + cre, 2.0 * zr * zi + cim
    r = math.sqrt(zr * zr + zi * zi)
    # complex derivative d|z|/dc = z * conj(z') / |z|
    gr = (zr * dr + zi * di) / r if r > 1e-24 else 0.0
    gi = (zi * dr - zr * di) / r if r > 1e-24 else 0.0
    gnorm2 = gr * gr + gi * gi
    if r < 1e-24 or gnorm2 < 1e-24:
        return cre, cim
    f = r - ESCAPE_RADIUS
    return cre - f * gr / gnorm2, cim - f * gi / gnorm2


def nonce_to_complex(nonce: int) -> Tuple[float, float]:
    """Deterministic map uint32 -> complex plane region containing M.

    Splits the nonce into two 16-bit halves and scales each into the
    region's real/imaginary extent. Pure function — identical nonce always
    lands at identical c.
    """
    hi = (nonce >> 16) & 0xFFFF
    lo = nonce & 0xFFFF
    cre = C_RE_MIN + (C_RE_MAX - C_RE_MIN) * (hi / 65535.0)
    cim = C_IM_MIN + (C_IM_MAX - C_IM_MIN) * (lo / 65535.0)
    return cre, cim


def boundary_affinity(nonce: int, max_iter: int = MAX_ITER) -> float:
    """Boundary affinity score in (0,1): 1.0 = on the boundary.

    Combines escape-time proximity to max_iter (deep orbits sit near the
    edge) with inverse exterior distance. Deterministic, real computation.
    """
    cre, cim = nonce_to_complex(nonce)
    n, _r = _escape_time(cre, cim, max_iter)
    if n >= max_iter:
        return 1.0  # interior/boundary orbit — maximal affinity
    depth = n / max_iter
    d = _exterior_distance(cre, cim, max_iter)
    proximity = 1.0 / (1.0 + d) if d > 0 else 1.0
    return 0.5 * depth + 0.5 * proximity


@dataclass
class AnchoredCandidate:
    nonce: int
    affinity: float
    snapped_cre: float
    snapped_cim: float


class MandelbrotResonanceEngine:
    """Boundary anchoring engine for the solve-path candidate ordering.

    Produces candidates whose complex-plane images are snapped toward the
    Mandelbrot boundary, ranked by measured boundary affinity. This is an
    ORDERING layer only: every candidate still requires physical SHA-256d
    evaluation against the pool target. Claim boundary identical to the
    other manifold orderings — no probability advantage asserted.
    """

    truth_label = "ordering-heuristic"

    def __init__(self, max_iter: int = MAX_ITER):
        self.max_iter = int(max_iter)

    def anchor(self, nonce: int) -> AnchoredCandidate:
        cre, cim = nonce_to_complex(int(nonce) & 0xFFFFFFFF)
        sre, sim = _snap_to_boundary(cre, cim, self.max_iter)
        return AnchoredCandidate(
            nonce=int(nonce) & 0xFFFFFFFF,
            affinity=boundary_affinity(int(nonce) & 0xFFFFFFFF, self.max_iter),
            snapped_cre=sre,
            snapped_cim=sim,
        )

    def order_candidates(self, nonces: List[int]) -> List[int]:
        """Reorder candidates by descending measured boundary affinity."""
        scored = sorted(
            ((boundary_affinity(int(n) & 0xFFFFFFFF, self.max_iter), int(n)) for n in nonces),
            key=lambda t: (-t[0], t[1]),
        )
        return [n for _a, n in scored]

    def telemetry(self, nonces: List[int]) -> Dict[str, object]:
        """Measured statistics for the probe/telemetry layer."""
        if not nonces:
            return {"candidates": 0, "truth_label": self.truth_label}
        aff = [boundary_affinity(int(n) & 0xFFFFFFFF, self.max_iter) for n in nonces]
        mean = sum(aff) / len(aff)
        return {
            "candidates": len(nonces),
            "affinity_mean": mean,
            "affinity_max": max(aff),
            "affinity_min": min(aff),
            "truth_label": self.truth_label,
            "claim_boundary": (
                "ordering heuristic only; no SHA-256d target-probability "
                "advantage asserted or implied"
            ),
        }
