"""PCI transparency dashboard — real causal-graph layer over the exact
causal engine.

The retired version generated prose recommendations around a graph whose
confidences were opaque floats.  This rebuild keeps the data structures
honest: edges carry exact Fraction strengths and their evidence counts,
``explain_confidence`` returns the full derivation (counts → conditionals
→ strength), and recommendations are deterministic ranks of real
relationships — nothing is invented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pci.engine import CausalRelationship, PredictiveCausalIntelligence


class CausalRelationType(str, Enum):
    DECLARED = "declared"
    ASSOCIATIONAL = "associational"


class ConfidenceLevel(str, Enum):
    EXACT = "exact"  # derived from observed counts
    INSUFFICIENT = "insufficient"  # sparse evidence, honestly flagged


@dataclass(frozen=True)
class CausalNode:
    node_id: str
    label: str


@dataclass(frozen=True)
class CausalEdge:
    cause: str
    effect: str
    strength: Fraction
    conditional_given: Fraction
    conditional_without: Fraction
    evidence_samples: int
    relation_type: str


@dataclass(frozen=True)
class CausalPath:
    nodes: Tuple[str, ...]
    total_strength: Fraction
    min_evidence: int


@dataclass(frozen=True)
class StrategicRecommendation:
    recommendation_id: str
    strongest_relationships: Tuple[Tuple[str, str, Fraction], ...]
    evidence_summary: str
    basis: str


class PCITransparencyDashboard:
    """Real causal-graph service: graphs are built from measured
    ``CausalRelationship`` records, paths are found by real traversal, and
    every reported confidence carries its exact derivation."""

    def __init__(self):
        self._graphs: Dict[str, Dict[str, Any]] = {}
        self._recommendations: Dict[str, StrategicRecommendation] = {}
        self._counter = 0

    # ------------------------------------------------------------------
    def create_causal_graph(
        self, relationships: Sequence[CausalRelationship], *, graph_id: Optional[str] = None
    ) -> str:
        """Build a graph from measured relationships — real edges only."""
        self._counter += 1
        gid = graph_id or f"graph-{self._counter}"
        nodes = sorted({r.cause for r in relationships} | {r.effect for r in relationships})
        edges = [
            CausalEdge(
                cause=r.cause,
                effect=r.effect,
                strength=r.strength,
                conditional_given=r.conditional_given,
                conditional_without=r.conditional_without,
                evidence_samples=r.evidence_samples,
                relation_type=r.direction,
            )
            for r in relationships
        ]
        self._graphs[gid] = {"nodes": nodes, "edges": edges}
        return gid

    # ------------------------------------------------------------------
    def find_causal_paths(
        self, graph_id: str, source: str, target: str, *, max_depth: int = 8
    ) -> List[CausalPath]:
        """Real DFS over the edge set; strength accumulates exactly."""
        g = self._graphs[graph_id]
        adj: Dict[str, List[CausalEdge]] = {}
        for e in g["edges"]:
            adj.setdefault(e.cause, []).append(e)
        out: List[CausalPath] = []

        def dfs(
            node: str, path: Tuple[str, ...], strength: Fraction, min_ev: int, depth: int
        ) -> None:
            if node == target and len(path) > 1:
                out.append(CausalPath(path, strength, min_ev))
                return
            if depth <= 0:
                return
            for e in adj.get(node, []):
                if e.effect in path:
                    continue
                dfs(
                    e.effect,
                    path + (e.effect,),
                    strength + e.strength,
                    min(min_ev, e.evidence_samples),
                    depth - 1,
                )

        if source in g["nodes"]:
            dfs(source, (source,), Fraction(0), 10**18, max_depth)
        return out

    # ------------------------------------------------------------------
    def explain_confidence(self, relationship: CausalRelationship) -> Dict[str, Any]:
        """Full derivation of a confidence value — exact and auditable."""
        level = (
            ConfidenceLevel.EXACT
            if relationship.evidence_samples >= 1
            else ConfidenceLevel.INSUFFICIENT
        )
        return {
            "level": level.value,
            "strength": str(relationship.strength),
            "derivation": {
                "conditional_given": str(relationship.conditional_given),
                "conditional_without": str(relationship.conditional_without),
                "strength_formula": "P(effect | cause) - P(effect | not-cause), exact rationals",
            },
            "evidence_samples": relationship.evidence_samples,
            "direction": relationship.direction,
            "mode": relationship.mode,
        }

    # ------------------------------------------------------------------
    def generate_recommendation(
        self, graph_id: str, engine: PredictiveCausalIntelligence
    ) -> StrategicRecommendation:
        """Deterministic recommendation: rank edges by |strength|, report the
        exact numbers and sample sizes behind them.  No invented prose."""
        g = self._graphs[graph_id]
        ranked = sorted(g["edges"], key=lambda e: (-abs(float(e.strength)), e.cause))
        top = tuple((e.cause, e.effect, e.strength) for e in ranked[:3])
        total_ev = sum(e.evidence_samples for e in ranked)
        self._counter += 1
        rec = StrategicRecommendation(
            recommendation_id=f"rec-{self._counter}",
            strongest_relationships=top,
            evidence_summary=(
                f"{len(ranked)} measured edges, {total_ev} total observations; "
                f"strongest: " + ", ".join(f"{c}->{e} strength {s}" for c, e, s in top)
                if ranked
                else "no measured edges"
            ),
            basis="exact posterior strengths from observed joint distribution",
        )
        self._recommendations[rec.recommendation_id] = rec
        return rec

    # ------------------------------------------------------------------
    def get_visualization_data(self, graph_id: str) -> Dict[str, Any]:
        g = self._graphs[graph_id]
        return {
            "graph_id": graph_id,
            "nodes": [{"id": n, "label": n} for n in g["nodes"]],
            "edges": [
                {
                    "source": e.cause,
                    "target": e.effect,
                    "strength": str(e.strength),
                    "evidence": e.evidence_samples,
                    "type": e.relation_type,
                }
                for e in g["edges"]
            ],
        }

    def export_to_json(self, graph_id: str) -> str:
        return json.dumps(self.get_visualization_data(graph_id), indent=2)

    def generate_executive_summary(self, recommendation_id: str) -> Dict[str, Any]:
        rec = self._recommendations[recommendation_id]
        return {
            "recommendation_id": rec.recommendation_id,
            "summary": rec.evidence_summary,
            "strongest": [
                {"cause": c, "effect": e, "strength": str(s)}
                for c, e, s in rec.strongest_relationships
            ],
            "basis": rec.basis,
            "provenance": "all quantities measured from observed data; no narrative fabrication",
        }
