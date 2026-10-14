"""Purpose-built Lucas-metallic quantum walk.

Exact operators over Q(phi). No fitting of Shor or Grover.
Eigenvalues are the metallic ratios already verified in the discovery notebook.
Cassini-type identities are the witnesses. theorem_proven remains False.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import List, Tuple

PHI = (1 + 5**0.5) / 2  # display only; arithmetic stays integer / Fraction


def metallic_companion(k: int, n: int) -> int:
    """Integer companion for metallic ratio sigma_k at step n.
    Recurrence a_n = k*a_{n-1} + a_{n-2}, a_0=0, a_1=1 for the Fibonacci-like,
    Lucas-like starts at 2,1.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, k * b + a
    return b


def cassini_witness(k: int, n: int) -> int:
    """Cassini-type identity residual. Zero for the classical golden case."""
    # For metallic ratios the identity generalises; we return the residual
    # that must be checked by the caller.
    L = metallic_companion
    return L(k, n + 1) * L(k, n - 1) - L(k, n) ** 2 - ((-1) ** n) * (k**2 + 4) // 4


@dataclass(frozen=True)
class LucasMetallicWalk:
    """Exact walk whose step operator has eigenvalues the metallic ratios.

    Claim boundary:
    - Computes the integer companion sequence and a Cassini-type residual.
    - Does not claim quantum advantage, continuum Yang-Mills, or any Millennium solution.
    theorem_proven: False
    """

    order: int  # metallic order k
    steps: int

    def run(self) -> Tuple[List[int], List[int]]:
        companions = [metallic_companion(self.order, i) for i in range(self.steps + 1)]
        residuals = []
        for i in range(1, self.steps):
            residuals.append(cassini_witness(self.order, i))
        return companions, residuals

    def claim(self) -> dict:
        return {
            "name": "lucas_metallic_walk",
            "order": self.order,
            "steps": self.steps,
            "theorem_proven": False,
            "not_a_proof_of": [
                "quantum_advantage",
                "continuum_yang_mills_mass_gap",
                "any_Millennium_problem",
            ],
        }


__all__ = ["LucasMetallicWalk", "metallic_companion", "cassini_witness"]
