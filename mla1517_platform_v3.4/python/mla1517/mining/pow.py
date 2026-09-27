"""Exact SHA256d header and target operations used by PYTHIA.

These functions are the proof boundary. Search ordering, M32 routing, and
intelligence decisions cannot admit a share. A candidate is valid only when
the complete header's double SHA256 integer is at or below the negotiated
target.
"""

from __future__ import annotations

import hashlib
import struct

# Physical-device execution is admitted only at declared Lucas scale indices.
# The gate is a schedule-integrity contract: it constrains which scaled
# work windows may be dispatched to hardware. It never admits a candidate —
# the SHA256d predicate below remains the sole proof authority.
from lucas.ladder import SCALE_RUNGS

LUCAS_EXECUTION_SCALE_INDICES = tuple(SCALE_RUNGS)


class LucasScaleError(ValueError):
    """A work allocation requested a scale index outside the Lucas ladder."""


def require_lucas_execution_scale(index: int) -> int:
    """Hardware gate: reject any allocation whose scale index deviates from
    the declared Lucas ladder. Returns the validated index."""
    if isinstance(index, bool) or not isinstance(index, int):
        raise LucasScaleError("Lucas execution scale index must be an integer")
    if index not in LUCAS_EXECUTION_SCALE_INDICES:
        raise LucasScaleError(
            f"scale index {index} deviates from the Lucas execution ladder "
            f"{LUCAS_EXECUTION_SCALE_INDICES}"
        )
    return index


def _bits_int(bits: int | str) -> int:
    value = int(bits, 16) if isinstance(bits, str) else int(bits)
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("compact bits must be a uint32")
    return value


def compact_target(bits: int | str) -> int:
    """Decode Bitcoin compact target encoding without floating arithmetic."""
    encoded = _bits_int(bits)
    exponent = encoded >> 24
    mantissa = encoded & 0x007FFFFF
    if encoded & 0x00800000:
        raise ValueError("negative compact target is invalid")
    if mantissa == 0:
        raise ValueError("zero compact target is invalid")
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    if target <= 0:
        raise ValueError("compact target decoded to zero")
    return target


def build_header(
    version: int, previous_hash: str, merkle_root: str, timestamp: int, bits: int | str, nonce: int
) -> bytes:
    """Build the 80-byte Bitcoin-style header in wire order."""
    if len(previous_hash) != 64 or len(merkle_root) != 64:
        raise ValueError("hash fields must be 32-byte hexadecimal strings")
    if not 0 <= nonce <= 0xFFFFFFFF:
        raise ValueError("nonce must be uint32")
    bits_value = _bits_int(bits)
    return (
        struct.pack("<I", version & 0xFFFFFFFF)
        + bytes.fromhex(previous_hash)[::-1]
        + bytes.fromhex(merkle_root)[::-1]
        + struct.pack("<III", timestamp & 0xFFFFFFFF, bits_value, nonce)
    )


def sha256d(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def check_pow(header: bytes, target: int) -> bool:
    """Return the independent PoW decision for a complete header."""
    if len(header) != 80:
        raise ValueError("PoW header must be exactly 80 bytes")
    if target <= 0:
        raise ValueError("target must be positive")
    return int.from_bytes(sha256d(header), "little") <= target
