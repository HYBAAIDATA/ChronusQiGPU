"""mtheory.hilbert — exact quantum register over the 11-qubit Hilbert space.

Exact state-vector evolution over C^2048 — the repository's "11D Hilbert
space": 11 qubits, 2048 computational basis states.  This module computes
the mathematical objects of quantum mechanics themselves — the state
vector, the unitary, and the Born-rule probability distribution —
EXACTLY.  No floats, no approximations, no PRNG "measurement" pretending
to be quantum.  Per AGENTS.md sections 1-2, a quantum computation IS
exact linear algebra over C; the substrate (here: CPython bignums) is
incidental.  A hardware QPU is neither used nor claimed.

Exact arithmetic representations
--------------------------------
* ``ExactComplex`` — an element of the biquadratic cyclotomic field
  Q(i, sqrt(2)) = Q(zeta_8), stored as four ``fractions.Fraction``
  coefficients on the basis {1, sqrt(2), i, i*sqrt(2)}.  Every amplitude
  reachable from a computational basis state by the gate set
  {H, X, Z, S, T, CNOT, phase-oracle} lives in this field.
* ``QSqrt2`` — a real element q + s*sqrt(2), the exact type of Born-rule
  probabilities |alpha|^2 in this field.
* ``QSqrt`` — an element q + s*sqrt(N) of the real quadratic field
  Q(sqrt(N)), the exact type of Grover amplitudes (sin(theta) = 1/sqrt(N)
  keeps every iterate inside Q(sqrt(N))).
* Roots of unity beyond zeta_8 (QFT on subregisters of dimension > 8,
  arbitrary rational-turn phases) are exact sympy cyclotomics; the
  register transparently accepts a mix of ``ExactComplex`` and sympy
  values and coerces only when needed.

"Measurement" API: ``distribution()`` returns the exact Born-rule
probability measure — the actual output of the mathematical measurement
postulate.  ``measure(seed)`` is downstream classical sampling OF that
exact distribution and is documented as such.
"""
# LUCAS WIRING: mtheory
# Substrate route: mtheory

from __future__ import annotations

import math
import os
import random
import re
from fractions import Fraction

import sympy as sp

__all__ = [
    "ExactComplex",
    "QSqrt2",
    "QSqrt",
    "QuantumRegister",
    "GroverExact",
    "GroverControllerBudgetError",
    "qft",
    "fourier_matrix",
    "verify_unitary",
    "matmul",
    "matrices_equal",
    "hadamard_matrix",
    "pauli_x_matrix",
    "pauli_z_matrix",
    "phase_s_matrix",
    "phase_t_matrix",
    "cnot_matrix",
    "reduced_density_matrix",
    "von_neumann_entropy_exact",
]


# ---------------------------------------------------------------------------
# Exact scalar types
# ---------------------------------------------------------------------------


def _frac(v) -> Fraction:
    """Admit declared rational values, never rationalize a float or boolean."""
    if type(v) is int or isinstance(v, Fraction):
        return Fraction(v)
    if isinstance(v, sp.Rational):
        return Fraction(int(v.p), int(v.q))
    if isinstance(v, str) and re.fullmatch(r"[+-]?\d+(?:/[+-]?\d+)?", v):
        return Fraction(v)
    raise TypeError("exact integer, Fraction, sympy Rational or rational text required")


def _integer(v, name: str, minimum: int = 0) -> int:
    if type(v) is not int and not isinstance(v, sp.Integer):
        raise TypeError(f"{name} must be an exact integer")
    value = int(v)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


