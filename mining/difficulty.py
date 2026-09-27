"""Difficulty controller — per-block target adjustment.

Difficulty is expressed as a 256-bit target derived deterministically
from the number of leading zero bits. Each accepted block tightens the
target by one bit (up to a ceiling); each missed cycle relaxes it by one
bit (down to the floor). No wall-clock, no randomness — the adjustment
is a pure function of the chain of outcomes. The nonce budget implied
by the difficulty is bounded by the ``mining_kernel`` ceiling L_n.
"""

# LUCAS WIRING: draws from lucas/ (pool) and the canonical turing_core
# substrate. MUST NOT import from any sibling algorithm.
# Substrate route: mining

from __future__ import annotations

from typing import Any, Dict, List

import turing_core

THEOREM_PROVEN = False

# Difficulty floor/ceiling expressed as leading-zero-bit counts. The
# floor (0 leading zeros) keeps the live run productive on CPU; the
# ceiling bounds how far a session can tighten.
MIN_ZERO_BITS = 0
MAX_ZERO_BITS = 16


class DifficultyController:
    """Adjusts the mining target once per block."""

    def __init__(self, zero_bits: int = MIN_ZERO_BITS) -> None:
        self._zero_bits = max(MIN_ZERO_BITS, min(int(zero_bits), MAX_ZERO_BITS))
        self._adjustments: List[Dict[str, Any]] = []

    # -- target -----------------------------------------------------------

    def target_int(self) -> int:
        """Current 256-bit target as an integer."""
        return turing_core.MAX_TARGET >> self._zero_bits

    def target_bytes(self) -> bytes:
        """Current target as 32 big-endian bytes."""
        return self.target_int().to_bytes(32, "big")

    def difficulty(self) -> float:
        """Pool difficulty relative to genesis difficulty 1."""
        return turing_core.target_to_difficulty(self.target_int())

    # -- per-block adjustment ----------------------------------------------

    def update(self, winner_found: bool) -> Dict[str, Any]:
        """Adjust after a block outcome. Tighten on success, relax on miss."""
        before = self._zero_bits
        if winner_found:
            self._zero_bits = min(self._zero_bits + 1, MAX_ZERO_BITS)
        else:
            self._zero_bits = max(self._zero_bits - 1, MIN_ZERO_BITS)
        record = {
            "winner_found": winner_found,
            "zero_bits_before": before,
            "zero_bits_after": self._zero_bits,
            "difficulty": self.difficulty(),
            "kernel": "mining_kernel",
            "theorem_proven": False,
        }
        self._adjustments.append(record)
        return record

    def status(self) -> Dict[str, Any]:
        return {
            "zero_bits": self._zero_bits,
            "difficulty": self.difficulty(),
            "adjustments": len(self._adjustments),
            "kernel": "mining_kernel",
            "theorem_proven": False,
        }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("mining_kernel")(2**16, n)
    result["module"] = __name__
    return result
