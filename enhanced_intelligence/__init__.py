"""
HYBA SOFTWARE LTD
Core Intelligence Infrastructure
===============================
Author  : Andre Taylor-Morris, Founder & CEO
Date    : March 2026

Ubiquitous Intelligence Architecture — canonical facade.

Consolidated: the three modules this package originally declared as local
submodules — ``intelligent_endpoint``, ``autonomy_governance`` and
``intelligence_bus`` — are canonically owned by the top-level ``Intelligence``
package. This package is now the stable public facade over them, so callers
keep one import path for the ubiquitous-intelligence surface regardless of
where the implementation lives.
"""

from Intelligence.autonomy_governance import (
    HARD_LIMITS,
    get_autonomy_description,
    is_action_permitted,
    validate_autonomy_boundaries,
)
from Intelligence.intelligence_bus import IntelligenceBus
from Intelligence.intelligent_endpoint import (
    AutonomyLevel,
    Decision,
    IntelligentEndpoint,
    IntelligenceState,
    LearningSignal,
    Observation,
)

PHI = 1.618033988749895

__all__ = [
    # Core classes
    "IntelligentEndpoint",
    "IntelligenceBus",
    # Enums
    "AutonomyLevel",
    "IntelligenceState",
    # Data structures
    "Observation",
    "Decision",
    "LearningSignal",
    # Constants
    "PHI",
    # Governance
    "HARD_LIMITS",
    "is_action_permitted",
    "get_autonomy_description",
    "validate_autonomy_boundaries",
]


def calculate_pure_quantum_intelligence(state=None, phi=PHI):
    """Report the φ-derived intelligence quotient for a measured state.

    ``coherence`` is read from ``state`` when supplied and defaults to 1.0.
    The quotient itself is the fixed identity ``φ²`` — it is a named
    statistic, not a measurement of consciousness.
    """
    if state is None:
        return {"phi": phi, "coherence": 1.0, "intelligence_quotient": phi**2}
    return {
        "phi": phi,
        "coherence": float(state.get("coherence", 1.0)),
        "intelligence_quotient": phi**2,
    }
