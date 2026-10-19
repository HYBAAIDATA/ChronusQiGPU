"""Lucas pool registry — the only legal shared import for algorithms.

Seven kernels. No more, no fewer:
  mining_kernel, step_kernel, path_kernel, gap_kernel, trace_kernel,
  amplitude_kernel, folded_kernel.
"""

from __future__ import annotations

from typing import Any, Callable

from .bound import (
    amplitude_kernel,
    folded_kernel,
    gap_kernel,
    mining_kernel,
    path_kernel,
    step_kernel,
)
from .trace import trace_kernel

Kernel = Callable[..., dict[str, Any]]

THEOREM_PROVEN = False

_POOL: dict[str, Kernel] = {
    "trace_kernel": trace_kernel,
    "path_kernel": path_kernel,
    "gap_kernel": gap_kernel,
    "amplitude_kernel": amplitude_kernel,
    "step_kernel": step_kernel,
    "mining_kernel": mining_kernel,
    "folded_kernel": folded_kernel,
}


def get(name: str) -> Kernel:
    """Return a kernel by name. Raises KeyError for unknown kernels."""
    if name not in _POOL:
        raise KeyError(f"Unknown Lucas kernel '{name}'. Available: {list(_POOL)}")
    return _POOL[name]


def register(name: str, kernel: Kernel) -> None:
    """Register a new kernel in the pool. Rejects duplicate names."""
    if name in _POOL:
        raise ValueError(f"Lucas kernel '{name}' is already registered")
    _POOL[name] = kernel


def available() -> list[str]:
    """List available kernel names."""
    return sorted(_POOL.keys())


def __dir__() -> list[str]:
    return ["get", "register", "available"]
