"""Finite, deterministic M32 routing topology for mining work allocation.

The 32 lanes are anchored to the 32 face-normal directions of the truncated
icosahedron (12 pentagon + 20 hexagon face centres). ``verify_spherical_design``
proves, in exact Q(sqrt(5)) arithmetic, that this frame is a spherical
5-design: every Legendre frame-potential moment of degree 1..5 vanishes
exactly. The proof is structural, not statistical; a degraded frame raises
``M32GovernanceError`` so callers fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import cmp_to_key, lru_cache
from itertools import product

LANES = 32
M32_EDGES = tuple(
    sorted(
        {
            tuple(sorted((lane, (lane + offset) % LANES)))
            for lane in range(LANES)
            for offset in (1, 2, 5, 8, 16)
            if lane != (lane + offset) % LANES
        }
    )
)


class M32GovernanceError(RuntimeError):
    """Raised when the M32 frame fails a declared structural invariant.

    Carrying the failing moments lets the Euclid governance layer remediate
    (re-anchor or quarantine the geometry) before any work is allocated on a
    degraded manifold.
    """

    def __init__(self, message: str, *, moments: dict | None = None) -> None:
        super().__init__(message)
        self.moments = moments or {}


class _Q5:
    """Exact element of Q(sqrt(5)): ``a + b*sqrt(5)`` with rational parts."""

    __slots__ = ("a", "b")

    def __init__(self, a=0, b=0):
        self.a = a if isinstance(a, Fraction) else Fraction(a)
        self.b = b if isinstance(b, Fraction) else Fraction(b)

    def __add__(self, other: "_Q5") -> "_Q5":
        return _Q5(self.a + other.a, self.b + other.b)

    def __sub__(self, other: "_Q5") -> "_Q5":
        return _Q5(self.a - other.a, self.b - other.b)

    def __neg__(self) -> "_Q5":
        return _Q5(-self.a, -self.b)

    def __mul__(self, other: "_Q5") -> "_Q5":
        return _Q5(
            self.a * other.a + 5 * self.b * other.b,
            self.a * other.b + self.b * other.a,
        )

    def __truediv__(self, other: "_Q5") -> "_Q5":
        norm = other.a * other.a - 5 * other.b * other.b
        if norm == 0:
            raise ZeroDivisionError("division by zero in Q(sqrt(5))")
        conj = _Q5(other.a, -other.b)
        num = self * conj
        return _Q5(num.a / norm, num.b / norm)

    def __pow__(self, n: int) -> "_Q5":
        if n < 0:
            return (_Q5(1) / self) ** (-n)
        result = _Q5(1)
        base = self
        while n:
            if n & 1:
                result = result * base
            base = base * base
            n >>= 1
        return result

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, _Q5) and self.a == other.a and self.b == other.b
        )

    def is_zero(self) -> bool:
        return self.a == 0 and self.b == 0

    def _cmp_int(self, n: int) -> int:
        """Sign of ``self - n`` computed exactly (0/±1)."""
        b = self.b
        d = self.a - n  # compare b*sqrt(5) vs -d
        if b == 0:
            return (d > 0) - (d < 0)
        # b*sqrt(5) vs -d : multiply out sign cases.
        if b > 0:
            if d >= 0:
                return 1
            return 1 if 5 * b * b > d * d else (-1 if 5 * b * b < d * d else 0)
        if d <= 0:
            return -1
        return -1 if 5 * b * b > d * d else (1 if 5 * b * b < d * d else 0)

    def floor(self) -> int:
        """Exact floor via float estimate plus exact-compare adjustment."""
        estimate = int(float(self.a) + float(self.b) * 2.23606797749979) - 1
        while self._cmp_int(estimate + 1) >= 0:
            estimate += 1
        while self._cmp_int(estimate) < 0:
            estimate -= 1
        return estimate

    def __repr__(self) -> str:
        return f"Q5({self.a} + {self.b}*sqrt5)"


def _q5_cmp(left: _Q5, right: _Q5) -> int:
    """Exact three-way comparison on Q(sqrt(5))."""
    return (left - right)._cmp_int(0)


_PHI = _Q5(Fraction(1, 2), Fraction(1, 2))
_PHI_INV = _Q5(Fraction(-1, 2), Fraction(1, 2))
_ZERO = _Q5(0)
_ONE = _Q5(1)

# Legendre polynomials P_1..P_5 as {power: rational coefficient}.
_LEGENDRE: dict[int, dict[int, Fraction]] = {
    1: {1: Fraction(1)},
    2: {2: Fraction(3, 2), 0: Fraction(-1, 2)},
    3: {3: Fraction(5, 2), 1: Fraction(-3, 2)},
    4: {4: Fraction(35, 8), 2: Fraction(-30, 8), 0: Fraction(3, 8)},
    5: {5: Fraction(63, 8), 3: Fraction(-70, 8), 1: Fraction(15, 8)},
}


def _cyclic(sign_a: int, first: _Q5, sign_b: int, second: _Q5) -> list[tuple[_Q5, ...]]:
    return [
        (_ZERO, first * _Q5(sign_a), second * _Q5(sign_b)),
        (first * _Q5(sign_a), second * _Q5(sign_b), _ZERO),
        (second * _Q5(sign_b), _ZERO, first * _Q5(sign_a)),
    ]


def truncated_icosahedron_frame() -> tuple[tuple[_Q5, ...], ...]:
    """The 32 M32 face-normal directions in exact Q(sqrt(5)) coordinates.

    Pentagon face centres are the icosahedron vertex directions (orbit A,
    norm^2 = phi + 2); hexagon face centres are the dodecahedron vertex
    directions (orbit B, norm^2 = 3). Coordinates are unnormalised; the
    design proof supplies the per-orbit norm factors.
    """
    orbit_a: list[tuple[_Q5, ...]] = []
    for sa, sb in product((1, -1), repeat=2):
        orbit_a.extend(_cyclic(sa, _ONE, sb, _PHI))
    orbit_b: list[tuple[_Q5, ...]] = [
        tuple(_Q5(s) for s in signs) for signs in product((1, -1), repeat=3)
    ]
    for sa, sb in product((1, -1), repeat=2):
        orbit_b.extend(_cyclic(sa, _PHI_INV, sb, _PHI))
    frame = tuple(orbit_a + orbit_b)
    if len(frame) != LANES:
        raise M32GovernanceError("M32 frame must contain exactly 32 directions")
    return frame


def _dot(p: tuple[_Q5, ...], q: tuple[_Q5, ...]) -> _Q5:
    return p[0] * q[0] + p[1] * q[1] + p[2] * q[2]


def _legendre_value(degree: int, cosine: _Q5) -> _Q5:
    total = _Q5(0)
    for power, coeff in _LEGENDRE[degree].items():
        total = total + (cosine ** power) * _Q5(coeff)
    return total


def spherical_design_moments(
    frame: tuple[tuple[_Q5, ...], ...] | None = None, max_degree: int = 5
) -> dict[int, dict[str, object]]:
    """Exact Legendre frame-potential moments of the M32 frame.

    For each degree ell, FP_ell = sum_{i,j} P_ell(x_i . x_j) vanishes iff
    every degree-ell harmonic moment vanishes (addition theorem), which is
    the spherical-design criterion. Same-orbit cosines live in Q(sqrt(5))
    directly (r_A^2 = phi + 2, r_B^2 = 3); cross-orbit cosines scale by
    w = 1/sqrt(3*phi + 6), which is provably outside Q(sqrt(5)), so the
    moment splits into a Q(sqrt(5)) part and a w-coefficient part that must
    each vanish.
    """
    points = list(frame) if frame is not None else list(truncated_icosahedron_frame())
    if len(points) != LANES:
        raise M32GovernanceError("frame must contain exactly 32 points")
    r2_a = _PHI + _Q5(2)
    r2_b = _Q5(3)
    # Orbit membership by squared norm.
    norms = [_dot(p, p) for p in points]
    if any(n != r2_a and n != r2_b for n in norms):
        raise M32GovernanceError(
            "frame contains a direction off the icosa/dodeca vertex orbits"
        )
    cross_r2 = r2_a * r2_b  # r_A * r_B squared = 3*phi + 6

    moments: dict[int, dict[str, object]] = {}
    for ell in range(1, max_degree + 1):
        q5_part = _Q5(0)  # rational field part of the pair sum
        w_part = _Q5(0)   # coefficient of w = (3*phi+6)^(-1/2)
        for i in range(LANES):
            for j in range(LANES):
                d = _dot(points[i], points[j])
                same = norms[i] == norms[j]
                if same:
                    denom = norms[i]  # r_i * r_j = r^2
                    q5_part = q5_part + _legendre_value(ell, d / denom)
                else:
                    # c = d * w; P_ell(d*w): term a_k d^k s^(-k/2).
                    for power, coeff in _LEGENDRE[ell].items():
                        term = (d ** power) * _Q5(coeff)
                        if power % 2 == 0:
                            term = term / (cross_r2 ** (power // 2))
                            q5_part = q5_part + term
                        else:
                            term = term / (cross_r2 ** ((power - 1) // 2))
                            w_part = w_part + term
        moments[ell] = {
            "q5_part": (q5_part.a, q5_part.b),
            "w_part": (w_part.a, w_part.b),
            "vanishes": q5_part.is_zero() and w_part.is_zero(),
        }
    return moments


@lru_cache(maxsize=1)
def _default_frame_moments() -> dict[int, dict[str, object]]:
    return spherical_design_moments()


def verify_spherical_design(
    frame: tuple[tuple[_Q5, ...], ...] | None = None, max_degree: int = 5
) -> dict[str, object]:
    """Prove the M32 frame is a spherical ``max_degree``-design.

    Returns the zero-moment proof record. Any surviving moment raises
    ``M32GovernanceError`` — the Euclid remediation hook — rather than
    letting a degraded allocation matrix reach the solver.
    """
    moments = (
        _default_frame_moments()
        if frame is None and max_degree == 5
        else spherical_design_moments(frame, max_degree)
    )
    bad = {ell: m for ell, m in moments.items() if not m["vanishes"]}
    if bad:
        raise M32GovernanceError(
            "M32 frame fails spherical-design zero moments at degrees "
            + ",".join(map(str, bad)),
            moments=moments,
        )
    return {
        "frame": "truncated_icosahedron_32f",
        "points": LANES,
        "design_degree": max_degree,
        "zero_moments": {ell: True for ell in moments},
        "arithmetic": "exact Q(sqrt(5)) + cross-orbit w-coefficient",
        "proof_kind": "legendre_frame_potential",
    }


class PhyllotaxisLaneIndex:
    """Golden-ratio folded storage map for the 32 lane trackers.

    Slot assignment uses the golden-angle (phyllotaxis) packing rule: each
    lane is keyed by ``frac(lane * phi)`` in exact Q(sqrt(5)) arithmetic and
    its slot is that key's rank among the 32 keys — the sunflower insertion
    order. Rank assignment is a bijection by construction (phi is irrational,
    so all 32 keys are distinct); it is a deterministic addressing
    permutation for lane state, not a compression or search advantage.
    """

    def __init__(self, lanes: int = LANES) -> None:
        if lanes != LANES:
            raise ValueError("phyllotaxis lane index is fixed at 32 lanes")
        self.lanes = lanes
        keys = [self._golden_key(lane) for lane in range(lanes)]
        ordered = sorted(
            range(lanes), key=cmp_to_key(lambda a, b: _q5_cmp(keys[a], keys[b]))
        )
        self._order = tuple(ordered)
        slots = [0] * lanes
        for rank, lane in enumerate(ordered):
            slots[lane] = rank
        if sorted(slots) != list(range(lanes)):
            raise M32GovernanceError("phyllotaxis slot map is not a bijection")
        self._slots = tuple(slots)

    @staticmethod
    def _golden_key(lane: int) -> _Q5:
        scaled = _Q5(Fraction(lane, 2), Fraction(lane, 2))  # lane * phi
        return scaled - _Q5(scaled.floor())

    def slot(self, lane: int) -> int:
        if not 0 <= lane < self.lanes:
            raise ValueError("lane out of range")
        return self._slots[lane]

    def order(self) -> tuple[int, ...]:
        """Lanes in golden-angle insertion order."""
        return self._order


@dataclass(frozen=True)
class M32Topology:
    lanes: int = LANES
    edges: tuple[tuple[int, int], ...] = M32_EDGES

    def __post_init__(self) -> None:
        if self.lanes != LANES:
            raise ValueError("PYTHIA's mining topology is fixed at 32 lanes")
        # Continuous spherical 5-design validation of the allocation frame.
        verify_spherical_design()

    def lane_for_nonce(self, nonce: int) -> int:
        if not 0 <= nonce <= 0xFFFFFFFF:
            raise ValueError("nonce must be uint32")
        return nonce % self.lanes

    def neighbors(self, lane: int) -> tuple[int, ...]:
        if not 0 <= lane < self.lanes:
            raise ValueError("lane out of range")
        return tuple(sorted({right if left == lane else left
                             for left, right in self.edges if lane in (left, right)}))

    def connected(self) -> bool:
        seen = {0}
        frontier = [0]
        while frontier:
            lane = frontier.pop()
            for neighbor in self.neighbors(lane):
                if neighbor not in seen:
                    seen.add(neighbor)
                    frontier.append(neighbor)
        return len(seen) == self.lanes

    def lane_order(self, start_lane: int = 0) -> tuple[int, ...]:
        """Return one complete, non-overlapping lane order."""
        if not 0 <= start_lane < self.lanes:
            raise ValueError("start lane out of range")
        return tuple((start_lane + offset) % self.lanes for offset in range(self.lanes))
