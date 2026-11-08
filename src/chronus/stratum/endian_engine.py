"""
Chronus Stratum V1 Endianness & Block Header Serialization Engine.

Bitcoin Header 80-Byte Structure:
---------------------------------
1. Version    (4 bytes,  little-endian unsigned int '<I')
2. PrevHash   (32 bytes, 32-bit word-swapped little-endian)
3. MerkleRoot (32 bytes, internal little-endian byte order, un-reversed)
4. nTime      (4 bytes,  little-endian unsigned int '<I')
5. nBits      (4 bytes,  little-endian unsigned int '<I')
6. Nonce      (4 bytes,  little-endian unsigned int '<I')

Total Length = 80 Bytes Exactly.
"""

import hashlib
import struct
from typing import List


def sha256d(data: bytes) -> bytes:
    """Standard Bitcoin double-SHA256 hash using hashlib.new for high throughput."""
    h1 = hashlib.new("sha256", data, usedforsecurity=False).digest()
    return hashlib.new("sha256", h1, usedforsecurity=False).digest()


def swap_prevhash_words(hex_or_bytes: str | bytes) -> bytes:
    """
    Stratum PrevHash Rule:
    Unpacks 64-character hex or 32 raw bytes as 8 big-endian unsigned 32-bit ints (>8I)
    and repacks as 8 little-endian unsigned 32-bit ints (<8I).
    This reverses Stratum V1's legacy 32-bit word-swapping quirk.
    """
    if isinstance(hex_or_bytes, str):
        raw = bytes.fromhex(hex_or_bytes)
    else:
        raw = hex_or_bytes

    if len(raw) != 32:
        raise ValueError(f"PrevHash must be exactly 32 bytes (64 hex chars), got {len(raw)} bytes.")

    return struct.pack("<8I", *struct.unpack(">8I", raw))


def merkle_root_from_txids(txids: List[bytes]) -> bytes:
    """
    Computes Bitcoin Merkle root from a list of transaction ID digests (32 bytes each).
    Applies pairwise odd-element duplication rule.
    Returns 32-byte digest in internal byte order (un-reversed).
    """
    if not txids:
        raise ValueError("Cannot compute Merkle root from empty txid list.")

    current_layer = list(txids)
    while len(current_layer) > 1:
        if len(current_layer) % 2 == 1:
            current_layer.append(current_layer[-1])  # Bitcoin odd-element duplication rule

        next_layer = []
        for i in range(0, len(current_layer), 2):
            combined = current_layer[i] + current_layer[i + 1]
            next_layer.append(sha256d(combined))
        current_layer = next_layer

    return current_layer[0]


def compute_merkle_root_stratum(
    coinb1_hex: str,
    extranonce1_hex: str,
    extranonce2_hex: str,
    coinb2_hex: str,
    merkle_branches_hex: List[str]
) -> bytes:
    """
    Assembles Coinbase TX and computes Merkle Root up the tree for Stratum V1.
    Returns 32-byte Merkle root in internal (little-endian) byte order without double-reversal.
    """
    coinbase_tx = bytes.fromhex(coinb1_hex + extranonce1_hex + extranonce2_hex + coinb2_hex)
    merkle_root = sha256d(coinbase_tx)

    for branch_hex in merkle_branches_hex:
        branch_bytes = bytes.fromhex(branch_hex)
        merkle_root = sha256d(merkle_root + branch_bytes)

    return merkle_root


def build_header80(
    version_int: int,
    prevhash_le_swapped: bytes,
    merkle_raw: bytes,
    ntime_int: int,
    nbits_int: int,
    nonce_int: int
) -> bytes:
    """
    Constructs the exact 80-byte Bitcoin block header.
    Asserts exact length == 80 bytes.
    """
    if len(prevhash_le_swapped) != 32:
        raise ValueError(f"PrevHash must be 32 bytes, got {len(prevhash_le_swapped)}")
    if len(merkle_raw) != 32:
        raise ValueError(f"MerkleRoot must be 32 bytes, got {len(merkle_raw)}")

    version_le = struct.pack("<I", version_int)
    ntime_le = struct.pack("<I", ntime_int)
    nbits_le = struct.pack("<I", nbits_int)
    nonce_le = struct.pack("<I", nonce_int)

    header = version_le + prevhash_le_swapped + merkle_raw + ntime_le + nbits_le + nonce_le
    assert len(header) == 80, f"Block header must be exactly 80 bytes, got {len(header)} bytes."
    return header
