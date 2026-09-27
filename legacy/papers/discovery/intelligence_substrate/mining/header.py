"""
Bitcoin 80-Byte Block Header Serializer & Verification
======================================================
Module: mining/header.py

Complies with standard Bitcoin block header serialization:
- version: 4 bytes (uint32, little-endian)
- prev_block_hash: 32 bytes (little-endian)
- merkle_root: 32 bytes (little-endian)
- timestamp: 4 bytes (uint32, little-endian)
- bits (compact target): 4 bytes (uint32, little-endian)
- nonce: 4 bytes (uint32, little-endian)
Total = 80 bytes exactly.
"""

from __future__ import annotations
import struct
import hashlib
from typing import Dict, Any


def serialise_header(
    version: int,
    prev_hash_hex: str,
    merkle_root_hex: str,
    timestamp: int,
    bits: int,
    nonce: int,
) -> bytes:
    """
    Serialises the 6 standard fields into an exact 80-byte Bitcoin block header.
    Hex strings are reversed to match internal wire format (little-endian).
    """
    version_bytes = struct.pack("<I", version)

    # Internal wire order reverses 32-byte RPC display hex
    prev_hash_bytes = bytes.fromhex(prev_hash_hex)[::-1]
    if len(prev_hash_bytes) != 32:
        raise ValueError(f"Previous hash must be 32 bytes, got {len(prev_hash_bytes)}")

    merkle_root_bytes = bytes.fromhex(merkle_root_hex)[::-1]
    if len(merkle_root_bytes) != 32:
        raise ValueError(f"Merkle root must be 32 bytes, got {len(merkle_root_bytes)}")

    time_bytes = struct.pack("<I", timestamp)
    bits_bytes = struct.pack("<I", bits)
    nonce_bytes = struct.pack("<I", nonce)

    header = (
        version_bytes + prev_hash_bytes + merkle_root_bytes + time_bytes + bits_bytes + nonce_bytes
    )
    assert len(header) == 80, f"Block header must be 80 bytes, got {len(header)}"
    return header


def hash_header(header_bytes: bytes) -> str:
    """Computes double SHA-256 of the 80-byte header in standard big-endian hex."""
    first = hashlib.sha256(header_bytes).digest()
    second = hashlib.sha256(first).digest()
    # Display format is reversed (big-endian)
    return second[::-1].hex()


def serialise_test() -> Dict[str, Any]:
    """
    Verification test serialising the canonical Bitcoin Genesis Block header (Block 0):
    - Version: 1
    - PrevHash: 0000000000000000000000000000000000000000000000000000000000000000
    - MerkleRoot: 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b
    - Time: 1231006505 (2009-01-03 18:15:05 UTC)
    - Bits: 0x1d00ffff (486604799)
    - Nonce: 2083236893 (0x7c2bac1d)

    Expected Hash: 000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f
    """
    version = 1
    prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    merkle_root = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
    timestamp = 1231006505
    bits = 0x1D00FFFF
    nonce = 2083236893

    header = serialise_header(
        version=version,
        prev_hash_hex=prev_hash,
        merkle_root_hex=merkle_root,
        timestamp=timestamp,
        bits=bits,
        nonce=nonce,
    )

    computed_hash = hash_header(header)
    expected_hash = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"

    is_valid = computed_hash == expected_hash
    result = {
        "valid": is_valid,
        "length_bytes": len(header),
        "header_hex": header.hex(),
        "computed_hash": computed_hash,
        "expected_hash": expected_hash,
    }
    return result


if __name__ == "__main__":
    print(serialise_test())
