# l_hras/intelligences/counterfactual.py

from dataclasses import dataclass
from typing import List
from l_hras.experimental.blueprint.intelligences.causal import CausalGraph

@dataclass
class Counterfactual:
    antecedent: str
    consequent: str
    probability: float
    evidence: List[str]

def counterfactual(graph: CausalGraph, intervention: str) -> Counterfactual:
    """Compute what would have happened."""
    # Simplified: propagate through the graph
    consequent = f"effect_of_{intervention}"
    return Counterfactual(
        antecedent=intervention,
        consequent=consequent,
        probability=0.5,
        evidence=[],
    )
