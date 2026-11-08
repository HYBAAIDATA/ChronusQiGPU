"""
Chronus Quantum iGPU Package
"""
from .core import ChronusVerificationOrchestrator
from .config import ChronusConfig
from .ns_dec import NavierStokesDECFluidRouter

__version__ = "36.0.0"
__all__ = ["ChronusVerificationOrchestrator", "ChronusConfig", "NavierStokesDECFluidRouter"]
