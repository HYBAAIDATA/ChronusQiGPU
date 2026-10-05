"""Exact stabilizer-state backend (Aaronson-Gottesman tableau over GF(2)).

A stabilizer state on n qubits is specified exactly by n independent
commuting Pauli generators plus n destabilizers — O(n^2) bits regardless
of the 2^n Hilbert-space dimension. This is the mathematically exact
representation that makes n = 10_000 tractable for the Clifford domain:
superposition, entanglement, interference and measurement are represented
without materialising a dense amplitude vector.

Gates supported: H, S (and S-dagger), X, Y, Z, CNOT, CZ, SWAP — the Clifford
group, which is closed under stabilizer evolution. Applying a non-Clifford
gate (T, arbitrary phase) raises ``StabilizerDomainError`` — fail closed,
never approximate.

Measurement returns exact Born probabilities. A Z measurement on a stabilizer
state has outcome distribution in {(1,0), (0,1), (1/2,1/2)} over ``Fraction``.
The random branch implements the Aaronson-Gottesman tableau update exactly:
one anticommuting stabilizer is chosen as the pivot; every *other* row that
anticommutes with the measured Z is cleared by multiplying it by the pivot,
except for the pivot's paired destabilizer, which is replaced by the old
pivot after clearing. Multiplying the pivot into its paired destabilizer would
multiply anticommuting Paulis and create an unrepresentable ±i phase.

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
        "I"
        if ((x >> q) & 1) == 0 and ((z >> q) & 1) == 0
        else "X"
        if ((x >> q) & 1) == 1 and ((z >> q) & 1) == 0
        else "Z"
        if ((x >> q) & 1) == 0 and ((z >> q) & 1) == 1
        else "Y"
        for q in range(n)
    )


def _symplectic_product(x1: int, z1: int, x2: int, z2: int) -> int:
    """Return the binary symplectic product of two Pauli rows."""
    return ((x1 & z2).bit_count() + (z1 & x2).bit_count()) & 1


class StabilizerState:
    """n-qubit stabilizer state as a CHP tableau.

    Rows 0..n-1 are destabilizers D_i; rows n..2n-1 are stabilizers S_i.
    Each row is (x_bits, z_bits, r) where the Pauli string is
    (-1)^r * prod_j (X^{x_j} Z^{z_j}). All integers — O(n^2) bits total.
    """

    def __init__(self, n_qubits: int):
        if n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        self.n = int(n_qubits)
        self._x = [0] * (2 * self.n)
        self._z = [0] * (2 * self.n)
        self._r = [0] * (2 * self.n)
        for i in range(self.n):
            self._x[i] = 1 << i
            self._z[self.n + i] = 1 << i

    # -- exact constructors -------------------------------------------------

    @classmethod
    def basis(cls, n_qubits: int) -> "StabilizerState":
        """Return |0...0>, with stabilizers Z_i."""
        return cls(n_qubits)

    @classmethod
    def plus(cls, n_qubits: int) -> "StabilizerState":
        """Return |+>^n exactly in tableau form."""
        s = cls(n_qubits)
        for i in range(s.n):
            s._x[i], s._z[i] = 0, 1 << i
            s._x[s.n + i], s._z[s.n + i] = 1 << i, 0
        return s

    @classmethod
    def ghz(cls, n_qubits: int) -> "StabilizerState":
        """Return GHZ_n = (|0^n> + |1^n>)/sqrt(2) exactly."""
        s = cls(n_qubits)
        n = s.n
        s._x = [0] * (2 * n)
        s._z = [0] * (2 * n)
        s._r = [0] * (2 * n)
        s._z[0] = 1
        suffix_mask = (1 << n) - 1
        for i in range(1, n):
            s._x[i] = suffix_mask & ~((1 << i) - 1)
        s._x[n] = (1 << n) - 1
        for i in range(1, n):
            s._z[n + i] = (1 << (i - 1)) | (1 << i)
        return s

    @classmethod
    def cluster_chain(cls, n_qubits: int) -> "StabilizerState":
        """Return the 1-D graph/cluster state exactly.

        The state is CZ edges applied to |+>^n. Under that Clifford
        conjugation the plus-state destabilizers Z_i remain Z_i while the
        stabilizers X_i become Z_{i-1} X_i Z_{i+1}. Using X_i as the
        destabilizers would commute with S_i and break the canonical tableau.
        """
        s = cls(n_qubits)
        n = s.n
        s._x = [0] * (2 * n)
        s._z = [0] * (2 * n)
        s._r = [0] * (2 * n)
        for i in range(n):
            s._z[i] = 1 << i
            s._x[n + i] = 1 << i
            if i > 0:
                s._z[n + i] |= 1 << (i - 1)
            if i < n - 1:
                s._z[n + i] |= 1 << (i + 1)
        return s

    # -- tableau row algebra -------------------------------------------------

    @staticmethod
    def _gsum(x1: int, z1: int, x2: int, z2: int) -> int:
        """Return the Aaronson-Gottesman Pauli-product phase exponent sum."""
        iy = x1 & z1
        ix = x1 & ~z1
        iz = ~x1 & z1
        return (
            (z2 & iy).bit_count()
            - (x2 & iy).bit_count()
            + (ix & x2 & z2).bit_count()
            - (ix & ~x2 & z2).bit_count()
            + (iz & x2 & ~z2).bit_count()
            - (iz & x2 & z2).bit_count()
        )

    def _rowsum(self, h: int, i: int) -> None:
        """Set row_h := row_i * row_h for commuting tableau rows."""
        g = self._gsum(self._x[i], self._z[i], self._x[h], self._z[h])
        p = 2 * self._r[i] + 2 * self._r[h] + g
        mod = p % 4
        if mod == 0:
            self._r[h] = 0
        elif mod == 2:
            self._r[h] = 1
        else:
            raise StabilizerDomainError(
                "rowsum produced an imaginary (+-i) Pauli product; "
                "the rows do not commute and cannot be combined in a real-phase tableau"
            )
        self._x[h] ^= self._x[i]
        self._z[h] ^= self._z[i]

    # -- gates ---------------------------------------------------------------

    def h(self, q: int) -> "StabilizerState":
        self._require_qubit(q)
        for i in range(2 * self.n):
            xb = (self._x[i] >> q) & 1
            zb = (self._z[i] >> q) & 1
            self._r[i] ^= xb & zb
            m = (self._x[i] ^ self._z[i]) & (1 << q)
            self._x[i] ^= m
            self._z[i] ^= m
        return self

    def s(self, q: int) -> "StabilizerState":
        self._require_qubit(q)
        for i in range(2 * self.n):
            xb = (self._x[i] >> q) & 1
            zb = (self._z[i] >> q) & 1
            self._r[i] ^= xb & zb
            self._z[i] ^= self._x[i] & (1 << q)
        return self

    def sdg(self, q: int) -> "StabilizerState":
        self._require_qubit(q)
        for i in range(2 * self.n):
            xb = (self._x[i] >> q) & 1
            zb = (self._z[i] >> q) & 1
            self._r[i] ^= xb & (zb ^ 1)
            self._z[i] ^= self._x[i] & (1 << q)
        return self

    def x(self, q: int) -> "StabilizerState":
        self._require_qubit(q)
        for i in range(2 * self.n):
            self._r[i] ^= (self._z[i] >> q) & 1
        return self

    def y(self, q: int) -> "StabilizerState":
        self._require_qubit(q)
        for i in range(2 * self.n):
            self._r[i] ^= ((self._x[i] >> q) & 1) ^ ((self._z[i] >> q) & 1)
        return self

    def z(self, q: int) -> "StabilizerState":
        self._require_qubit(q)
        for i in range(2 * self.n):
            self._r[i] ^= (self._x[i] >> q) & 1
        return self

    def cnot(self, c: int, t: int) -> "StabilizerState":
        self._require_qubit(c)
        self._require_qubit(t)
        if c == t:
            raise ValueError("CNOT requires distinct qubits")
        cm = 1 << c
        tm = 1 << t
        for i in range(2 * self.n):
            xc = (self._x[i] & cm) != 0
            zt = (self._z[i] & tm) != 0
            xt = (self._x[i] & tm) != 0
            zc = (self._z[i] & cm) != 0
            self._r[i] ^= xc and zt and (xt ^ zc ^ 1)
            if xc:
                self._x[i] ^= tm
            if zt:
                self._z[i] ^= cm
        return self

    def cz(self, a: int, b: int) -> "StabilizerState":
        return self.h(b).cnot(a, b).h(b)

    def swap(self, a: int, b: int) -> "StabilizerState":
        return self.cnot(a, b).cnot(b, a).cnot(a, b)

    def t(self, q: int) -> None:
        self._require_qubit(q)
        raise StabilizerDomainError(
            "T gate is non-Clifford; stabilizer backend cannot represent it exactly. "
            "Use an admitted exact universal backend within its declared resource envelope."
        )

    def apply_phase_gate(self, q: int, theta) -> None:
        self._require_qubit(q)
        raise StabilizerDomainError(
            "arbitrary phase rotation is non-Clifford; stabilizer backend fails closed"
        )

    def _require_qubit(self, q: int) -> None:
        if not 0 <= q < self.n:
            raise IndexError(f"qubit {q} out of range [0,{self.n})")

    # -- measurement ---------------------------------------------------------

    def measurement_probabilities(self, q: int) -> Tuple[Fraction, Fraction]:
        """Return the exact Z-basis Born distribution for qubit q."""
        self._require_qubit(q)
        for p in range(self.n, 2 * self.n):
            if (self._x[p] >> q) & 1:
                return Fraction(1, 2), Fraction(1, 2)
        bit = self._deterministic_outcome(q)
        return (Fraction(0), Fraction(1)) if bit else (Fraction(1), Fraction(0))

    def expectation_z(self, q: int) -> Fraction:
        """Return <Z_q> exactly in {-1, 0, +1}."""
        p0, p1 = self.measurement_probabilities(q)
        return p0 - p1

    def measure(
        self,
        q: int,
        outcome: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> dict:
        """Measure and collapse qubit q in the Z basis exactly.

        For a random stabilizer measurement the distribution is exactly
        (1/2, 1/2). If ``outcome`` is omitted, ``seed`` selects a labelled
        classical draw; without a seed the canonical branch is outcome 0.
        Deterministic measurements return their actual outcome and reject an
        explicitly forced impossible outcome.
        """
        self._require_qubit(q)
        n = self.n
        p0, p1 = self.measurement_probabilities(q)
        random_outcome = p0 == p1

        if outcome is None:
            if random_outcome and seed is not None:
                outcome = 1 if random.Random(seed).random() < float(p1) else 0
            elif random_outcome:
                outcome = 0
        if outcome is not None and outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")

        pivot = None
        for p in range(n, 2 * n):
            if (self._x[p] >> q) & 1:
                pivot = p
                break

        if pivot is not None:
            paired_destabilizer = pivot - n
            # CHP random-measurement update. The paired destabilizer is not
            # rowsummed with its anticommuting stabilizer pivot: doing so would
            # produce ±i. It is replaced by the old pivot after all other rows
            # that anticommute with Z_q have been cleared.
            for i in range(2 * n):
                if i in (pivot, paired_destabilizer):
                    continue
                if (self._x[i] >> q) & 1:
                    self._rowsum(i, pivot)

            self._x[paired_destabilizer] = self._x[pivot]
            self._z[paired_destabilizer] = self._z[pivot]
            self._r[paired_destabilizer] = self._r[pivot]

            self._x[pivot] = 0
            self._z[pivot] = 1 << q
            self._r[pivot] = int(outcome)
        else:
            actual = self._deterministic_outcome(q)
            if outcome is None:
                outcome = actual
            if outcome != actual:
                raise ValueError(
                    f"deterministic measurement outcome is {actual}; cannot force {outcome}"
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
        """Return the sign bit of Z_q as a product of stabilizer generators."""
        sx = 0
        sz = 0
        sr = 0
        for i in range(self.n):
            if (self._x[i] >> q) & 1:
                g = self._gsum(
                    self._x[self.n + i],
                    self._z[self.n + i],
                    sx,
                    sz,
                )
                p = 2 * self._r[self.n + i] + 2 * sr + g
                mod = p % 4
                if mod not in (0, 2):
                    raise StabilizerDomainError(
                        "deterministic measurement produced an imaginary phase"
                    )
                sr = 1 if mod == 2 else 0
                sx ^= self._x[self.n + i]
                sz ^= self._z[self.n + i]
        return sr

    # -- mathematical invariant verification --------------------------------

    def validate_invariants(self) -> None:
        """Validate the canonical stabilizer/destabilizer symplectic basis.

        This is an explicit verification surface for tests, audits and
        checkpoints. It is intentionally not called after every gate because
        pairwise validation is O(n^2); gate updates themselves preserve the
        tableau algebra exactly.
        """
        n = self.n
        if len(self._x) != 2 * n or len(self._z) != 2 * n or len(self._r) != 2 * n:
            raise StabilizerDomainError("tableau has the wrong number of rows")
        if any(r not in (0, 1) for r in self._r):
            raise StabilizerDomainError("tableau phase bits must be binary")

        stabilizer_vectors = []
        for i in range(n):
            di = i
            si = n + i
            stabilizer_vectors.append(self._x[si] | (self._z[si] << n))
            for j in range(n):
                dj = j
                sj = n + j
                dd = _symplectic_product(
                    self._x[di], self._z[di], self._x[dj], self._z[dj]
                )
                ss = _symplectic_product(
                    self._x[si], self._z[si], self._x[sj], self._z[sj]
                )
                ds = _symplectic_product(
                    self._x[di], self._z[di], self._x[sj], self._z[sj]
                )
                if dd:
                    raise StabilizerDomainError(
                        f"destabilizers D_{i}, D_{j} anticommute"
                    )
                if ss:
                    raise StabilizerDomainError(
                        f"stabilizers S_{i}, S_{j} anticommute"
                    )
                if ds != (1 if i == j else 0):
                    raise StabilizerDomainError(
                        f"canonical pairing violated for D_{i}, S_{j}"
                    )
        if _gf2_rank(stabilizer_vectors) != n:
            raise StabilizerDomainError("stabilizer generators are not independent")

    # -- entanglement ---------------------------------------------------------

    def entanglement_entropy(self, subset: Iterable[int]) -> int:
        """Return exact stabilizer entropy across subset|complement in e-bits."""
        a = set(int(q) for q in subset)
        if not a or a == set(range(self.n)):
            raise ValueError("subset must be a proper nonempty subset")
        for q in a:
            self._require_qubit(q)
        b = [q for q in range(self.n) if q not in a]
        mask_b = 0
        for q in b:
            mask_b |= 1 << q
        rows = [
            (self._x[i] & mask_b) | ((self._z[i] & mask_b) << self.n)
            for i in range(self.n, 2 * self.n)
        ]
        rank_b = _gf2_rank(rows)
        return len(a) - (self.n - rank_b)

    def stabilizer_strings(self) -> List[str]:
        return [
            ("-" if self._r[self.n + i] else "+")
            + _row_str(self._x[self.n + i], self._z[self.n + i], self.n)
            for i in range(self.n)
        ]

    def __repr__(self) -> str:
        return f"StabilizerState(n_qubits={self.n})"


def _gf2_rank(rows: Sequence[int]) -> int:
    """Gaussian-elimination rank over GF(2) for integer bit rows."""
    pivots: dict[int, int] = {}
    for row in rows:
        value = row
        while value:
            bit = value.bit_length() - 1
            pivot = pivots.get(bit)
            if pivot is None:
                pivots[bit] = value
                break
            value ^= pivot
    return len(pivots)


__all__ = [
    "StabilizerDomainError",
    "StabilizerState",
]