class QSqrt2:
    """Exact real number q + s*sqrt(2), q and s Fractions.

    Born-rule probabilities |alpha|^2 of ExactComplex amplitudes have
    this type.  Equality against int/Fraction holds iff s == 0.
    """

    __slots__ = ("q", "s")

    def __init__(self, q=0, s=0):
        self.q = _frac(q)
        self.s = _frac(s)

    def __add__(self, other):
        if isinstance(other, QSqrt2):
            return QSqrt2(self.q + other.q, self.s + other.s)
        if isinstance(other, (int, Fraction, sp.Rational)):
            return QSqrt2(self.q + _frac(other), self.s)
        return NotImplemented

    __radd__ = __add__

    def __sub__(self, other):
        if isinstance(other, QSqrt2):
            return QSqrt2(self.q - other.q, self.s - other.s)
        if isinstance(other, (int, Fraction, sp.Rational)):
            return QSqrt2(self.q - _frac(other), self.s)
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, (int, Fraction, sp.Rational)):
            return QSqrt2(_frac(other) - self.q, -self.s)
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, QSqrt2):
            return QSqrt2(
                self.q * other.q + 2 * self.s * other.s,
                self.q * other.s + self.s * other.q,
            )
        if isinstance(other, (int, Fraction, sp.Rational)):
            f = _frac(other)
            return QSqrt2(self.q * f, self.s * f)
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other):
        f = _frac(other)
        return QSqrt2(self.q / f, self.s / f)

    def __neg__(self):
        return QSqrt2(-self.q, -self.s)

    def __eq__(self, other):
        if isinstance(other, QSqrt2):
            return self.q == other.q and self.s == other.s
        if isinstance(other, (int, Fraction, sp.Rational)):
            return self.s == 0 and self.q == _frac(other)
        return NotImplemented

    def __hash__(self):
        # Rational elements (s == 0) are equal to int/Fraction, so their
        # hash must agree or set/dict lookups silently miss.
        if self.s == 0:
            return hash(self.q)
        return hash((self.q, self.s))

    def _sign(self) -> int:
        """Exact sign of q + s*sqrt(2), computed without floats."""
        if self.s == 0:
            return (self.q > 0) - (self.q < 0)
        if self.q == 0:
            return (self.s > 0) - (self.s < 0)
        if self.q > 0 and self.s > 0:
            return 1
        if self.q < 0 and self.s < 0:
            return -1
        # opposite signs: sign(q + s*sqrt2) = sign(q) * sign(q^2 - 2 s^2)
        cmp_sq = self.q * self.q - 2 * self.s * self.s
        sgn_q = 1 if self.q > 0 else -1
        return sgn_q * ((cmp_sq > 0) - (cmp_sq < 0))

    def _cmp_key(self, other):
        if isinstance(other, QSqrt2):
            return self - other
        if isinstance(other, (int, Fraction, sp.Rational)):
            return QSqrt2(self.q - _frac(other), self.s)
        return NotImplemented

    def __lt__(self, other):
        d = self._cmp_key(other)
        return NotImplemented if d is NotImplemented else d._sign() < 0

    def __le__(self, other):
        d = self._cmp_key(other)
        return NotImplemented if d is NotImplemented else d._sign() <= 0

    def __gt__(self, other):
        d = self._cmp_key(other)
        return NotImplemented if d is NotImplemented else d._sign() > 0

    def __ge__(self, other):
        d = self._cmp_key(other)
        return NotImplemented if d is NotImplemented else d._sign() >= 0

    def is_zero(self):
        return self.q == 0 and self.s == 0

    def as_fraction(self) -> Fraction:
        """Exact rational value; raises if this is genuinely irrational."""
        if self.s != 0:
            raise ValueError(f"irrational value {self!r} has no Fraction form")
        return self.q

    def to_sympy(self):
        return sp.Rational(self.q.numerator, self.q.denominator) + sp.Rational(
            self.s.numerator, self.s.denominator
        ) * sp.sqrt(2)

    def __float__(self):
        return float(self.q) + float(self.s) * math.sqrt(2)

    def __repr__(self):
        return f"QSqrt2({self.q}, {self.s})"


class ExactComplex:
    """Exact element of Q(i, sqrt(2)) = Q(zeta_8).

    Value = re_q + re_s*sqrt(2) + i*(im_q + im_s*sqrt(2)), all four
    coefficients Fractions.  Closed under +, -, *, conjugation and under
    the gate set {H, X, Z, S, T, CNOT}: H contributes 1/sqrt(2) = sqrt(2)/2
    (the re_s/im_s slots), S contributes i, T contributes (1+i)*sqrt(2)/2.
    """

    __slots__ = ("re_q", "re_s", "im_q", "im_s")

    def __init__(self, re_q=0, re_s=0, im_q=0, im_s=0):
        self.re_q = _frac(re_q)
        self.re_s = _frac(re_s)
        self.im_q = _frac(im_q)
        self.im_s = _frac(im_s)

    @classmethod
    def rational(cls, q) -> "ExactComplex":
        return cls(_frac(q), 0, 0, 0)

    def __add__(self, other):
        if isinstance(other, ExactComplex):
            return ExactComplex(
                self.re_q + other.re_q,
                self.re_s + other.re_s,
                self.im_q + other.im_q,
                self.im_s + other.im_s,
            )
        if isinstance(other, (int, Fraction, sp.Rational)):
            return ExactComplex(self.re_q + _frac(other), self.re_s, self.im_q, self.im_s)
        return NotImplemented

    __radd__ = __add__

    def __sub__(self, other):
        if isinstance(other, ExactComplex):
            return ExactComplex(
                self.re_q - other.re_q,
                self.re_s - other.re_s,
                self.im_q - other.im_q,
                self.im_s - other.im_s,
            )
        if isinstance(other, (int, Fraction, sp.Rational)):
            return ExactComplex(self.re_q - _frac(other), self.re_s, self.im_q, self.im_s)
        return NotImplemented

    def __rsub__(self, other):
        if isinstance(other, (int, Fraction, sp.Rational)):
            return ExactComplex(_frac(other) - self.re_q, -self.re_s, -self.im_q, -self.im_s)
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, ExactComplex):
            a, b, c, d = self.re_q, self.re_s, self.im_q, self.im_s
            e, f, g, h = other.re_q, other.re_s, other.im_q, other.im_s
            return ExactComplex(
                a * e + 2 * b * f - c * g - 2 * d * h,
                a * f + b * e - c * h - d * g,
                a * g + 2 * b * h + c * e + 2 * d * f,
                a * h + b * g + c * f + d * e,
            )
        if isinstance(other, (int, Fraction, sp.Rational)):
            f = _frac(other)
            return ExactComplex(self.re_q * f, self.re_s * f, self.im_q * f, self.im_s * f)
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other):
        f = _frac(other)
        return ExactComplex(self.re_q / f, self.re_s / f, self.im_q / f, self.im_s / f)

    def __neg__(self):
        return ExactComplex(-self.re_q, -self.re_s, -self.im_q, -self.im_s)

    def __eq__(self, other):
        if isinstance(other, ExactComplex):
            return (
                self.re_q == other.re_q
                and self.re_s == other.re_s
                and self.im_q == other.im_q
                and self.im_s == other.im_s
            )
        if isinstance(other, (int, Fraction, sp.Rational)):
            f = _frac(other)
            return self.re_q == f and self.re_s == 0 and self.im_q == 0 and self.im_s == 0
        return NotImplemented

    def __hash__(self):
        if self.re_s == 0 and self.im_q == 0 and self.im_s == 0:
            return hash(self.re_q)
        return hash((self.re_q, self.re_s, self.im_q, self.im_s))

    def is_zero(self):
        return self.re_q == 0 and self.re_s == 0 and self.im_q == 0 and self.im_s == 0

    def conjugate(self) -> "ExactComplex":
        return ExactComplex(self.re_q, self.re_s, -self.im_q, -self.im_s)

    def abs2(self) -> QSqrt2:
        """Exact |z|^2 in Q(sqrt(2))."""
        a, b, c, d = self.re_q, self.re_s, self.im_q, self.im_s
        return QSqrt2(
            a * a + 2 * b * b + c * c + 2 * d * d,
            2 * (a * b + c * d),
        )

    def to_sympy(self):
        return (
            sp.Rational(self.re_q.numerator, self.re_q.denominator)
            + sp.Rational(self.re_s.numerator, self.re_s.denominator) * sp.sqrt(2)
            + sp.I
            * (
                sp.Rational(self.im_q.numerator, self.im_q.denominator)
                + sp.Rational(self.im_s.numerator, self.im_s.denominator) * sp.sqrt(2)
            )
        )

    def __repr__(self):
        return (
            f"ExactComplex(re_q={self.re_q}, re_s={self.re_s}, "
            f"im_q={self.im_q}, im_s={self.im_s})"
        )


