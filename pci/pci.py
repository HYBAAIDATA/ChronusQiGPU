"""Legacy import shim for PCI classes.

The canonical home is :mod:`pci.engine`. The previous spelling
(``src.hyba_quantum.algorithms.pci``) only resolved while
:mod:`hyba_compat` was installed; importing the canonical module directly
keeps this shim self-contained.
"""

from pci.engine import (
    CausalMode,
    CausalPrediction,
    CausalRelationship,
    PredictiveCausalIntelligence,
    VirtualQuantumComputer,
    create_predictive_causal_intelligence,
)

__all__ = [
    "CausalMode",
    "CausalPrediction",
    "CausalRelationship",
    "PredictiveCausalIntelligence",
    "VirtualQuantumComputer",
    "create_predictive_causal_intelligence",
]
