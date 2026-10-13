"""Yang-Mills finite-volume mass gap research scaffold.

Provides an internal research surface for analyzing the quantum-group
Laplacian on the binary icosahedral group 2I (the 600-cell triangulation of S^3).

Important:
This is a finite-volume lattice/group-algebra model. It does not establish
a proof of the Clay Millennium problem on continuum R^4.
proof_claim remains False.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from millennium.exact_gap import (
    EVIDENCE_CLASS,
    PROOF_CLAIM,
    CONTINUUM_CLAIM,
    SCOPE,
    ExactGap,
    derive_exact_mass_gap,
    exact_gap_from_class_algebra,
)


@dataclass
class YangMillsScaffoldConfig:
    """Configuration for the Yang-Mills finite-volume research scaffold."""

    k_generating_set: int = 12
    compute_full_spectrum: bool = True
    enforce_boundary_honesty: bool = True


class YangMillsScaffold:
    """Internal research scaffold for exact finite-volume Yang-Mills spectral gap analysis."""

    def __init__(self, config: Optional[YangMillsScaffoldConfig] = None) -> None:
        self.config = config or YangMillsScaffoldConfig()

    def analyze_finite_spectrum(self) -> Dict[str, Any]:
        """Compute the exact proof-carrying spectrum of the 2I Laplacian."""
        gap_obj = exact_gap_from_class_algebra()
        return {
            "status": "FINITE_VOLUME_SPECTRAL_VERIFICATION",
            "gap_exact": {
                "formula": "(3 - sqrt(5))/4",
                "float_value": gap_obj.gap_float,
                "dimension": gap_obj.dimension,
                "verified": gap_obj.verify_exact(),
            },
            "char_poly_coeffs": list(gap_obj.char_poly_coeffs),
            "level_count": len(gap_obj.levels),
            "levels": [
                {
                    "irrep": lvl.irrep_index,
                    "dimension": lvl.dimension,
                    "multiplicity": lvl.multiplicity,
                    "eigenvalue_exact": f"({lvl.eigenvalue_exact[0]} + {lvl.eigenvalue_exact[1]}*sqrt(5))/{lvl.eigenvalue_exact[2]}",
                    "eigenvalue_float": lvl.eigenvalue_float,
                }
                for lvl in gap_obj.levels
            ],
            "evidence_class": EVIDENCE_CLASS,
            "proof_claim": PROOF_CLAIM,
            "continuum_claim": CONTINUUM_CLAIM,
            "scope": SCOPE,
        }

    def compute_gap_ratio(self) -> float:
        """Return the exact floating point mass gap Δ = (3 - √5)/4."""
        gap_obj = exact_gap_from_class_algebra()
        return gap_obj.gap_float


__all__ = [
    "YangMillsScaffold",
    "YangMillsScaffoldConfig",
]