EC_ZERO = ExactComplex(0)
EC_ONE = ExactComplex(1)
EC_I = ExactComplex(0, 0, 1, 0)
EC_INV_SQRT2 = ExactComplex(0, Fraction(1, 2))  # sqrt(2)/2 == 1/sqrt(2)
EC_T_PHASE = ExactComplex(0, Fraction(1, 2), 0, Fraction(1, 2))  # e^{i pi/4}


class QSqrt:
    """Exact element q + s*sqrt(root) of the real quadratic field Q(sqrt(root)).

    ``root`` is a positive integer (not necessarily squarefree; if root is
    a perfect square the value is rational and equality with Fraction/int
    still works).
    """

    __slots__ = ("q", "s", "root")

    def __init__(self, q=0, s=0, root=2):
        self.q = _frac(q)
        self.s = _frac(s)
        self.root = int(root)

    def _scalar_eq(self, other):
        f = _frac(other)
        r = math.isqrt(self.root)
        if r * r == self.root:
            return self.q + self.s * r == f
        return self.s == 0 and self.q == f

    def __eq__(self, other):
        if isinstance(other, QSqrt):
            if self.root == other.root:
                return self.q == other.q and self.s == other.s
            return self.to_sympy() == other.to_sympy()
        if isinstance(other, (int, Fraction, sp.Rational)):
            return self._scalar_eq(other)
        return NotImplemented

    def __hash__(self):
        try:
            return hash(self.as_fraction())
        except ValueError:
            # Irrational elements hash on the canonical sympy form so
            # different-root representations of the same value agree.
            return hash(self.to_sympy())

    def square(self) -> "QSqrt":
        return QSqrt(
            self.q * self.q + self.root * self.s * self.s,
            2 * self.q * self.s,
            self.root,
        )

    def as_fraction(self) -> Fraction:
        r = math.isqrt(self.root)
        if r * r == self.root:
            return self.q + self.s * r
        if self.s == 0:
            return self.q
        raise ValueError(f"irrational value {self!r} has no Fraction form")

    def to_sympy(self):
        return sp.Rational(self.q.numerator, self.q.denominator) + sp.Rational(
            self.s.numerator, self.s.denominator
        ) * sp.sqrt(self.root)

    def __repr__(self):
        return f"QSqrt(q={self.q}, s={self.s}, root={self.root})"


# ---------------------------------------------------------------------------
# Coercion helpers: the register may hold ExactComplex or exact sympy values
# (QFT beyond dim 8, generic rational-turn phases).  Gates take the fast
# pure-Fraction path whenever both operands are ExactComplex.
# ---------------------------------------------------------------------------


def _to_sympy(v):
    if isinstance(v, ExactComplex):
        return v.to_sympy()
    if isinstance(v, (int, Fraction)):
        return sp.Rational(v) if isinstance(v, int) else sp.Rational(v.numerator, v.denominator)
    return v


