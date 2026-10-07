"""First-principles quantum tensor — Python port of first_principles_quantum.ts.

This is the project's OWN tensor infrastructure. It is NOT a wrapper around
sklearn, xgboost, lightgbm, or tensorflow. It is exact complex linear
algebra over C^N, mirroring the TypeScript substrate:

    Q = (H, U, M, ⊗, C)

- H  : Hilbert space H_n = C^(2^n)
- U  : Unitary group U(N) — matrix exponential exp(-iHt/ℏ)
- M  : Measurement operators (PVM / POVM) — Born rule
- ⊗  : Tensor product (Kronecker)
- C  : Complex scalar field

Orders of Truth:
- MATHEMATICAL: follows from explicit Hilbert space axioms, unitary Lie
  groups, and spectral theorems.
- COMPUTATIONAL: exact complex linear algebra over C^N, verified by
  deterministic unit tests.

The algebraic substrate is exact where it uses integer/Decimal operators.
This tensor layer is deterministic finite-precision IEEE-754 complex
arithmetic; it must not be described as exact symbolic arithmetic.

This module is zero-dependency (Python stdlib + math + cmath only). It does
not import numpy, sklearn, tensorflow, or any external ML library. It uses
Python's built-in ``complex`` type for exact complex arithmetic and the
``math`` / ``cmath`` modules for transcendental functions.

The 32-node dual-overlay frame (icosahedron plus its dual dodecahedron at
the icosahedron's face centres) and the Pisot-family Hamiltonians come from
Kellogg's own substrate. No sibling product is imported.
"""

# LUCAS WIRING: implements its Lucas kernel inline (kellogg.substrate,
# L_n = trace(R^n)). MUST NOT import from any sibling algorithm.
# Substrate route: trace

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 0. COMPLEX SCALAR FIELD (C)
# ---------------------------------------------------------------------------


class Complex:
    """Deterministic finite-precision complex scalar.

    Values are stored as IEEE-754 ``float`` components. Non-finite values
    are rejected instead of silently converted to zero, so instability
    remains observable at the boundary.
    """

    __slots__ = ("re", "im")

    ZERO: "Complex"
    ONE: "Complex"
    I: "Complex"
    MINUS_ONE: "Complex"
    MINUS_I: "Complex"
    INV_SQRT2: "Complex"

    def __init__(self, re: float, im: float = 0.0) -> None:
        re = float(re)
        im = float(im)
        if not math.isfinite(re) or not math.isfinite(im):
            raise ValueError("non-finite complex component")
        self.re = re
        self.im = im

    @staticmethod
    def polar(r: float, theta: float) -> "Complex":
        return Complex(r * math.cos(theta), r * math.sin(theta))

    @staticmethod
    def from_native(z: complex) -> "Complex":
        return Complex(z.real, z.imag)

    def add(self, other: "Complex") -> "Complex":
        return Complex(self.re + other.re, self.im + other.im)

    def sub(self, other: "Complex") -> "Complex":
        return Complex(self.re - other.re, self.im - other.im)

    def mul(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float)):
            return Complex(self.re * other, self.im * other)
        return Complex(
            self.re * other.re - self.im * other.im,
            self.re * other.im + self.im * other.re,
        )

    def div(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float)):
            return Complex(self.re / other, self.im / other)
        denom = other.re * other.re + other.im * other.im
        if denom == 0:
            raise ZeroDivisionError("Complex division by zero")
        return Complex(
            (self.re * other.re + self.im * other.im) / denom,
            (self.im * other.re - self.re * other.im) / denom,
        )

    def conj(self) -> "Complex":
        return Complex(self.re, -self.im)

    def abs2(self) -> float:
        return self.re * self.re + self.im * self.im

    def abs(self) -> float:
        return math.hypot(self.re, self.im)

    def arg(self) -> float:
        return math.atan2(self.im, self.re)

    def exp(self) -> "Complex":
        r = math.exp(self.re)
        return Complex(r * math.cos(self.im), r * math.sin(self.im))

    def neg(self) -> "Complex":
        return Complex(-self.re, -self.im)

    def equals(self, other: "Complex", tol: float = 1e-12) -> bool:
        return abs(self.re - other.re) <= tol and abs(self.im - other.im) <= tol

    def to_native(self) -> complex:
        return complex(self.re, self.im)

    def __add__(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float)):
            other = Complex(other)
        if not isinstance(other, Complex):
            return NotImplemented
        return self.add(other)

    __radd__ = __add__

    def __sub__(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float)):
            other = Complex(other)
        if not isinstance(other, Complex):
            return NotImplemented
        return self.sub(other)

    def __rsub__(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float)):
            return Complex(other).sub(self)
        return NotImplemented

    def __mul__(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float, Complex)):
            return self.mul(other)
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float, Complex)):
            return self.div(other)
        return NotImplemented

    def __rtruediv__(self, other: "Complex | float") -> "Complex":
        if isinstance(other, (int, float)):
            return Complex(other).div(self)
        return NotImplemented

    def __neg__(self) -> "Complex":
        return self.neg()

    def __abs__(self) -> float:
        return self.abs()

    def __complex__(self) -> complex:
        return self.to_native()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Complex) and self.re == other.re and self.im == other.im

    def __hash__(self) -> int:
        return hash((self.re, self.im))

    def __repr__(self) -> str:
        if abs(self.im) < 1e-10:
            return f"{self.re:.6g}"
        sign = "+" if self.im >= 0 else "-"
        return f"{self.re:.6g} {sign} {abs(self.im):.6g}i"


Complex.ZERO = Complex(0.0, 0.0)
Complex.ONE = Complex(1.0, 0.0)
Complex.I = Complex(0.0, 1.0)
Complex.MINUS_ONE = Complex(-1.0, 0.0)
Complex.MINUS_I = Complex(0.0, -1.0)
Complex.INV_SQRT2 = Complex(1.0 / math.sqrt(2.0), 0.0)


