"""
HYBA_DATA Enterprise Platform Module

The complete stack — one offering:
  Layer 1: Data Residency (Sovereignty + Compliance)
  Layer 2: φ-GPU Scaling (Golden Ratio Hardware)
  Layer 3: Folded Memory (PULVINI Compression)
  Layer 4: Geodesic Search (Manifold Optimization)
  Layer 5: AI Training (At Scale)
  Layer 6: Quantum Engine (φ-Grover)
"""
from .complete_engine import (
    CompleteSovereigntyEngine,
    PlatformConfig,
    PlatformStatus,
    PlatformLayer,
)
from .roi import ROICalculator, ROIReport

__all__ = [
    "CompleteSovereigntyEngine",
    "PlatformConfig",
    "PlatformStatus",
    "PlatformLayer",
    "ROICalculator",
    "ROIReport",
]
