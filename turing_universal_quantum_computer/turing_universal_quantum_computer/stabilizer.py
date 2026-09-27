"""Exact stabilizer-state backend (Aaronson-Gottesman tableau over GF(2)).

A stabilizer state on n qubits is specified exactly by n independent
commuting Pauli generators plus n destabilizers — O(n^2) bits regardless
of the 2^n Hilbert-space dimension.  This is the mathematically exact
representation that makes n = 10_000 tractable: superposition
(|+>^{otimes n}), entanglement (GHZ, cluster states), interference and
measurement are all exact — no amplitude ever densifies.

Gates supported: H, S (and S-dagger), X, Z, CNOT, CZ, SWAP — the Clifford
group, which is closed under stabilizer evolution.  Applying a non-Clifford
gate (T, arbitrary phase) raises ``StabilizerDomainError`` — fail closed,
never approximate.

Measurement returns exact Born probabilities: a Z-measurement on a
stabilizer state has outcome distribution in { (1,0), (0,1),
(1/2,1/2) } over Fraction — no sampling is required to report it.  When a
definite outcome is needed, ``measure`` applies the canonical collapse
(outcome +1 on degenerate) or accepts an explicit ``outcome``/``seed`` at
the classical boundary — the same convention as ``hilbert.QuantumRegister``
(seeded sampling OF the exact distribution, clearly labelled classical).

Reference: Aaronson & Gottesman, Phys. Rev. A 70, 052328 (2004),
"Improved simulation of stabilizer circuits" — the CHP tableau algorithm.
"""

from __future__ import annotations

from fractions import Fraction
import random
from typing import Iterable, List, Optional, Sequence, Tuple


class StabilizerDomainError(ValueError):
    """Operation outside the Clifford/stabilizer domain — fail closed."""


def _row_str(x: int, z: int, n: int) -> str:
    return "".join(
        "I" if ((x >> q) & 1) == 0 and ((z >> q) & 1) == 0
        else "X" if ((x >> q) & 1) == 1 and ((z >> q) & 1) == 0
        else "Z" if ((x >> q) & 1) == 0 and ((z >> q) & 1) == 1
        else "Y"
        for q in range(n)
    )


