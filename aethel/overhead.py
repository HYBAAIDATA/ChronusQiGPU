"""Overhead ledger for the first-principles substrate.

The mathematics does not run on a device. This module prices an already
chosen traversal: how many arithmetic operations it declared, how many
addresses it touched, and the modeled miss cost of successive addresses.
A larger miss cost is not a measured cache-miss counter and not a
throughput claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class OverheadLedger:
    """Declared cost of a substrate traversal. Hardware agnostic."""

    arithmetic_ops: int
    memory_touches: int
    miss_cost: int
    label: str = ""

    def __post_init__(self) -> None:
        for name in ("arithmetic_ops", "memory_touches", "miss_cost"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")


def price_addresses(addresses: Sequence[int], *, label: str = "") -> OverheadLedger:
    """Touch each address once. Miss cost is the sum of absolute jumps."""
    if any(address < 0 for address in addresses):
        raise ValueError("addresses must be non-negative")
    if len(addresses) < 2:
        jumps = 0
    else:
        jumps = sum(abs(right - left) for left, right in zip(addresses, addresses[1:]))
    return OverheadLedger(
        arithmetic_ops=0,
        memory_touches=len(addresses),
        miss_cost=jumps,
        label=label,
    )


def price_exact_generator(samples: int, *, label: str = "exact-modular") -> OverheadLedger:
    """One multiply and one modulus reduction per sample. No device term."""
    if samples < 0:
        raise ValueError("samples must be non-negative")
    return OverheadLedger(
        arithmetic_ops=2 * samples,
        memory_touches=samples,
        miss_cost=0,
        label=label,
    )


__all__ = ["OverheadLedger", "price_addresses", "price_exact_generator"]
