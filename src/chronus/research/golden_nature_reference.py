"""Explicit numeric reference; not part of the exact execution path."""
import math
from fractions import Fraction
from chronus.math.golden_nature import (
    _count, kronecker_golden_exact, phyllotaxis_exact, anti_resonant_frequencies_exact,
)

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

    def probes(a,b):
        width=b-a
        if math.isfinite(width):
            return b-ratio*width, a+ratio*width
        return ratio*a+(1-ratio)*b, (1-ratio)*a+ratio*b

    c,d=probes(a,b)
    fc, fd, count = evaluate(c), evaluate(d), 2
    for _ in range(_count(max_iter)):
        if b-a <= tol:
            break
        if c >= d or not a < c < b or not a < d < b:
            candidates={c:fc,d:fd}
            for endpoint in (a,b):
                if endpoint not in candidates:
                    candidates[endpoint]=evaluate(endpoint)
                    count+=1
            x=min(candidates,key=candidates.get)
            # Only conclude for adjacent representable candidates.
            if math.nextafter(a,b) < b and math.nextafter(a,b) != c:
                raise ArithmeticError("numerical resolution exhausted")
            if c != d or math.nextafter(c,b)<b:
                raise ArithmeticError("numerical resolution exhausted")
            return x,candidates[x],count
        if fc <= fd:
            b, d, fd = d, c, fc
            c = probes(a,b)[0]
            fc = evaluate(c)
        else:
            a, c, fc = c, d, fd
            d = probes(a,b)[1]
            fd = evaluate(d)
        count += 1
    if b-a > tol:
        raise ArithmeticError("requested bracket tolerance not reached")
    x = a/2+b/2
    return x, evaluate(x), count+1


def numeric_frequency(frequency):
    # Root isolation on [1,3], numerical reference only.
    lo, hi = 1.0, 3.0
    for _ in range(54):
        mid = (lo+hi)/2
        value = 0.0
        for c in frequency.polynomial:
            value = value*mid+c
        if value > 0:
            hi = mid
        else:
            lo = mid
    return float(frequency.base)*(1+frequency.coefficient*((lo+hi)/2))


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
    from dataclasses import replace
    for i, frequency in enumerate(anti_resonant_frequencies_exact(len(state)//2, Fraction(str(base_omega)))):
        phase = numeric_frequency(replace(frequency, base=frequency.base*Fraction(str(time_step))))
        if not math.isfinite(phase):
            raise ValueError("nonfinite phase")
        c, s = math.cos(phase), math.sin(phase)
        a, b = state[2*i:2*i+2]
        out.extend((c*a-1j*s*b, c*b-1j*s*a))
        residual = max(residual, abs(c*c+s*s-1))
    return out, residual


