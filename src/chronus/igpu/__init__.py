"""iGPU — execution-lane runtime for the Chronus elevation.

The Chronus elevation adds Tier 4 (role-aware negotiation) and Tier 6
(cloud adapters) to the existing iGPU runtime. This package re-exports the
new ABI and adapter types.
"""

from __future__ import annotations

from .abi import role_adjacency, role_from_consortium
from .adapters import ADAPTER_TABLE, promote_adapter

__all__ = [
    "role_from_consortium",
    "role_adjacency",
    "ADAPTER_TABLE",
    "promote_adapter",
]