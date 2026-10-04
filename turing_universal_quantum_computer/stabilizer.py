"""TEST FIXTURE ONLY - verbatim copy of the repository's stabilizer.py.

Kept locally so collapse-dependent logic (marginals, shot sampling) is verified
against the real CHP tableau. Never pushed.
"""

from __future__ import annotations

from fractions import Fraction
import random
from typing import Iterable, List, Optional, Sequence, Tuple


class StabilizerDomainError(ValueError):
    """Operation outside the Clifford/stabilizer domain - fail closed."""


def _row_str(x: int, z: int, n: int) -> str:
    return "".join(
        "I" if ((x >> q) & 1) == 0 and ((z >> q) & 1) == 0
        else "X" if ((x >> q) & 1) == 1 and ((z >> q) & 1) == 0
        else "Z" if ((x >> q) & 1) == 0 and ((z >> q) & 1) == 1
        else "Y"
        for q in range(n)
    )


class StabilizerState:
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

    @classmethod
    def basis(cls, n_qubits: int) -> "StabilizerState":
        return cls(n_qubits)

    @classmethod
    def plus(cls, n_qubits: int) -> "StabilizerState":
        s = cls(n_qubits)
        for i in range(s.n):
            s._x[i], s._z[i] = 0, 1 << i
            s._x[s.n + i], s._z[s.n + i] = 1 << i, 0
        return s

    @classmethod
    def ghz(cls, n_qubits: int) -> "StabilizerState":
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
        s = cls(n_qubits)
        n = s.n
        s._x = [0] * (2 * n)
        s._z = [0] * (2 * n)
        s._r = [0] * (2 * n)
        for i in range(n):
            s._x[i] = 1 << i
            s._x[n + i] = 1 << i
            if i > 0:
                s._z[n + i] |= 1 << (i - 1)
            if i < n - 1:
                s._z[n + i] |= 1 << (i + 1)
        return s

    @staticmethod
    def _gsum(x1: int, z1: int, x2: int, z2: int) -> int:
        iy = x1 & z1
        ix = x1 & ~z1
        iz = ~x1 & z1
        total = (
            (z2 & iy).bit_count() - (x2 & iy).bit_count()
            + ((ix & x2 & z2).bit_count() - (ix & ~x2 & z2).bit_count())
            + ((iz & x2 & ~z2).bit_count() - (iz & x2 & z2).bit_count())
        )
        return total

    def _rowsum(self, h: int, i: int) -> None:
        g = self._gsum(self._x[i], self._z[i], self._x[h], self._z[h])
        p = 2 * self._r[i] + 2 * self._r[h] + g
        if p % 4 == 0:
            self._r[h] = 0
        elif p % 4 == 2:
            self._r[h] = 1
        else:
            raise StabilizerDomainError(
                "rowsum produced an imaginary (+-i) Pauli product - "
                "tableau cannot store it"
            )
        self._x[h] ^= self._x[i]
        self._z[h] ^= self._z[i]

    def h(self, q: int) -> "StabilizerState":
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
        self._require_qubit(q)
        n = self.n
        for i in range(2 * n):
            xb, zb = (self._x[i] >> q) & 1, (self._z[i] >> q) & 1
            self._r[i] ^= xb & zb
            self._z[i] ^= self._x[i] & (1 << q)
        return self

    def sdg(self, q: int) -> "StabilizerState":
        self._require_qubit(q)
        n = self.n
        for i in range(2 * n):
            xb, zb = (self._x[i] >> q) & 1, (self._z[i] >> q) & 1
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
        return self.h(b).cnot(a, b).h(b)

    def swap(self, a: int, b: int) -> "StabilizerState":
        return self.cnot(a, b).cnot(b, a).cnot(a, b)

    def t(self, q: int) -> None:
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

    def measurement_probabilities(self, q: int) -> Tuple[Fraction, Fraction]:
        self._require_qubit(q)
        for p in range(self.n, 2 * self.n):
            if (self._x[p] >> q) & 1:
                return Fraction(1, 2), Fraction(1, 2)
        bit = self._deterministic_outcome(q)
        return (Fraction(0), Fraction(1)) if bit else (Fraction(1), Fraction(0))

    def expectation_z(self, q: int) -> Fraction:
        p0, p1 = self.measurement_probabilities(q)
        return p0 - p1

    def measure(self, q: int, outcome: Optional[int] = None,
                seed: Optional[int] = None) -> dict:
        self._require_qubit(q)
        n = self.n
        p0, p1 = self.measurement_probabilities(q)
        random_outcome = p0 == p1
        if outcome is None:
            if random_outcome:
                # An unseeded random draw takes the 0 branch, as before.
                if seed is not None and random.Random(seed).random() < float(p1):
                    outcome = 1
                else:
                    outcome = 0
            else:
                # A deterministic qubit has an outcome whether or not the caller
                # knows it.  Defaulting to 0 here made measuring a qubit that is
                # deterministically |1> impossible: the call raised instead of
                # reporting the value it had just computed.
                outcome = self._deterministic_outcome(q)
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
            self._x[p - n], self._z[p - n], self._r[p - n] = self._x[p], self._z[p], self._r[p]
            self._x[p], self._z[p], self._r[p] = 0, 1 << q, outcome
        else:
            actual = self._deterministic_outcome(q)
            if outcome != actual:
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
        n = self.n
        sx = sz = 0
        sr = 0
        for i in range(n):
            if (self._x[i] >> q) & 1:
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

    def entanglement_entropy(self, subset: Iterable[int]) -> int:
        A = set(int(q) for q in subset)
        if not A or A == set(range(self.n)):
            raise ValueError("subset must be a proper nonempty subset")
        for q in A:
            self._require_qubit(q)
        B = [q for q in range(self.n) if q not in A]
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


__all__ = ["StabilizerDomainError", "StabilizerState"]
