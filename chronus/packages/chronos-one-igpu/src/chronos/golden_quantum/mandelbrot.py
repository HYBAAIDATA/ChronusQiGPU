"""Certified Mandelbrot diagnostics used only as experimental ranking advice.

``escape_iterations`` iterates z -> z^2 + c in exact rounded dyadic
arithmetic with a rigorously tracked error bound. Escape is reported only
when |z| is *proven* greater than max(2, |c|): at that point the standard
Mandelbrot escape argument makes divergence a theorem, not a measurement.
If the orbit is not proven escaping within ``max_iterations`` the bound is
returned, exactly as before; if the orbit passes through a region where the
certified precision quota cannot resolve the boundary, the precision is
doubled up to a quota before reporting the bound (honest undecided, never a
silent float guess).
"""
from fractions import Fraction
import math


def _ceil_dyadic(value, bits):
    """Smallest multiple of 2^-bits >= value (upper bound for error terms)."""
    scale = 1 << bits
    scaled = value * scale
    num = scaled.numerator // scaled.denominator
    if scaled != num:
        num += 1
    return Fraction(num, scale)


def _round_dyadic(value, bits):
    """Round a Fraction to the nearest multiple of 2^-bits."""
    scale = 1 << bits
    scaled = value * scale
    num = scaled.numerator // scaled.denominator
    rem = scaled - num
    if rem * 2 >= 1:
        num += 1
    return Fraction(num, scale)


def _sqrt_lower(q):
    scale = 1 << 64
    r = math.isqrt(q.numerator * scale * scale // q.denominator)
    return Fraction(max(r - 1, 0), scale)


class MandelbrotResonanceEngine:
    def escape_iterations(self, c, max_iterations=32):
        if not isinstance(c, complex):
            c = complex(c)
        if not math.isfinite(c.real) or not math.isfinite(c.imag) or type(max_iterations) is not int \
                or not 1 <= max_iterations <= 1024:
            raise ValueError("finite c and bounded iterations required")
        return self._escape_certified(
            Fraction(float(c.real)), Fraction(float(c.imag)), max_iterations)

    def _escape_certified(self, c_re, c_im, max_iterations, bits=192, bits_cap=1536):
        eps = Fraction(1, 1 << (bits - 1))          # rounding error per iterate component
        c_bound = abs(c_re) + abs(c_im)              # |c| upper bound (exact)
        z_re, z_im = Fraction(0), Fraction(0)
        delta = Fraction(0)                          # certified |z_true - z_computed| bound
        for i in range(max_iterations):
            re = _round_dyadic(z_re * z_re - z_im * z_im + c_re, bits)
            im = _round_dyadic(2 * z_re * z_im + c_im, bits)
            # error propagation: |(z+e)^2 - z^2| <= (2|z| + e)e + rounding eps.
            # The bound is rounded UP to a dyadic each step so its denominator
            # stays bounded; it remains a valid (slightly looser) upper bound.
            z_abs = _ceil_dyadic(abs(z_re) + abs(z_im), bits - 16)
            delta = _ceil_dyadic((2 * z_abs + delta) * delta + 2 * eps, bits - 16)
            z_re, z_im = re, im
            z2_lo = _sqrt_lower(z_re * z_re + z_im * z_im)
            z_lo = z2_lo - delta
            # Certified divergence (theorem): |z| > 2 and |z|(|z|-1) > |c|
            # implies |z_{n+1}| >= |z|^2 - |c| > |z|, so the orbit grows
            # strictly forever. The >= |c| case needs only the weaker
            # |z|(|z|-1) > |c|, which this certifies at equality boundaries
            # that a strict |z| >= |c| bound could not resolve.
            if z_lo > 2 and z_lo * (z_lo - 1) > c_bound:
                return i + 1                       # proven escape (theorem)
            if delta > 1 and bits < bits_cap:
                # precision exhausted; restart this orbit at higher precision
                return self._escape_certified(c_re, c_im, max_iterations, bits * 2, bits_cap)
            if delta > 1:
                break                                # undecidable within quota
        return max_iterations                        # no proven escape in bound

    def escape_iterations_reference(self, c, max_iterations=32):
        """NON-PRODUCTION FP64 reference implementation."""
        if not math.isfinite(c.real) or not math.isfinite(c.imag) or type(max_iterations) is not int \
                or not 1 <= max_iterations <= 1024:
            raise ValueError("finite c and bounded iterations required")
        z = 0j
        for i in range(max_iterations):
            z = z * z + c
            if abs(z) > 2:
                return i + 1
        return max_iterations

    def rank(self, candidates):
        values = list(candidates)
        if not values:
            return []
        lo, hi = min(values), max(values); width = max(1, hi - lo)
        return sorted(values, key=lambda n: (-self.escape_iterations(
            complex(-2 + 3 * (n - lo) / width, 0.25)), n))


class FractalQuantumOptimizer(MandelbrotResonanceEngine):
    """Compatibility name for finite diagnostic ranking, not physical cooling."""


def _snap_boundary(self, c, iterations=64, steps=48):
    if type(steps) is not int or not 1 <= steps <= 128:
        raise ValueError('bounded boundary refinement required')
    self.escape_iterations(c, iterations)
    if self.escape_iterations(c, iterations) == iterations:
        raise ValueError('outside endpoint required for boundary bisection')
    inside = 0j
    outside = complex(c)
    for _ in range(steps):
        midpoint = (inside + outside) / 2
        if self.escape_iterations(midpoint, iterations) == iterations:
            inside = midpoint
        else:
            outside = midpoint
    return {'boundary_estimate': (inside + outside) / 2, 'bracket_width': abs(outside - inside),
            'iterations': iterations, 'steps': steps}


MandelbrotResonanceEngine.snap_boundary = _snap_boundary
