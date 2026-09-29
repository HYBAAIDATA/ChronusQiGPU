"""Hendrix coprime-stride nonce order over a leased window.

The schedule comes from the Turing VQC package (``pisot.HendrixSchedule``):
position ``i`` of a window of ``n`` nonces visits ``base + (i * stride) % n``
with ``gcd(stride, n) == 1``, a bijection of ``[base, base + n)``. It is an
ORDER only: every visited nonce is still hashed with double SHA256 and compared
with the negotiated target, and the window never leaves its lease.

A load failure is never swallowed: ``load_hendrix`` returns the error and
``hendrix_schedule`` raises it as ``NonceOrderUnavailable``.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple

__all__ = [
    "NonceOrderUnavailable",
    "hendrix_nonces",
    "hendrix_schedule",
    "load_hendrix",
    "worker_nonces",
]


class NonceOrderUnavailable(RuntimeError):
    """A requested nonce-order strategy is not implemented in this runtime."""


def _import() -> Any:
    from turing_universal_quantum_computer.pisot import HendrixStructuredSearch

    return HendrixStructuredSearch


@lru_cache(maxsize=1)
def load_hendrix() -> Tuple[Optional[Any], Optional[str]]:
    """``(HendrixStructuredSearch, None)`` from an install or the in-tree
    distribution, else ``(None, reason)``. Same resolution as policy_audit."""
    try:
        return _import(), None
    except Exception as exc:
        first = f"{type(exc).__name__}: {exc}"
    dist = Path(__file__).resolve().parents[4] / "turing_universal_quantum_computer"
    if not (dist / "turing_universal_quantum_computer" / "pisot.py").is_file():
        return None, first
    for name in [m for m in sys.modules if m.split(".")[0] == "turing_universal_quantum_computer"]:
        del sys.modules[name]
    sys.path.insert(0, str(dist))
    try:
        return _import(), None
    except Exception as exc:
        return None, f"{first}; in-tree: {type(exc).__name__}: {exc}"


@lru_cache(maxsize=64)
def hendrix_schedule(window: int, workers: int = 1) -> Any:
    """The verified Hendrix schedule for a window of ``window`` nonces."""
    search_cls, error = load_hendrix()
    if search_cls is None:
        raise NonceOrderUnavailable(f"Hendrix schedule unavailable: {error}")
    return search_cls(workers=workers).plan(int(window))


def hendrix_nonces(base: int, schedule: Any, position: int, count: int) -> List[int]:
    """Nonces at permutation positions ``[position, position + count)``."""
    return [(base + schedule.nonce_at(p)) & 0xFFFFFFFF for p in range(position, position + count)]


def worker_nonces(base: int, schedule: Any, worker_id: int) -> Iterator[int]:
    """One worker arm: its permutation positions mapped into the lease."""
    return ((base + n) & 0xFFFFFFFF for n in schedule.worker_nonces(worker_id))
