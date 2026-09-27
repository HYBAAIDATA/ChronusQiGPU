"""Content-integrity Cassini seals for observed mining records.

A Cassini seal here is an integrity seal for a persisted record. It is not a
Bitcoin proof, not a SHA256d target result, and not evidence of hardware work.
"""
from __future__ import annotations

import hashlib
import hmac
import struct

_DOMAIN = b"PYTHIA-CASSINI-SEAL-V1\0"


class InvalidCassiniSeal(ValueError):
    """A record seal does not match its complete persisted context."""


def compute_seal(*, state: bytes, sequence: int, watermark: int, lane_id: int) -> str:
    if not isinstance(state, bytes) or len(state) != 64:
        raise InvalidCassiniSeal("Cassini state must be exactly 64 bytes")
    if min(sequence, watermark, lane_id) < 0:
        raise InvalidCassiniSeal("Cassini coordinates cannot be negative")
    payload = _DOMAIN + struct.pack("<QQQ", sequence, watermark, lane_id) + state
    return hashlib.sha256(hashlib.sha256(payload).digest()).hexdigest()


def verify_seal(*, state: bytes, sequence: int, watermark: int, lane_id: int, seal: str) -> None:
    if not isinstance(seal, str) or len(seal) != 64:
        raise InvalidCassiniSeal("Cassini seal must be a 32-byte hexadecimal digest")
    try:
        bytes.fromhex(seal)
    except ValueError as exc:
        raise InvalidCassiniSeal("Cassini seal is not hexadecimal") from exc
    expected = compute_seal(state=state, sequence=sequence, watermark=watermark, lane_id=lane_id)
    if not hmac.compare_digest(expected, seal.lower()):
        raise InvalidCassiniSeal("Cassini seal mismatch")
