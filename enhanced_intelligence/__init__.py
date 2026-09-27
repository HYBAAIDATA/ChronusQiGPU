"""
HYBA SOFTWARE LTD
Core Intelligence Infrastructure
===============================
Author  : Andre Taylor-Morris, Founder & CEO
Date    : March 2026
Status  : Production Implementation

Ubiquitous Intelligence Architecture - Core Components
Every endpoint observes, reasons, acts, learns, and reports.
Intelligence IS the system.
"""

from .intelligent_endpoint import (
    AutonomyLevel,
    Decision,
    IntelligenceState,
    IntelligentEndpoint,
    LearningSignal,
    Observation,
)

PHI = 1.618033988749895

from .autonomy_governance import (
    HARD_LIMITS,
    get_autonomy_description,
    is_action_permitted,
    validate_autonomy_boundaries,
)
from .intelligence_bus import IntelligenceBus

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


def calculate_pure_quantum_intelligence(state=None, phi=1.618033988749895):
    """Stub bridge: compute quantum intelligence score from state vector."""
    if state is None:
        return {"phi": phi, "coherence": 1.0, "intelligence_quotient": phi**2}
    return {
        "phi": phi,
        "coherence": float(state.get("coherence", 1.0)),
        "intelligence_quotient": phi**2,
    }
