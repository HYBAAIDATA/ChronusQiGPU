"""Legacy XOR construction - RETAINED FOR NEGATIVE PROOF ONLY.

This is the P0-1 defect: keystream = HMAC(key, plaintext), deterministic in the
message, no semantic security, 32-byte block repeated across the buffer.

It exists here so the test suite can PROVE the new AEAD is different in kind.
It must never be imported by a production path.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Final

IS_PRODUCTION_SAFE: Final[bool] = False
CLAIM_LANE: Final[str] = "DEFECT_REFERENCE"


def legacy_xor_obfuscate(data: bytes, key: bytes) -> bytes:
    """The broken original. Do not use. Present only as a negative control."""
    signature = hmac.new(key, data, hashlib.sha256).digest()
    repeats = (len(data) // len(signature)) + 1
    stream = signature * repeats
    return bytes(a ^ b for a, b in zip(data, stream))
