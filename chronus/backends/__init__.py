"""Declared Chronus execution backends (plugin surface).

Every backend exposes ``probe() -> dict`` and ``execute(op, payload)``. The
contract module ``chronus.backend`` dispatches to these plugins. Nothing here
imports a backend library at contract-load time, and the contract layer never
imports pyopencl / libmla1517_mmio / azure SDKs.
"""
from __future__ import annotations

__all__ = [
    "cpu_reference",
    "opencl_igpu",
    "mla1517_mmio",
    "remote",
]
