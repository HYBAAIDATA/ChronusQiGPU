"""Declared pool source for procurement commitments.

A constant is acceptable for a pilot. A hyperscaler will ask what the pool is
and how it is replenished — answer from this module, not from an inline magic
number in the route handler.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Pilot default: 64 GiB of indexable address space commitments.
# Replenishment: operator sets CHRONUS_PROCUREMENT_POOL_BYTES; no auto-scale.
PILOT_POOL_BYTES = 64 * 1024 * 1024 * 1024
POOL_ENV = "CHRONUS_PROCUREMENT_POOL_BYTES"
SOURCE_ENV = "CHRONUS_PROCUREMENT_POOL_SOURCE"


@dataclass(frozen=True)
class PoolSource:
    """How many bytes may be committed and where that number came from."""

    pool_bytes: int
    source: str
    replenishment: str

    def to_public_dict(self) -> dict[str, object]:
        return {
            "pool_bytes": self.pool_bytes,
            "source": self.source,
            "replenishment": self.replenishment,
        }


def load_pool() -> PoolSource:
    raw = os.getenv(POOL_ENV)
    if raw:
        pool_bytes = int(raw)
        source = os.getenv(SOURCE_ENV, f"env:{POOL_ENV}")
        replenishment = "operator_set_env"
    else:
        pool_bytes = PILOT_POOL_BYTES
        source = "pilot_constant"
        replenishment = "manual_operator_reset"
    if pool_bytes <= 0:
        raise ValueError(f"{POOL_ENV} must be positive")
    return PoolSource(
        pool_bytes=pool_bytes,
        source=source,
        replenishment=replenishment,
    )
