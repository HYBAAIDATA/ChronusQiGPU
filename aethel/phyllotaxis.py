"""Sunflower / Vogel phyllotaxis packing — first-principles φ geometry.

Storage slots are placed on the Fermat/Vogel spiral:

    r(n) = scale * sqrt(n)
    θ(n) = n * GOLDEN_ANGLE

where GOLDEN_ANGLE = 2π · φ^{-2} = π(3 - √5) ≈ 2.399963229728653.

This is packing geometry for Theseus commits — not a biotech compiler,
not infinite capacity, and not a B-tree locality claim.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

# Exact algebraic form: 2π / φ² = π(3 − √5)
GOLDEN_ANGLE: float = math.pi * (3.0 - math.sqrt(5.0))
# Machine reference matching punch 0x05 / OpenCL tables
GOLDEN_ANGLE_REF: float = 2.39996322972865332

_PHI: float = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass(frozen=True)
class PhyllotaxisSite:
    """One sunflower-disk slot."""

    index: int
    radius: float
    theta: float
    x: float
    y: float
    # Discrete ring ≈ floor(r); used for sector routing
    ring: int
    # Angular bucket in [0, buckets)
    sector: int


def golden_angle_theta(n: int) -> float:
    """θ(n) = n · GOLDEN_ANGLE, n ≥ 0."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError(f"phyllotaxis index must be int ≥ 0, got {n!r}")
    return n * GOLDEN_ANGLE


def vogel_site(
    n: int,
    *,
    scale: float = 1.0,
    buckets: int = 32,
) -> PhyllotaxisSite:
    """Place slot ``n`` on the Vogel sunflower spiral.

    ``buckets`` defaults to 32 to align with the Chronus M32 face frame
    for sector/lane routing — a packing hint, not a hash preimage.
    """
    if scale <= 0:
        raise ValueError("scale must be > 0")
    if buckets < 1:
        raise ValueError("buckets must be ≥ 1")
    theta = golden_angle_theta(n)
    radius = scale * math.sqrt(float(n))
    x = radius * math.cos(theta)
    y = radius * math.sin(theta)
    ring = int(math.floor(radius)) if radius > 0 else 0
    # Map angle into [0, 2π) then bucket
    two_pi = 2.0 * math.pi
    norm = theta % two_pi
    if norm < 0:
        norm += two_pi
    sector = int(norm / two_pi * buckets) % buckets
    return PhyllotaxisSite(
        index=n,
        radius=radius,
        theta=theta,
        x=x,
        y=y,
        ring=ring,
        sector=sector,
    )


def pack_indices(
    count: int,
    *,
    scale: float = 1.0,
    buckets: int = 32,
) -> List[PhyllotaxisSite]:
    """Pack ``count`` consecutive slots starting at 0."""
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError(f"count must be int ≥ 0, got {count!r}")
    return [vogel_site(i, scale=scale, buckets=buckets) for i in range(count)]


def pack_from_anchor(
    anchor: int,
    *,
    scale: float = 1.0,
    buckets: int = 32,
    modulus: int = 90,
) -> PhyllotaxisSite:
    """Map a Cassini/pv-lattice anchor into a sunflower site.

    Anchors live in ``[0, modulus)`` (default 90-slot manifold domain).
    """
    if not isinstance(anchor, int) or isinstance(anchor, bool):
        raise ValueError(f"anchor must be int, got {anchor!r}")
    if modulus < 1:
        raise ValueError("modulus must be ≥ 1")
    if not 0 <= anchor < modulus:
        raise ValueError(f"anchor {anchor} outside [0, {modulus})")
    return vogel_site(anchor, scale=scale, buckets=buckets)


def nearest_site(
    x: float,
    y: float,
    sites: Sequence[PhyllotaxisSite],
) -> PhyllotaxisSite:
    """Nearest packed site to a Euclidean query point (fail-closed if empty)."""
    if not sites:
        raise ValueError("sites must be non-empty")
    best = sites[0]
    best_d = (best.x - x) ** 2 + (best.y - y) ** 2
    for site in sites[1:]:
        d = (site.x - x) ** 2 + (site.y - y) ** 2
        if d < best_d:
            best = site
            best_d = d
    return best


def sector_lane(site: PhyllotaxisSite) -> int:
    """M32-aligned lane id = sunflower sector."""
    return site.sector


def verify_golden_angle_constant(tol: float = 1e-12) -> bool:
    """Algebraic GOLDEN_ANGLE matches punch-table reference within ``tol``."""
    return abs(GOLDEN_ANGLE - GOLDEN_ANGLE_REF) <= tol and abs(
        GOLDEN_ANGLE - (2.0 * math.pi / (_PHI ** 2))
    ) <= tol


def packing_metrics(sites: Iterable[PhyllotaxisSite]) -> dict:
    """Measured packing summary (no simulated capacity claims)."""
    materialised = list(sites)
    if not materialised:
        return {
            "count": 0,
            "max_radius": 0.0,
            "sectors_used": 0,
            "truth": "measured",
        }
    sectors = {s.sector for s in materialised}
    return {
        "count": len(materialised),
        "max_radius": max(s.radius for s in materialised),
        "sectors_used": len(sectors),
        "sector_ids": sorted(sectors),
        "truth": "measured",
    }


__all__ = [
    "GOLDEN_ANGLE",
    "GOLDEN_ANGLE_REF",
    "PhyllotaxisSite",
    "golden_angle_theta",
    "vogel_site",
    "pack_indices",
    "pack_from_anchor",
    "nearest_site",
    "sector_lane",
    "verify_golden_angle_constant",
    "packing_metrics",
]
