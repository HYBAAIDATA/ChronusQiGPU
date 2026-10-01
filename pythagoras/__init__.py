"""PYTHAGORAS v12 — meta-evolutionary computational intelligence substrate.

The engine remains domain-agnostic. v12 adds the complete EUCLID-owned
Intelligence boundary, shared multi-agent manifold, governance analytics and
Salamander transactional healing bridge without reviving superseded V6 files.
"""

from .phi_resonance import PHI, PhiResonanceCalculator
from .domain import Domain, resolve_domain
from .domains import (
    CircuitDomain,
    CodeDomain,
    MarketDomain,
    MoleculeDomain,
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
    rolling_window_normalize,
    run_isolated_execution,
    safe_git_lock_recovery,
    write_source_utf8,
)
from .core import (
    ASTPrimitives,
    EuclidIntelligenceEngine,
    LucasSequenceCalculator,
    TononiPenroseSubstrate,
)
from .adapter import PythagorasEngineAdapter
from .agents.manifold import AgentID, PayloadType, SharedEntangledManifold
from .agents.orchestrator import MultiAgentEntangledOrchestrator
from .enterprise.roi_governance import EnterpriseROIGovernanceEngine
from .healing import RepositoryHealingOrchestrator

__version__ = "12.0.0"

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
    "PythagorasEngineAdapter",
    "EuclidIntelligenceEngine",
    "LucasSequenceCalculator",
    "ASTPrimitives",
    "TononiPenroseSubstrate",
    "AgentID",
    "PayloadType",
    "SharedEntangledManifold",
    "MultiAgentEntangledOrchestrator",
    "EnterpriseROIGovernanceEngine",
    "RepositoryHealingOrchestrator",
    "normalize_future_imports",
    "read_source_utf8",
    "write_source_utf8",
    "safe_git_lock_recovery",
    "run_isolated_execution",
    "rolling_window_normalize",
]