def _e_add(a, b):
    if isinstance(a, ExactComplex) and isinstance(b, ExactComplex):
        return a + b
    return _to_sympy(a) + _to_sympy(b)


def _e_sub(a, b):
    if isinstance(a, ExactComplex) and isinstance(b, ExactComplex):
        return a - b
    return _to_sympy(a) - _to_sympy(b)


def _e_mul(a, b):
    if isinstance(a, ExactComplex) and isinstance(b, ExactComplex):
        return a * b
    return _to_sympy(a) * _to_sympy(b)


def _e_neg(a):
    return -a


def _e_div(a, d: int):
    if isinstance(a, ExactComplex):
        return a / d
    return _to_sympy(a) / d


def _e_conj(a):
    if isinstance(a, ExactComplex):
        return a.conjugate()
    return sp.conjugate(_to_sympy(a))


def _e_abs2(a):
    if isinstance(a, ExactComplex):
        return a.abs2()
    return sp.expand(_to_sympy(a) * sp.conjugate(_to_sympy(a)))


def _e_is_zero(a) -> bool:
    if isinstance(a, ExactComplex):
        return a.is_zero()
    return bool(sp.simplify(_to_sympy(a)) == 0)


_EIGHTH_ROOTS = {
    Fraction(0): EC_ONE,
    Fraction(1, 8): EC_T_PHASE,
    Fraction(1, 4): EC_I,
    Fraction(3, 8): ExactComplex(0, Fraction(-1, 2), 0, Fraction(1, 2)),
    Fraction(1, 2): ExactComplex(-1),
    Fraction(5, 8): ExactComplex(0, Fraction(-1, 2), 0, Fraction(-1, 2)),
    Fraction(3, 4): ExactComplex(0, 0, -1, 0),
    Fraction(7, 8): ExactComplex(0, Fraction(1, 2), 0, Fraction(-1, 2)),
}


def _phase_factor(theta_exact):
    """Resolve an exact phase specification to a unit-modulus factor.

    ``theta_exact`` may be:
      * an ``ExactComplex`` — used literally as e^{i theta};
      * a sympy ``Expr`` — used literally as e^{i theta};
      * an int/Fraction/sympy Rational ``t`` — interpreted as a number of
        *turns*: the phase factor is e^{2 pi i t}.  Fractions whose reduced
        denominator divides 8 stay inside Q(zeta_8) as ``ExactComplex``;
        all others become exact sympy cyclotomics.
    """
    if isinstance(theta_exact, ExactComplex):
        if theta_exact.abs2() != 1:
            raise ValueError("literal phase factor must have exact unit modulus")
        return theta_exact
    if isinstance(theta_exact, sp.Expr) and not isinstance(theta_exact, sp.Rational):
        if theta_exact.atoms(sp.Float):
            raise TypeError("floating-point atoms are forbidden in phase factors")
        if sp.simplify(theta_exact * sp.conjugate(theta_exact) - 1) != 0:
            raise ValueError("literal phase factor needs an exact unit-modulus proof")
        return theta_exact
    t = _frac(theta_exact) % 1
    if t in _EIGHTH_ROOTS:
        return _EIGHTH_ROOTS[t]
    return sp.exp(2 * sp.pi * sp.I * sp.Rational(t.numerator, t.denominator))


# ---------------------------------------------------------------------------
# QuantumRegister — sparse exact state vector in C^{2^n}
# ---------------------------------------------------------------------------


def _pack_bits(index: int, positions) -> int:
    out = 0
    for p, q in enumerate(positions):
        out |= ((index >> q) & 1) << p
    return out


def _scatter_bits(value: int, positions) -> int:
    out = 0
    for p, q in enumerate(positions):
        if (value >> p) & 1:
            out |= 1 << q
    return out


