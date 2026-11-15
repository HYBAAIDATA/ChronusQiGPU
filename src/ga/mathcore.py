"""Bounded mathematical foundation for the GA research namespace.

The preserved v3 source searched all candidate field generators at import and
could perform billions of Python iterations. This module uses a short list of
degree-16 polynomial constants and verifies each candidate with the prime
factors of ``2**16 - 1``. The check is bounded and completes in microseconds.

The lattice is an in-process research data structure. It uses ordinary Python
dictionary indexing and collision buckets; it is not durable or distributed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from math import cos, pi, sin, sqrt
from threading import RLock
from typing import Any

PHI = (1 + sqrt(5)) / 2
GOLDEN_ANGLE = 2 * pi / (PHI**2)
FIB_HASH_64 = 0x9E3779B97F4A7C15

N = 16
Q = 1 << N
ORDER = Q - 1
ORDER_PRIME_FACTORS = (3, 5, 17, 257)
MASK64 = (1 << 64) - 1

# Full polynomial bit patterns include x^16. The first two constants are
# verified at import; the remaining constants are bounded fallbacks.
PRIMITIVE_POLYNOMIAL_CANDIDATES = (0x1002D, 0x1100B, 0x1002F, 0x11009)


def _multiply_polynomials(a: int, b: int, modulus: int) -> int:
    """Carry-less multiplication reduced by a degree-16 binary polynomial."""
    a &= Q - 1
    b &= Q - 1
    result = 0
    while b:
        if b & 1:
            result ^= a
        b >>= 1
        a <<= 1
        if a & Q:
            a ^= modulus
    return result & (Q - 1)


def _power_polynomial(base: int, exponent: int, modulus: int) -> int:
    result = 1
    while exponent:
        if exponent & 1:
            result = _multiply_polynomials(result, base, modulus)
        base = _multiply_polynomials(base, base, modulus)
        exponent >>= 1
    return result


def is_primitive_polynomial(modulus: int) -> bool:
    """Return whether ``x`` generates the non-zero elements of GF(2^16)."""
    if modulus.bit_length() != N + 1 or not modulus & Q:
        return False
    if _power_polynomial(2, ORDER, modulus) != 1:
        return False
    return all(
        _power_polynomial(2, ORDER // factor, modulus) != 1
        for factor in ORDER_PRIME_FACTORS
    )


class GaloisField:
    """GF(2^16) with XOR addition and table-backed multiplication.

    Only the reviewed field size is accepted. Supporting arbitrary ``p`` and
    ``n`` would require separate irreducibility and primitive-element evidence.
    """

    def __init__(self, p: int = 2, n: int = N):
        if p != 2 or n != N:
            raise ValueError("this foundation supports only GF(2^16)")

        modulus = next(
            (
                candidate
                for candidate in PRIMITIVE_POLYNOMIAL_CANDIDATES
                if is_primitive_polynomial(candidate)
            ),
            None,
        )
        if modulus is None:
            raise ValueError("no verified primitive polynomial is configured")

        self.p = p
        self.n = n
        self.q = Q
        self.order = ORDER
        self.modulus = modulus
        self.primitive = 2
        self._verify_primitive()

        self.exp: tuple[int, ...] | None = None
        self.log: tuple[int, ...] | None = None
        self._ready = False
        self._table_lock = RLock()

    def _verify_primitive(self) -> None:
        """Prove the configured generator has exact order ``2**16 - 1``."""
        if _power_polynomial(self.primitive, ORDER, self.modulus) != 1:
            raise ValueError("alpha^(q-1) != 1: polynomial is reducible")
        for factor in ORDER_PRIME_FACTORS:
            if _power_polynomial(self.primitive, ORDER // factor, self.modulus) == 1:
                raise ValueError("configured polynomial is not primitive")

    def _ensure_tables(self) -> tuple[tuple[int, ...], tuple[int, ...]]:
        if self._ready:
            assert self.exp is not None and self.log is not None
            return self.exp, self.log
        with self._table_lock:
            if self._ready:
                assert self.exp is not None and self.log is not None
                return self.exp, self.log
            exp = [0] * ORDER
            log = [0] * Q
            value = 1
            for exponent in range(ORDER):
                exp[exponent] = value
                log[value] = exponent
                value <<= 1
                if value & Q:
                    value ^= self.modulus
            if value != 1 or len(set(exp)) != ORDER:
                raise ValueError("configured polynomial did not generate GF(2^16)")
            self.log = tuple(log)
            self.exp = tuple(exp)
            self._ready = True
            return self.exp, self.log

    @staticmethod
    def _element(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("field elements must be integers")
        if not 0 <= value < Q:
            raise ValueError(f"field element must be in [0, {Q})")
        return value

    def add(self, a: int, b: int) -> int:
        return self._element(a) ^ self._element(b)

    def mul(self, a: int, b: int) -> int:
        a = self._element(a)
        b = self._element(b)
        if a == 0 or b == 0:
            return 0
        exp, log = self._ensure_tables()
        return exp[(log[a] + log[b]) % ORDER]

    def pow(self, a: int, exponent: int) -> int:
        a = self._element(a)
        if isinstance(exponent, bool) or not isinstance(exponent, int):
            raise TypeError("exponent must be an integer")
        if exponent < 0:
            return self.pow(self.inv(a), -exponent)
        if exponent == 0:
            return 1
        if a == 0:
            return 0
        exp, log = self._ensure_tables()
        return exp[(log[a] * exponent) % ORDER]

    def inv(self, a: int) -> int:
        a = self._element(a)
        if a == 0:
            raise ZeroDivisionError("0 has no inverse in GF(2^16)")
        exp, log = self._ensure_tables()
        return exp[(-log[a]) % ORDER]

    def trace(self, a: int) -> int:
        value = self._element(a)
        result = value
        for _ in range(self.n - 1):
            value = self.mul(value, value)
            result ^= value
        if result not in (0, 1):
            raise ArithmeticError("field trace did not land in GF(2)")
        return result

    def index_to_poly(self, index: int):
        """Return little-endian binary coefficients as a NumPy array.

        NumPy is imported lazily so the module import budget measures the field
        construction rather than third-party interpreter start-up.
        """
        index = self._element(index)

        return np.array([(index >> bit) & 1 for bit in range(self.n)], dtype=int)

    def poly_to_index(self, coefficients: Iterable[int]) -> int:
        values = tuple(int(value) for value in coefficients)
        if len(values) != self.n or any(value not in (0, 1) for value in values):
            raise ValueError(f"expected {self.n} binary coefficients")
        return sum(value << bit for bit, value in enumerate(values))


@dataclass(frozen=True)
class LookupResult:
    record: dict[str, Any] | None
    probes: int


class PhyllotaxisLattice:
    """Thread-safe, collision-preserving in-process key/value lattice.

    Coordinates are presentation metadata. Correct retrieval is provided by a
    key-to-slot dictionary and a per-slot collision bucket, not by geometry.
    """

    def __init__(self, capacity: int = 100_000):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self.data: dict[int, dict[str, dict[str, Any]]] = {}
        self.indices: dict[str, int] = {}
        self._lock = RLock()

    def golden_coordinate(self, index: int) -> tuple[float, float]:
        theta = index * GOLDEN_ANGLE
        radius = sqrt(index)
        return radius * cos(theta), radius * sin(theta)

    def _slot_for_key(self, key: str) -> int:
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], "big")
        mixed = (value * FIB_HASH_64) & ((1 << 64) - 1)
        return mixed % self.capacity

    @staticmethod
    def _fibonacci_up_to(value: int) -> list[int]:
        """Return the ``1, 2, 3, ...`` Fibonacci basis through ``value``."""
        if value < 1:
            return []
        fibonacci = [1, 2]
        while fibonacci[-1] <= value:
            fibonacci.append(fibonacci[-1] + fibonacci[-2])
        return fibonacci[:-1]

    def _zeckendorf_index(self, hash_value: int) -> int:
        """Return the Zeckendorf coding of ``hash_value``.

        Bit ``i`` is set exactly when basis value ``F_i`` (with ``F_0 = 1``
        and ``F_1 = 2``) occurs in the unique non-consecutive Fibonacci sum.
        The returned coding therefore satisfies ``code & (code >> 1) == 0``.
        """
        if (
            isinstance(hash_value, bool)
            or not isinstance(hash_value, int)
            or hash_value < 0
        ):
            raise ValueError("hash value must be a non-negative integer")
        if hash_value == 0:
            return 0
        fibonacci = self._fibonacci_up_to(hash_value)
        coding = 0
        remaining = hash_value
        for index in range(len(fibonacci) - 1, -1, -1):
            if fibonacci[index] <= remaining:
                coding |= 1 << index
                remaining -= fibonacci[index]
                if remaining == 0:
                    break
        if remaining != 0 or coding & (coding >> 1):
            raise ArithmeticError("invalid Zeckendorf coding")
        return coding

    def store(self, key: str, value: Any) -> int:
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        with self._lock:
            slot = self._slot_for_key(key)
            record = {
                "key": key,
                "value": deepcopy(value),
                "coordinates": self.golden_coordinate(slot),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.data.setdefault(slot, {})[key] = record
            self.indices[key] = slot
            return slot

    def retrieve_with_probes(self, key: str) -> LookupResult:
        with self._lock:
            slot = self.indices.get(key)
            if slot is None:
                return LookupResult(None, 1)
            record = self.data.get(slot, {}).get(key)
            return LookupResult(deepcopy(record), 2)

    def retrieve(self, key: str) -> dict[str, Any] | None:
        return self.retrieve_with_probes(key).record

    def spiral_query(self, center_key: str, radius: float) -> list[dict[str, Any]]:
        if radius < 0:
            raise ValueError("radius must be non-negative")
        with self._lock:
            center = self.retrieve(center_key)
            if center is None:
                return []
            center_x, center_y = center["coordinates"]
            results = []
            for bucket in self.data.values():
                for record in bucket.values():
                    x, y = record["coordinates"]
                    if (x - center_x) ** 2 + (y - center_y) ** 2 <= radius**2:
                        results.append(deepcopy(record))
            return results

    def _get_fibonacci_neighbors(self, index: int, depth: int) -> list[int]:
        if isinstance(depth, bool) or not isinstance(depth, int) or depth < 0:
            raise ValueError("depth must be a non-negative integer")
        neighbors = []
        previous, current = 1, 2
        for _ in range(depth):
            neighbors.extend(
                ((index + previous) % self.capacity, (index - previous) % self.capacity)
            )
            previous, current = current, previous + current
        return neighbors


GALOIS = GaloisField()
