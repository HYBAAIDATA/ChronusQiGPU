"""Nonce scheduler — deterministic ordering of the nonce search.

The probe order is derived from the block header through the canonical
multi-family Zeckendorf schedule in ``turing_core`` — golden, silver,
plastic, supergolden and tribonacci limbs interleaved so the scan is
spread across lag structures. Fully deterministic: the same header
always produces the same schedule. The schedule length is bounded by
the ``mining_kernel`` ceiling L_n at the current ladder rung.
"""

# LUCAS WIRING: draws from lucas/ (pool) and the canonical turing_core
# substrate. MUST NOT import from any sibling algorithm.
# Substrate route: mining

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from lucas.ladder import FULL_LADDER
from lucas.core import lucas

import turing_core

THEOREM_PROVEN = False


def _header_seed(header: bytes) -> int:
    """Deterministic schedule seed derived from the block header."""
    return int.from_bytes(hashlib.sha256(header).digest()[:8], "little")


def _rung_for_budget(budget: int) -> int:
    """Smallest ladder rung whose L_n covers the schedule budget."""
    for rung in FULL_LADDER:
        if lucas(rung) >= budget:
            return rung
    return FULL_LADDER[-1]


class NonceScheduler:
    """Orders the nonce search inside a Lucas-bounded window."""

    def __init__(self, nonce_window: int = 1_000_000, cap: int = 10_000) -> None:
        self.nonce_window = max(int(nonce_window), 1)
        self.cap = max(int(cap), 1)
        self._schedules_built = 0

    def schedule(self, header: bytes) -> List[int]:
        """Return the deterministic probe order for this block header."""
        seed = _header_seed(header)
        sched = turing_core.extended_nonce_schedule(self.nonce_window, seed=seed, cap=self.cap)
        self._schedules_built += 1
        return sched

    def kernel_check(self, schedule_len: int) -> Dict[str, Any]:
        """Bound the emitted schedule under the mining_kernel ceiling."""
        from lucas.pool import get as _lucas_get

        n = _rung_for_budget(max(schedule_len, 1))
        result = _lucas_get("mining_kernel")(schedule_len, n)
        result["module"] = __name__
        return result

    def status(self) -> Dict[str, Any]:
        return {
            "nonce_window": self.nonce_window,
            "cap": self.cap,
            "schedules_built": self._schedules_built,
            "kernel": "mining_kernel",
            "theorem_proven": False,
        }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("mining_kernel")(10_000, n)
    result["module"] = __name__
    return result
