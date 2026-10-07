"""The 11D golden-weighted vector and its Klein fold, exactly in Q(phi).

A 3D direction lifts to 11 components v_i = n_(i mod 3) * phi^-(i div 3).
The phi-weighted norm is ||v||^2 = sum_i phi^-(i+1) v_i^2. The fold

    v -> v / sqrt(1 + ||v||^2)

maps all of R^11 into the open unit ball (folded norm^2 = N / (1 + N) < 1),
and unfold w -> w / sqrt(1 - ||w||^2) inverts it.

The weights need sqrt 5, so the field is Q(phi) = Q(sqrt 5), not Q(sqrt 2).
The square roots stay exact by carrying every vector as c * sqrt(r) with
c in Q(phi)^11 and radicand r in Q(phi), r > 0: fold sends r to
r / (1 + r ||c||^2) and unfold sends it back, so the round trip is equality,
not a tolerance. A unit 3D normal d / |d| is c = d, r = 1 / |d|^2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from .scales import Zphi, zeckendorf_11d
from .substrate import PHI_FIELD, QPhi

DIM = 11
_INV_PHI = PHI_FIELD.inverse()


def _inv_phi_power(k: int) -> QPhi:
    out = QPhi(1)
    for _ in range(k):
        out = out * _INV_PHI
    return out


WEIGHTS: Tuple[QPhi, ...] = tuple(_inv_phi_power(i + 1) for i in range(DIM))
LIFT_SCALES: Tuple[QPhi, ...] = tuple(_inv_phi_power(i // 3) for i in range(DIM))


class Vector11Error(ValueError):
    """An 11D vector contract was violated."""


@dataclass(frozen=True)
class RootVector:
    """The exact vector coeffs * sqrt(radicand) in Q(phi)^11 * sqrt(Q(phi))."""

    coeffs: Tuple[QPhi, ...]
    radicand: QPhi

    def __post_init__(self) -> None:
        if len(self.coeffs) != DIM:
            raise Vector11Error("an 11D vector needs 11 components")
        if self.radicand.sign() <= 0:
            raise Vector11Error("radicand must be positive")

    def coeff_norm_sq(self) -> QPhi:
        total = QPhi(0)
        for w, c in zip(WEIGHTS, self.coeffs):
            total = total + w * c * c
        return total

    def norm_sq(self) -> QPhi:
        """Exact phi-weighted norm squared."""
        return self.radicand * self.coeff_norm_sq()

    def inside_unit_ball(self) -> bool:
        return self.norm_sq() < QPhi(1)

    def to_float(self) -> Tuple[float, ...]:
        """One-way crossing into IEEE-754."""
        phi = 1.618033988749895
        scale = (float(self.radicand.a) + float(self.radicand.b) * phi) ** 0.5
        return tuple((float(c.a) + float(c.b) * phi) * scale for c in self.coeffs)

    def same_vector(self, other: "RootVector") -> bool:
        """Equality of c*sqrt(r): componentwise c_i^2 r == c'_i^2 r' with equal signs."""
        for a, b in zip(self.coeffs, other.coeffs):
            if a.sign() != b.sign():
                return False
            if (a * a * self.radicand - b * b * other.radicand).sign() != 0:
                return False
        return True


def lift(direction: Sequence[QPhi | Zphi | int], radicand: QPhi | int = 1) -> RootVector:
    """Lift a 3D direction (times sqrt(radicand)) into 11D."""
    if len(direction) != 3:
        raise Vector11Error("lift takes a 3D direction")
    d = [QPhi.of(x) for x in direction]
    coeffs = tuple(d[i % 3] * LIFT_SCALES[i] for i in range(DIM))
    return RootVector(coeffs, QPhi.of(radicand))


def unit_lift(direction: Sequence[QPhi | Zphi | int]) -> RootVector:
    """Lift the unit normal d / |d|: radicand 1 / |d|^2, exact."""
    d = [QPhi.of(x) for x in direction]
    euclid = d[0] * d[0] + d[1] * d[1] + d[2] * d[2]
    return lift(d, euclid.inverse())


def fold(v: RootVector) -> RootVector:
    """Klein fold v / sqrt(1 + ||v||^2): radicand r -> r / (1 + r ||c||^2)."""
    radicand = v.radicand / (QPhi(1) + v.norm_sq())
    return RootVector(v.coeffs, radicand)


def unfold(w: RootVector) -> RootVector:
    """Inverse fold w / sqrt(1 - ||w||^2); defined inside the open unit ball."""
    gap = QPhi(1) - w.norm_sq()
    if gap.sign() <= 0:
        raise Vector11Error("unfold is defined only inside the open unit ball")
    return RootVector(w.coeffs, w.radicand / gap)


def fold_certificate(v: RootVector) -> dict:
    """Exact fold record: norms, ball membership, round trip, Zeckendorf token."""
    from .certificate import cex_digest

    w = fold(v)
    back = unfold(w)
    digest = cex_digest({"coeffs": list(v.coeffs), "radicand": v.radicand})
    return {
        "norm_sq": v.norm_sq(),
        "folded_norm_sq": w.norm_sq(),
        "inside_unit_ball": w.inside_unit_ball(),
        "roundtrip_exact": back.coeffs == v.coeffs and back.radicand == v.radicand,
        "zeckendorf": zeckendorf_11d(int(digest, 16) % (1 << 64)),
        "digest": digest,
    }


__all__ = [
    "DIM",
    "LIFT_SCALES",
    "RootVector",
    "Vector11Error",
    "WEIGHTS",
    "fold",
    "fold_certificate",
    "lift",
    "unfold",
    "unit_lift",
]
