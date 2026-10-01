# l_hras/intelligences/causal.py

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CausalEdge:
    cause: str
    effect: str
    strength: float
    confidence: float

@dataclass
class CausalGraph:
    nodes: List[str] = field(default_factory=list)
    edges: List[CausalEdge] = field(default_factory=list)

@dataclass
class CausalExplanation:
    observation: str
    causes: List[CausalEdge]
    root_cause: Optional[CausalEdge]
    confidence: float

def causal_infer(graph: CausalGraph, observation: str) -> CausalExplanation:
    """Infer the cause of the observation."""
    causes = [e for e in graph.edges if e.effect == observation]
    ranked = sorted(causes, key=lambda e: e.strength * e.confidence, reverse=True)
    return CausalExplanation(
        observation=observation,
        causes=ranked,
        root_cause=ranked[0] if ranked else None,
        confidence=ranked[0].confidence if ranked else 0.0,
    )
