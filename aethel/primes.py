"""Galois-field prime substrate.

Payloads are committed under composite keys built from prime power
products in GF(MODULUS_Q), preventing the factorial blowup of a naive
prime-factorisation index.  Each prime lane holds one ``PrimeCell`` per
uuid carrying a Zeckendorf-compressed exponent and Cassini parity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .constants import MODULUS_Q, PRIMES_25
from .zeckendorf import HardenedZeckendorfCodec


@dataclass
class PrimeCell:
    prime: int
    exponent: int
    data_hash: int
    cassini_parity: int
    zeckendorf_mask: int
    crystallized: bool = False
    access_count: int = 0
    last_access: int = 0
    created_at: int = 0


class GaloisPrimeSubstrate:
    """Prime substrate with Galois-field composite keys."""

    def __init__(self, n_primes: int = 25, modulus: int = MODULUS_Q):
        self.n_primes = n_primes
        self.primes = PRIMES_25[:n_primes]
        self.modulus = modulus
        self.cells: Dict[int, Dict[str, PrimeCell]] = {}
        self.composite_index: Dict[int, List[str]] = {}
        self.uuid_index: Dict[str, Any] = {}
        self._tick = 0
        self._writes = 0
        self._reads = 0

    def commit(self, anchor: int, uuid_str: str, payload: bytes) -> int:
        """Commit with a Galois-field composite key."""
        self._tick += 1
        self._writes += 1

        exponents = self._encode(payload)
        # Galois field composite: v_p(x) = e mod M
        composite = 1
        for i, e in enumerate(exponents):
            p = self.primes[i % len(self.primes)]
            if e > 0:
                composite = (composite * pow(p, e % self.modulus, self.modulus)) % self.modulus

        for i, e in enumerate(exponents[: len(self.primes)]):
            p = self.primes[i]
            if e > 0:
                self.cells.setdefault(p, {})[uuid_str] = PrimeCell(
                    prime=p,
                    exponent=e % self.modulus,
                    data_hash=int.from_bytes(
                        hashlib.sha256(uuid_str.encode()).digest()[:4], "big"
                    ),
                    cassini_parity=(-1) ** (anchor + i),
                    zeckendorf_mask=HardenedZeckendorfCodec.encode(e % self.modulus),
                    created_at=self._tick,
                )

        self.composite_index.setdefault(composite, []).append(uuid_str)
        self.uuid_index[uuid_str] = (anchor, composite, exponents, len(payload))
        return composite

    def fetch(self, uuid_str: str) -> Optional[bytes]:
        self._reads += 1
        entry = self.uuid_index.get(uuid_str)
        if entry is None:
            return None
        _anchor, _composite, exponents, total_len = entry
        decoded = self._decode(exponents)
        return bytes(decoded[:total_len])

    def _encode(self, payload: bytes) -> List[int]:
        """Encode a payload as a discrete valuation vector across chunks."""
        exps = []
        for i in range(0, len(payload), 7):
            chunk = payload[i : i + 7].ljust(7, b"\x00")
            exps.append(int.from_bytes(chunk, "big"))
        if not exps:
            exps = [0]
        return exps

    def _decode(self, exponents: List[int]) -> bytes:
        data = bytearray()
        for e in exponents:
            data.extend((e % self.modulus).to_bytes(7, "big"))
        return bytes(data)

    def crystallize(self, prime: int) -> bool:
        cells = self.cells.get(prime)
        if cells:
            for cell in cells.values():
                cell.crystallized = True
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        return {
            "n_primes": self.n_primes,
            "primes_used": len(self.cells),
            "writes": self._writes,
            "reads": self._reads,
            "capacity_bits": self.n_primes * 56,
            "capacity_states": 2 ** (self.n_primes * 56),
            "modulus": self.modulus,
            "crystallized": sum(
                1 for bucket in self.cells.values() for c in bucket.values() if c.crystallized
            ),
        }
