"""Declarative SHA-256d target oracle for triad Grover values at k=32.

A state value is (ntime << 32) | nonce.  The predicate rebuilds the 80-byte
header (prefix[:68] | ntime | nbits | nonce) and tests Bitcoin's rule
int.from_bytes(SHA256d(header), "little") <= target.  The first 64-byte block
is compressed once per ntime (midstate via ``hashlib`` ``copy``); each
evaluation then costs exactly two SHA-256 compressions (block 2 + outer hash).

Single honest counter: ``evaluations`` (distinct values hashed) and
``compressions`` (= 2 * evaluations + midstates).  Every call is a classical
SHA-256d evaluation.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Dict

from chronus.stratum.gatekeeper import decode_nbits_target


def target_from_bits(bits: int) -> int:
    """Bitcoin compact nBits -> target via the repository's gatekeeper decoder:
    right shift for exponents <= 3, sign bit rejected, target must be in (0, 2^256)."""
    if isinstance(bits, bool) or not isinstance(bits, int) or not 0 <= bits < (1 << 32):
        raise ValueError("bits must be a 32-bit compact target")
    return decode_nbits_target(bits)


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


class Sha256dTargetOracle:
    def __init__(self, header_prefix: bytes, target: int) -> None:
        if not isinstance(header_prefix, (bytes, bytearray)) or len(header_prefix) < 76:
            raise ValueError("header prefix must carry at least 76 bytes")
        if isinstance(target, bool) or not isinstance(target, int) or not 0 <= target < (1 << 256):
            raise ValueError("target must be an unsigned 256-bit integer")
        self.prefix = bytes(header_prefix[:76])
        self.ntime = struct.unpack("<I", self.prefix[68:72])[0]
        self.target = target
        self.evaluations = 0
        self.midstates = 0
        self._mid: Dict[int, object] = {}

    @property
    def compressions(self) -> int:
        return 2 * self.evaluations + self.midstates

    def _header(self, value: int) -> bytes:
        return (self.prefix[:68] + struct.pack("<I", (value >> 32) & 0xFFFFFFFF)
                + self.prefix[72:76] + struct.pack("<I", value & 0xFFFFFFFF))

    def digest(self, value: int) -> bytes:
        ntime = (value >> 32) & 0xFFFFFFFF
        mid = self._mid.get(ntime)
        if mid is None:
            mid = hashlib.sha256(self.prefix[:64])
            self._mid[ntime] = mid
            self.midstates += 1
        h = mid.copy()
        h.update(self.prefix[64:68] + struct.pack("<I", ntime) + self.prefix[72:76]
                 + struct.pack("<I", value & 0xFFFFFFFF))
        self.evaluations += 1
        return hashlib.sha256(h.digest()).digest()

    def __call__(self, value: int) -> bool:
        return int.from_bytes(self.digest(value), "little") <= self.target

    def verify(self, value: int) -> tuple:
        """Fresh full SHA-256d of the rebuilt header (3 compressions, counted separately)."""
        d = sha256d(self._header(value))
        return int.from_bytes(d, "little") <= self.target, d[::-1].hex()
