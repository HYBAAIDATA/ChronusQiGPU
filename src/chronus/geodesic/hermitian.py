"""Finite-field Hermitian tensor with genuinely alternating curvature component.

This is a mathematical Hermitian form on F_257[phi] = F_(257^2), using the
nontrivial Frobenius involution phi -> 1-phi. It is not a Riemannian
Fubini-Study metric over C, and has no probabilistic Born interpretation.

The legacy bilinear formula in chronus.quantum.geometric_polychoron
uses symmetric dot products, so its nominal antisymmetric component is
identically zero; it cannot certify Berry or Yang-Mills curvature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from chronus.quantum.geometric_polychoron import F257Phi, P


def conjugate(x: F257Phi) -> F257Phi:
    """257th Frobenius automorphism: (a+b*phi)^257 = (a+b)-b*phi."""
    return F257Phi(x.a + x.b, -x.b)


def hermitian(u: Sequence[F257Phi], v: Sequence[F257Phi]) -> F257Phi:
    if not u or len(u) != len(v):
        raise ValueError("Hermitian vectors must be nonempty and equally sized")
    result = F257Phi.zero()
    for x, y in zip(u, v):
        result = result + conjugate(x) * y
    return result


@dataclass(frozen=True)
class FiniteHermitianTensor:
    """Exact finite field projective Hermitian tensor and conjugate components."""
    tensor: F257Phi
    real_trace_half: int
    alternating_coefficient: int

    @classmethod
    def evaluate(cls,
                 state: Sequence[F257Phi],
                 direction_i: Sequence[F257Phi],
                 direction_j: Sequence[F257Phi]) -> "FiniteHermitianTensor":
        if not state or not len(state) == len(direction_i) == len(direction_j):
            raise ValueError("all three finite-field vectors must be equally sized")
        denominator = hermitian(state, state)
        if denominator.is_zero():
            raise ValueError("state has null Hermitian norm")
        inv_den = denominator.inverse()
        # Q_ij = <di|dj>/<psi|psi>
        #      - (<di|psi><psi|dj>)/<psi|psi>^2.
        q = (hermitian(direction_i, direction_j) * inv_den -
             hermitian(direction_i, state) *
             hermitian(state, direction_j) * inv_den * inv_den)
        # Fixed-field 'real' trace component: Tr_{F257^2/F257}(q)/2.
        # The coefficient of phi reverses sign under conjugation and
        # is therefore the genuinely alternating component.
        real = (q.a + q.b * pow(2, P-2, P)) % P
        return cls(q, real, q.b)

    def is_hermitian_partner_of(self, other: "FiniteHermitianTensor") -> bool:
        return other.tensor == conjugate(self.tensor)
