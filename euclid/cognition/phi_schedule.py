"""φ-based exploration ordering — exploratory, parametric use only.

Per the Lucas/Pisot precision contract (#110): this module is a *parametric*
ordering heuristic computed in host binary64.  It claims no structural or
certifying role, no mining or scheduling advantage, and no speedup.  Any
promotion beyond exploration ordering is measurement-gated and must compare
against :func:`neutral_order` as the honest baseline.
"""
from __future__ import annotations

EVIDENCE_CLASS = "exploratory-parametric"

# Host float64 golden ratio.  Parametric use only; see module docstring.
PHI = (1.0 + 5.0 ** 0.5) / 2.0
PSI = (1.0 - 5.0 ** 0.5) / 2.0


def pisot_damp(n: int) -> float:
    """Quantum convergence factor (1 - |psi|^n) for ladder rung n."""
    if n < 0:
        raise ValueError("ladder rung n must be non-negative")
    return 1.0 - abs(PSI) ** n


def pisot_subspace_size(total_size: int, n: int) -> int:
    """Deterministic Pisot-damped subspace budget for ladder rung n."""
    import math

    if total_size < 0:
        raise ValueError("total_size must be >= 0")
    return math.ceil(total_size * pisot_damp(n))


def phi_order(size: int) -> list[int]:
    """Golden-ratio low-discrepancy permutation of ``range(size)``.

    Deterministic for a given size; useful as an exploration-order policy
    whose value must be established empirically against ``neutral_order``.
    """
    if size < 0:
        raise ValueError("size must be >= 0")
    return sorted(range(size), key=lambda index: (index * PHI) % 1.0)


def neutral_order(size: int) -> list[int]:
    """Identity ordering: the neutral baseline for φ-ordering experiments."""
    if size < 0:
        raise ValueError("size must be >= 0")
    return list(range(size))


__all__ = [
    "EVIDENCE_CLASS",
    "PHI",
    "PSI",
    "neutral_order",
    "phi_order",
    "pisot_damp",
    "pisot_subspace_size",
]

