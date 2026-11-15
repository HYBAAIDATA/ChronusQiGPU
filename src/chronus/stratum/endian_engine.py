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
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, List, Tuple


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


@dataclass(frozen=True)
class StratumJob:
    """One mining.notify work order."""

    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: Tuple[str, ...]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool = False

    @classmethod
    def from_notify(cls, params: List[Any]) -> "StratumJob":
        if len(params) != 9:
            raise ValueError("mining.notify must carry 9 parameters")
        (
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            clean_jobs,
        ) = params
        return cls(
            job_id=str(job_id),
            prevhash=str(prevhash),
            coinb1=str(coinb1),
            coinb2=str(coinb2),
            merkle_branch=tuple(str(b) for b in merkle_branch),
            version=str(version),
            nbits=str(nbits),
            ntime=str(ntime),
            clean_jobs=bool(clean_jobs),
        )


@dataclass(frozen=True)
class StratumSession:
    """Subscription state returned after the subscribe handshake."""

    extranonce1: bytes
    extranonce2_size: int
    # The pool difficulty is an exact rational. It stays a Fraction so that
    # difficulty_to_target never has to round through a binary float.
    difficulty: Fraction = Fraction(1)

    @property
    def target(self) -> int:
        return difficulty_to_target(self.difficulty)


# Stratum difficulty-1 target: 0x00000000FFFF0000...0000 (2**208 * 0xFFFF).
DIFF1_TARGET = 0xFFFF << 208


def difficulty_to_target(difficulty) -> int:
    """Convert a pool difficulty to the 256-bit share target using exact rational arithmetic.

    Uses Fraction instead of float division so that difficulties near 2**240
    do not lose low bits past float64's 53-bit mantissa.
    """
    try:
        d = Fraction(difficulty)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError("difficulty must be a positive number") from exc
    if d <= 0:
        raise ValueError("difficulty must be a positive number")
    target = int(DIFF1_TARGET / d)
    return min(target, (1 << 256) - 1)


def build_coinbase(job: StratumJob, extranonce2: bytes, session: StratumSession) -> bytes:
    """Assemble the full coinbase transaction for a share attempt."""
    if len(extranonce2) != session.extranonce2_size:
        raise ValueError(
            f"extranonce2 must be exactly {session.extranonce2_size} bytes"
        )
    return (
        bytes.fromhex(job.coinb1)
        + session.extranonce1
        + extranonce2
        + bytes.fromhex(job.coinb2)
    )


def merkle_root(coinbase_hash: bytes, branch: Tuple[str, ...]) -> bytes:
    """Fold the coinbase hash through the merkle branch (internal byte order)."""
    node = coinbase_hash
    for step in branch:
        node = sha256d(node + bytes.fromhex(step))
    return node


def build_header_prefix(
    job: StratumJob, extranonce2: bytes, session: StratumSession
) -> bytes:
    """Build the 76-byte header prefix; the final 4 bytes are the LE nonce."""
    coinbase = build_coinbase(job, extranonce2, session)
    root = merkle_root(sha256d(coinbase), job.merkle_branch)
    prevhash_raw = bytes.fromhex(job.prevhash)
    if len(prevhash_raw) != 32:
        raise ValueError("prevhash must be 32 bytes")
    prefix = (
        _le_word(job.version)
        + swap_prevhash_words(prevhash_raw)
        + root
        + _le_word(job.ntime)
        + _le_word(job.nbits)
    )
    if len(prefix) != 76:
        raise AssertionError("header prefix must be 76 bytes")
    return prefix


def _le_word(hex_be: str) -> bytes:
    """Decode a 4-byte big-endian hex display word into header (LE) bytes."""
    raw = bytes.fromhex(hex_be)
    if len(raw) != 4:
        raise ValueError(f"expected 4-byte hex word, got {hex_be!r}")
    return raw[::-1]