# ---------------------------------------------------------------------------
# 1. COMPLEX LINEAR ALGEBRA & MATRICES (M ∈ C^(m × n))
# ---------------------------------------------------------------------------


class ComplexMatrix:
    """Exact complex matrix over C^(m × n).

    Mirrors ``ComplexMatrix`` from ``first_principles_quantum.ts``.
    All operations are deterministic complex linear algebra — no random
    initialization, no heuristics.
    """

    __slots__ = ("rows", "cols", "data")

    def __init__(self, rows: int, cols: int, data: Optional[List[List[Complex]]] = None) -> None:
        self.rows = rows
        self.cols = cols
        if data is not None:
            self.data = data
        else:
            self.data = [[Complex.ZERO for _ in range(cols)] for _ in range(rows)]

    @staticmethod
    def identity(n: int) -> "ComplexMatrix":
        m = ComplexMatrix(n, n)
        for i in range(n):
            m.data[i][i] = Complex.ONE
        return m

    @staticmethod
    def zero(rows: int, cols: int) -> "ComplexMatrix":
        return ComplexMatrix(rows, cols)

    @staticmethod
    def from_real(array2d: Sequence[Sequence[float]]) -> "ComplexMatrix":
        rows = len(array2d)
        cols = len(array2d[0]) if rows > 0 else 0
        data = [[Complex(float(v), 0.0) for v in row] for row in array2d]
        return ComplexMatrix(rows, cols, data)

    @staticmethod
    def diagonal(diag: Sequence[Complex]) -> "ComplexMatrix":
        n = len(diag)
        m = ComplexMatrix(n, n)
        for i in range(n):
            m.data[i][i] = diag[i]
        return m

    def get(self, r: int, c: int) -> Complex:
        return self.data[r][c]

    def set(self, r: int, c: int, val: Complex) -> None:
        self.data[r][c] = val

    def add(self, other: "ComplexMatrix") -> "ComplexMatrix":
        if self.rows != other.rows or self.cols != other.cols:
            raise ValueError(
                f"Matrix dimension mismatch: ({self.rows}x{self.cols}) vs ({other.rows}x{other.cols})"
            )
        res = ComplexMatrix(self.rows, self.cols)
        for r in range(self.rows):
            for c in range(self.cols):
                res.data[r][c] = self.data[r][c].add(other.data[r][c])
        return res

    def sub(self, other: "ComplexMatrix") -> "ComplexMatrix":
        if self.rows != other.rows or self.cols != other.cols:
            raise ValueError(
                f"Matrix dimension mismatch: ({self.rows}x{self.cols}) vs ({other.rows}x{other.cols})"
            )
        res = ComplexMatrix(self.rows, self.cols)
        for r in range(self.rows):
            for c in range(self.cols):
                res.data[r][c] = self.data[r][c].sub(other.data[r][c])
        return res

    def scale(self, scalar: "Complex | float") -> "ComplexMatrix":
        s = scalar if isinstance(scalar, Complex) else Complex(scalar, 0.0)
        res = ComplexMatrix(self.rows, self.cols)
        for r in range(self.rows):
            for c in range(self.cols):
                res.data[r][c] = self.data[r][c].mul(s)
        return res

    def matmul(self, other: "ComplexMatrix") -> "ComplexMatrix":
        if self.cols != other.rows:
            raise ValueError(
                f"Matrix multiplication shape mismatch: ({self.rows}x{self.cols}) * ({other.rows}x{other.cols})"
            )
        res = ComplexMatrix(self.rows, other.cols)
        for r in range(self.rows):
            for c in range(other.cols):
                s = Complex.ZERO
                for k in range(self.cols):
                    s = s.add(self.data[r][k].mul(other.data[k][c]))
                res.data[r][c] = s
        return res

    def apply(self, vec: Sequence[Complex]) -> List[Complex]:
        """Matrix-vector product: M |v⟩."""
        if self.cols != len(vec):
            raise ValueError(
                f"Vector dimension mismatch: matrix cols {self.cols} vs vec len {len(vec)}"
            )
        res: List[Complex] = [Complex.ZERO] * self.rows
        for r in range(self.rows):
            s = Complex.ZERO
            for c in range(self.cols):
                s = s.add(self.data[r][c].mul(vec[c]))
            res[r] = s
        return res

    def dagger(self) -> "ComplexMatrix":
        """Conjugate transpose (Hermitian adjoint) M†."""
        res = ComplexMatrix(self.cols, self.rows)
        for r in range(self.rows):
            for c in range(self.cols):
                res.data[c][r] = self.data[r][c].conj()
        return res

    def trace(self) -> Complex:
        if self.rows != self.cols:
            raise ValueError("Trace requires square matrix")
        s = Complex.ZERO
        for i in range(self.rows):
            s = s.add(self.data[i][i])
        return s

    def tensor(self, other: "ComplexMatrix") -> "ComplexMatrix":
        """Kronecker product A ⊗ B."""
        r_out = self.rows * other.rows
        c_out = self.cols * other.cols
        res = ComplexMatrix(r_out, c_out)
        for r1 in range(self.rows):
            for c1 in range(self.cols):
                v1 = self.data[r1][c1]
                for r2 in range(other.rows):
                    for c2 in range(other.cols):
                        res.data[r1 * other.rows + r2][c1 * other.cols + c2] = v1.mul(
                            other.data[r2][c2]
                        )
        return res

    def is_unitary(self, tol: float = 1e-10) -> Tuple[bool, float]:
        if self.rows != self.cols:
            return (False, float("inf"))
        prod = self.matmul(self.dagger())
        max_err = 0.0
        for r in range(self.rows):
            for c in range(self.cols):
                expected = 1.0 if r == c else 0.0
                diff = math.hypot(prod.data[r][c].re - expected, prod.data[r][c].im)
                if diff > max_err:
                    max_err = diff
        return (max_err <= tol, max_err)

    def is_hermitian(self, tol: float = 1e-10) -> Tuple[bool, float]:
        if self.rows != self.cols:
            return (False, float("inf"))
        max_err = 0.0
        for r in range(self.rows):
            for c in range(self.cols):
                diff = math.hypot(
                    self.data[r][c].re - self.data[c][r].re,
                    self.data[r][c].im + self.data[c][r].im,
                )
                if diff > max_err:
                    max_err = diff
        return (max_err <= tol, max_err)

    @staticmethod
    def matrix_exp_unitary(H: "ComplexMatrix", t: float, max_terms: int = 30) -> "ComplexMatrix":
        """Matrix exponential exp(-i * H * t) via scaling-and-squaring + Taylor series.

        For finite-dimensional Hermitian H, exp(-iHt) is unitary. The Taylor
        series converges unconditionally, but for large ||Ht|| it needs many
        terms. We use scaling-and-squaring: compute exp(A / 2^s) via Taylor
        (fast convergence when ||A/2^s|| < 1), then square the result s times.
        This preserves unitarity at each step and keeps the Taylor series
        well-conditioned.
        """
        if H.rows != H.cols:
            raise ValueError("Matrix exponentiation requires square matrix")
        n = H.rows
        A = ComplexMatrix(n, n)
        for r in range(n):
            for c in range(n):
                # -i * (re + i*im) = im - i*re
                A.data[r][c] = Complex(t * H.data[r][c].im, -t * H.data[r][c].re)

        # Scaling: choose s so that ||A / 2^s|| < 0.5
        a_norm = A.frobenius_norm()
        if a_norm == 0.0:
            return ComplexMatrix.identity(n)
        s = 0
        scaled = a_norm
        while scaled > 0.5 and s < 50:
            scaled /= 2.0
            s += 1
        scale_factor = 1.0 / (2**s)
        A_scaled = A.scale(scale_factor)

        # Taylor series on the scaled matrix (converges fast for ||A_scaled|| < 0.5)
        result = ComplexMatrix.identity(n)
        term = ComplexMatrix.identity(n)
        for k in range(1, max_terms + 1):
            term = term.matmul(A_scaled).scale(1.0 / k)
            result = result.add(term)
            term_norm = 0.0
            for r in range(n):
                for c in range(n):
                    term_norm += term.data[r][c].abs2()
            if math.sqrt(term_norm) < 1e-15:
                break

        # Squaring: result = result^s (each squaring preserves unitarity)
        for _ in range(s):
            result = result.matmul(result)

        return result

    def frobenius_norm(self) -> float:
        s = 0.0
        for r in range(self.rows):
            for c in range(self.cols):
                s += self.data[r][c].abs2()
        return math.sqrt(s)


