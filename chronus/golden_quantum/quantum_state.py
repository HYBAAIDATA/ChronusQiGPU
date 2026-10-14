"""Exact rational state vectors with certified float projections.

The stored state is a tuple of exact rational amplitudes (each a complex
number with Fraction real/imag parts, derived bit-exactly from the caller's
float64 input) together with its exact squared norm. The normalized state is
the exactly-defined vector amplitudes_exact / sqrt(norm_squared_exact).

``amplitudes`` and ``probabilities`` are certified float64 projections of
that exact state. ``probabilities_exact`` returns the exact Born weights
|a_i|^2 / ||a||^2 as Fractions.

``HamiltonianEngine.evolve`` computes e^{-iHt} psi by an exact rational
series with a rigorous tail bound, and attaches ``evolution_certificate`` to
the returned state. The dense FP64 eigendecomposition is retained only as
``evolve_reference`` (explicitly non-production).
"""
from fractions import Fraction
import math

import numpy as np

MAX_DIMENSION = 4096
CERTIFIED_EVOLVE_MAX_DIMENSION = 64


def _exact_pair(value):
    c = complex(value)
    return (Fraction(float(c.real)), Fraction(float(c.imag)))


def _pair_norm2(pair):
    return pair[0] * pair[0] + pair[1] * pair[1]


