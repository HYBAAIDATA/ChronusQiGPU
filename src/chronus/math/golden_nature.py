"""Golden nature primitives with an explicit exact/numerical boundary.

Reuse the maintained Q(sqrt(5)), storage constant and Zeckendorf arithmetic.
No universal finite-sample, optimisation or predictive superiority is asserted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from chronus.geodesic.embedding_11d import Q5, PHI, PHI_INV
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
    lo = math.floor(a + min(2*b, 3*b))
    hi = math.ceil(a + max(2*b, 3*b)) + 1
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


def _float(x):
    return float(x.a) + float(x.b)*math.sqrt(5)


def kronecker_golden_1d(n, seed=0.5):
    """Numerical projection for plotting; not an exact witness."""
    return [_float(x) for x in kronecker_golden_exact(n, Fraction(str(seed)))]


def phyllotaxis_disk(n):
    """Numerical Cartesian projection of exact polar coordinates."""
    result = []
    for r2, turns in phyllotaxis_exact(n):
        radius, theta = math.sqrt(float(r2)), math.tau*_float(turns)
        result.append((radius*math.cos(theta), radius*math.sin(theta)))
    return result


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
    tolerance = _rational(tol)
    if (b-a).sign() <= 0 or tolerance <= 0:
        raise ValueError("ordered nonempty bracket and positive tolerance required")
    _count(max_iter)

    def evaluate(x):
        y = f(x)
        return y if isinstance(y, Q5) else Q5(_rational(y))

    if (b-a-tolerance).sign() <= 0:
        return MinimumBracket(a, b, 0, True)
    c, d = b-PHI_INV*(b-a), a+PHI_INV*(b-a)
    fc, fd, count = evaluate(c), evaluate(d), 2
    for _ in range(max_iter):
        if (b-a-tolerance).sign() <= 0:
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
    return MinimumBracket(a, b, count, (b-a-tolerance).sign() <= 0)


def golden_section_minimize(f, a, b, tol=1e-12, max_iter=200):
    """Numerical reference for a strictly unimodal floating objective."""
    if not all(math.isfinite(x) for x in (a, b, tol)) or not a < b or tol <= 0:
        raise ValueError("invalid bracket")
    ratio = (math.sqrt(5)-1)/2

    def evaluate(x):
        value = f(x)
        if not math.isfinite(value):
            raise ValueError("nonfinite objective")
        return value

    c, d = b-ratio*(b-a), a+ratio*(b-a)
    fc, fd, count = evaluate(c), evaluate(d), 2
    for _ in range(_count(max_iter)):
        if b-a <= tol:
            break
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b-ratio*(b-a)
            fc = evaluate(c)
        else:
            a, c, fc = c, d, fd
            d = a+ratio*(b-a)
            fd = evaluate(d)
        count += 1
    if b-a > tol:
        raise ArithmeticError("requested bracket tolerance not reached")
    x = a+(b-a)/2
    return x, evaluate(x), count+1


# Polynomial coefficients in descending order; root is the unique real
# root > 1 for the three cubic families, larger real root for the quadratics.
FAMILY_POLYNOMIALS = {
    "golden": (1, -1, -1),
    "silver": (1, -2, -1),
    "plastic": (1, 0, -1, -1),
    "supergolden": (1, -1, 0, -1),
    "tribonacci": (1, -1, -1, -1),
}


@dataclass(frozen=True)
class AlgebraicFrequency:
    family: str
    base: Fraction
    coefficient: int

    @property
    def polynomial(self):
        return FAMILY_POLYNOMIALS[self.family]

    def numeric(self):
        # Root isolation on [1,3], numerical reference only.
        lo, hi = 1.0, 3.0
        for _ in range(54):
            mid = (lo+hi)/2
            value = 0.0
            for c in self.polynomial:
                value = value*mid+c
            if value > 0:
                hi = mid
            else:
                lo = mid
        return float(self.base)*(1+self.coefficient*((lo+hi)/2))


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


def anti_resonant_frequencies(n_blocks, base_omega=0.15):
    return [x.numeric() for x in anti_resonant_frequencies_exact(
        n_blocks, Fraction(str(base_omega)))]


def evolve_anti_resonant(state, time_step=0.5, base_omega=0.15):
    """Evaluate exact symbolic block exp(-i omega t X) in numerical reference."""
    if not state or len(state)%2 or not math.isfinite(time_step):
        raise ValueError("nonempty even state and finite time required")
    if any(not math.isfinite(complex(x).real) or not math.isfinite(complex(x).imag)
           for x in state):
        raise ValueError("nonfinite state")
    out, residual = [], 0.0
    for i, omega in enumerate(anti_resonant_frequencies(len(state)//2, base_omega)):
        c, s = math.cos(omega*time_step), math.sin(omega*time_step)
        a, b = state[2*i:2*i+2]
        out.extend((c*a-1j*s*b, c*b-1j*s*a))
        residual = max(residual, abs(c*c+s*s-1))
    return out, residual


def ranked_zeckendorf_bits(rows):
    """Exact dense ordinal encoding; no magnitude, float coercion or truncation.

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
    return [tuple(int(i in z) for z in row for i in range(2,top+1)) for row in codes]


def ranked_fidelity(left, right):
    """Exact fidelity for normalized, uncentered binary-amplitude states."""
    if (not left or len(left)!=len(right) or
            any(type(x) is not int or x not in (0,1) for x in (*left,*right))):
        raise ValueError("matching binary vectors required")
    a,b = sum(left),sum(right)
    if not a or not b:
        raise ValueError("zero state")
    dot = sum(x*y for x,y in zip(left,right))
    return Fraction(dot*dot,a*b)
