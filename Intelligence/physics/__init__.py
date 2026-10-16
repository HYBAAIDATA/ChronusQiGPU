"""EUCLID Unified Intelligence — Physics & Physical Simulation Subdomain.

Consolidates TOE (Theory of Everything) physical models, exact first-principles
quantum operators, Lucas metallic walks, and hardware/iGPU dispatch planes.
"""
from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    # Quantum & Mathematical Substrate
    "first_principles_quantum",
    "quantum_algorithms",
    "pde_substrate",
    # Lucas Metallic Walk & Geodesic Trajectories
    "lucas_scales",
    "poincare_cassini_search",
    # Physical Simulation & Mining
    "mining_native",
    "agentic_mining",
    # TOE Solvers & Bridges
    "get_toe_bridge",
    "get_toe_machine",
]

_SUBMODULE_MAP = {
    "first_principles_quantum": "Intelligence.first_principles_quantum",
    "quantum_algorithms": "Intelligence.quantum_algorithms",
    "pde_substrate": "Intelligence.pde_substrate",
    "lucas_scales": "Intelligence.lucas_scales",
    "poincare_cassini_search": "Intelligence.poincare_cassini_search",
    "mining_native": "Intelligence.mining_native",
    "agentic_mining": "Intelligence.agentic_mining",
}


def get_toe_bridge():
    """Return canonical TOE bridge creator."""
    from toe.bridge import create_toe_bridge
    return create_toe_bridge


def get_toe_machine():
    """Return canonical TOE machine constructor."""
    from toe.machine import TOEMachine
    return TOEMachine


def __getattr__(name: str) -> Any:
    if name in _SUBMODULE_MAP:
        return importlib.import_module(_SUBMODULE_MAP[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
