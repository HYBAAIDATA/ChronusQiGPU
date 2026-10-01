"""Production PYTHAGORAS engine surface.

Only version-neutral production components are exported. Historical staged V6 module
names are deliberately unsupported so stale dependencies fail loudly during validation.
"""

from .evolution import AnnealingConfig, PythagorasEvolutionEngine
from .geometry import CGPGeometryState, CollectiveGeometryCoordinator
from .primitive_discovery import DiscoveredPrimitiveCandidate, PrimitiveDiscoveryEngine
from .primitive_repository import CrossFilePrimitiveRepository
from .surrogate import NeuralSurrogateEvaluator

__all__ = [
    "AnnealingConfig",
    "PythagorasEvolutionEngine",
    "CGPGeometryState",
    "CollectiveGeometryCoordinator",
    "DiscoveredPrimitiveCandidate",
    "PrimitiveDiscoveryEngine",
    "CrossFilePrimitiveRepository",
    "NeuralSurrogateEvaluator",
]
