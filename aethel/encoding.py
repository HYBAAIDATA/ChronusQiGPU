"""Aethel encoding layer — Binet + Zeckendorf fold/unfold.

``fold`` maps payload bytes to a :class:`ZeckendorfVector`: one Zeckendorf
mask per 8-byte chunk, each mask a unique sum of non-consecutive
Fibonacci numbers (Zeckendorf's theorem — no gaps in representation, no
adjacent indices).  ``unfold`` restores the payload byte-identically.

``BinetIndex`` (re-exported from :mod:`aethel.fibonacci`) is the closed-form
index arithmetic the fold/unfold domain shares with the storage layer's
recursive Fibonacci index — contract B3 asserts exact integer agreement.

Domain boundary: ``fold`` rejects payloads longer than ``max_fold_len``
(default ``MAX_FOLD_LEN``) with :class:`FoldDomainOverflow` — never silent
truncation, never silent extension.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Tuple

from .errors import FoldDomainOverflow, ZeckendorfInvariantError
from .fibonacci import BinetIndex, binet_fibonacci
from .zeckendorf import (
    HardenedZeckendorfCodec,
    SparseTopology,
    apply_zeckendorf_compression,
    reverse_zeckendorf_expansion,
)

logger = logging.getLogger("aethel.encoding")

#: Declared fold domain: payloads up to 1 MiB.  Above this the caller must
#: shard — folding never truncates.
MAX_FOLD_LEN = 1 << 20


@dataclass(frozen=True)
class ZeckendorfVector:
    """The folded representation of a payload.

    ``blocks`` maps byte offset -> Zeckendorf mask; every mask satisfies
    ``(mask & (mask << 1)) == 0`` (non-adjacency — Zeckendorf uniqueness).
    ``total_bytes`` is the original payload length.
    """

    blocks: Tuple[Tuple[int, int], ...] = field(default_factory=tuple)
    total_bytes: int = 0

    @classmethod
    def from_sparse(cls, sparse: SparseTopology) -> "ZeckendorfVector":
        return cls(
            blocks=tuple(sorted(sparse.blocks.items())),
            total_bytes=sparse.total_bytes,
        )

    def to_sparse(self) -> SparseTopology:
        sparse = SparseTopology()
        sparse.blocks = dict(self.blocks)
        sparse.total_bytes = self.total_bytes
        return sparse

    @property
    def block_map(self) -> Dict[int, int]:
        return dict(self.blocks)

    @property
    def folded_units(self) -> int:
        return len(self.blocks)

    def verify(self) -> bool:
        """True iff every mask is non-adjacent and every offset is a
        non-negative multiple of 8."""
        for offset, mask in self.blocks:
            if offset < 0 or offset % 8 != 0:
                return False
            if not HardenedZeckendorfCodec.verify_non_adjacent(mask):
                return False
        return True


def fold(payload: bytes, *, max_fold_len: int = MAX_FOLD_LEN) -> ZeckendorfVector:
    """Fold payload bytes into a ZeckendorfVector.

    Precondition: ``0 <= len(payload) <= max_fold_len``.
    Postcondition: ``unfold(fold(x)) == x`` byte-identically, and the
    result's ``verify()`` is True.
    Raises: FoldDomainOverflow when the payload exceeds the declared domain;
    ZeckendorfInvariantError if the encoder produced an adjacent mask
    (declared unreachable — means corruption).
    Thread-safety: pure with respect to ``payload``; safe to call
    concurrently.
    """
    payload = bytes(payload)
    if len(payload) > max_fold_len:
        raise FoldDomainOverflow(
            f"payload of {len(payload)} bytes exceeds declared fold domain "
            f"{max_fold_len} bytes"
        )
    sparse = apply_zeckendorf_compression(payload)
    vector = ZeckendorfVector.from_sparse(sparse)
    if not vector.verify():
        raise ZeckendorfInvariantError(
            "fold produced a Zeckendorf vector violating non-adjacency"
        )
    logger.debug(
        "fold: %d bytes -> %d units", len(payload), vector.folded_units
    )
    return vector


def unfold(vector: ZeckendorfVector) -> bytes:
    """Unfold a ZeckendorfVector back to the original payload bytes.

    Precondition: ``vector.verify()`` is True.
    Postcondition: the returned bytes satisfy ``len == vector.total_bytes``
    and ``unfold(fold(x)) == x``.
    Raises: ZeckendorfInvariantError when the vector is malformed.
    Thread-safety: pure.
    """
    if not isinstance(vector, ZeckendorfVector) or not vector.verify():
        raise ZeckendorfInvariantError("malformed Zeckendorf vector")
    data = reverse_zeckendorf_expansion(vector.to_sparse())
    if len(data) != vector.total_bytes:
        raise ZeckendorfInvariantError(
            f"unfold produced {len(data)} bytes; expected {vector.total_bytes}"
        )
    logger.debug("unfold: %d units -> %d bytes", vector.folded_units, len(data))
    return data


def encoding_domain() -> dict:
    """The declared encoding domain — used by CONTRACT.md claims B1-B4."""
    return {
        "max_fold_len": MAX_FOLD_LEN,
        "chunk_bytes": 8,
        "fibonacci_table_hi": HardenedZeckendorfCodec.FIBONACCI[-1],
        "binet_exact": True,
    }


__all__ = [
    "BinetIndex",
    "FoldDomainOverflow",
    "MAX_FOLD_LEN",
    "ZeckendorfInvariantError",
    "ZeckendorfVector",
    "binet_fibonacci",
    "encoding_domain",
    "fold",
    "unfold",
]
