"""
HYBA_DATA Quantum Module — Quantum Error Correction & Quantum Primitives.

Implements:
- Surface code QEC (9-qubit, distance-3)
- Steane code QEC (7-qubit, CSS)
- Bit-flip and phase-flip repetition codes
- Syndrome measurement and error detection
- Error correction with manifold-aware decoding
- Integration with phi-resonance for optimized decoding

Author: HYBA Software Ltd
Version: 9.0.0
"""
from .qec import (
    SurfaceCode, SteaneCode, BitFlipCode, PhaseFlipCode,
    SyndromeResult, ErrorCorrectionResult,
    QECIntegrator,
)
__all__ = [
    "SurfaceCode", "SteaneCode", "BitFlipCode", "PhaseFlipCode",
    "SyndromeResult", "ErrorCorrectionResult", "QECIntegrator",
]