# ---------------------------------------------------------------------------
# 2. HILBERT SPACE & QUANTUM STATE (H_n = C^(2^n))
# ---------------------------------------------------------------------------


class QuantumState:
    """Quantum state |ψ⟩ in Hilbert space H_n = C^(dim).

    Mirrors ``QuantumState`` from ``first_principles_quantum.ts``.
    Amplitudes are exact complex numbers; the state is normalized on
    construction when ``normalize=True``.
    """

    __slots__ = ("dim", "amplitudes")

    def __init__(
        self,
        dim: int,
        amplitudes: Optional[Sequence[Complex]] = None,
        normalize: bool = False,
    ) -> None:
        self.dim = dim
        if amplitudes is not None:
            if len(amplitudes) != dim:
                raise ValueError(
                    f"State amplitude dimension mismatch: expected {dim}, got {len(amplitudes)}"
                )
            self.amplitudes = list(amplitudes)
        else:
            self.amplitudes = [Complex.ONE if i == 0 else Complex.ZERO for i in range(dim)]
        if normalize:
            n = self.norm()
            if n == 0:
                raise ValueError("Cannot normalize null vector in Hilbert space")
            self.amplitudes = [a.div(n) for a in self.amplitudes]

    @staticmethod
    def from_basis(dim: int, basis_index: int) -> "QuantumState":
        amps = [Complex.ONE if i == basis_index else Complex.ZERO for i in range(dim)]
        return QuantumState(dim, amps)

    @staticmethod
    def uniform_superposition(dim: int) -> "QuantumState":
        inv_sqrt = 1.0 / math.sqrt(dim)
        amp = Complex(inv_sqrt, 0.0)
        return QuantumState(dim, [amp] * dim)

    @staticmethod
    def from_real_vector(values: Sequence[float], normalize: bool = True) -> "QuantumState":
        """Construct a quantum state from a real-valued data vector.

        This is the bridge from classical data to quantum state: each
        data point becomes an amplitude. The state is normalized so the
        Born rule probabilities sum to 1.
        """
        amps = [Complex(float(v), 0.0) for v in values]
        return QuantumState(len(amps), amps, normalize=normalize)

    @staticmethod
    def from_exact_state(state) -> "QuantumState":
        """Embed an ``kellogg.exact_tensor.ExactStateVector`` here.

        Explicit one-way boundary: exact F4 amplitudes project to IEEE-754
        complex values. The projection cannot be promoted back into exact
        amplitudes — certificates and authority data stay in
        ``kellogg.exact_tensor``.
        """
        sqrt2 = math.sqrt(2.0)
        amps = [
            Complex(
                float(a.a) + float(a.b) * sqrt2,
                float(a.c) + float(a.d) * sqrt2,
            )
            for a in state.amplitudes
        ]
        return QuantumState(len(amps), amps)

    def norm(self) -> float:
        s = 0.0
        for a in self.amplitudes:
            s += a.abs2()
        return math.sqrt(s)

    def normalize(self) -> "QuantumState":
        n = self.norm()
        if n == 0:
            raise ValueError("Cannot normalize null vector in Hilbert space")
        return QuantumState(self.dim, [a.div(n) for a in self.amplitudes])

    def inner(self, other: "QuantumState") -> Complex:
        """⟨other | this⟩ = Σ other_i* · this_i"""
        if self.dim != other.dim:
            raise ValueError("Hilbert space dimension mismatch in inner product")
        s = Complex.ZERO
        for i in range(self.dim):
            s = s.add(other.amplitudes[i].conj().mul(self.amplitudes[i]))
        return s

    def probabilities(self) -> List[float]:
        """Born rule: Pr(i) = |α_i|²."""
        return [a.abs2() for a in self.amplitudes]

    def apply_unitary(self, U: ComplexMatrix) -> "QuantumState":
        """Schrödinger evolution: |ψ'⟩ = U |ψ⟩."""
        if U.rows != self.dim or U.cols != self.dim:
            raise ValueError(
                f"Unitary dimension ({U.rows}x{U.cols}) incompatible with state dim {self.dim}"
            )
        return QuantumState(self.dim, U.apply(self.amplitudes))

    def tensor(self, other: "QuantumState") -> "QuantumState":
        """|this⟩ ⊗ |other⟩"""
        out_dim = self.dim * other.dim
        out: List[Complex] = [Complex.ZERO] * out_dim
        for i in range(self.dim):
            for j in range(other.dim):
                out[i * other.dim + j] = self.amplitudes[i].mul(other.amplitudes[j])
        return QuantumState(out_dim, out)

    def expectation(self, observable: ComplexMatrix) -> float:
        """⟨ψ | A | ψ⟩ — expectation value of observable A."""
        transformed = observable.apply(self.amplitudes)
        s = Complex.ZERO
        for i in range(self.dim):
            s = s.add(self.amplitudes[i].conj().mul(transformed[i]))
        return s.re

    def measure_born(self, rng) -> Tuple[int, float, "QuantumState"]:
        """Born-rule measurement with an explicit caller-seeded PRNG.

        Returns (outcome, probability, collapsed state). p_i = |α_i|²
        forms the cumulative distribution; ``rng.random()`` supplies the
        draw. This is the one place measurement meets a random threshold —
        use :meth:`measure_pvm` for the deterministic selector.
        """
        probs = self.probabilities()
        draw = float(rng.random())
        cumulative = 0.0
        selected = len(probs) - 1
        for i, p in enumerate(probs):
            cumulative += p
            if draw < cumulative:
                selected = i
                break
        post = [Complex.ONE if i == selected else Complex.ZERO for i in range(self.dim)]
        return (selected, probs[selected], QuantumState(self.dim, post))

    def measure_pvm(self, random_seed: Optional[float] = None) -> Tuple[int, float, "QuantumState"]:
        """Deterministic collapse onto the maximum Born-weight outcome.

        Returns (outcome, probability, post-measurement collapsed state).

        Without ``random_seed`` this selects argmax_i |α_i|² — a
        deterministic selector, not a Born-rule sample. For actual
        Born-distributed sampling pass a seeded PRNG to
        :meth:`measure_born`; ``random_seed`` here is retained as an
        explicit CDF threshold for reproducing measurement sequences.
        """
        probs = self.probabilities()
        if random_seed is not None:
            # The seed is a CDF threshold, not a PRNG initializer: it must lie
            # in [0, 1). Anything outside silently pinned the outcome to a
            # boundary state — fail closed instead. The strict `<` keeps this
            # consistent with measure_born at the p=0 boundary.
            r = float(random_seed)
            if not 0.0 <= r < 1.0:
                raise ValueError("measure_pvm random_seed must be a CDF threshold in [0, 1)")
            cumulative = 0.0
            selected = len(probs) - 1
            for i in range(len(probs)):
                cumulative += probs[i]
                if r < cumulative:
                    selected = i
                    break
        else:
            # Deterministic: select the outcome with the highest Born
            # probability. This is the maximum-likelihood outcome — the
            # quantum state's own structure determines the collapse.
            selected = 0
            max_prob = 0.0
            for i in range(len(probs)):
                if probs[i] > max_prob:
                    max_prob = probs[i]
                    selected = i
        post_amps = [Complex.ONE if i == selected else Complex.ZERO for i in range(self.dim)]
        return (selected, probs[selected], QuantumState(self.dim, post_amps))

    def density_matrix(self) -> ComplexMatrix:
        """ρ = |ψ⟩⟨ψ| — pure-state density matrix."""
        m = ComplexMatrix(self.dim, self.dim)
        for r in range(self.dim):
            for c in range(self.dim):
                m.data[r][c] = self.amplitudes[r].mul(self.amplitudes[c].conj())
        return m

    def to_exact_state(self):
        """Forbidden direction: float amplitudes cannot enter the exact plane."""
        raise IrreversibleBoundary(
            "float -> exact is not a permitted crossing; exact states are "
            "constructed in kellogg.exact_tensor and project to float via "
            "QuantumState.from_exact_state only"
        )

    def purity(self) -> float:
        """Tr(ρ²) — density matrix purity. 1.0 for pure states."""
        rho = self.density_matrix()
        rho2 = rho.matmul(rho)
        return rho2.trace().re

    def von_neumann_entropy(self) -> float:
        """S = -Tr(ρ log₂ ρ) for this state's own density operator.

        A QuantumState is a ray — ρ = |ψ⟩⟨ψ| is pure, so S(ρ) = 0 exactly.
        The Shannon entropy of the Born distribution is a different
        quantity; use :meth:`measurement_entropy` for that. For entropy of
        a *mixed* density operator (e.g. a reduced state), call the
        module-level ``von_neumann_entropy(rho)``.
        """
        return 0.0

    def measurement_entropy(self) -> float:
        """Shannon entropy H(p) of the Born distribution in bits.

        This is the classical spread of the computational-basis
        measurement outcomes — a diagnostic, not S(ρ). DECLARED float.
        """
        s = 0.0
        for p in self.probabilities():
            if p > 1e-15:
                s -= p * math.log2(p)
        return s

    def fidelity(self, other: "QuantumState") -> float:
        """F = |⟨ψ | φ⟩|² — quantum fidelity between two pure states."""
        return self.inner(other).abs2()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "dim": self.dim,
            "amplitudes": [(a.re, a.im) for a in self.amplitudes],
            "norm": self.norm(),
            "probabilities": self.probabilities(),
        }


