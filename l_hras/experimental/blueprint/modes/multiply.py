# l_hras/modes/multiply.py

import numpy as np
from dataclasses import dataclass
from typing import List
from l_hras.experimental.blueprint.intelligences.entangled import EntangledIntelligence, IntelligenceType

@dataclass
class Multiplication:
    vectors: List[np.ndarray]
    combined: np.ndarray
    cardinality: int
    attestation: str

def multiply(ei: EntangledIntelligence) -> Multiplication:
    """When we attack, we multiply."""
    vectors = []
    for i, state in ei.states.items():
        vectors.append(state.amplitudes)
    # Tensor product
    combined = vectors[0]
    for v in vectors[1:]:
        combined = np.kron(combined, v)
    return Multiplication(
        vectors=vectors,
        combined=combined,
        cardinality=len(vectors) ** len(ei.states),
        attestation="multiplied",
    )
