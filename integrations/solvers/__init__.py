"""Solver scaffolds for EUCLID's emergent intelligence.

Each scaffold targets a specific mathematical problem domain:
- bsd_scaffold: Birch and Swinnerton-Dyer conjecture exploration
- tce_scaffold: Tate's conjecture (pending)
- mahler_scaffold: Mahler measure (pending)

References:
- Clay Mathematics Institute Millennium Prize Problems
  https://www.claymath.org/millennium-problems/
- Birch, B. J., & Swinnerton-Dyer, H. P. F. (1965). Notes on elliptic curves (II).
  Journal für die reine und angewandte Mathematik, 218, 79-108.
- Wilfrid Hodges (1993). Model Theory. Cambridge University Press.
- Penrose, R. (1989). The Emperor's New Mind. Oxford University Press.
- Tononi, G. (2008). Consciousness as Integrated Information.
  Brain Research Reviews, 58(2), 109-120.
"""

from __future__ import annotations

from integrations.solvers.bsd_scaffold import (
    BSDScribe,
    BSDScribeConfig,
    EllipticCurve,
    EllipticCurvePoint,
    integrate_information,
)

__all__ = [
    "BSDScribe",
    "BSDScribeConfig",
    "EllipticCurve",
    "EllipticCurvePoint",
    "integrate_information",
]