class IrreversibleBoundary(Exception):
    """Float plane may not be promoted into the exact F4 plane."""


def float_to_exact(state: QuantumState):
    """There is no float -> exact bridge. This always raises."""
    raise IrreversibleBoundary(
        "float amplitudes carry no certificate of exactness; construct the "
        "state in kellogg.exact_tensor instead"
    )


def partial_trace(
    rho: ComplexMatrix, subsystem_dims: Sequence[int], keep: Sequence[int]
) -> ComplexMatrix:
    """True partial trace rho_A = Tr_B(rho) over Kronecker-ordered subsystems.

    ``subsystem_dims`` lists the local dimensions in tensor order; ``keep``
    is the sorted subset of subsystem indices retained. This operates on
    the full density operator — no diagonal shortcuts (Law 4.2).
    """
    dims = [int(d) for d in subsystem_dims]
    total = 1
    for d in dims:
        if d < 1:
            raise ValueError("subsystem dims must be positive")
        total *= d
    if rho.rows != total or rho.cols != total:
        raise ValueError("density matrix dimension does not match subsystem dims")
    keep = tuple(sorted({int(k) for k in keep}))
    if not keep or any(k < 0 or k >= len(dims) for k in keep):
        raise ValueError("keep must be a nonempty subset of subsystem indices")
    traced = [k for k in range(len(dims)) if k not in keep]
    dk = 1
    for k in keep:
        dk *= dims[k]
    out = ComplexMatrix.zero(dk, dk)

    # Mixed-radix index bookkeeping: basis index i decomposes as
    # i = sum_j digit_j * stride_j over the subsystem dims.
    strides = [1] * len(dims)
    for j in range(1, len(dims)):
        strides[j] = strides[j - 1] * dims[j - 1]

    def _split(index: int) -> Tuple[int, int]:
        k_idx = t_idx = 0
        for j, stride in enumerate(strides):
            digit = (index // stride) % dims[j]
            if j in keep:
                k_idx += digit * _k_stride[keep.index(j)]
            else:
                t_idx += digit * _t_stride[traced.index(j)]
        return k_idx, t_idx

    _k_stride = [1] * len(keep)
    for j in range(1, len(keep)):
        _k_stride[j] = _k_stride[j - 1] * dims[keep[j - 1]]
    _t_stride = [1] * len(traced)
    for j in range(1, len(traced)):
        _t_stride[j] = _t_stride[j - 1] * dims[traced[j - 1]]

    for a in range(total):
        ka, ta = _split(a)
        for b in range(total):
            kb, tb = _split(b)
            if ta == tb:
                out.data[ka][kb] = out.data[ka][kb].add(rho.data[a][b])
    return out


def von_neumann_entropy(rho: ComplexMatrix, *, tol: float = 1e-10) -> float:
    """S(rho) = -Tr(rho log2 rho) on a full density operator.

    DECLARED FLOAT BOUNDARY: rho's eigenvalues are obtained by Jacobi
    iteration on the real-symmetric embedding [[Re, -Im],[Im, Re]] (each
    eigenvalue appears twice; pairs are averaged). Logarithms are
    transcendental — this is the one place LAYER 4 emits floats.
    """
    from .exact_tensor import _jacobi_eigenvalues_real

    if rho.rows != rho.cols:
        raise ValueError("density operator must be square")
    n = rho.rows
    embed = [[0.0] * (2 * n) for _ in range(2 * n)]
    for r in range(n):
        for c in range(n):
            z = rho.data[r][c]
            embed[r][c] = z.re
            embed[r + n][c + n] = z.re
            embed[r][c + n] = -z.im
            embed[r + n][c] = z.im
    eig = _jacobi_eigenvalues_real(embed)
    spectrum = [(eig[2 * i] + eig[2 * i + 1]) / 2.0 for i in range(n)]
    entropy = 0.0
    for lam in spectrum:
        if lam < -tol or lam > 1.0 + tol:
            raise ArithmeticError(f"non-physical eigenvalue {lam} in density matrix")
        if lam > tol:
            entropy -= lam * math.log2(lam)
    return entropy


# ---------------------------------------------------------------------------
# 3. QUANTUM OBSERVABLES (Hermitian operators)
# ---------------------------------------------------------------------------


class Observables:
    """Standard quantum observables as Hermitian matrices."""

    @staticmethod
    def position(dim: int) -> ComplexMatrix:
        """Position operator x̂ — diagonal with equally spaced eigenvalues."""
        diag = [Complex(float(i) - dim / 2.0, 0.0) for i in range(dim)]
        return ComplexMatrix.diagonal(diag)

    @staticmethod
    def momentum(dim: int, hbar: float = 1.0) -> ComplexMatrix:
        """Momentum operator p̂ = -iℏ(d/dx) — finite-difference Hermitian approximation."""
        m = ComplexMatrix(dim, dim)
        for i in range(dim):
            for j in range(dim):
                if i == j + 1:
                    m.data[i][j] = Complex(0.0, hbar)
                elif i == j - 1:
                    m.data[i][j] = Complex(0.0, -hbar)
        # Symmetrize for hermiticity
        return m

    @staticmethod
    def harmonic_oscillator_hamiltonian(
        dim: int, hbar: float = 1.0, mass: float = 1.0, omega: float = 1.0
    ) -> ComplexMatrix:
        """H = p²/2m + ½mω²x² — harmonic oscillator Hamiltonian.

        Discretized on a dim-point lattice. This is the same Hamiltonian
        used in toe.engine's volatility and synthetic data generation.
        """
        x = Observables.position(dim)
        p = Observables.momentum(dim, hbar)
        # p² = p · p
        p2 = p.matmul(p)
        # H = p²/(2m) + ½mω²x²
        kinetic = p2.scale(1.0 / (2.0 * mass))
        # x² = x · x
        x2 = x.matmul(x)
        potential = x2.scale(0.5 * mass * omega * omega)
        return kinetic.add(potential)

    @staticmethod
    def number_operator(dim: int, hbar: float = 1.0, omega: float = 1.0) -> ComplexMatrix:
        """n̂ = H/(ℏω) - ½ — number operator for the harmonic oscillator."""
        H = Observables.harmonic_oscillator_hamiltonian(dim, hbar, 1.0, omega)
        n = H.scale(1.0 / (hbar * omega))
        # subtract ½ I
        for i in range(dim):
            n.data[i][i] = n.data[i][i].sub(Complex(0.5, 0.0))
        return n

    @staticmethod
    def family_hamiltonian(family: str, dim: int) -> ComplexMatrix:
        """Hermitian generator from an algebraic family's Pisot companion matrix.

        Embeds the symmetric part H = (M + Mᵀ)/2 of the family's companion
        matrix into the leading d×d block of a dim-dimensional Hilbert
        space (zeros elsewhere), so Schrödinger evolution can run on any
        member of the extended algebraic family — golden, silver, plastic,
        supergolden, or tribonacci.
        """
        from .substrate import family_companion

        M = family_companion(family)
        d = len(M)
        if dim < d:
            raise ValueError(f"dim must be >= {d} for family '{family}'")
        H = ComplexMatrix(dim, dim)
        for i in range(d):
            for j in range(d):
                H.data[i][j] = Complex((M[i][j] + M[j][i]) / 2.0, 0.0)
        return H


# ---------------------------------------------------------------------------
# 4. QUANTUM FISHER INFORMATION
# ---------------------------------------------------------------------------


def quantum_fisher_information(state: QuantumState, observable: ComplexMatrix) -> float:
    """Quantum Fisher information F_Q for a pure state and observable.

    F_Q = 4 (⟨A²⟩ - ⟨A⟩²) = 4 Var(A)

    This sets the Cramér-Rao bound: Var(θ̂) ≥ 1/F_Q.

    The pure-state form is enforced by construction: the substrate only
    represents rays |ψ⟩, so no density-matrix input can silently require
    the mixed-state SLD form F_Q[ρ,A] = 2Σ (λ_i−λ_j)²/(λ_i+λ_j)|⟨i|A|j⟩|².
    Expectations are normalized by ⟨ψ|ψ⟩ so an unnormalized ray still
    yields the correct variance.

    ⟨A²⟩ is evaluated as ⟨ψ|A·(A|ψ⟩) — two O(n²) matvecs instead of the
    O(n³) A·A product — which is valid for any square A, Hermitian or not.
    """
    norm2 = sum(a.abs2() for a in state.amplitudes)
    if norm2 == 0.0:
        return 0.0
    a_psi = observable.apply(state.amplitudes)
    a2_psi = observable.apply(a_psi)
    mean_a = 0.0
    mean_a2 = 0.0
    for i in range(state.dim):
        conj_i = state.amplitudes[i].conj()
        mean_a += conj_i.mul(a_psi[i]).re
        mean_a2 += conj_i.mul(a2_psi[i]).re
    mean_a /= norm2
    mean_a2 /= norm2
    variance = mean_a2 - mean_a * mean_a
    return 4.0 * max(variance, 0.0)


# ---------------------------------------------------------------------------
# 5. 32-FACE DUAL-OVERLAY HILBERT SPACE PROJECTOR
# ---------------------------------------------------------------------------


def dual_overlay_frame() -> List[Tuple[float, float, float]]:
    """The 32-node dual-overlay frame (icosahedron + dodecahedron) on S².

    The 20 dodecahedron vertices are the icosahedron's face centres, so the
    two solids are duals; ``dual_frame_is_dual`` checks it.
    """
    return _pure_python_dual_overlay()


def dual_frame_is_dual(tolerance: float = 1e-12) -> bool:
    """Check that every dodecahedron vertex is an icosahedron face centre."""
    frame = _pure_python_dual_overlay()
    ico, dod = frame[:12], frame[12:]
    edge = min(
        math.dist(ico[i], ico[j]) for i in range(12) for j in range(i + 1, 12)
    )

    def adjacent(i: int, j: int) -> bool:
        return abs(math.dist(ico[i], ico[j]) - edge) < 1e-9

    centres = []
    for i in range(12):
        for j in range(i + 1, 12):
            for k in range(j + 1, 12):
                if adjacent(i, j) and adjacent(j, k) and adjacent(i, k):
                    c = [ico[i][a] + ico[j][a] + ico[k][a] for a in range(3)]
                    norm = math.sqrt(sum(v * v for v in c))
                    centres.append(tuple(v / norm for v in c))
    if len(centres) != 20:
        return False
    return all(
        min(math.dist(vertex, centre) for centre in centres) < tolerance for vertex in dod
    )


def _pure_python_dual_overlay() -> List[Tuple[float, float, float]]:
    """Pure-Python icosahedron + dodecahedron vertices on S²."""
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    inv = 1.0 / math.sqrt(1.0 + phi * phi)

    # Icosahedron (12 vertices)
    ico: List[Tuple[float, float, float]] = [
        (0, inv, phi * inv),
        (0, -inv, phi * inv),
        (0, inv, -phi * inv),
        (0, -inv, -phi * inv),
        (inv, phi * inv, 0),
        (-inv, phi * inv, 0),
        (inv, -phi * inv, 0),
        (-inv, -phi * inv, 0),
        (phi * inv, 0, inv),
        (phi * inv, 0, -inv),
        (-phi * inv, 0, inv),
        (-phi * inv, 0, -inv),
    ]
    # Dodecahedron (20 vertices)
    a = 1.0 / math.sqrt(3.0)
    b = phi / math.sqrt(3.0)
    dod: List[Tuple[float, float, float]] = [
        (a, a, a),
        (a, a, -a),
        (a, -a, a),
        (a, -a, -a),
        (-a, a, a),
        (-a, a, -a),
        (-a, -a, a),
        (-a, -a, -a),
        (0, b, 1.0 / phi * a),
        (0, b, -1.0 / phi * a),
        (0, -b, 1.0 / phi * a),
        (0, -b, -1.0 / phi * a),
        (b, 1.0 / phi * a, 0),
        (b, -1.0 / phi * a, 0),
        (-b, 1.0 / phi * a, 0),
        (-b, -1.0 / phi * a, 0),
        (1.0 / phi * a, 0, b),
        (1.0 / phi * a, 0, -b),
        (-1.0 / phi * a, 0, b),
        (-1.0 / phi * a, 0, -b),
    ]
    return ico + dod


def project_to_32_face(state_3d: Tuple[float, float, float]) -> List[float]:
    """Project a 3D state vector onto the 32-face frame → Born probabilities.

    Returns 32 probabilities summing to 1, where each probability is the
    Born rule projection |⟨face_i | ψ⟩|².
    """
    frame = dual_overlay_frame()
    norm = math.sqrt(sum(x * x for x in state_3d)) + 1e-12
    ns = (state_3d[0] / norm, state_3d[1] / norm, state_3d[2] / norm)
    overlaps = [sum(f[i] * ns[i] for i in range(3)) for f in frame]
    probs = [o * o for o in overlaps]
    total = sum(probs)
    return [p / total for p in probs] if total > 0 else [1.0 / 32.0] * 32


def effective_subspace_dimension(state_3d: Tuple[float, float, float]) -> float:
    """N_eff = 1 / Σ p_i² — effective subspace dimension on the 32-face frame."""
    probs = project_to_32_face(state_3d)
    s = sum(p * p for p in probs)
    return 1.0 / s if s > 0 else 32.0


# ---------------------------------------------------------------------------
# 6. PATH-INTEGRAL TRAJECTORY PROPAGATOR
# ---------------------------------------------------------------------------


def path_integral_propagate(
    state: QuantumState,
    hamiltonian: ComplexMatrix,
    t: float,
    hbar: float = 1.0,
    n_steps: int = 1,
) -> QuantumState:
    """Schrödinger time evolution: |ψ(t)⟩ = exp(-iHt/ℏ) |ψ(0)⟩.

    The path integral K(b,a) = ∫ Dx(t) exp(iS/ℏ) reduces to the matrix
    exponential of the Hamiltonian for finite-dimensional systems. We
    compute it via the exact Taylor series (``matrix_exp_unitary``).

    For long-time evolution, the propagation is split into ``n_steps``
    Trotter steps to improve numerical stability while preserving
    unitarity exactly at each step.
    """
    if n_steps <= 1:
        U = ComplexMatrix.matrix_exp_unitary(hamiltonian, t / hbar)
        return state.apply_unitary(U)
    dt = t / n_steps
    current = state
    for _ in range(n_steps):
        U = ComplexMatrix.matrix_exp_unitary(hamiltonian, dt / hbar)
        current = current.apply_unitary(U)
    return current


def trajectory_forecast(
    state: QuantumState,
    hamiltonian: ComplexMatrix,
    times: Sequence[float],
    hbar: float = 1.0,
) -> List[QuantumState]:
    """Forecast the quantum state at multiple future times.

    Returns a list of states |ψ(t_k)⟩ for each t_k in ``times``.
    """
    return [path_integral_propagate(state, hamiltonian, t, hbar) for t in times]


# ---------------------------------------------------------------------------
# 7. CAUSAL FACTOR ANALYSIS (quantum measurement-theoretic)
# ---------------------------------------------------------------------------


def causal_factor_ranking(
    state: QuantumState,
    factor_observables: Dict[str, ComplexMatrix],
) -> List[Tuple[str, float]]:
    """Rank causal factors by quantum expectation value magnitude.

    Each factor is a Hermitian observable. The ranking is by |⟨A⟩| —
    the absolute expectation value. Factors with larger |⟨A⟩| have
    stronger causal influence on the state.

    This is the quantum-measurement-theoretic "why" analysis: it tells
    you which observables (factors) are most strongly correlated with the
    current state, which is the quantum analogue of causal factor
    importance.
    """
    ranked: List[Tuple[str, float]] = []
    for name, obs in factor_observables.items():
        exp_val = state.expectation(obs)
        ranked.append((name, abs(exp_val)))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def born_probabilities(
    state: QuantumState, factor_names: Optional[Sequence[str]] = None
) -> Dict[str, float]:
    """Born rule probabilities for each basis state.

    Pr(i) = |α_i|². If ``factor_names`` are provided, they label each
    basis state; otherwise generic "basis_0", "basis_1", ... are used.
    """
    probs = state.probabilities()
    if factor_names and len(factor_names) == len(probs):
        return {str(name): float(p) for name, p in zip(factor_names, probs)}
    return {f"basis_{i}": float(p) for i, p in enumerate(probs)}


# ---------------------------------------------------------------------------
# 8. DENSITY-MATRIX COHERENCE & DECOHERENCE
# ---------------------------------------------------------------------------


def density_matrix_purity(state: QuantumState) -> float:
    """Tr(ρ²) — purity. 1.0 = pure (coherent), 1/N = maximally mixed."""
    return state.purity()


def decoherence_measure(state: QuantumState) -> float:
    """1 - Tr(ρ²) — decoherence measure. 0 = pure, (N-1)/N = fully decohered."""
    return 1.0 - state.purity()


def model_agreement_from_ensemble(predictions: Sequence[QuantumState]) -> float:
    """Quantum model agreement from an ensemble of measurement outcomes.

    Treats each prediction as a quantum state and computes the average
    pairwise fidelity. High fidelity = models agree = low decoherence.
    """
    if len(predictions) < 2:
        return 1.0
    total = 0.0
    count = 0
    for i in range(len(predictions)):
        for j in range(i + 1, len(predictions)):
            if predictions[i].dim == predictions[j].dim:
                total += predictions[i].fidelity(predictions[j])
                count += 1
    return total / count if count > 0 else 1.0


# ---------------------------------------------------------------------------
# 9. DATA-TO-STATE ENCODING (sector-agnostic)
# ---------------------------------------------------------------------------


def encode_data_to_state(
    data: Any,
    dim: int = 32,
    normalize: bool = True,
) -> QuantumState:
    """Encode arbitrary data into a quantum state vector.

    This is the sector-agnostic, data-agnostic bridge: common data shapes
    (dict, list, numpy array, bytes, text, scalar) are mapped to a normalized
    quantum state in a ``dim``-dimensional Hilbert space.

    The encoding is deterministic (no random initialization):
    - dict / list / array → deterministic real amplitudes (padded/truncated)
    - bytes → byte values as amplitudes
    - text → UTF-8 byte values as amplitudes
    - scalar → single amplitude (rest zero)
    - None → uniform superposition

    Mapping keys are included in sorted order so two schemas with identical
    values but different field names do not collapse to the same state.
    """
    if data is None:
        return QuantumState.uniform_superposition(dim)

    def flatten(value: Any) -> List[float]:
        if isinstance(value, bool):
            return [1.0 if value else 0.0]
        if isinstance(value, (int, float)):
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("non-finite numeric input")
            return [number]
        if isinstance(value, str):
            return [float(b) for b in value.encode("utf-8")]
        if isinstance(value, (bytes, bytearray)):
            return [float(b) for b in value]
        if isinstance(value, dict):
            result: List[float] = []
            for key in sorted(value, key=lambda item: str(item)):
                result.extend(flatten(str(key)))
                result.extend(flatten(value[key]))
            return result
        if isinstance(value, (list, tuple)):
            result: List[float] = []
            for item in value:
                result.extend(flatten(item))
            return result
        try:
            arr = list(value.flatten()) if hasattr(value, "flatten") else list(value)
        except Exception as exc:
            raise TypeError(f"unsupported TOE input type: {type(value).__name__}") from exc
        return flatten(arr)

    values = flatten(data)
    if not values:
        return QuantumState.uniform_superposition(dim)
    if not any(value != 0.0 for value in values):
        return QuantumState.uniform_superposition(dim)

    # Pad or truncate to dim
    if len(values) < dim:
        values.extend([0.0] * (dim - len(values)))
    elif len(values) > dim:
        values = values[:dim]

    return QuantumState.from_real_vector(values, normalize=normalize)


# ---------------------------------------------------------------------------
# 10. CONVENIENCE: FULL STATE TOMOGRAPHY
# ---------------------------------------------------------------------------


def state_tomography(
    state: QuantumState,
    hbar: float = 1.0,
    mass: float = 1.0,
    omega: float = 1.0,
) -> Dict[str, Any]:
    """Full quantum state tomography — characterize a state by its observables.

    Returns expectation values of:
    - Energy ⟨H⟩ (harmonic oscillator Hamiltonian)
    - Momentum ⟨p⟩
    - Position ⟨x⟩
    - Number ⟨n̂⟩
    - Purity Tr(ρ²)
    - von Neumann entropy S
    - Fisher information F_Q (w.r.t. position)
    - Effective subspace dimension N_eff (on 32-face frame)
    """
    dim = state.dim
    H = Observables.harmonic_oscillator_hamiltonian(dim, hbar, mass, omega)
    p = Observables.momentum(dim, hbar)
    x = Observables.position(dim)
    n_op = Observables.number_operator(dim, hbar, omega)

    energy = state.expectation(H)
    momentum = state.expectation(p)
    position = state.expectation(x)
    number = state.expectation(n_op)
    purity = state.purity()
    entropy = state.von_neumann_entropy()  # pure ray -> exactly 0.0
    measurement_entropy = state.measurement_entropy()
    fisher = quantum_fisher_information(state, x)

    # 3D projection for N_eff
    probs = state.probabilities()
    if dim >= 3:
        state_3d = (
            probs[0],
            probs[1] if dim > 1 else 0.0,
            probs[2] if dim > 2 else 0.0,
        )
        n_eff = effective_subspace_dimension(state_3d)
    else:
        n_eff = float(dim)

    return {
        "dim": dim,
        "energy": energy,
        "momentum": momentum,
        "position": position,
        "number": number,
        "purity": purity,
        "von_neumann_entropy": entropy,
        "measurement_entropy": measurement_entropy,
        "fisher_information": fisher,
        "effective_dimension": n_eff,
        "norm": state.norm(),
        "born_probabilities": probs,
    }


__all__ = [
    "Complex",
    "ComplexMatrix",
    "QuantumState",
    "Observables",
    "quantum_fisher_information",
    "dual_overlay_frame",
    "project_to_32_face",
    "effective_subspace_dimension",
    "path_integral_propagate",
    "trajectory_forecast",
    "causal_factor_ranking",
    "born_probabilities",
    "density_matrix_purity",
    "decoherence_measure",
    "model_agreement_from_ensemble",
    "encode_data_to_state",
    "state_tomography",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route: trace(R^n) against L_n, exactly.

    R is the golden transfer matrix. This proves the route is live; it is
    not a per-algorithm cost claim.
    """
    from .scales import lucas
    from .substrate import TRANSFER, int_mat_pow, trace

    tr = trace(int_mat_pow(TRANSFER, n))
    bound = lucas(n)
    return {
        "kernel": "trace_kernel",
        "n": n,
        "trace_Mn": tr,
        "lucas_bound": bound,
        "bound": bound,
        "is_lucas_bounded": abs(tr) <= bound,
        "theorem_proven": False,
        "module": __name__,
    }