class QuantumRegister:
    """Sparse exact state vector on ``n_qubits`` qubits (default 11 → C^2048).

    ``self.amplitudes`` maps basis index -> exact amplitude
    (``ExactComplex`` or exact sympy Expr).  Zero amplitudes are never
    stored; the vector is never densified to floats.  Qubit q is bit q of
    the basis index (qubit 0 = least significant bit).
    """

    def __init__(self, n_qubits: int = 11, basis: int = 0, max_amplitudes=None):
        n_qubits = _integer(n_qubits, "n_qubits", 1)
        basis = _integer(basis, "basis")
        if not 0 <= basis < (1 << n_qubits):
            raise ValueError("basis index out of range")
        self.n_qubits = n_qubits
        self.dim = 1 << n_qubits
        # Fail-closed resource bound on the sparse support.  n_qubits is
        # unlimited — a basis state at n=10000 is one dict entry — but
        # operations that would densify the state (H^{otimes n}, diffusion)
        # raise instead of silently attempting 2^n materialisation.
        self.max_amplitudes = (
            _integer(max_amplitudes, "max_amplitudes", 1) if max_amplitudes is not None
            else int(os.environ.get("PYTHIA_MAX_AMPLITUDES", 1 << 24))
        )
        if self.max_amplitudes < 1:
            raise ValueError("max_amplitudes must be >= 1")
        self.amplitudes = {basis: EC_ONE}

    def _check_support(self, extra: int = 0):
        if len(self.amplitudes) + extra > self.max_amplitudes:
            raise MemoryError(
                f"sparse state would exceed {self.max_amplitudes} nonzero "
                f"amplitudes (n_qubits={self.n_qubits}); use the stabilizer, "
                "closed-form, or symbolic backends for wide states"
            )

    def copy(self) -> "QuantumRegister":
        r = QuantumRegister(self.n_qubits, max_amplitudes=self.max_amplitudes)
        r.amplitudes = dict(self.amplitudes)
        return r

    def _require_qubit(self, q: int) -> int:
        q = _integer(q, "qubit")
        if q >= self.n_qubits:
            raise IndexError(f"qubit {q} out of range [0,{self.n_qubits})")
        return q

    # -- one-qubit gates ---------------------------------------------------

    def apply_h(self, q: int):
        """Hadamard on qubit q: |a,b> -> ((a+b)/sqrt(2), (a-b)/sqrt(2))."""
        q = self._require_qubit(q)
        mask = 1 << q
        # Worst case doubles the support of states untouched on qubit q.
        self._check_support(len(self.amplitudes))
        inv = EC_INV_SQRT2
        seen = set()
        for i in list(self.amplitudes):
            base = i & ~mask
            if base in seen:
                continue
            seen.add(base)
            j = base | mask
            a = self.amplitudes.get(base, EC_ZERO)
            b = self.amplitudes.get(j, EC_ZERO)
            s = _e_mul(_e_add(a, b), inv)
            d = _e_mul(_e_sub(a, b), inv)
            if _e_is_zero(s):
                self.amplitudes.pop(base, None)
            else:
                self.amplitudes[base] = s
            if _e_is_zero(d):
                self.amplitudes.pop(j, None)
            else:
                self.amplitudes[j] = d

    def apply_x(self, q: int):
        q = self._require_qubit(q)
        mask = 1 << q
        seen = set()
        for i in list(self.amplitudes):
            base = i & ~mask
            if base in seen:
                continue
            seen.add(base)
            j = base | mask
            a = self.amplitudes.pop(base, None)
            b = self.amplitudes.pop(j, None)
            if b is not None:
                self.amplitudes[base] = b
            if a is not None:
                self.amplitudes[j] = a

    def apply_z(self, q: int):
        q = self._require_qubit(q)
        mask = 1 << q
        for i in list(self.amplitudes):
            if i & mask:
                self.amplitudes[i] = _e_neg(self.amplitudes[i])

    def apply_s(self, q: int):
        q = self._require_qubit(q)
        mask = 1 << q
        for i in list(self.amplitudes):
            if i & mask:
                self.amplitudes[i] = _e_mul(self.amplitudes[i], EC_I)

    def apply_t(self, q: int):
        q = self._require_qubit(q)
        mask = 1 << q
        for i in list(self.amplitudes):
            if i & mask:
                self.amplitudes[i] = _e_mul(self.amplitudes[i], EC_T_PHASE)

    def apply_phase(self, q: int, theta_exact):
        """Multiply amplitudes with bit q set by an exact unit phase.

        ``theta_exact``: see ``_phase_factor`` — an ExactComplex/sympy
        value used literally, or a rational number of turns t giving the
        exact cyclotomic e^{2 pi i t}.
        """
        q = self._require_qubit(q)
        factor = _phase_factor(theta_exact)
        mask = 1 << q
        for i in list(self.amplitudes):
            if i & mask:
                self.amplitudes[i] = _e_mul(self.amplitudes[i], factor)

    def apply_cnot(self, c: int, t: int):
        c = self._require_qubit(c)
        t = self._require_qubit(t)
        if c == t:
            raise ValueError("control and target must differ")
        cm, tm = 1 << c, 1 << t
        seen = set()
        for i in list(self.amplitudes):
            if not (i & cm):
                continue
            base = i & ~tm
            if base in seen:
                continue
            seen.add(base)
            j = base | tm
            a = self.amplitudes.pop(base, None)
            b = self.amplitudes.pop(j, None)
            if b is not None:
                self.amplitudes[base] = b
            if a is not None:
                self.amplitudes[j] = a

    # -- oracles and composite operations ----------------------------------

    def apply_grover_oracle(self, marked):
        """Exact phase oracle O = I - 2|w><w|: negate marked amplitudes."""
        if type(marked) is int or isinstance(marked, sp.Integer):
            marked = (marked,)
        indices = tuple(_integer(w, "marked index") for w in marked)
        if any(w >= self.dim for w in indices):
            raise IndexError("marked index outside register")
        if len(set(indices)) != len(indices):
            raise ValueError("marked oracle indices must be unique")
        for w in indices:
            if w in self.amplitudes:
                self.amplitudes[w] = _e_neg(self.amplitudes[w])

    def uniform_superposition(self):
        """|s> = H^{otimes n}|0>: every amplitude becomes 2^{-n/2} exactly."""
        for q in range(self.n_qubits):
            self.apply_h(q)

    def diffusion(self):
        """Exact Grover diffusion D = 2|s><s| - I (inversion about the mean)."""
        # D fills every basis index i where 2*mu - a_i != 0 — for a sparse
        # state that is generically the full 2^n support.
        if self.dim > self.max_amplitudes:
            raise MemoryError(
                f"diffusion would densify to 2^{self.n_qubits} amplitudes, "
                f"exceeding bound {self.max_amplitudes}"
            )
        mu = EC_ZERO
        for v in self.amplitudes.values():
            mu = _e_add(mu, v)
        mu = _e_div(mu, self.dim)
        two_mu = _e_mul(mu, ExactComplex(2)) if isinstance(mu, ExactComplex) else 2 * mu
        for i in range(self.dim):
            a = self.amplitudes.get(i, EC_ZERO)
            v = _e_sub(two_mu, a)
            if _e_is_zero(v):
                self.amplitudes.pop(i, None)
            else:
                self.amplitudes[i] = v

    # -- exact measurement --------------------------------------------------

    def norm_squared(self):
        """Exact sum |alpha|^2 — QSqrt2 for pure Q(i,sqrt2) states, else sympy."""
        acc = QSqrt2(0)
        acc_sp = sp.Integer(0)
        has_sp = False
        for v in self.amplitudes.values():
            if isinstance(v, ExactComplex):
                acc += v.abs2()
            else:
                acc_sp += _e_abs2(v)
                has_sp = True
        if has_sp:
            return sp.simplify(acc_sp + acc.to_sympy())
        return acc

    def assert_normalized(self):
        ns = self.norm_squared()
        if isinstance(ns, QSqrt2):
            if ns != 1:
                raise AssertionError(f"state not normalized: |psi|^2 = {ns!r}")
        else:
            if sp.simplify(ns - 1) != 0:
                raise AssertionError(f"state not normalized: |psi|^2 = {ns}")
        return True

    def distribution(self, include_zeros: bool = False):
        """The exact Born-rule probability measure.

        Returns {basis_index: exact probability} — QSqrt2 values for
        Q(i,sqrt2) states, exact sympy values for cyclotomic states.
        This IS the measurement output per the mathematical postulate
        (AGENTS.md section 1.2.1); no sampling is involved.
        """
        out = {}
        if include_zeros:
            items = ((i, self.amplitudes.get(i, EC_ZERO)) for i in range(self.dim))
        else:
            items = self.amplitudes.items()
        for i, a in items:
            p = _e_abs2(a)
            if include_zeros or not (
                isinstance(p, QSqrt2) and p.is_zero() or p == 0
            ):
                out[i] = p
        return out

    def measure(self, seed: int) -> int:
        """Downstream CLASSICAL sampling of the exact distribution().

        Not part of the quantum computation: draws one basis index by
        comparing a seeded PRNG uniform against the exact cumulative
        Born-rule probabilities (converted to float only at this classical
        boundary).  For the quantum output itself use ``distribution()``.
        """
        rng = random.Random(seed)
        r = rng.random()
        cumulative = 0.0
        last = None
        for i in sorted(self.amplitudes):
            cumulative += float(_e_abs2(self.amplitudes[i]))
            last = i
            if r < cumulative:
                return i
        return last

    # -- exact operator extraction ------------------------------------------

    @staticmethod
    def operator_matrix(n_qubits: int, gate_fn):
        """Build the exact 2^n x 2^n matrix of a gate by applying it to
        each computational basis state: column j = U|j>."""
        dim = 1 << n_qubits
        mat = [[EC_ZERO] * dim for _ in range(dim)]
        for j in range(dim):
            r = QuantumRegister(n_qubits, basis=j)
            gate_fn(r)
            for i, a in r.amplitudes.items():
                mat[i][j] = a
        return mat


