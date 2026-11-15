"""iGPU — execution-lane runtime for the Chronus elevation.

The Chronus elevation adds Tier 4 (role-aware negotiation) and Tier 6
(cloud adapters) to the existing iGPU runtime. This package re-exports the
new ABI and adapter types.
"""

from __future__ import annotations

from importlib import resources

from .abi import role_adjacency, role_from_consortium
from .adapters import ADAPTER_TABLE, promote_adapter


def kernel_source(name: str) -> str:
    """Return the source text of a packaged OpenCL kernel."""
    if not name.endswith(".cl") or "/" in name or "\\" in name:
        raise ValueError("kernel name must be a bare *.cl file name")
    return resources.files("chronus.kernels").joinpath(name).read_text(encoding="utf-8")


__all__ = [
    "role_from_consortium",
    "role_adjacency",
    "ADAPTER_TABLE",
    "promote_adapter",
    "kernel_source",
]