class MathematicalQuantumState:
    def __init__(self, amplitudes, _exact=None):
        if _exact is None:
            a = np.asarray(amplitudes, dtype=np.complex128)
            if a.ndim != 1 or not 0 < a.size <= MAX_DIMENSION or not np.isfinite(a).all():
                raise ValueError("finite bounded 1-D state required")
            self._exact = tuple(_exact_pair(v) for v in a)
        else:
            self._exact = tuple(_exact)
        self._norm2_exact = sum(_pair_norm2(p) for p in self._exact)
        if self._norm2_exact <= 0:
            raise ValueError("invalid state norm")
        # Certified float64 projection: divide by a dyadic lower bound on
        # sqrt(norm2) computed in exact integer arithmetic (norm2 may be far
        # outside float64 range, e.g. 1e600 or 1e-600). The shift adapts to the
        # fraction's bit-length so the integer square root always works at
        # ~128-bit relative precision.
        num, den = self._norm2_exact.numerator, self._norm2_exact.denominator
        shift = 256 - (num.bit_length() - den.bit_length())
        if shift % 2:
            shift += 1
        if shift >= 0:
            arg = num * (1 << shift) // den
        else:
            arg = num // (den << (-shift))
        # sqrt(arg) ~ sqrt(norm2) * 2^(shift/2); divide by 2^(shift/2) to get a
        # dyadic lower bound on sqrt(norm2) at ~128-bit relative precision.
        scale = Fraction(math.isqrt(arg)) * (Fraction(1, 2) ** (shift // 2))
        if scale <= 0:
            raise ValueError("invalid state norm")
        self.amplitudes = np.array(
            [complex(float(re_ / scale), float(im_ / scale)) for re_, im_ in self._exact],
            dtype=np.complex128)

    @property
    def amplitudes_exact(self):
        """Exact rational amplitudes; normalized state is these / sqrt(norm_squared_exact)."""
        return self._exact

    @property
    def norm_squared_exact(self):
        return self._norm2_exact

    @property
    def probabilities(self):
        return np.abs(self.amplitudes) ** 2

    @property
    def probabilities_exact(self):
        return tuple(_pair_norm2(p) / self._norm2_exact for p in self._exact)


class Operator:
    def __init__(self, matrix):
        a = np.asarray(matrix, dtype=np.complex128)
        if a.ndim != 2 or a.shape[0] != a.shape[1] or not 0 < a.shape[0] <= 512 or not np.isfinite(a).all():
            raise ValueError("finite bounded square operator required")
        self.matrix = a.copy()
        self._exact = tuple(tuple(_exact_pair(v) for v in row) for row in a)

    @property
    def matrix_exact(self):
        return self._exact

    def apply_exact(self, state):
        if len(self._exact) != len(state.amplitudes_exact):
            raise ValueError("dimension mismatch")
        out = []
        for row in self._exact:
            acc = (Fraction(0), Fraction(0))
            for (re_m, im_m), (re_v, im_v) in zip(row, state.amplitudes_exact):
                acc = (acc[0] + re_m * re_v - im_m * im_v,
                       acc[1] + re_m * im_v + im_m * re_v)
            out.append(acc)
        return MathematicalQuantumState(None, _exact=tuple(out))

    def apply(self, state):
        return self.apply_exact(state)


def _unit_hermitian_bound(h_exact):
    """Certified spectral-norm bound: max row sum of |h_ij|."""
    bound = Fraction(0)
    for row in h_exact:
        rowsum = Fraction(0)
        for re_, im_ in row:
            m2 = re_ * re_ + im_ * im_
            # upper bound sqrt via isqrt at 64-bit scale
            scale = 1 << 32
            r = math.isqrt(m2.numerator * scale * scale // m2.denominator)
            rowsum += Fraction(r + 1, scale)
        bound = max(bound, rowsum)
    return bound


class HamiltonianEngine:
    """Exact certified Hamiltonian evolution plus the retained FP64 reference."""

    def evolve(self, state, hamiltonian, time=1.0, tolerance=None):
        """Certified exact evolution: e^{-iHt} psi as exact rational series.

        The Hamiltonian is converted bit-exactly to complex rationals and the
        exponential series is summed exactly; the certificate carries a
        rigorous tail bound. Dimensions above the certified quota fail closed.
        """
        h = Operator(hamiltonian).matrix
        if h.shape[0] != state.amplitudes.size:
            raise ValueError("dimension/time mismatch")
        if not np.isfinite(time):
            raise ValueError("phase overflow")
        h_exact = Operator(hamiltonian).matrix_exact
        n = len(h_exact)
        if n > CERTIFIED_EVOLVE_MAX_DIMENSION:
            raise ValueError("certified evolution quota exceeded (dimension %d > %d)"
                             % (n, CERTIFIED_EVOLVE_MAX_DIMENSION))
        for i in range(n):
            for j in range(n):
                a, b = h_exact[i][j], h_exact[j][i]
                if a[0] != b[0] or a[1] != -b[1]:
                    raise ValueError("Hamiltonian must be Hermitian")
        t = Fraction(float(time))
        tol = Fraction(1, 10 ** 13) if tolerance is None else Fraction(float(tolerance))
        # Series: psi(t) = sum_k (-i)^k (tH)^k psi / k!
        # M = tH folded into the recurrence; the (-i)^k phase is applied at
        # accumulation time through a 4-cycle of exact sign factors.
        m_exact = tuple(tuple((re_ * t, im_ * t) for re_, im_ in row) for row in h_exact)
        psi = list(state.amplitudes_exact)
        q = _unit_hermitian_bound(m_exact)
        psi_norm2 = state.norm_squared_exact
        scale = 1 << 32
        psi_norm_upper = Fraction(math.isqrt(psi_norm2.numerator * scale * scale
                                             // psi_norm2.denominator) + 1, scale)
        acc = [(Fraction(0), Fraction(0))] * n
        term = list(psi)
        sign_cycle = ((1, 0), (0, -1), (-1, 0), (0, 1))  # (-i)^k
        k = 0
        tail = psi_norm_upper + 1
        while True:
            sgn = sign_cycle[k % 4]
            for i in range(n):
                acc[i] = (acc[i][0] + term[i][0] * sgn[0] - term[i][1] * sgn[1],
                          acc[i][1] + term[i][0] * sgn[1] + term[i][1] * sgn[0])
            # Tail bound after K terms:
            #   ||psi|| sum_{k>K} q^k/k! <= ||psi|| q^{K+1}/(K+1)! / (1 - q/(K+2))
            if q < k + 2:
                lead = psi_norm_upper * q ** (k + 1) / Fraction(math.factorial(k + 1))
                tail = lead / (1 - q / Fraction(k + 2))
                if tail <= tol:
                    break
            if k > 512:
                raise ArithmeticError("certified series did not converge within quota")
            k += 1
            new_term = []
            for i in range(n):
                acc_t = (Fraction(0), Fraction(0))
                for j in range(n):
                    re_m, im_m = m_exact[i][j]
                    re_v, im_v = term[j]
                    acc_t = (acc_t[0] + re_m * re_v - im_m * im_v,
                             acc_t[1] + re_m * im_v + im_m * re_v)
                new_term.append(acc_t)
            term = [(re_ / k, im_ / k) for re_, im_ in new_term]
        out = MathematicalQuantumState(None, _exact=tuple(acc))
        out.evolution_certificate = {
            "method": "exact_rational_exponential_series",
            "series_terms": k + 1,
            "certified_error_radius": str(float(tail)),
            "operator_norm_bound": str(float(q)),
            "arithmetic": "exact_rational",
            "certified": True,
            "dimension": n,
        }
        return out

    def evolve_reference(self, state, hamiltonian, time=1.0):
        """NON-PRODUCTION FP64 eigendecomposition reference implementation."""
        h = Operator(hamiltonian).matrix
        if not np.allclose(h, h.conj().T, atol=1e-12, rtol=1e-12):
            raise ValueError("Hamiltonian must be Hermitian")
        if h.shape[0] != state.amplitudes.size or not np.isfinite(time):
            raise ValueError("dimension/time mismatch")
        values, vectors = np.linalg.eigh(h)
        phases = values * time
        if not np.isfinite(phases).all():
            raise ValueError("phase overflow")
        out = MathematicalQuantumState(
            vectors @ (np.exp(-1j * phases) * (vectors.conj().T @ state.amplitudes)))
        out.evolution_certificate = {
            "method": "fp64_eigh_reference",
            "arithmetic": "fp64_reference",
            "certified": False,
            "non_production_reference": True,
        }
        return out
