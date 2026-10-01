# l_hras/modes/entangle.py

from l_hras.experimental.blueprint.intelligences.entangled import entangle, EntangledIntelligence, IntelligenceType
from typing import Set

def entangle_all(intelligences: Set[IntelligenceType]) -> EntangledIntelligence:
    """All intelligence is connected via entanglement."""
    return entangle(intelligences)
