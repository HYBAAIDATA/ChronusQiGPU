"""Consciousness measurement and quantum-consciousness modelling.

Promoted from ``legacy/`` during the intelligence consolidation. These
modules are honest measurement layers: they report coherence / emergence
metrics computed from real state, and they degrade to declared stub mode
when an optional substrate (orchestrator, emergence probe) is absent.

- :class:`ConsciousnessEngine` — Phi-scaled emergence measurement with a
  declared consciousness threshold; no fabricated detection.
- :class:`QuantumConsciousnessSystem` — quantum-state-vector model of
  consciousness levels over the complex Hilbert space.
- :class:`EmergenceMetrics` — per-school activity accounting feeding the
  emergence coefficient used by the engine.
"""

from .consciousness_engine import ConsciousnessEngine
from .emergence_metrics import EmergenceMetrics, EmergenceSnapshot, SchoolActivity
from .quantum_consciousness_system import (
    ConsciousnessLevel,
    ConsciousnessStateVector,
    QuantumConsciousnessSystem,
    QuantumPattern,
    lucas_bound,
)

__all__ = [
    "ConsciousnessEngine",
    "ConsciousnessLevel",
    "ConsciousnessStateVector",
    "EmergenceMetrics",
    "EmergenceSnapshot",
    "QuantumConsciousnessSystem",
    "QuantumPattern",
    "SchoolActivity",
    "lucas_bound",
]
