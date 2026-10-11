"""Local receipt minting — the free tier produces receipts it can verify.

A minted receipt is internally consistent under the published φ¹⁵/ZECK
fold: coordinate_masks + context_id → canonical_int → token. It proves the
fold, nothing more — producer identity is NOT attested (provenance remains
``unsupported`` at every verification level, exactly like upstream
certificates).

Derivations are deterministic and documented so anyone can reproduce them:

- ``data`` → 11 coordinate masks: SHA-256(payload) is split into 11 chunks;
  each chunk supplies bits at even Fibonacci-index positions {2,4,…,24},
  making every mask producible (non-adjacent) by construction.
- ``coordinate_masks`` may instead be supplied directly (each must be a
  producible mask or minting fails honestly).
- ``non_adjacent_mask``: bits at even positions {0,2,…,10} taken from the
  canonical accumulator — non-adjacent by construction.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from . import __version__
from .verify import canonical_accumulator

__all__ = ["mint_receipt", "data_coordinate_masks"]

_DIMS = 11


def data_coordinate_masks(data: bytes) -> List[int]:
    """Map arbitrary payload bytes to 11 producible Zeckendorf masks.

    SHA-256(data) → 11 chunks of 22 bits; each chunk's bit i lands at
    Fibonacci-index position 2·i+2, so masks use only even positions in
    [2,24] — non-adjacent and producible by construction.
    """
    digest = hashlib.sha256(data).digest()
    value = int.from_bytes(digest, "big")  # 256-bit seed
    masks: List[int] = []
    for d in range(_DIMS):
        chunk = value & ((1 << 22) - 1)
        value >>= 22
        masks.append(sum(((chunk >> i) & 1) << (2 * i + 2) for i in range(11)))
    return masks


def _decoupling_mask(canonical: int) -> int:
    """Non-adjacent 11-bit mask from canonical bits at even positions."""
    return sum(((canonical >> i) & 1) << (2 * i) for i in range(6))


def mint_receipt(
    *,
    context_id: str = "",
    coordinate_masks: Optional[List[int]] = None,
    data: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Mint a contract-v2 receipt. Deterministic; verifies against verify.py
    and verify.js by construction. The receipt is fold-consistent only —
    ``producer.provenance`` is honestly ``unsupported``."""
    if coordinate_masks is None:
        if data is not None:
            coordinate_masks = data_coordinate_masks(data)
        else:
            coordinate_masks = [0] * _DIMS
    if len(coordinate_masks) != _DIMS or not all(
        isinstance(m, int) and 0 <= m for m in coordinate_masks
    ):
        raise ValueError(f"coordinate_masks must be {_DIMS} non-negative ints")
    canonical = canonical_accumulator(list(coordinate_masks), context_id)
    receipt: Dict[str, Any] = {
        "token_hex": f"ZECK-{canonical:016X}",
        "non_adjacent_mask": _decoupling_mask(canonical),
        "canonical_int": canonical,
        "coordinate_masks": list(coordinate_masks),
        "context_id": context_id,
        "producer": {
            "distribution": "hyba-pythia-consumer",
            "version": __version__,
            "derivation": ("sha256-data" if data is not None else
                           ("explicit" if coordinate_masks != [0] * _DIMS else "zero-masks")),
            "provenance": "unsupported — minted receipts prove the fold, not origin",
        },
    }
    return receipt
