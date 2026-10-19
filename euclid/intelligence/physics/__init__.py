"""EUCLID Unified Intelligence — Physics & Physical Simulation Submodule."""
from __future__ import annotations

from typing import Any
import Intelligence.physics as _physics

__all__ = [
    "first_principles_quantum",
    "quantum_algorithms",
    "pde_substrate",
    "lucas_scales",
    "poincare_cassini_search",
    "mining_native",
    "agentic_mining",
    "get_toe_bridge",
    "get_toe_machine",
]


def __getattr__(name: str) -> Any:
    return getattr(_physics, name)


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(dir(_physics)))