class StabilizerState:
    """n-qubit stabilizer state as a CHP tableau.

    Rows 0..n-1 are destabilizers D_i; rows n..2n-1 are stabilizers S_i.
    Each row is (x_bits, z_bits, r) where the Pauli string is
    (-1)^r * prod_j (X^{x_j} Z^{z_j}).  All integers — O(n^2) bits total.
    """

    def __init__(self, n_qubits: int):
        if n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        self.n = int(n_qubits)
        # |0>^n canonical tableau: destabilizers D_i = X_i, stabilizers S_i = Z_i.
        self._x = [0] * (2 * self.n)
        self._z = [0] * (2 * self.n)
        self._r = [0] * (2 * self.n)
        for i in range(self.n):
            self._x[i] = 1 << i           # D_i = X_i
            self._z[self.n + i] = 1 << i  # S_i = Z_i

    # -- exact constructors -------------------------------------------------

    @classmethod
    def basis(cls, n_qubits: int) -> "StabilizerState":
        """|0...0>: stabilizers Z_i."""
        return cls(n_qubits)

    @classmethod
    def plus(cls, n_qubits: int) -> "StabilizerState":
        """|+>^{otimes n}: stabilizers X_i — the full uniform superposition.

        This is the exact 2^n-term equal superposition represented in
        O(n^2) bits — the stabilizer theorem is what makes "superposition
        at n=10000" a well-defined exact object rather than a hand-wave.
        """
        s = cls(n_qubits)
        for i in range(s.n):
            # swap D/S roles: D_i = Z_i, S_i = X_i
            s._x[i], s._z[i] = 0, 1 << i
            s._x[s.n + i], s._z[s.n + i] = 1 << i, 0
        return s

    @classmethod
    def ghz(cls, n_qubits: int) -> "StabilizerState":
        """GHZ_n = (|0^n> + |1^n>)/sqrt(2) — maximal n-party entanglement.

        Stabilizers: S_0 = X^{otimes n}; S_i = Z_{i-1} Z_i (i >= 1).
        Destabilizers: D_0 = Z_0; D_i = prod_{k>=i} X_k, which anticommutes
        with S_i only (it meets Z_{i-1}Z_i at one site, Z_i Z_{i+1} at two).
        """
        s = cls(n_qubits)
        n = s.n
        s._x = [0] * (2 * n)
        s._z = [0] * (2 * n)
        s._r = [0] * (2 * n)
        s._z[0] = 1  # D_0 = Z_0
        suffix_mask = (1 << n) - 1
        for i in range(1, n):
            s._x[i] = suffix_mask & ~((1 << i) - 1)  # D_i = X_i..X_{n-1}
        s._x[n] = (1 << n) - 1  # S_0 = X^{otimes n}
        for i in range(1, n):
            s._z[n + i] = (1 << (i - 1)) | (1 << i)  # S_i = Z_{i-1} Z_i
        return s

    @classmethod
    def cluster_chain(cls, n_qubits: int) -> "StabilizerState":
        """1-D cluster state: stabilizers K_i = Z_{i-1} X_i Z_{i+1}."""
        s = cls(n_qubits)
        n = s.n
        s._x = [0] * (2 * n)
        s._z = [0] * (2 * n)
        s._r = [0] * (2 * n)
        # Graph state: destabilizer D_i = X_i; stabilizer S_i = X_i * prod Z_nbrs.
        for i in range(n):
            s._x[i] = 1 << i
            s._x[n + i] = 1 << i
            if i > 0:
                s._z[n + i] |= 1 << (i - 1)
            if i < n - 1:
                s._z[n + i] |= 1 << (i + 1)
        return s

    # -- tableau row algebra -------------------------------------------------

    @staticmethod
    def _gsum(x1: int, z1: int, x2: int, z2: int) -> int:
        """sum_j g(x1_j,z1_j,x2_j,z2_j) via bit-parallel masks.

        g is the i-exponent when multiplying Pauli row 1 by row 2
        (Aaronson-Gottesman):  I:0;  Y:(z2-x2);  X:z2*(2x2-1);  Z:x2*(1-2z2).
        """
        iy = x1 & z1          # row1 = Y
        ix = x1 & ~z1         # row1 = X
        iz = ~x1 & z1         # row1 = Z
        total = (
            (z2 & iy).bit_count() - (x2 & iy).bit_count()
            + ((ix & x2 & z2).bit_count() - (ix & ~x2 & z2).bit_count())
            + ((iz & x2 & ~z2).bit_count() - (iz & x2 & z2).bit_count())
        )
        return total

    def _rowsum(self, h: int, i: int) -> None:
        """row_h := row_i * row_h (AG Tableau rowsum)."""
        g = self._gsum(self._x[i], self._z[i], self._x[h], self._z[h])
        p = 2 * self._r[i] + 2 * self._r[h] + g
        if p % 4 == 0:
            self._r[h] = 0
        elif p % 4 == 2:
            self._r[h] = 1
        else:
            raise StabilizerDomainError(
                "rowsum produced an imaginary (+-i) Pauli product — "
                "tableau cannot store it"
            )
        self._x[h] ^= self._x[i]
        self._z[h] ^= self._z[i]

    # -- gates (exact Clifford conjugation) ----------------------------------

    def h(self, q: int) -> "StabilizerState":
        """Hadamard: swap X<->Z on qubit q; sign flips where both were set."""
        self._require_qubit(q)
        n = self.n
        for i in range(2 * n):
            xb, zb = (self._x[i] >> q) & 1, (self._z[i] >> q) & 1
            self._r[i] ^= xb & zb
            m = (self._x[i] ^ self._z[i]) & (1 << q)
            self._x[i] ^= m
            self._z[i] ^= m
        return self

    def s(self, q: int) -> "StabilizerState":
        """Phase gate S: Z->Z, X->Y (x XORs into z; sign flips where X*Z)."""
        self._require_qubit(q)
        n = self.n
        for i in range(2 * n):
            xb, zb = (self._x[i] >> q) & 1, (self._z[i] >> q) & 1
            self._r[i] ^= xb & zb
            self._z[i] ^= self._x[i] & (1 << q)
        return self

    def sdg(self, q: int) -> "StabilizerState":
        """S-dagger: X -> -Y (conjugation sends X to -Y)."""
        self._require_qubit(q)
        n = self.n
        for i in range(2 * n):
            xb, zb = (self._x[i] >> q) & 1, (self._z[i] >> q) & 1
            self._r[i] ^= xb & (zb ^ 1)
            self._z[i] ^= self._x[i] & (1 << q)
        return self

    def x(self, q: int) -> "StabilizerState":
        """Pauli X (unitary conjugation): flips sign of Z/Y on qubit q."""
        self._require_qubit(q)
        for i in range(2 * self.n):
            self._r[i] ^= (self._z[i] >> q) & 1
        return self

    def y(self, q: int) -> "StabilizerState":
        """Pauli Y (unitary conjugation): flips sign of X/Z on qubit q."""
        self._require_qubit(q)
        for i in range(2 * self.n):
            self._r[i] ^= ((self._x[i] >> q) & 1) ^ ((self._z[i] >> q) & 1)
        return self

    def z(self, q: int) -> "StabilizerState":
        """Pauli Z (unitary conjugation): flips sign of X/Y on qubit q."""
        self._require_qubit(q)
        for i in range(2 * self.n):
            self._r[i] ^= (self._x[i] >> q) & 1
        return self

    def cnot(self, c: int, t: int) -> "StabilizerState":
        """CNOT control->target: x_t ^= x_c; z_c ^= z_t; phase rule."""
        self._require_qubit(c)
        self._require_qubit(t)
        if c == t:
            raise ValueError("CNOT requires distinct qubits")
        cm, tm = 1 << c, 1 << t
        for i in range(2 * self.n):
            xc, zt = (self._x[i] & cm) != 0, (self._z[i] & tm) != 0
            xt, zc = (self._x[i] & tm) != 0, (self._z[i] & cm) != 0
            self._r[i] ^= xc and zt and (xt ^ zc ^ 1)
            if xc:
                self._x[i] ^= tm
            if zt:
                self._z[i] ^= cm
        return self

    def cz(self, a: int, b: int) -> "StabilizerState":
        """Controlled-Z — via H(b) CNOT(a,b) H(b)."""
        return self.h(b).cnot(a, b).h(b)

    def swap(self, a: int, b: int) -> "StabilizerState":
        """SWAP = CNOT(a,b) CNOT(b,a) CNOT(a,b)."""
        return self.cnot(a, b).cnot(b, a).cnot(a, b)

    def t(self, q: int) -> None:
        """T is non-Clifford — outside the stabilizer domain."""
        raise StabilizerDomainError(
            "T gate is non-Clifford; stabilizer backend cannot represent it "
            "exactly. Use hilbert.QuantumRegister (sparse exact) on bounded "
            "support, or an explicit exact-extension backend."
        )

    def apply_phase_gate(self, q: int, theta) -> None:
        raise StabilizerDomainError(
            "arbitrary phase rotation is non-Clifford; stabilizer backend "
            "fails closed rather than approximate"
        )

    def _require_qubit(self, q: int) -> None:
        if not 0 <= q < self.n:
            raise IndexError(f"qubit {q} out of range [0,{self.n})")

    # -- measurement ---------------------------------------------------------

    def measurement_probabilities(self, q: int) -> Tuple[Fraction, Fraction]:
        """Exact Born distribution of a Z-basis measurement on qubit q.

        Stabilizer measurement theory gives exactly three possibilities:
        deterministic +1 -> (1, 0), deterministic -1 -> (0, 1), or
        maximally random -> (1/2, 1/2).  Returned as exact Fractions.
        """
        self._require_qubit(q)
        for p in range(self.n, 2 * self.n):
            if (self._x[p] >> q) & 1:
                return Fraction(1, 2), Fraction(1, 2)
        # deterministic: outcome sign from destabilizer product
        bit = self._deterministic_outcome(q)
        return (Fraction(0), Fraction(1)) if bit else (Fraction(1), Fraction(0))

    def expectation_z(self, q: int) -> Fraction:
        """<Z_q> in {0, +1, -1} exactly."""
        p0, p1 = self.measurement_probabilities(q)
        return p0 - p1

    def measure(self, q: int, outcome: Optional[int] = None,
                seed: Optional[int] = None) -> dict:
        """Collapse qubit q in the Z basis; returns the exact result record.

        ``outcome`` forces +1/0 or -1/1 (basis value 0 or 1).  If omitted
        and the measurement is degenerate, a seeded draw samples the exact
        (1/2, 1/2) distribution — the seeded RNG is classical sampling OF
        the exact distribution, same boundary as QuantumRegister.measure.
        If neither is given, canonical collapse takes outcome 0.
        """
        self._require_qubit(q)
        n = self.n
        p0, p1 = self.measurement_probabilities(q)
        random_outcome = p0 == p1
        if outcome is None:
            if random_outcome and seed is not None:
                outcome = 1 if random.Random(seed).random() < float(p1) else 0
            else:
                outcome = 0  # canonical deterministic collapse convention
        if outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")

        anticommuting = None
        for p in range(n, 2 * n):
            if (self._x[p] >> q) & 1:
                anticommuting = p
                break
        if anticommuting is not None:
            p = anticommuting
            for i in range(2 * n):
                if i != p and (self._x[i] >> q) & 1:
                    self._rowsum(i, p)
            # Move stabilizer p into destabilizer slot; new stabilizer is Z_q.
            self._x[p - n], self._z[p - n], self._r[p - n] = self._x[p], self._z[p], self._r[p]
            self._x[p], self._z[p], self._r[p] = 0, 1 << q, outcome
        else:
            actual = self._deterministic_outcome(q)
            if outcome != actual:
                # Forcing the impossible outcome is not a collapse — fail.
                raise ValueError(
                    f"deterministic measurement outcome is {actual}; "
                    f"cannot force {outcome}"
                )
        return {
            "qubit": q,
            "outcome": outcome,
            "p0": p0,
            "p1": p1,
            "degenerate": random_outcome,
            "seeded_classical_draw": random_outcome and seed is not None,
        }

    def _deterministic_outcome(self, q: int) -> int:
        """Sign bit of Z_q as a product of stabilizers (AG deterministic case)."""
        n = self.n
        # scratch row = product over stabilizers S_i where D_i anticommutes with Z_q
        sx = sz = 0
        sr = 0
        # emulate a scratch row by reusing _gsum on synthetic ints
        for i in range(n):
            if (self._x[i] >> q) & 1:
                # rowsum(scratch, stabilizer i)
                g = self._gsum(self._x[n + i], self._z[n + i], sx, sz)
                p = 2 * self._r[n + i] + 2 * sr + g
                if p % 4 not in (0, 2):
                    raise StabilizerDomainError(
                        "deterministic measurement produced imaginary phase"
                    )
                sr = 1 if p % 4 == 2 else 0
                sx ^= self._x[n + i]
                sz ^= self._z[n + i]
        return sr

    # -- entanglement ---------------------------------------------------------

    def entanglement_entropy(self, subset: Iterable[int]) -> int:
        """Exact entropy of the stabilizer state across cut subset|rest.

        For a stabilizer state, S_A = n_A - dim(S_A) where S_A is the
        subgroup of the stabilizer supported entirely on A.  Equivalently
        S_A = rank_GF2(generators restricted to B) - n_B.  Result is an
        integer (e-bits); stabilizer states have integer entanglement.
        """
        A = set(int(q) for q in subset)
        if not A or A == set(range(self.n)):
            raise ValueError("subset must be a proper nonempty subset")
        for q in A:
            self._require_qubit(q)
        B = [q for q in range(self.n) if q not in A]
        # Restrict each stabilizer generator to B-columns.  GF(2) rank is
        # invariant under embedding, so mask the original bit positions and
        # park z at offset n — no per-qubit re-indexing needed (O(n) big-int
        # ops instead of O(n^2)).
        mask_b = 0
        for q in B:
            mask_b |= 1 << q
        rows = [
            (self._x[i] & mask_b) | ((self._z[i] & mask_b) << self.n)
            for i in range(self.n, 2 * self.n)
        ]
        rank_b = _gf2_rank(rows)
        return len(A) - (self.n - rank_b)

    def stabilizer_strings(self) -> List[str]:
        return [
            ("-" if self._r[self.n + i] else "+") + _row_str(self._x[self.n + i], self._z[self.n + i], self.n)
            for i in range(self.n)
        ]

    def __repr__(self) -> str:
        return f"StabilizerState(n_qubits={self.n})"


def _gf2_rank(rows: Sequence[int]) -> int:
    """Gaussian elimination rank over GF(2) of integer bit-rows."""
    pivots: dict[int, int] = {}
    for r in rows:
        v = r
        while v:
            b = v.bit_length() - 1
            p = pivots.get(b)
            if p is None:
                pivots[b] = v
                break
            v ^= p
    return len(pivots)


__all__ = [
    "StabilizerDomainError",
    "StabilizerState",
]
