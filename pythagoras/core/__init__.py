"""Core mathematical services shipped through the PYTHAGORAS v12 boundary."""

from .euclid_intelligence import (
    PHI,
    PLASTIC_PISOT,
    EuclidIntelligenceEngine,
    LucasSequenceCalculator,
)
from .phi_metric import PHI_TARGET, PhiResonanceCalculator
from .primitives import ASTPrimitives
from .tononi_penrose import TononiPenroseSubstrate

__all__ = [
    "PHI",
    "PHI_TARGET",
    "PLASTIC_PISOT",
    "ASTPrimitives",
    "EuclidIntelligenceEngine",
    "LucasSequenceCalculator",
    "PhiResonanceCalculator",
    "TononiPenroseSubstrate",
]
