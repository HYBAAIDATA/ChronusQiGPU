"""
PYTHAGORAS — META-EVOLUTIONARY ENGINE
Self-improving evolution and structural resonance platform.

The engine is domain-agnostic. Domains are pluggable via the Domain ABC:
code (Python AST), circuit, molecule, market, network. Code was the first
domain — not the only one.
"""

from .phi_resonance import PhiResonanceCalculator, PHI
from .domain import Domain, resolve_domain
from .domains import (
    CodeDomain,
    CircuitDomain,
    MoleculeDomain,
    MarketDomain,
    NetworkDomain,
    available_domains,
    get_domain,
    register_domain,
)
from .cgp import CGP, CGPNode
from .pythagoras_mutation import PythagorasMutator, SurrogateFitnessModel
from .meta_evolution import MetaEvolutionController
from .auto_primitive import AutoPrimitiveDiscovery
from .geometry_evolution import GeometryEvolution
from .orchestrator import (
    Pythagoras,
    normalize_future_imports,
    read_source_utf8,
    write_source_utf8,
    safe_git_lock_recovery,
    run_isolated_execution,
    rolling_window_normalize,
)

__all__ = [
    "PHI",
    "PhiResonanceCalculator",
    "Domain",
    "resolve_domain",
    "CodeDomain",
    "CircuitDomain",
    "MoleculeDomain",
    "MarketDomain",
    "NetworkDomain",
    "available_domains",
    "get_domain",
    "register_domain",
    "CGP",
    "CGPNode",
    "PythagorasMutator",
    "SurrogateFitnessModel",
    "MetaEvolutionController",
    "AutoPrimitiveDiscovery",
    "GeometryEvolution",
    "Pythagoras",
    "normalize_future_imports",
    "read_source_utf8",
    "write_source_utf8",
    "safe_git_lock_recovery",
    "run_isolated_execution",
    "rolling_window_normalize",
]
