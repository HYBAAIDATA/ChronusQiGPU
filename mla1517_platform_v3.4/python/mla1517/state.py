"""The 11D state model — the computational state space of an MLA object.

Eleven axes, each an EXACT integer or a small exact tuple:

    D1  payload (nonce / object index)
    D2  Lucas scale
    D3  Pisot fold state
    D4  Fibonacci exact state (F_n, F_{n+1})
    D5  Zeckendorf code (uint32 mask)
    D6  Binet/algebraic view (numerator, denominator)
    D7  prime address
    D8  polyhedral position (M32 site)
    D9  transform / eigenbasis index
    D10 Cassini proof state (seal +1 / -1)
    D11 lineage and time state (version, epoch)

This is a COMPUTATIONAL state space. It is not a claim about physical
11-dimensional hardware, and the module says so at the point of use.

The descriptor is a fixed 64-byte ABI. The size is asserted at import, so a
layout change cannot pass silently.
"""

from __future__ import annotations

import ctypes
import hashlib
from dataclasses import dataclass
from typing import Any, Dict

from .constants import STATE_BYTES

__all__ = ["MLA1517State", "StateError", "m32_site_for", "descriptor_size"]


class StateError(ValueError):
    """A state violated the 11D contract."""


class MLA1517State(ctypes.Structure):
    """The 64-byte hot descriptor. D1..D11 plus a gauge and reserved words.

    Laid out with explicit field widths so the C ABI is unambiguous and the
    total is exactly 64 bytes, which is asserted below.
    """

    # Field widths MUST match primedb_engine.MLA1517State exactly: that
    # struct is the ABI the native C storage library is compiled against.
    # Widening d2/d3/d4 to uint64 would silently produce an 80-byte
    # descriptor that no longer matches the C side.
    _fields_ = [
        ("d1_nonce", ctypes.c_uint64),  # 8
        ("d2_lucas", ctypes.c_uint32),  # 4
        ("d3_pisot", ctypes.c_uint32),  # 4
        ("d4_fib", ctypes.c_uint32),  # 4
        ("d5_zeckendorf", ctypes.c_uint32),  # 4
        ("d6_binet", ctypes.c_uint32),  # 4
        ("d7_prime_addr", ctypes.c_uint32),  # 4
        ("d8_route", ctypes.c_uint32),  # 4
        ("d9_eigen", ctypes.c_uint32),  # 4
        ("d10_cassini", ctypes.c_int32),  # 4
        ("d11_time_state", ctypes.c_uint32),  # 4
        ("d12_gauge", ctypes.c_uint32),  # 4
        ("reserved1", ctypes.c_uint32),  # 4
        ("reserved2", ctypes.c_uint32),  # 4
        ("reserved3", ctypes.c_uint32),  # 4
    ]


def descriptor_size() -> int:
    """Actual byte size of the descriptor. Must equal ``STATE_BYTES``."""
    return ctypes.sizeof(MLA1517State)


# The ABI is a contract; a silent layout change is a correctness bug.
if descriptor_size() != STATE_BYTES:  # pragma: no cover - structural guard
    raise RuntimeError(f"MLA1517State layout is {descriptor_size()} bytes, expected {STATE_BYTES}")


def m32_site_for(prime_address: int, site_count: int = 32) -> int:
    """Route an object to an M32 site. O(1) arithmetic, no table."""
    if site_count <= 0:
        raise StateError("site count must be positive")
    return int(prime_address) % int(site_count)


@dataclass(frozen=True)
class LogicalState:
    """The Python-level 11D state, before serialisation to the 64 bytes."""

    index: int
    lucas_scale: int
    zeckendorf_mask: int
    prime_address: int
    site: int
    cassini_seal: int
    version: int
    payload: bytes = b""

    def digest(self) -> str:
        """Content address: SHA-256 over the exact canonical fields.

        The Cassini seal is signed (+1 / -1), so it is hashed as a signed
        value; forcing it into an unsigned field would raise on every odd
        index.
        """
        h = hashlib.sha256()
        h.update(b"mla1517.state.v1")
        for v in (
            self.index,
            self.lucas_scale,
            self.zeckendorf_mask,
            self.prime_address,
            self.site,
        ):
            h.update(int(v).to_bytes(8, "little", signed=False))
        h.update(int(self.cassini_seal).to_bytes(8, "little", signed=True))
        h.update(int(self.version).to_bytes(8, "little", signed=False))
        h.update(self.payload)
        return h.hexdigest()

    def to_descriptor(self) -> MLA1517State:
        """Serialise to the fixed 64-byte hot descriptor."""
        from .core import fib, lucas
        from .pisot_fold import pisot_fold
        from .zeckendorf_codec import to_mask

        fold = pisot_fold(self.index)
        return MLA1517State(
            d1_nonce=self.index,
            d2_lucas=lucas(self.lucas_scale),
            d3_pisot=abs(fold.folded.residual.numerator) % (1 << 64),
            d4_fib=fib(self.index),
            d5_zeckendorf=to_mask(self.index),
            d6_binet=abs(fold.folded.residual.numerator) % (1 << 32),
            d7_prime_addr=self.prime_address,
            d8_route=self.site,
            d9_eigen=self.index % 32,
            d10_cassini=self.cassini_seal,
            d11_time_state=self.version,
            d12_gauge=0,
            reserved1=0,
            reserved2=0,
            reserved3=0,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "lucas_scale": self.lucas_scale,
            "zeckendorf_mask": self.zeckendorf_mask,
            "prime_address": self.prime_address,
            "site": self.site,
            "cassini_seal": self.cassini_seal,
            "version": self.version,
            "digest": self.digest(),
        }
