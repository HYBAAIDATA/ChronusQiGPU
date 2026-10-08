"""Canonical Poincare-golden 11D nonce order over a leased window.

This adapter composes the verified 32-face dodecahedron/icosahedron search
crystal with the production execution router.  It changes candidate order
only: SHA256d and the negotiated target remain the sole proof authority.

Import failures are explicit.  A requested order is never silently replaced
with M32, sequential, or another traversal.
"""

from __future__ import annotations

from chronos_one_igpu.reference_contract import require_reference, reference_only, require_production_context
from functools import lru_cache
from typing import Any, List, Optional, Tuple

from .hendrix_order import NonceOrderUnavailable

__all__ = [
    "load_poincare_11d",
    "poincare_11d_nonces",
]


def _import() -> Any:
    from Intelligence.search_crystal import PoincareCassiniSearchEngine

    return PoincareCassiniSearchEngine


@reference_only('poincare_11d_order')
@lru_cache(maxsize=1)
def load_poincare_11d() -> Tuple[Optional[Any], Optional[str]]:
    """Return the canonical engine class, or its exact import failure."""
    require_reference('poincare_11d_order')
    try:
        return _import(), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def poincare_11d_nonces(
    header: bytes,
    base: int,
    window: int,
    position: int = 0,
    count: Optional[int] = None,
) -> List[int]:
    """Return permutation positions from the canonical 11D order.

    The header's 76-byte prefix ranks all 32 dual-solid faces by their
    golden-weighted ``direction_11d`` affinity.  Each face shard then uses the
    canonical Cassini-certified affine permutation.
    """
    require_reference('poincare_11d_order')
    if len(header) != 80:
        raise ValueError("header must be 80 bytes")
    if type(base) is not int or not 0 <= base <= 0xFFFFFFFF:
        raise ValueError("base must be uint32")
    if type(window) is not int or window < 0 or base + window > 1 << 32:
        raise ValueError("window must fit inside the uint32 nonce space")
    if type(position) is not int or not 0 <= position <= window:
        raise ValueError("position must be inside the window")
    take = window - position if count is None else count
    if type(take) is not int or take < 0 or position + take > window:
        raise ValueError("count must fit inside the remaining window")
    if window == 0:
        return []

    engine_cls, error = load_poincare_11d()
    if engine_cls is None:
        raise NonceOrderUnavailable(f"Poincare 11D order unavailable: {error}")
    prefix = bytes(header[:76])
    try:
        engine = engine_cls(total_nonce_space=window, nonce_start=base)
        ranked_faces = engine._rank_faces(prefix)
        order = engine.enumerate_nonces(prefix, selected_faces=ranked_faces)
    except Exception as exc:
        raise NonceOrderUnavailable(
            f"Poincare 11D order unavailable: {type(exc).__name__}: {exc}"
        ) from exc
    if len(order) != window or len(set(order)) != window:
        raise NonceOrderUnavailable(
            "Poincare 11D order failed unique full-window coverage"
        )
    if any(nonce < base or nonce >= base + window for nonce in order):
        raise NonceOrderUnavailable("Poincare 11D order escaped its nonce lease")
    return order[position : position + take]
