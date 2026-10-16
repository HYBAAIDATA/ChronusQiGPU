"""Exact, hardware-neutral Lucas engine reference backend."""
from __future__ import annotations
from bisect import bisect_left
from dataclasses import dataclass
from typing import Iterable

class InvariantViolation(ValueError):
    pass

def _index(n: int):
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise ValueError("index must be a non-negative integer")

def fibonacci_pair(n: int) -> tuple[int, int]:
    _index(n)
    if n == 0: return 0, 1
    a, b = fibonacci_pair(n >> 1)
    c, d = a * ((b << 1) - a), a * a + b * b
    return (c, d) if n % 2 == 0 else (d, c + d)

def lucas(n: int) -> int:
    f, f1 = fibonacci_pair(n)
    return 2 * f1 - f

def lucas_recurrence(limit: int) -> list[int]:
    _index(limit)
    values = [2] if limit == 0 else [2, 1]
    for _ in range(2, limit + 1): values.append(values[-1] + values[-2])
    return values

def _mm(a, b):
    return ((a[0][0]*b[0][0]+a[0][1]*b[1][0], a[0][0]*b[0][1]+a[0][1]*b[1][1]),
            (a[1][0]*b[0][0]+a[1][1]*b[1][0], a[1][0]*b[0][1]+a[1][1]*b[1][1]))

def _mpow(base, n):
    out = ((1, 0), (0, 1))
    while n:
        if n & 1: out = _mm(out, base)
        base, n = _mm(base, base), n >> 1
    return out

def binet_exact(n: int) -> int:
    """Exact Binet equivalent: L_n = trace([[1,1],[1,0]]^n)."""
    _index(n); q = _mpow(((1, 1), (1, 0)), n)
    return q[0][0] + q[1][1]

def zeckendorf_encode(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("value must be a non-negative integer")
    if value == 0: return 0
    weights = [1, 2]
    while weights[-1] <= value: weights.append(weights[-1] + weights[-2])
    weights.pop(); mask = 0
    for bit in range(len(weights)-1, -1, -1):
        if weights[bit] <= value: value -= weights[bit]; mask |= 1 << bit
    if value or mask & (mask << 1): raise InvariantViolation("non-canonical Zeckendorf encoding")
    return mask

def zeckendorf_decode(mask: int) -> int:
    if not isinstance(mask, int) or isinstance(mask, bool) or mask < 0:
        raise ValueError("mask must be a non-negative integer")
    if mask & (mask << 1): raise InvariantViolation("adjacent Zeckendorf bits")
    weights = [1, 2]
    while len(weights) < mask.bit_length(): weights.append(weights[-1] + weights[-2])
    return sum(weights[i] for i in range(mask.bit_length()) if mask & (1 << i))

def is_prime(value: int) -> bool:
    if value < 2: return False
    if value % 2 == 0: return value == 2
    d = 3
    while d*d <= value:
        if value % d == 0: return False
        d += 2
    return True

def nth_prime(k: int) -> int:
    if not isinstance(k, int) or k < 1: raise ValueError("prime index is one-based")
    found = 0; candidate = 1
    while found < k:
        candidate += 1
        if is_prime(candidate): found += 1
    return candidate

@dataclass(frozen=True)
class CassiniCertificate:
    index: int
    lf_residue: int
    neighbor_residue: int | None
    def verify(self):
        if self.lf_residue != 4 * ((-1) ** self.index):
            raise InvariantViolation("Lucas/Fibonacci Cassini failure")
        if self.index and self.neighbor_residue != 5 * ((-1) ** (self.index + 1)):
            raise InvariantViolation("Lucas neighbor Cassini failure")

@dataclass(frozen=True)
class PisotCertificate:
    exponent: int
    numerator: int
    denominator: int
    @staticmethod
    def for_exponent(n: int):
        _index(n); return PisotCertificate(n, 2**n, 3**n)  # |psi| < 2/3
    def verify(self):
        if self.exponent >= 1 and not self.numerator < self.denominator:
            raise InvariantViolation("Pisot bound is not below 1")
        if self.exponent >= 2 and not 2*self.numerator < self.denominator:
            raise InvariantViolation("Pisot bound is not below 1/2")

@dataclass(frozen=True)
class BinetFold:
    index: int
    f_n: int
    f_n1: int
    def verify(self):
        if (self.f_n, self.f_n1) != fibonacci_pair(self.index):
            raise InvariantViolation("invalid Binet fold")

def binet_fold(index: int) -> BinetFold:
    _index(index); f, f1 = fibonacci_pair(index); out = BinetFold(index, f, f1); out.verify(); return out

def binet_unfold(folded: BinetFold) -> int:
    folded.verify(); a, b = folded.f_n, folded.f_n1
    if (a, b) == (0, 1): return 0
    n = 1
    while (a, b) != (1, 1):
        if not (b > a > 0): raise InvariantViolation("not a Fibonacci orbit")
        a, b = b-a, a; n += 1
    return n

@dataclass(frozen=True)
class LucasRecord:
    index: int
    lucas_value: int
    fibonacci_value: int
    fibonacci_next: int
    zeckendorf_mask: int
    prime_address: int
    cassini: CassiniCertificate
    pisot: PisotCertificate
    fold: BinetFold
    def verify(self):
        _index(self.index); f, f1 = fibonacci_pair(self.index)
        if (self.fibonacci_value, self.fibonacci_next) != (f, f1): raise InvariantViolation("Fibonacci mismatch")
        if self.lucas_value != lucas(self.index): raise InvariantViolation("Lucas mismatch")
        if zeckendorf_decode(self.zeckendorf_mask) != self.index: raise InvariantViolation("address mismatch")
        if self.prime_address != nth_prime(self.index + 1): raise InvariantViolation("prime address mismatch")
        self.cassini.verify(); self.pisot.verify(); self.fold.verify()
        if binet_unfold(self.fold) != self.index: raise InvariantViolation("fold round-trip failure")

def make_record(index: int) -> LucasRecord:
    _index(index); f, f1 = fibonacci_pair(index); l = 2*f1-f
    prev = lucas(index-1) if index else None
    cert = CassiniCertificate(index, l*l-5*f*f, None if not index else prev*lucas(index+1)-l*l)
    record = LucasRecord(index, l, f, f1, zeckendorf_encode(index), nth_prime(index+1), cert, PisotCertificate.for_exponent(index), binet_fold(index))
    record.verify(); return record

class PrimeIndexedStore:
    """Sorted prime-addressed reference store; verifies on every write/read."""
    def __init__(self): self._rows: list[tuple[int, LucasRecord]] = []
    def write(self, record: LucasRecord):
        record.verify(); keys = [x[0] for x in self._rows]; pos = bisect_left(keys, record.prime_address)
        if pos < len(self._rows) and keys[pos] == record.prime_address: self._rows[pos] = (record.prime_address, record)
        else: self._rows.insert(pos, (record.prime_address, record))
    def read(self, address: int) -> LucasRecord:
        keys = [x[0] for x in self._rows]; pos = bisect_left(keys, address)
        if pos == len(self._rows) or keys[pos] != address: raise KeyError(address)
        record = self._rows[pos][1]; record.verify(); return record
    def __len__(self): return len(self._rows)

def process_batch(indices: Iterable[int]) -> list[LucasRecord]:
    return [make_record(i) for i in indices]
