"""Lazy exact companion-matrix composition and folded-word operations.

Uses the (phi, 1) basis. The companion matrix is not the Hensel-lifted
M15 matrix at every width. No intermediate materialization is required
for composition; executing the final matrix still costs one pass.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from chronus.kernels.gl2_transform import invert_gl2_mod2k


def _width(bits: int) -> int:
    if type(bits) is not int or bits not in range(8, 65, 8):
        raise ValueError("word width must be 8..64 in multiples of 8")
    return 1 << bits


def pisano_period(bits: int) -> int:
    _width(bits)
    return 3 * (1 << (bits - 1))


def modular_fib_pair(n: int, bits: int) -> tuple[int, int]:
    """Fast doubling with reduction on every operation; bounded coefficients."""
    modulus = _width(bits)
    if type(n) is not int or n < 0:
        raise ValueError("nonnegative integer exponent required")
    n %= pisano_period(bits)
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c = a * (2 * b - a) % modulus
        d = (a * a + b * b) % modulus
        a, b = (d, (c + d) % modulus) if bit == "1" else (c, d)
    return a, b


def phi_matrix(n: int, bits: int) -> tuple[tuple[int, int], tuple[int, int]]:
    f, nxt = modular_fib_pair(n, bits)
    return ((nxt, f), (f, (nxt - f) % _width(bits)))


def _words(words, bits: int) -> tuple[int, ...]:
    modulus = _width(bits)
    if not isinstance(words, (list, tuple)) or len(words) % 2:
        raise ValueError("an even number of words is required")
    if any(type(word) is not int or not 0 <= word < modulus for word in words):
        raise ValueError("word outside the declared residue domain")
    return tuple(words)


def _apply(words, matrix, bits: int) -> tuple[int, ...]:
    words = _words(words, bits)
    modulus = _width(bits)
    ((a, b), (c, d)) = matrix
    out = []
    for x, y in zip(words[::2], words[1::2]):
        out.extend(((a*x + b*y) % modulus, (c*x + d*y) % modulus))
    return tuple(out)


class FoldLedger:
    """Compose nonnegative stages modulo the period; materialize on request."""

    def __init__(self, bits: int = 64):
        self._bits = bits
        self._period = pisano_period(bits)
        self._acc = 0
        self._materializations = 0

    @property
    def bits(self):
        return self._bits

    @property
    def period(self):
        return self._period

    @property
    def acc(self):
        return self._acc

    @property
    def materializations(self):
        return self._materializations

    def stage(self, n: int) -> FoldLedger:
        if type(n) is not int or n < 0:
            raise ValueError("stage must be a nonnegative integer")
        self._acc = (self._acc + n) % self._period
        return self

    def materialize(self, words) -> tuple[int, ...]:
        result = _apply(words, phi_matrix(self.acc, self.bits), self.bits)
        self._materializations += 1
        return result

    def unfold(self, words) -> tuple[int, ...]:
        matrix = invert_gl2_mod2k(phi_matrix(self.acc, self.bits), self.bits)
        result = _apply(words, matrix, self.bits)
        self._materializations += 1
        return result


@dataclass(frozen=True)
class FoldedWords:
    """Canonical residue words under one explicitly identified transform."""

    bits: int
    exponent: int
    words: tuple[int, ...]

    def __post_init__(self):
        if type(self.exponent) is not int or not 0 <= self.exponent < pisano_period(self.bits):
            raise ValueError("noncanonical transform exponent")
        object.__setattr__(self, "words", _words(self.words, self.bits))

    @classmethod
    def from_plain(cls, ledger: FoldLedger, words):
        return cls(ledger.bits, ledger.acc, ledger.materialize(words))

    def _same_transform(self, other):
        if not isinstance(other, FoldedWords) or (self.bits, self.exponent) != (other.bits, other.exponent):
            raise ValueError("fold parameter mismatch")

    def _pair(self, other):
        self._same_transform(other)
        if len(self.words) != len(other.words):
            raise ValueError("word count mismatch")
        return zip(self.words, other.words)

    def add(self, other):
        modulus = _width(self.bits)
        return FoldedWords(self.bits, self.exponent, tuple((x+y) % modulus for x,y in self._pair(other)))

    def sub(self, other):
        modulus = _width(self.bits)
        return FoldedWords(self.bits, self.exponent, tuple((x-y) % modulus for x,y in self._pair(other)))

    def scale(self, scalar: int):
        if type(scalar) is not int:
            raise ValueError("integer scalar required")
        modulus = _width(self.bits)
        return FoldedWords(self.bits, self.exponent, tuple((scalar*x) % modulus for x in self.words))

    def equals(self, other):
        self._same_transform(other)
        return self.words == other.words

    def gram_dot(self, other) -> int:
        """Original modular dot product via the inverse-transpose metric."""
        self._pair(other)
        ((a,b),(c,d)) = invert_gl2_mod2k(phi_matrix(self.exponent, self.bits), self.bits)
        g00, g01, g11 = a*a+c*c, a*b+c*d, b*b+d*d
        total = 0
        for x,y,u,v in zip(self.words[::2], self.words[1::2], other.words[::2], other.words[1::2]):
            total += x*(g00*u+g01*v) + y*(g01*u+g11*v)
        return total % _width(self.bits)


def dedup(values) -> tuple[FoldedWords, ...]:
    values = tuple(values)
    if values:
        if not isinstance(values[0], FoldedWords):
            raise ValueError("folded values required")
        for value in values:
            values[0]._same_transform(value)
    return tuple(dict.fromkeys(values))


def keyed_lookup(entries, key: FoldedWords):
    if not isinstance(key, FoldedWords):
        raise ValueError("folded key required")
    for entry in entries:
        key._same_transform(entry)
    return entries[key]


OPS_FOLDED = frozenset({"add", "sub", "scale", "equals", "dedup", "keyed_lookup", "gram_dot"})
OPS_BOUNDARY = frozenset({"sort", "threshold", "topk", "magnitude_join", "zeckendorf_next"})


def is_equivariant(op_name: str) -> bool:
    if op_name in OPS_FOLDED:
        return True
    if op_name in OPS_BOUNDARY:
        return False
    raise ValueError("unclassified operation")


def fold_residency(workload_ops) -> Fraction:
    """Exact eligible-operation fraction, not a measured execution counter."""
    ops = tuple(workload_ops)
    if not ops:
        raise ValueError("empty workload has no residency fraction")
    return Fraction(sum(is_equivariant(op) for op in ops), len(ops))


def word_sum(words, bits=64) -> int:
    return sum(_words(words, bits)) % _width(bits)


def compensating_edit(words, deltas, bits=64):
    words = _words(words, bits)
    if not isinstance(deltas, (list, tuple)) or len(deltas) != len(words):
        raise ValueError("edit length mismatch")
    if any(type(d) is not int for d in deltas):
        raise ValueError("integer edits required")
    edited = tuple((w+d) % _width(bits) for w,d in zip(words,deltas))
    return edited, word_sum(edited, bits) != word_sum(words, bits)