# ---------------------------------------------------------------------------
# Exact gate matrices and matrix algebra over the exact ring
# ---------------------------------------------------------------------------


def hadamard_matrix():
    h = EC_INV_SQRT2
    return [[h, h], [h, _e_neg(h)]]


def pauli_x_matrix():
    return [[EC_ZERO, EC_ONE], [EC_ONE, EC_ZERO]]


def pauli_z_matrix():
    return [[EC_ONE, EC_ZERO], [EC_ZERO, ExactComplex(-1)]]


def phase_s_matrix():
    return [[EC_ONE, EC_ZERO], [EC_ZERO, EC_I]]


def phase_t_matrix():
    return [[EC_ONE, EC_ZERO], [EC_ZERO, EC_T_PHASE]]


def cnot_matrix():
    m = [[EC_ZERO] * 4 for _ in range(4)]
    m[0][0] = EC_ONE
    m[1][1] = EC_ONE
    m[3][2] = EC_ONE
    m[2][3] = EC_ONE
    return m


def matmul(A, B):
    n = len(A)
    k = len(B)
    m = len(B[0])
    out = [[EC_ZERO] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            s = EC_ZERO
            for p in range(k):
                s = _e_add(s, _e_mul(A[i][p], B[p][j]))
            out[i][j] = s
    return out


def matrices_equal(A, B) -> bool:
    if len(A) != len(B) or len(A[0]) != len(B[0]):
        return False
    for ra, rb in zip(A, B):
        for a, b in zip(ra, rb):
            if a != b:
                return False
    return True


def verify_unitary(U) -> bool:
    """Exact check U^dagger U = I on a square exact matrix.

    Returns True; raises AssertionError pinpointing the failing entry.
    Works on ExactComplex and exact sympy entries alike.
    """
    n = len(U)
    if not n or any(len(row) != n for row in U):
        raise ValueError("a nonempty square operator matrix is required")
    for i in range(n):
        for j in range(n):
            s = EC_ZERO
            for k in range(n):
                s = _e_add(s, _e_mul(_e_conj(U[k][i]), U[k][j]))
            if i == j:
                ok = (s == 1) if isinstance(s, ExactComplex) else sp.simplify(_to_sympy(s) - 1) == 0
                if not ok:
                    raise AssertionError(f"(U^dag U)[{i}][{j}] = {s!r} != 1")
            else:
                ok = _e_is_zero(s)
                if not ok:
                    raise AssertionError(f"(U^dag U)[{i}][{j}] = {s!r} != 0")
    return True


# ---------------------------------------------------------------------------
# Exact Quantum Fourier Transform on a subregister
# ---------------------------------------------------------------------------


def fourier_matrix(m: int, inverse: bool = False):
    """Exact DFT matrix F[j][k] = omega^{jk}/sqrt(m), omega = e^{2 pi i / m}.

    For m in {1, 2, 4, 8} all entries lie in Q(zeta_8) and are
    ``ExactComplex``.  For other m the entries are exact sympy
    cyclotomics exp(2 pi i jk / m) / sqrt(m).
    """
    if m in (1, 2, 4, 8):
        scale = {
            1: EC_ONE,
            2: EC_INV_SQRT2,
            4: ExactComplex(Fraction(1, 2)),
            8: ExactComplex(0, Fraction(1, 4)),
        }[m]
        mat = []
        for j in range(m):
            row = []
            for k in range(m):
                w = _phase_factor(Fraction((j * k) % m, m))
                if inverse:
                    w = w.conjugate()
                row.append(w * scale)
            mat.append(row)
        return mat
    sign = -1 if inverse else 1
    omega = sp.exp(sign * 2 * sp.pi * sp.I / m)
    rt = sp.sqrt(m)
    return [[omega ** (j * k) / rt for k in range(m)] for j in range(m)]


def qft(register: QuantumRegister, qubits, inverse: bool = False):
    """Exact QFT on the subregister spanned by ``qubits`` (bit positions).

    For every fixed assignment of the remaining environment qubits, the
    M = 2^|qubits| amplitude subvector is multiplied by the exact Fourier
    matrix F_M (see ``fourier_matrix``).  Subregisters of size <= 3 stay
    inside Q(zeta_8); larger ones produce exact sympy cyclotomics.
    """
    qubits = tuple(sorted(qubits))
    m = 1 << len(qubits)
    env_qubits = tuple(q for q in range(register.n_qubits) if q not in qubits)
    F = fourier_matrix(m, inverse=inverse)

    groups = {}
    for i, a in register.amplitudes.items():
        e = _pack_bits(i, env_qubits)
        groups.setdefault(e, {})[_pack_bits(i, qubits)] = a

    new_amps = {}
    for e, vec in groups.items():
        e_bits = _scatter_bits(e, env_qubits)
        for k in range(m):
            acc = EC_ZERO
            for j in range(m):
                if j in vec:
                    acc = _e_add(acc, _e_mul(F[k][j], vec[j]))
            if not _e_is_zero(acc):
                new_amps[e_bits | _scatter_bits(k, qubits)] = acc
    register.amplitudes = new_amps
    return register


# ---------------------------------------------------------------------------
# GroverExact — exact amplitude amplification in the 2D invariant subspace
# ---------------------------------------------------------------------------


class GroverControllerBudgetError(ValueError):
    """Default peak selection exceeds its declared controller work budget."""


class GroverExact:
    """Exact Grover iteration on N = 2^n_qubits states, one marked |w>.

    The evolution stays inside span{|w>, |s'>} where |s'> is the uniform
    superposition over unmarked states.  With sin(theta) = 1/sqrt(N),
    every amplitude after k iterates of G = D.O (phase oracle then
    inversion about the mean) has the exact form coeff/sqrt(N) with
    coeff a Fraction — i.e. an element of Q(sqrt(N)).  We track the two
    rational coefficients (A on the marked state, B on each unmarked
    state) through the exact recurrences

        M  = ((N-1) B - A) / N          (post-oracle mean, in 1/sqrt(N))
        A' = A + 2M,   B' = 2M - B

    No floats in amplitudes or iteration selection: ``optimal_iterations``
    certifies the first peak by exact adjacent Born-probability comparison.
    """

    def __init__(self, n_qubits: int, marked: int = 0):
        n_qubits = _integer(n_qubits, "n_qubits", 1)
        marked = _integer(marked, "marked")
        self.n_qubits = n_qubits
        self.N = 1 << n_qubits
        if not 0 <= marked < self.N:
            raise ValueError("marked index out of range")
        self.marked = marked

    def _coeffs(self, k: int):
        """Exact (A_k, B_k) — amplitudes are A_k/sqrt(N) and B_k/sqrt(N)."""
        k = _integer(k, "k")
        N = self.N
        A, B = Fraction(1), Fraction(1)
        for _ in range(k):
            M = ((N - 1) * B - A) / N
            A, B = A + 2 * M, 2 * M - B
        return A, B

    def iterate(self, k: int):
        """Exact amplitudes after k Grover iterates: (a_k, b_k) as QSqrt.

        a_k is the amplitude of the marked state |w>; b_k is the amplitude
        of EACH unmarked state.  Both are elements of Q(sqrt(N)).
        """
        A, B = self._coeffs(k)
        return QSqrt(0, A / self.N, self.N), QSqrt(0, B / self.N, self.N)

    def optimal_iterations(self, *, max_stages: int = 1024) -> int:
        """First-peak Grover count from exact adjacent Born probabilities.

        Advance the two rational coefficients until the next probability
        fails to improve. Ties choose the earlier count. This certifies the
        first amplification peak, not a global optimum over all later cycles.
        It needs O(sqrt(N)) recurrence stages; rational bit costs are additional.
        The default controller admits N <= max_stages**2 conservatively and
        executes at most max_stages transitions. This is an explicit work
        envelope, not a limit on the exact quantum representation. Callers
        may request a larger controller budget or supply an iteration count.
        """
        max_stages = _integer(max_stages, "max_stages", 1)
        if self.N > max_stages * max_stages:
            raise GroverControllerBudgetError(
                "exact peak selection exceeds the controller admission budget; "
                "provide iterations explicitly or request a larger max_stages"
            )
        A, B = Fraction(1), Fraction(1)
        for k in range(max_stages):
            mean = ((self.N - 1) * B - A) / self.N
            next_a, next_b = A + 2 * mean, 2 * mean - B
            if next_a * next_a <= A * A:
                return k
            A, B = next_a, next_b
        raise GroverControllerBudgetError("exact peak selection exhausted max_stages")

    def success_probability(self, k: int) -> Fraction:
        """Exact a_k^2 = sin^2((2k+1) theta) as a Fraction in Q."""
        A, _ = self._coeffs(k)
        return A * A / self.N

    def distribution(self, k: int):
        """Exact {"marked": p, "each_unmarked": q} probability dict."""
        A, B = self._coeffs(k)
        return {"marked": A * A / self.N, "each_unmarked": B * B / self.N}

    def full_distribution(self, k: int):
        """Exact per-basis-state {index: probability} dict."""
        d = self.distribution(k)
        out = {}
        for i in range(self.N):
            out[i] = d["marked"] if i == self.marked else d["each_unmarked"]
        return out

    def run_register(self, k=None) -> QuantumRegister:
        """Register-level exact run on a QuantumRegister of n qubits.

        Builds |s> = H^{otimes n}|0> exactly, then applies k actual Grover
        iterates (phase oracle + inversion about the mean) to the sparse
        exact state vector.  k defaults to ``optimal_iterations()``.
        """
        if k is None:
            k = self.optimal_iterations()
        reg = QuantumRegister(self.n_qubits)
        reg.uniform_superposition()
        for _ in range(k):
            reg.apply_grover_oracle(self.marked)
            reg.diffusion()
        return reg


# ---------------------------------------------------------------------------
# Exact entanglement entropy
# ---------------------------------------------------------------------------


def reduced_density_matrix(register: QuantumRegister, subsystem):
    """Exact reduced density matrix rho_A = Tr_env |psi><psi|.

    ``subsystem`` is the list of qubits retained.  Returns a sympy Matrix
    with exact entries (ExactComplex amplitudes are converted exactly).
    """
    subsystem = tuple(sorted(subsystem))
    env_qubits = tuple(q for q in range(register.n_qubits) if q not in subsystem)
    d = 1 << len(subsystem)
    groups = {}
    for i, a in register.amplitudes.items():
        e = _pack_bits(i, env_qubits)
        groups.setdefault(e, []).append((_pack_bits(i, subsystem), a))
    rho = sp.zeros(d, d)
    for items in groups.values():
        for p, a in items:
            sa = _to_sympy(a)
            for q2, b in items:
                rho[p, q2] += sa * sp.conjugate(_to_sympy(b))
    return rho


def von_neumann_entropy_exact(register: QuantumRegister, subsystem):
    """Exact S = -Tr rho_A log2 rho_A for exactly-computable spectra.

    Computes the eigenvalues of the exact reduced density matrix via
    sympy's symbolic eigensolver and returns the exact entropy expression
    (a sympy Integer/Rational/log-expression — e.g. exactly 1 bit for a
    Bell half).  Raises NotImplementedError if the characteristic
    polynomial does not factor symbolically.
    """
    rho = reduced_density_matrix(register, subsystem)
    eig = rho.eigenvals()
    if sum(eig.values()) != rho.rows:
        raise NotImplementedError("eigenspectrum not exactly solvable")
    s = sp.Integer(0)
    for lam, mult in eig.items():
        if lam == 0:
            continue
        s -= mult * lam * sp.log(lam, 2)
    return sp.simplify(s)
