"""Exact two-amplitude Grover fold (integer / Fraction arithmetic).

Uniform start scales out 1/sqrt(N): the stored marked amplitude a and
unmarked amplitude b begin at the integers a = b = 1.  Physical amplitudes
are a/sqrt(N) and b/sqrt(N); they are never materialised.

Canonical iterate (phases +/-1 only):

    oracle:    a -> -a
    diffusion: m = (M*a + (N-M)*b)/N
               a' = 2m - a,  b' = 2m - b

m, a', b' are rationals (fractions.Fraction).  Success probability
M*a^2/N and the Cassini identity M*a^2 + (N-M)*b^2 == N are exact.

Partial / Pisot-damped complex phases e^{i beta} are not represented.
1 - |psi|^n is exact in Q(sqrt(5)) (see QSqrt5) but is not a +/-1 phase
and is not used as a Grover phase on the search path.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Union

Number = Union[int, Fraction]

ITERATION_CAP = 2_000_000


def _Q(x: Number) -> Fraction:
    return x if isinstance(x, Fraction) else Fraction(int(x))


def exceeds_phi_inverse(p: Number) -> bool:
    """Exact test p > (sqrt(5)-1)/2 with no roots or floats.

    p > (sqrt(5)-1)/2  <=>  2p+1 > sqrt(5)  (since 2p+1 > 0 for p > -1/2)
                       <=>  (2p+1)^2 > 5.
    Writing p = n/d in lowest terms: (2n + d)^2 > 5 d^2, in integers.
    Equality cannot hold: phi^{-1} is irrational.
    """
    p = _Q(p)
    n, d = p.numerator, p.denominator
    if d < 0:
        n, d = -n, -d
    s = 2 * n + d
    return s > 0 and s * s > 5 * d * d


@dataclass
class FoldedGrover:
    """Grover state folded onto span{|w>, |u>}, scaled by sqrt(N).

    a, b are int or Fraction (never float).  Start: a = b = 1.
    """

    N: int
    M: int
    a: Number
    b: Number

    @classmethod
    def uniform(cls, N: int, M: int) -> "FoldedGrover":
        if N <= 0 or M < 0 or M > N:
            raise ValueError("N must be positive and 0 <= M <= N")
        return cls(N=int(N), M=int(M), a=1, b=1)

    def step(self) -> None:
        """One exact canonical iterate.  No phase arguments."""
        if self.M <= 0 or self.M >= self.N:
            return
        a = -_Q(self.a)
        b = _Q(self.b)
        m = (self.M * a + (self.N - self.M) * b) / Fraction(self.N)
        self.a = 2 * m - a
        self.b = 2 * m - b
        self._maybe_to_int()

    def _maybe_to_int(self) -> None:
        if isinstance(self.a, Fraction) and self.a.denominator == 1:
            self.a = self.a.numerator
        if isinstance(self.b, Fraction) and self.b.denominator == 1:
            self.b = self.b.numerator

    @property
    def marked_probability(self) -> Fraction:
        a = _Q(self.a)
        return Fraction(self.M) * a * a / Fraction(self.N)

    def cassini_scaled(self) -> Fraction:
        """M a^2 + (N-M) b^2; equals N exactly after every iterate."""
        a, b = _Q(self.a), _Q(self.b)
        return Fraction(self.M) * a * a + Fraction(self.N - self.M) * b * b

    def cassini_witness(self) -> Fraction:
        """Normalized conservation: equals 1 exactly."""
        return self.cassini_scaled() / Fraction(self.N)

    def cassini_witness_exact(self) -> Fraction:
        return self.cassini_witness()


def optimal_iterations(N: int, M: int) -> int:
    """Peak of the exact success probability, found by stepping the recurrence.

    No closed-form angle is used.  If the peak would require more than
    ITERATION_CAP steps (N/M > cap^2, a conservative integer bound),
    returns ITERATION_CAP + 1 and does not step.
    """
    if M <= 0 or M >= N:
        return 0
    if N // M > ITERATION_CAP * ITERATION_CAP:
        return ITERATION_CAP + 1
    st = FoldedGrover.uniform(N, M)
    best_k = 0
    best_p = st.marked_probability
    for k in range(1, ITERATION_CAP + 1):
        st.step()
        p = st.marked_probability
        if p > best_p:
            best_k, best_p = k, p
        else:
            break
    return best_k


def analytical_success(N: int, M: int, k: int) -> Fraction:
    """Exact marked probability after k canonical iterates."""
    if M <= 0 or M >= N:
        return Fraction(1)
    if k < 0:
        raise ValueError("k must be non-negative")
    if k > ITERATION_CAP:
        # Peak was not materialised by stepping.
        return Fraction(1)
    st = FoldedGrover.uniform(N, M)
    for _ in range(k):
        st.step()
    return st.marked_probability


def run_folded(
    N: int, M: int, iterations: Optional[int] = None, damp: Optional[Number] = None
) -> dict:
    """Exact folded Grover with canonical +/-1 phases only.

    ``damp`` is accepted for call-site compatibility and must be omitted,
    None, or 1; any other value is an inexact phase and is refused.
    """
    if damp is not None:
        if isinstance(damp, (int, Fraction)):
            canonical = _Q(damp) == 1
        elif isinstance(damp, float) and damp == 1.0:
            # 1.0 is the exact real 1; accepted only as a synonym of damp=1.
            canonical = True
        else:
            canonical = False
        if not canonical:
            raise ValueError(
                "partial or Pisot-damped phases are not exact +/-1 and are not "
                "used by the exact fold"
            )
    k = optimal_iterations(N, M) if iterations is None else int(iterations)
    if k > ITERATION_CAP:
        return {
            "N": N, "M": M, "k": k, "damp": 1,
            "P_marked": Fraction(1),
            "P_analytic_full": Fraction(1),
            "cassini_drift": Fraction(0),
        }
    state = FoldedGrover.uniform(N, M)
    drift = Fraction(0)
    for _ in range(k):
        state.step()
        drift = max(drift, abs(state.cassini_witness() - 1))
    p = state.marked_probability
    return {
        "N": N, "M": M, "k": k, "damp": 1,
        "P_marked": p,
        "P_analytic_full": p,
        "cassini_drift": drift,
    }


# ---------------------------------------------------------------------------
# 1 - |psi|^n as an element of Q(sqrt(5)), not used as a Grover phase
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QSqrt5:
    """a + b*sqrt(5) with a, b rational.  Arithmetic never takes a root."""

    a: Fraction
    b: Fraction

    def __post_init__(self) -> None:
        object.__setattr__(self, "a", _Q(self.a))
        object.__setattr__(self, "b", _Q(self.b))

    def __add__(self, other: "QSqrt5 | Number") -> "QSqrt5":
        o = other if isinstance(other, QSqrt5) else QSqrt5(_Q(other), 0)
        return QSqrt5(self.a + o.a, self.b + o.b)

    def __sub__(self, other: "QSqrt5 | Number") -> "QSqrt5":
        o = other if isinstance(other, QSqrt5) else QSqrt5(_Q(other), 0)
        return QSqrt5(self.a - o.a, self.b - o.b)

    def __mul__(self, other: "QSqrt5 | Number") -> "QSqrt5":
        o = other if isinstance(other, QSqrt5) else QSqrt5(_Q(other), 0)
        return QSqrt5(self.a * o.a + 5 * self.b * o.b, self.a * o.b + self.b * o.a)

    def __pow__(self, n: int) -> "QSqrt5":
        if n < 0:
            raise ValueError("negative powers not required")
        out = QSqrt5(1, 0)
        base = self
        e = n
        while e:
            if e & 1:
                out = out * base
            base = base * base
            e >>= 1
        return out

    def __eq__(self, other: object) -> bool:
        if isinstance(other, QSqrt5):
            return self.a == other.a and self.b == other.b
        if isinstance(other, (int, Fraction)):
            return self.b == 0 and self.a == _Q(other)
        return NotImplemented


def abs_psi() -> QSqrt5:
    """|psi| = (sqrt(5)-1)/2 = -1/2 + (1/2)*sqrt(5)."""
    return QSqrt5(Fraction(-1, 2), Fraction(1, 2))


def pisot_damp_qsqrt5(n: int) -> QSqrt5:
    """Exact 1 - |psi|^n in Q(sqrt(5)).  Not a Grover phase."""
    if n < 0:
        raise ValueError("n must be non-negative")
    return QSqrt5(1, 0) - (abs_psi() ** n)



# ---------------------------------------------------------------------------
# Exact Z[phi] Binet / Pisot helpers (no float, no cmath)
#
# Reuses kellogg.scales: Zphi (kellogg/scales.py:33), Zphi.sign (line 80),
# PHI (line 115), phi_power (line 154), binet_fold (line 163),
# pisot_drift (line 180), lucas (line 144).
# Sibling ring: lucas.algebra.ZPhi (lucas/algebra.py:21) and PHI (line 85).
# Identities: phi^n = F_{n-1} + F_n phi; L_n = phi^n + psi^n = trace(phi^n);
# |phi^n - L_n| = |psi|^n = phi^{-n} = (phi-1)^n.
# ---------------------------------------------------------------------------

from kellogg.scales import (  # noqa: E402
    PHI,
    ZPHI_ONE,
    Zphi,
    lucas as binet_lucas,
    phi_power,
    pisot_drift,
)

PSI = PHI.conjugate()  # 1 - phi, kellogg/scales.py:72-74


def abs_psi_power(n: int) -> Zphi:
    """|psi|^n = phi^{-n} = (phi - 1)^n, an element of Z[phi]."""
    if n < 0:
        raise ValueError("n must be non-negative")
    return (PHI - ZPHI_ONE) ** n


def binet_residual(n: int) -> Zphi:
    """|phi^n - L_n| = |psi|^n as the positive Z[phi] element (phi-1)^n.

    The signed drift phi^n - L_n is kellogg.scales.pisot_drift (scales.py:180).
    """
    return abs_psi_power(n)


def pisot_damp(n: int) -> Zphi:
    """1 - |psi|^n = 1 - phi^{-n} in Z[phi].  Not a Grover phase."""
    return ZPHI_ONE - abs_psi_power(n)


def zphi_lt_rational(z: Zphi, num: int, den: int) -> bool:
    """Exact comparison z < num/den with den > 0, via Zphi.sign."""
    if den <= 0:
        raise ValueError("denominator must be positive")
    return Zphi(z.a * den - num, z.b * den).sign() < 0


def convergence_bits(n: int) -> int:
    """floor(log2(phi^n)) = floor(-log2(|psi|^n)), by comparing phi^n to 2^k."""
    if n <= 0:
        return 0
    pn = phi_power(n)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if (pn - Zphi(1 << mid, 0)).sign() >= 0:
            lo = mid
        else:
            hi = mid - 1
    return lo
