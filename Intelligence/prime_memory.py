"""Prime-addressed exponent store — data encoded as prime exponents.

Every byte-chunk of the payload becomes the exponent of one prime. The
"address" is a SHA-256 fingerprint of the exponent vector — the literal
composite product `prod p_i^e_i` is not materialized because 64-bit
exponents would make it a ~10^19-bit integer (infeasible to compute).

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

DIM = 11
PHI = (1 + np.sqrt(5)) / 2
PSI = 1 - PHI
SQRT5 = np.sqrt(5)

PRIMES = [
    2,
    3,
    5,
    7,
    11,
    13,
    17,
    19,
    23,
    29,
    31,
    37,
    41,
    43,
    47,
    53,
    59,
    61,
    67,
    71,
    73,
    79,
    83,
    89,
    97,
    101,
    103,
    107,
    109,
    113,
    127,
    131,
    137,
    139,
    149,
    151,
    157,
    163,
    167,
    173,
    179,
    181,
    191,
    193,
    197,
    199,
    211,
    223,
    227,
    229,
    233,
    239,
    241,
    251,
    257,
    263,
    269,
    271,
    277,
    281,
    283,
    293,
    307,
    311,
    313,
    317,
    331,
    337,
    347,
    349,
    353,
    359,
    367,
    373,
    379,
    383,
    389,
    397,
    401,
    409,
    419,
    421,
    431,
    433,
    439,
    443,
    449,
    457,
    461,
    463,
    467,
    479,
    487,
    491,
    499,
    503,
    509,
    521,
    523,
    541,
    547,
    557,
    563,
    569,
    571,
    577,
    587,
    593,
    599,
    601,
    607,
    613,
    617,
    619,
    631,
    641,
    643,
    647,
    653,
    659,
    661,
    673,
    677,
    683,
    691,
    701,
    709,
    719,
    727,
    733,
    739,
    743,
    751,
    757,
    761,
    769,
    773,
    787,
    797,
    809,
    811,
    821,
    823,
    827,
    829,
    839,
    853,
    857,
    859,
    863,
    877,
    881,
    883,
    887,
    907,
    911,
    919,
    929,
    937,
    941,
    947,
    953,
    967,
    971,
    977,
    983,
    991,
    997,
]


def _zeckendorf_encode(n: int) -> int:
    fibs = [1, 2]
    while fibs[-1] < n:
        fibs.append(fibs[-1] + fibs[-2])
    mask = 0
    for i, f in enumerate(reversed(fibs[:-1])):
        if f <= n:
            mask |= 1 << i
            n -= f
    return mask


def _composite_fingerprint(exponents: List[int]) -> int:
    """SHA-256 fingerprint of the exponent vector (the feasible 'composite')."""
    h = hashlib.sha256()
    for e in exponents:
        nbytes = max(1, (int(e).bit_length() + 7) // 8)
        h.update(int(e).to_bytes(nbytes, "big"))
    return int.from_bytes(h.digest(), "big")


@dataclass
class PrimeCell:
    """A single prime memory cell."""

    prime: int
    exponent: int
    data_hash: int
    cassini_parity: int
    zeckendorf_mask: int
    crystallized: bool = False
    access_count: int = 0
    last_access: int = 0
    created_at: int = 0


@dataclass
class PrimeAddress:
    """A prime-addressed memory location (fingerprinted composite)."""

    prime_indices: List[int]
    exponents: List[int]
    composite: int

    def to_bytes(self) -> bytes:
        return self.composite.to_bytes((self.composite.bit_length() + 7) // 8, "big")


class PrimeMemory:
    """Prime-addressed memory — data lives in the exponent vector."""

    def __init__(self, n_primes: int = 25):
        self.n_primes = n_primes
        self.primes = PRIMES[:n_primes]
        self.cells: Dict[int, PrimeCell] = {}
        self.composite_index: Dict[int, int] = {}
        self._tick = 0
        self._total_writes = 0
        self._total_reads = 0

    def write(self, data: bytes) -> PrimeAddress:
        self._tick += 1
        exponents = self._encode_to_exponents(data)
        composite = _composite_fingerprint(exponents)
        for i, (p, e) in enumerate(zip(self.primes, exponents)):
            if e > 0:
                self.cells[p] = PrimeCell(
                    prime=p,
                    exponent=e,
                    data_hash=hash(data) & 0xFFFFFFFF,
                    cassini_parity=1 if i % 2 == 0 else -1,
                    zeckendorf_mask=_zeckendorf_encode(e),
                    created_at=self._tick,
                )
        self.composite_index[composite] = self._tick
        self._total_writes += 1
        return PrimeAddress(
            prime_indices=list(range(len(self.primes))),
            exponents=exponents,
            composite=composite,
        )

    def read(self, address: PrimeAddress) -> bytes:
        self._total_reads += 1
        data = self._decode_from_exponents(address.exponents)
        for p in self.primes:
            if p in self.cells:
                self.cells[p].access_count += 1
                self.cells[p].last_access = self._tick
        return data

    def _encode_to_exponents(self, data: bytes) -> List[int]:
        """Every 8 bytes of payload becomes one exponent."""
        exponents = []
        for i in range(0, len(data), 8):
            chunk = data[i : i + 8]
            chunk = chunk.ljust(8, b"\x00")
            exponents.append(int.from_bytes(chunk, "big"))
        while len(exponents) < self.n_primes:
            exponents.append(0)
        return exponents[: self.n_primes]

    def _decode_from_exponents(self, exponents: List[int]) -> bytes:
        data = b""
        for exp in exponents:
            if exp == 0:
                continue
            data += exp.to_bytes(8, "big")
        return data.rstrip(b"\x00")

    def crystallize(self, prime: int) -> bool:
        if prime in self.cells:
            self.cells[prime].crystallized = True
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        total_exponents = sum(c.exponent for c in self.cells.values())
        return {
            "n_primes": self.n_primes,
            "primes_used": len(self.cells),
            "total_writes": self._total_writes,
            "total_reads": self._total_reads,
            "total_exponent_bits": total_exponents * 64,
            "capacity_bits": self.n_primes * 64,
            "capacity_states": 2 ** (self.n_primes * 64),
            "crystallized": sum(1 for c in self.cells.values() if c.crystallized),
        }


class ExponentialPrimeStore:
    """Prime store with key-hash-driven cell selection."""

    def __init__(self, n_primes: int = 168):
        self.n_primes = n_primes
        self.primes = PRIMES[:n_primes]
        self.memory = PrimeMemory(n_primes)
        self.address_space = 2 ** (n_primes * 64)

    def store(self, key: str, value: bytes) -> PrimeAddress:
        key_hash = int(hashlib.sha256(key.encode()).hexdigest(), 16)
        selected = [i for i in range(self.n_primes) if (key_hash >> i) & 1]
        exponents = self.memory._encode_to_exponents(value)
        self.memory._tick += 1
        for i in selected:
            if i < len(exponents):
                self.memory.cells[self.primes[i]] = PrimeCell(
                    prime=self.primes[i],
                    exponent=exponents[i],
                    data_hash=hash(value) & 0xFFFFFFFF,
                    cassini_parity=1 if i % 2 == 0 else -1,
                    zeckendorf_mask=_zeckendorf_encode(exponents[i]),
                    created_at=self.memory._tick,
                )
        composite = _composite_fingerprint(exponents)
        return PrimeAddress(
            prime_indices=selected,
            exponents=exponents,
            composite=composite,
        )

    def retrieve(self, address: PrimeAddress) -> bytes:
        return self.memory._decode_from_exponents(address.exponents)

    def stats(self) -> Dict[str, Any]:
        return {
            "n_primes": self.n_primes,
            "address_space": self.address_space,
            "address_space_bits": self.n_primes * 64,
            "memory": self.memory.stats(),
        }


class QuantumPrimeMemory:
    """Amplitude store that also fingerprints payload into prime cells."""

    def __init__(self, n_qubits: int = DIM):
        self.n_qubits = n_qubits
        self.hilbert_dim = 2**n_qubits
        self.prime_store = ExponentialPrimeStore(n_primes=25)
        self.superpositions: Dict[int, np.ndarray] = {}

    def store_superposition(self, key: int, amplitudes: np.ndarray):
        if amplitudes.shape[0] != self.hilbert_dim:
            raise ValueError(f"Expected {self.hilbert_dim} amplitudes")
        norm = np.linalg.norm(amplitudes)
        if norm > 0:
            amplitudes = amplitudes / norm
        self.superpositions[key] = amplitudes
        self.prime_store.store(str(key), amplitudes.tobytes())

    def measure(self, key: int, shots: int = 1024) -> Dict[str, int]:
        amplitudes = self.superpositions.get(key)
        if amplitudes is None:
            return {}
        probs = np.abs(amplitudes) ** 2
        probs = probs / probs.sum()
        outcomes = np.random.choice(self.hilbert_dim, size=shots, p=probs)
        counts: Dict[str, int] = {}
        for o in outcomes:
            bitstring = format(o, f"0{self.n_qubits}b")
            counts[bitstring] = counts.get(bitstring, 0) + 1
        return counts

    def stats(self) -> Dict[str, Any]:
        return {
            "n_qubits": self.n_qubits,
            "hilbert_dim": self.hilbert_dim,
            "stored_states": len(self.superpositions),
            "prime_store": self.prime_store.stats(),
        }


if __name__ == "__main__":
    print("=" * 78)
    print("PRIME-ADDRESSED EXPONENT STORE")
    print("=" * 78)

    mem = PrimeMemory(n_primes=25)
    for i in range(1000):
        mem.write(f"block_{i}_data".encode() * 8)

    stats = mem.stats()
    print(f"\nPrimes: {stats['n_primes']}")
    print(f"Capacity bits: {stats['capacity_bits']}")
    print(f"Total writes: {stats['total_writes']}")
    print("=" * 78)
