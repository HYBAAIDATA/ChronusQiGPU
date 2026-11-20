"""Golden nature primitives with an explicit exact/numerical boundary.

Reuse the maintained Q(sqrt(5)), storage constant and Zeckendorf arithmetic.
No universal finite-sample, optimisation or predictive superiority is asserted.
"""
from __future__ import annotations

from types import MappingProxyType
from dataclasses import dataclass
from fractions import Fraction

from golden_ontology.substrate import PV_REGISTRY
from chronus.geodesic.embedding_11d import Q5, PHI_INV
from chronus.execution.structural import zeckendorf_encode
from chronus.storage.phyllotaxis import GOLDEN_RATIO_CONJUGATE_64

MASK_64 = (1 << 64) - 1
FIB_HASH_MULT_64 = GOLDEN_RATIO_CONJUGATE_64
FIB_HASH_INV_64 = pow(FIB_HASH_MULT_64, -1, 1 << 64)


def _count(n):
    if type(n) is not int or n < 0:
        raise ValueError("count must be a nonnegative integer")
    return n


def _rational(x):
    if type(x) is not int and not isinstance(x, Fraction):
        raise TypeError("exact rational required")
    return Fraction(x)


def _floor(x):
    # sqrt(5) in (2,3) supplies a rigorous integer bracket.
    a, b = x.a, x.b
    low, high = a+min(2*b,3*b), a+max(2*b,3*b)
    lo = low.numerator//low.denominator
    hi = -((-high.numerator)//high.denominator)+1
    while hi-lo > 1:
        mid = (lo+hi)//2
        if (x-mid).sign() >= 0:
            lo = mid
        else:
            hi = mid
    return lo


def _frac(x):
    return x - _floor(x)


def kronecker_golden_exact(n, seed=Fraction(1, 2)):
    """Exact turns in Q(sqrt(5)), not a floating recurrence."""
    start = _rational(seed)
    return [_frac(PHI_INV*k + start) for k in range(_count(n))]


def phyllotaxis_exact(n):
    """Return (radius squared, turns). Polar point is defined without rounding."""
    n = _count(n)
    return [(Fraction(2*k+1, 2*n), _frac(PHI_INV*PHI_INV*k)) for k in range(n)]


def fibonacci_scatter(x):
    """Permutation of canonical unsigned 64-bit words."""
    if type(x) is not int or not 0 <= x <= MASK_64:
        raise ValueError("canonical uint64 required")
    return (x*FIB_HASH_MULT_64) & MASK_64


def fibonacci_unscatter(y):
    if type(y) is not int or not 0 <= y <= MASK_64:
        raise ValueError("canonical uint64 required")
    return (y*FIB_HASH_INV_64) & MASK_64


@dataclass(frozen=True)
class MinimumBracket:
    lower: Q5
    upper: Q5
    evaluations: int
    converged: bool


def golden_section_exact(f, a, b, tol=Fraction(1, 10**12), max_iter=200):
    """Exact bracket under a unimodal objective and exact ordered values.

    Objective must return Q5, int or Fraction. Under strict unimodality
    the bracket retains a minimizer. Equal evaluations retain [c,d] in
    the strict case; using one side preserves the fixed-ratio reuse.
    """
    a, b = Q5(_rational(a)), Q5(_rational(b))
    # This is an exact rational limiting width, not an arithmetic error budget.
    width_limit = _rational(tol)
    if (b-a).sign() <= 0 or width_limit <= 0:
        raise ValueError("ordered nonempty bracket and positive limiting width required")
    _count(max_iter)

    def evaluate(x):
        y = f(x)
        return y if isinstance(y, Q5) else Q5(_rational(y))

    if (b-a-width_limit).sign() <= 0:
        return MinimumBracket(a, b, 0, True)
    c, d = b-PHI_INV*(b-a), a+PHI_INV*(b-a)
    fc, fd, count = evaluate(c), evaluate(d), 2
    for _ in range(max_iter):
        if (b-a-width_limit).sign() <= 0:
            break
        if (fc-fd).sign() <= 0:
            b, d, fd = d, c, fc
            c = b-PHI_INV*(b-a)
            fc = evaluate(c)
        else:
            a, c, fc = c, d, fd
            d = a+PHI_INV*(b-a)
            fd = evaluate(d)
        count += 1
    return MinimumBracket(a, b, count, (b-a-width_limit).sign() <= 0)


# Polynomial coefficients in descending order; root is the unique real
# root > 1 for the three cubic families, larger real root for the quadratics.
FAMILY_POLYNOMIALS = MappingProxyType({name: family.polynomial for name, family in PV_REGISTRY.items()})


@dataclass(frozen=True)
class AlgebraicFrequency:
    family: str
    base: Fraction
    coefficient: int

    def __post_init__(self):
        if self.family not in FAMILY_POLYNOMIALS or _rational(self.base)<=0:
            raise ValueError("registered family and positive exact base required")
        if type(self.coefficient) is not int or self.coefficient<=0:
            raise ValueError("positive integer coefficient required")

    @property
    def polynomial(self):
        return FAMILY_POLYNOMIALS[self.family]

def anti_resonant_frequencies_exact(n_blocks, base_omega=Fraction(3,20)):
    """Symbolic frequencies base*(1+j*alpha), j positive and unique per family.

    Within a family, a rational ratio forces both rational and irrational
    coefficients to match. Across families the fields differ (quadratic
    degrees/discriminants 5,8; cubic discriminants -23,-31,-44 have distinct
    square classes). Thus distinct block frequencies have irrational ratios.
    This excludes exact pairwise common nonzero periods, NOT arbitrary integer
    linear relations or near-resonance at finite precision.
    """
    base = _rational(base_omega)
    if base <= 0:
        raise ValueError("positive base required")
    names = tuple(FAMILY_POLYNOMIALS)
    return [AlgebraicFrequency(names[k%len(names)], base, 1+k//len(names))
            for k in range(_count(n_blocks))]


def ranked_zeckendorf_bits(rows):
    """Exact dense ordinal encoding; no magnitude, float coercion or truncation.

    Comparisons require the same ordinal rank basis (columns and distinct counts).
    Invariant under strictly increasing per-column transformations. Decreasing
    transformations reverse ranks; do not claim invariance to all monotone maps.
    """
    rows = [tuple(_rational(v) for v in row) for row in rows]
    if not rows or not rows[0] or any(len(row)!=len(rows[0]) for row in rows):
        raise ValueError("nonempty rectangular matrix required")
    maps = [{v:i+1 for i,v in enumerate(sorted(set(col)))} for col in zip(*rows)]
    codes = [[set(zeckendorf_encode(maps[j][v])) for j,v in enumerate(row)]
             for row in rows]
    top = max(max(z) for row in codes for z in row)
    basis=tuple(len(m) for m in maps)
    return [RankedBits((int(i in z) for z in row for i in range(2,top+1)),basis) for row in codes]


class RankedBits(tuple):
    """Ordinal vector with explicit basis metadata."""
    def __new__(cls, values, basis):
        instance=super().__new__(cls,values)
        object.__setattr__(instance,"basis",tuple(basis))
        return instance

    def __setattr__(self,name,value):
        raise AttributeError("ordinal basis is immutable")


def ranked_fidelity(left, right):
    """Exact fidelity for normalized, uncentered binary-amplitude states."""
    if isinstance(left,RankedBits) or isinstance(right,RankedBits):
        if not isinstance(left,RankedBits) or not isinstance(right,RankedBits) or left.basis!=right.basis:
            raise ValueError("ordinal rank basis mismatch")
    if (not left or len(left)!=len(right) or
            any(type(x) is not int or x not in (0,1) for x in (*left,*right))):
        raise ValueError("matching binary vectors required")
    a,b = sum(left),sum(right)
    if not a or not b:
        raise ValueError("zero state")
    dot = sum(x*y for x,y in zip(left,right))
    return Fraction(dot*dot,a*b)
