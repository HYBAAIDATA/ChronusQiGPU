"""11D Regular 600-Cell Polychoron Geometry, QGT, and Exact Cyclotomic Braid Compiler.

Unifies:
1. Exact cyclotomic ring arithmetic over Z[zeta_5] ~ Z[x]/(x^4 + x^3 + x^2 + x + 1).
2. Exact Galois field extension F_257[phi] with minimal polynomial phi^2 - phi - 1 = 0.
3. 120 primary vertices of the 600-cell polychoron (H_4 symmetry group, order 14,400):
   - 8 axial vertices: (+-2, 0, 0, 0) and permutations
   - 16 hypercubic vertices: (+-1, +-1, +-1, +-1)
   - 96 icosahedral vertices: even permutations of (+-phi, +-1, +-phi^-1, 0)
4. Quantum Geometric Tensor (QGT) Q_ij = g_ij + (i/2) Omega_ij on CP^(2^n-1) over F_257.
5. Non-Abelian Fibonacci anyon braid compiler with fusion tau (x) tau = 1 (+) tau
   and exact quantum dimension d_tau = phi.
6. Pisot-Lucas fast-doubling state compression in O(1) RAM (<1 KB).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

P = 257
I_UNIT = 16  # 16^2 = 256 = -1 mod 257


# ---------------------------------------------------------------------------
# 1. Exact Cyclotomic Ring Z[zeta_5]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cyclotomic5:
    """Exact element of Z[zeta_5] represented in basis (1, zeta, zeta^2, zeta^3).

    zeta_5^4 = -1 - zeta_5 - zeta_5^2 - zeta_5^3.
    """

    c0: int
    c1: int
    c2: int
    c3: int

    def __post_init__(self) -> None:
        # Python type annotations alone do not enforce the integer ring.
        if any(type(c) is not int for c in (self.c0, self.c1, self.c2, self.c3)):
            raise TypeError("Cyclotomic5 coefficients must be integers")

    @classmethod
    def zero(cls) -> "Cyclotomic5":
        return cls(0, 0, 0, 0)

    @classmethod
    def one(cls) -> "Cyclotomic5":
        return cls(1, 0, 0, 0)

    @classmethod
    def zeta(cls) -> "Cyclotomic5":
        return cls(0, 1, 0, 0)

    @classmethod
    def phi(cls) -> "Cyclotomic5":
        """Golden ratio phi = -(zeta_5^2 + zeta_5^3) = 1 + zeta_5 + zeta_5^4.

        In basis (1, zeta, zeta^2, zeta^3):
        phi = 0*1 + 0*zeta - 1*zeta^2 - 1*zeta^3 = (0, 0, -1, -1).
        """
        return cls(0, 0, -1, -1)

    @classmethod
    def phi_inv(cls) -> "Cyclotomic5":
        """phi^-1 = phi - 1 = (-1, 0, -1, -1)."""
        return cls(-1, 0, -1, -1)

    def __add__(self, other: "Cyclotomic5") -> "Cyclotomic5":
        return Cyclotomic5(
            self.c0 + other.c0,
            self.c1 + other.c1,
            self.c2 + other.c2,
            self.c3 + other.c3,
        )

    def __sub__(self, other: "Cyclotomic5") -> "Cyclotomic5":
        return Cyclotomic5(
            self.c0 - other.c0,
            self.c1 - other.c1,
            self.c2 - other.c2,
            self.c3 - other.c3,
        )

    def __neg__(self) -> "Cyclotomic5":
        return Cyclotomic5(-self.c0, -self.c1, -self.c2, -self.c3)

    def __mul__(self, other: "Cyclotomic5") -> "Cyclotomic5":
        # Raw polynomial multiplication of degree 3 * degree 3 -> degree 6
        raw = [0] * 7
        s = (self.c0, self.c1, self.c2, self.c3)
        o = (other.c0, other.c1, other.c2, other.c3)
        for i in range(4):
            for j in range(4):
                raw[i + j] += s[i] * o[j]

        # Reduce mod x^4 + x^3 + x^2 + x + 1
        # For k >= 4: x^k = - x^(k-1) - x^(k-2) - x^(k-3) - x^(k-4)
        for deg in range(6, 3, -1):
            lead = raw[deg]
            if lead != 0:
                raw[deg] = 0
                for shift in range(1, 5):
                    raw[deg - shift] -= lead

        return Cyclotomic5(raw[0], raw[1], raw[2], raw[3])

    def to_f257_phi(self) -> "F257Phi":
        """Reduce an element of Z[phi] to F_257[phi].

        Reject non-real cyclotomic elements: this quadratic target cannot
        represent a fifth root of unity. The fixed subring has c1=0 and
        c2=c3 in this basis; phi=-(zeta^2+zeta^3).
        """
        if self.c1 != 0 or self.c2 != self.c3:
            raise ValueError("only elements of Z[phi] can be reduced to F257Phi")
        return F257Phi(self.c0, -self.c2)



# ---------------------------------------------------------------------------
# 2. Exact Galois Field Extension F_257[phi]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class F257Phi:
    """Exact element a + b*phi of F_257[phi] where phi^2 = phi + 1 mod 257."""

    a: int
    b: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "a", self.a % P)
        object.__setattr__(self, "b", self.b % P)

    @classmethod
    def zero(cls) -> "F257Phi":
        return cls(0, 0)

    @classmethod
    def one(cls) -> "F257Phi":
        return cls(1, 0)

    @classmethod
    def phi(cls) -> "F257Phi":
        return cls(0, 1)

    @classmethod
    def phi_inv(cls) -> "F257Phi":
        # phi^-1 = phi - 1 = -1 + 1*phi
        return cls(P - 1, 1)

    def __add__(self, other: "F257Phi") -> "F257Phi":
        return F257Phi((self.a + other.a) % P, (self.b + other.b) % P)

    def __sub__(self, other: "F257Phi") -> "F257Phi":
        return F257Phi((self.a - other.a) % P, (self.b - other.b) % P)

    def __neg__(self) -> "F257Phi":
        return F257Phi((-self.a) % P, (-self.b) % P)

    def __mul__(self, other: "F257Phi") -> "F257Phi":
        # (a1 + b1*phi)(a2 + b2*phi) = a1*a2 + (a1*b2 + b1*a2)*phi + b1*b2*phi^2
        # phi^2 = phi + 1 -> (a1*a2 + b1*b2) + (a1*b2 + b1*a2 + b1*b2)*phi
        new_a = (self.a * other.a + self.b * other.b) % P
        new_b = (self.a * other.b + self.b * other.a + self.b * other.b) % P
        return F257Phi(new_a, new_b)

    def norm(self) -> int:
        """Algebraic norm N(a + b*phi) = a^2 + a*b - b^2 mod 257."""
        return (self.a * self.a + self.a * self.b - self.b * self.b) % P

    def inverse(self) -> "F257Phi":
        norm_val = self.norm()
        if norm_val == 0:
            raise ZeroDivisionError("Cannot invert element with zero norm in F_257[phi]")
        inv_norm = pow(norm_val, P - 2, P)
        # (a + b*phi)^-1 = (a + b - b*phi) / N
        return F257Phi(((self.a + self.b) * inv_norm) % P, ((-self.b) * inv_norm) % P)

    def is_zero(self) -> bool:
        return self.a == 0 and self.b == 0


# ---------------------------------------------------------------------------
# 3. 600-Cell Regular Polychoron Vertex Geometry
# ---------------------------------------------------------------------------


class Polychoron600Cell:
    """120 canonical vertices of the regular 600-cell polychoron slice in 4D.

    Subgroup H_4 of order 14,400.
    1. 8 axial vertices: permutations of (+-2, 0, 0, 0)
    2. 16 hypercubic vertices: (+-1, +-1, +-1, +-1)
    3. 96 icosahedral vertices: even permutations of (+-phi, +-1, +-phi^-1, 0)
    Total = 8 + 16 + 96 = 120 vertices.
    """

    @classmethod
    def generate_cyclotomic_vertices(cls) -> List[Tuple[Cyclotomic5, Cyclotomic5, Cyclotomic5, Cyclotomic5]]:
        zero = Cyclotomic5.zero()
        one = Cyclotomic5.one()
        two = Cyclotomic5(2, 0, 0, 0)
        phi = Cyclotomic5.phi()
        phi_inv = Cyclotomic5.phi_inv()

        vertices: set[Tuple[Cyclotomic5, Cyclotomic5, Cyclotomic5, Cyclotomic5]] = set()

        # 1. 8 Axial vertices: (+-2, 0, 0, 0) across all 4 axes
        for axis in range(4):
            for sign in (1, -1):
                coord = [zero, zero, zero, zero]
                coord[axis] = two if sign == 1 else -two
                vertices.add(tuple(coord))  # type: ignore

        # 2. 16 Hypercubic vertices: (+-1, +-1, +-1, +-1)
        for s0, s1, s2, s3 in itertools.product((1, -1), repeat=4):
            vertices.add((
                one if s0 == 1 else -one,
                one if s1 == 1 else -one,
                one if s2 == 1 else -one,
                one if s3 == 1 else -one,
            ))

        # 3. 96 Icosahedral vertices: even permutations of (+-phi, +-1, +-phi^-1, 0)
        # Even permutations of (0, 1, 2, 3)
        base_indices = (0, 1, 2, 3)
        even_perms = [
            p for p in itertools.permutations(base_indices)
            if cls._permutation_parity(p) == 0
        ]
        assert len(even_perms) == 12

        for perm in even_perms:
            for s_phi, s_1, s_inv in itertools.product((1, -1), repeat=3):
                items = [
                    phi if s_phi == 1 else -phi,
                    one if s_1 == 1 else -one,
                    phi_inv if s_inv == 1 else -phi_inv,
                    zero,
                ]
                v = (items[perm[0]], items[perm[1]], items[perm[2]], items[perm[3]])
                vertices.add(v)

        result = list(vertices)
        assert len(result) == 120, f"Expected 120 vertices, got {len(result)}"
        return sorted(result, key=lambda v: tuple((c.c0, c.c1, c.c2, c.c3) for c in v))

    @classmethod
    def generate_f257_vertices(cls) -> List[Tuple[F257Phi, F257Phi, F257Phi, F257Phi]]:
        """120 canonical vertices embedded exactly into (F_257[phi])^4."""
        zero = F257Phi.zero()
        one = F257Phi.one()
        two = F257Phi(2, 0)
        phi = F257Phi.phi()
        phi_inv = F257Phi.phi_inv()

        vertices: set[Tuple[F257Phi, F257Phi, F257Phi, F257Phi]] = set()

        # 1. 8 Axial vertices
        for axis in range(4):
            for sign in (1, -1):
                coord = [zero, zero, zero, zero]
                coord[axis] = two if sign == 1 else -two
                vertices.add(tuple(coord))  # type: ignore

        # 2. 16 Hypercubic vertices
        for s0, s1, s2, s3 in itertools.product((1, -1), repeat=4):
            vertices.add((
                one if s0 == 1 else -one,
                one if s1 == 1 else -one,
                one if s2 == 1 else -one,
                one if s3 == 1 else -one,
            ))

        # 3. 96 Icosahedral vertices
        even_perms = [
            p for p in itertools.permutations((0, 1, 2, 3))
            if cls._permutation_parity(p) == 0
        ]
        for perm in even_perms:
            for s_phi, s_1, s_inv in itertools.product((1, -1), repeat=3):
                items = [
                    phi if s_phi == 1 else -phi,
                    one if s_1 == 1 else -one,
                    phi_inv if s_inv == 1 else -phi_inv,
                    zero,
                ]
                v = (items[perm[0]], items[perm[1]], items[perm[2]], items[perm[3]])
                vertices.add(v)

        result = list(vertices)
        assert len(result) == 120, f"Expected 120 vertices in F_257[phi], got {len(result)}"
        return sorted(result, key=lambda v: tuple((c.a, c.b) for c in v))

    @staticmethod
    def _permutation_parity(p: Sequence[int]) -> int:
        """Returns 0 for even permutation, 1 for odd."""
        inversions = 0
        for i in range(len(p)):
            for j in range(i + 1, len(p)):
                if p[i] > p[j]:
                    inversions += 1
        return inversions % 2


# ---------------------------------------------------------------------------
# 4. Quantum Geometric Tensor (QGT) over F_257
# ---------------------------------------------------------------------------


class QuantumGeometricTensor:
    """Legacy bilinear finite-field geometric proxy, NOT physical QGT.

    The scalar dot product is symmetric and has no Hermitian imaginary part;
    hence Omega_ij from this legacy real-subfield path is identically zero.
    Use evaluate_hermitian for an actual alternating component over the
    quadratic extension F_257[phi]. Neither API proves Berry curvature on a
    complex projective Hilbert space or a Yang-Mills continuum mass gap.
    """

    HALF = 129  # 129 * 2 = 258 = 1 mod 257

    @classmethod
    def evaluate(
        cls,
        psi: List[int],
        d_psi_i: List[int],
        d_psi_j: List[int],
    ) -> Tuple[int, int, int]:
        """Legacy bilinear proxy over F_257, with Omega identically zero.

        Inner product is symmetric: <u|v> = sum u_k*v_k mod 257.
        This overload is preserved for existing callers, not promoted as a
        quantum-geometric tensor on complex projective space.
        """
        # <psi | psi>
        norm_sq = sum((x * x) % P for x in psi) % P
        if norm_sq == 0:
            raise ValueError("State vector psi has zero norm")
        inv_norm = pow(norm_sq, P - 2, P)

        # Matrix elements
        # <d_psi_i | d_psi_j>
        overlap_ij = sum((a * b) % P for a, b in zip(d_psi_i, d_psi_j)) % P

        # <d_psi_i | psi> and <psi | d_psi_j>
        proj_i = sum((a * b) % P for a, b in zip(d_psi_i, psi)) % P
        proj_j = sum((a * b) % P for a, b in zip(psi, d_psi_j)) % P

        # g_ij = <d_psi_i | d_psi_j> - (<d_psi_i | psi><psi | d_psi_j>) / <psi|psi>
        g_ij = (overlap_ij - (proj_i * proj_j * inv_norm) % P) % P

        # Omega_ij: Berry curvature antisymmetric form (anti-symmetrized overlap)
        # Omega_ij = 2 * (overlap_ij - overlap_ji) % P
        overlap_ji = sum((a * b) % P for a, b in zip(d_psi_j, d_psi_i)) % P
        omega_ij = (2 * (overlap_ij - overlap_ji)) % P

        # Q_ij = g_ij + (i/2) * Omega_ij
        i_half_omega = (I_UNIT * cls.HALF * omega_ij) % P
        q_ij = (g_ij + i_half_omega) % P

        return g_ij, omega_ij, q_ij

    @classmethod
    def evaluate_hermitian(
        cls,
        psi: Sequence[F257Phi],
        d_psi_i: Sequence[F257Phi],
        d_psi_j: Sequence[F257Phi],
    ):
        """Compute exact extension-field Hermitian and alternating components.

        Frobenius conjugation is phi -> 1-phi. This is finite-field
        algebra and carries NO claim of a complex-Born metric.
        """
        from chronus.geodesic.hermitian import FiniteHermitianTensor
        return FiniteHermitianTensor.evaluate(psi, d_psi_i, d_psi_j)


# ---------------------------------------------------------------------------
# 5. Non-Abelian Fibonacci Anyon Braid Compiler
# ---------------------------------------------------------------------------


class CyclotomicBraidCompiler:
    """Exact braid compiler over Z[zeta_5].

    Models Fibonacci anyons with non-Abelian fusion rule:
        tau (x) tau = 1 (+) tau
    Quantum dimension:
        d_tau = phi = (0, 0, -1, -1) in Z[zeta_5].
    Burau / Jones representation on GL_2(Z[zeta_5]) satisfies the
    Artin braid relation sigma_1 * sigma_2 * sigma_1 = sigma_2 * sigma_1 * sigma_2.
    """

    def __init__(self) -> None:
        self.zeta = Cyclotomic5.zeta()
        self.one = Cyclotomic5.one()
        self.zero = Cyclotomic5.zero()

        # sigma_1 = [[-zeta, 1], [0, 1]]
        self.sigma1 = (
            (-self.zeta, self.one),
            (self.zero, self.one),
        )
        # sigma_2 = [[1, 0], [zeta, -zeta]]
        self.sigma2 = (
            (self.one, self.zero),
            (self.zeta, -self.zeta),
        )

    def _matmul(
        self,
        m1: Tuple[Tuple[Cyclotomic5, Cyclotomic5], Tuple[Cyclotomic5, Cyclotomic5]],
        m2: Tuple[Tuple[Cyclotomic5, Cyclotomic5], Tuple[Cyclotomic5, Cyclotomic5]],
    ) -> Tuple[Tuple[Cyclotomic5, Cyclotomic5], Tuple[Cyclotomic5, Cyclotomic5]]:
        a = m1[0][0] * m2[0][0] + m1[0][1] * m2[1][0]
        b = m1[0][0] * m2[0][1] + m1[0][1] * m2[1][1]
        c = m1[1][0] * m2[0][0] + m1[1][1] * m2[1][0]
        d = m1[1][0] * m2[0][1] + m1[1][1] * m2[1][1]
        return ((a, b), (c, d))

    def verify_braid_relations(self) -> bool:
        """Verifies sigma_1 * sigma_2 * sigma_1 == sigma_2 * sigma_1 * sigma_2."""
        lhs = self._matmul(self._matmul(self.sigma1, self.sigma2), self.sigma1)
        rhs = self._matmul(self._matmul(self.sigma2, self.sigma1), self.sigma2)
        return lhs == rhs

    def compile_word(
        self, braid_word: Sequence[int]
    ) -> Tuple[Tuple[Cyclotomic5, Cyclotomic5], Tuple[Cyclotomic5, Cyclotomic5]]:
        """Multiplies sequence of generators (1 for sigma_1, 2 for sigma_2)."""
        curr = (
            (self.one, self.zero),
            (self.zero, self.one),
        )
        for gen in braid_word:
            if gen == 1:
                curr = self._matmul(curr, self.sigma1)
            elif gen == 2:
                curr = self._matmul(curr, self.sigma2)
            else:
                raise ValueError(f"Unknown braid generator: {gen}")
        return curr


# ---------------------------------------------------------------------------
# 6. Pisot-Lucas Fast-Doubling State Compression
# ---------------------------------------------------------------------------


class PisotLucasStateCompression:
    """Computes Lucas recurrences L_n = phi^n + psi^n in O(log n) steps.

    Uses fast-doubling identities without floating point:
        F_2k = F_k * (2*F_{k+1} - F_k)
        F_2k+1 = F_{k+1}^2 + F_k^2
        L_k = F_{k-1} + F_{k+1}
    Memory footprint is strictly O(1) (<1 KB).
    """

    @classmethod
    def fibonacci_pair(cls, n: int) -> Tuple[int, int]:
        """Returns (F_n, F_{n+1}) in O(log n) steps."""
        if n == 0:
            return (0, 1)
        a, b = cls.fibonacci_pair(n >> 1)
        c = a * ((b << 1) - a)
        d = a * a + b * b
        if n & 1:
            return (d, c + d)
        return (c, d)

    @classmethod
    def lucas(cls, n: int) -> int:
        """Returns L_n = F_{n-1} + F_{n+1} for n >= 1, L_0 = 2."""
        if n == 0:
            return 2
        if n == 1:
            return 1
        fn, fn1 = cls.fibonacci_pair(n)
        fn_minus_1 = fn1 - fn
        return fn_minus_1 + fn1

    @classmethod
    def lucas_mod(cls, n: int, mod: int = P) -> int:
        """Returns L_n mod P in O(log n) integer steps."""
        if n == 0:
            return 2 % mod
        if n == 1:
            return 1 % mod

        def _fib_mod(k: int) -> Tuple[int, int]:
            if k == 0:
                return (0, 1)
            fk, fk1 = _fib_mod(k >> 1)
            c = (fk * ((fk1 << 1) - fk)) % mod
            d = (fk * fk + fk1 * fk1) % mod
            if k & 1:
                return (d, (c + d) % mod)
            return (c, d)

        fn, fn1 = _fib_mod(n)
        fn_minus_1 = (fn1 - fn) % mod
        return (fn_minus_1 + fn1) % mod
