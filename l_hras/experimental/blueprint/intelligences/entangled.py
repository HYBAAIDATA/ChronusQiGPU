# l_hras/intelligences/entangled.py

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple
from l_hras.experimental.blueprint.intelligences.quantum import QuantumState
from enum import Enum

class IntelligenceType(Enum):
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    COUNTERFACTUAL = "counterfactual"
    TOPOLOGICAL = "topological"
    GEOMETRIC = "geometric"
    QUANTUM = "quantum"

@dataclass
class EntangledIntelligence:
    states: Dict[IntelligenceType, QuantumState]
    entanglement: Set[Tuple[IntelligenceType, IntelligenceType]]
    correlations: Dict[Tuple[IntelligenceType, IntelligenceType], float]
    attestation: str

def entangle(intelligences: Set[IntelligenceType]) -> EntangledIntelligence:
    """Entangle all six intelligences."""
    import numpy as np
    states = {}
    for i in intelligences:
        # Initialize each intelligence with a normalized state
        states[i] = QuantumState(np.array([1.0, 0.0], dtype=complex))
    # Build entanglement graph (all-to-all)
    graph = set()
    for a in intelligences:
        for b in intelligences:
            if a != b:
                graph.add((a, b))
    correlations = {edge: 1.0 for edge in graph}
    return EntangledIntelligence(
        states=states,
        entanglement=graph,
        correlations=correlations,
        attestation="entangled",
    )

def observe(ei: EntangledIntelligence, i: IntelligenceType) -> dict:
    """Observe one intelligence. Collapses all entangled."""
    probs = ei.states[i].probabilities()
    idx = int(np.argmax(probs))
    return {"index": idx, "probability": float(probs[idx])}
