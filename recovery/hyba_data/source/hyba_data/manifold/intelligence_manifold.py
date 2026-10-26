"""Six-dimensional intelligence manifold for code-structure analysis.

The manifold is a deterministic mathematical audit surface over code topology.
It provides predictive, causal, counterfactual, topological, geometric, and
quantum signals. The quantum dimension is wired to
quantum_core.phi_resonance_gate and is a classical unitary-approximation
simulation of a phi-resonance quantum gate (no physical quantum hardware
execution); it fails closed to a neutral reading if the quantum core module
is unavailable. This module makes no claim of autonomous source edits.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PHI = (1.0 + math.sqrt(5.0)) / 2.0

# Wire the repo-root quantum_core package so the manifold's quantum dimension
# can import quantum_core.phi_resonance_gate. MIDAS uses a flat layout (no
# python_backend wrapper), so the repo root is two levels up from this file:
# hyba_genesis_api/core/intelligence_manifold.py -> hyba_genesis_api -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@dataclass(frozen=True)
class ManifoldTelemetry:
    """Bounded six-dimensional telemetry for a code topology observation."""

    predictive_free_energy: float
    causal_impact: float
    counterfactual_possible: bool
    euler_characteristic: int
    topological_genus_proxy: int
    fisher_curvature: float
    geometric_stability: float
    ricci_flow_curvature: float
    quantum_resonance_gap: float
    quantum_coherence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ManifoldStabilizer:
    """Prevent Ricci-flow collapse with a Perelman W-entropy proxy."""

    def preserve_volume(
        self, current_curvature: float, complexity_density: float
    ) -> float:
        """Apply a volume-preserving bias to curvature smoothing."""

        volume_bias = math.log(max(float(complexity_density), 0.0) + 1.1)
        return float(max(0.0, current_curvature) + (0.005 * volume_bias))


class IntelligenceManifold:
    """Compute a 6-D intelligence surface over code topology, weights, and quantum resonance."""

    PHI = PHI

    def __init__(self) -> None:
        self.causal_graph: Dict[str, List[str]] = {}
        self.state_history: List[float] = []
        self.stabilizer = ManifoldStabilizer()

    def update_causal_graph(self, edges: Iterable[Tuple[str, str]]) -> None:
        """Load directed dependencies as Function -> Dependencies."""

        graph: Dict[str, List[str]] = {}
        for source, target in edges:
            graph.setdefault(source, [])
            graph.setdefault(target, [])
            graph[source].append(target)
        self.causal_graph = {
            node: sorted(set(targets)) for node, targets in graph.items()
        }

    def calculate_fisher_curvature(self, weights: Sequence[float]) -> float:
        """Approximate Fisher curvature using coefficient of variation."""

        positive = [
            abs(float(weight)) for weight in weights if math.isfinite(float(weight))
        ]
        if not positive:
            return 0.0
        mean = sum(positive) / len(positive)
        if mean == 0.0:
            return 0.0
        variance = sum((weight - mean) ** 2 for weight in positive) / len(positive)
        return float(math.sqrt(variance) / mean)

    def calculate_ricci_flow(
        self, curvature: float, step_size: float | None = None
    ) -> float:
        """Smooth high-curvature logic toward a flatter explanation manifold."""

        configured_step = (
            float(os.getenv("HYBA_RICCI_STEP_SIZE", "0.01"))
            if step_size is None
            else step_size
        )
        bounded_step = max(0.0, min(0.5, float(configured_step)))
        smoothed = float(max(0.0, float(curvature)) * (1.0 - (2.0 * bounded_step)))
        return self.stabilizer.preserve_volume(
            smoothed, complexity_density=max(curvature, 0.0)
        )

    def compute_euler_characteristic(
        self, nodes: int, edges: int, faces: int = 1
    ) -> int:
        """Return χ = V - E + F for a simplified AST/call-graph surface."""

        return int(nodes) - int(edges) + int(faces)

    def infer_causal_impact(self, node_id: str) -> float:
        """Deterministic Pearlian do(node removed) hub proxy from outgoing degree."""

        return float(len(self.causal_graph.get(node_id, [])) * self.PHI)

    def identify_critical_functions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return high-impact causal hubs sorted by deterministic impact."""

        hubs = [
            {
                "node_id": node_id,
                "causal_impact": round(self.infer_causal_impact(node_id), 6),
            }
            for node_id in self.causal_graph
        ]
        return sorted(hubs, key=lambda item: (-item["causal_impact"], item["node_id"]))[
            :limit
        ]

    def check_task_possibility(
        self, current_logic: str, target_transformation: str
    ) -> bool:
        """Constructor-theory proxy: can the target symbols be composed now?"""

        if not target_transformation:
            return True
        available = set(current_logic)
        return all(char in available for char in target_transformation)

    def compute_quantum_resonance(
        self, weights: Optional[Sequence[float]] = None
    ) -> Dict[str, float]:
        """Sixth (quantum) manifold dimension via quantum_core.phi_resonance_gate.

        Classically simulates a phi-resonance quantum gate projection (a
        unitary approximation, not physical quantum hardware) to produce a
        resonance gap and coherence score. Fails closed to a neutral reading
        if the quantum core module cannot be imported or evaluated.
        """

        try:
            from quantum_core.phi_resonance_gate import manifold_projection_state

            sample = [float(w) for w in (weights or self.state_history or [1.0])]
            num_qubits = max(1, min(4, len(sample)))
            qc = SimpleNamespace(num_qubits=num_qubits)
            projection = manifold_projection_state(qc, steps=3, phi=self.PHI)
            gap = float(projection["manifold_gap"])
            coherence = 1.0 / (1.0 + gap)
            return {
                "quantum_resonance_gap": round(gap, 6),
                "quantum_coherence": round(coherence, 6),
            }
        except Exception:
            return {"quantum_resonance_gap": 0.0, "quantum_coherence": 0.0}

    def synthesize(
        self,
        *,
        nodes: int,
        edges: int,
        weights: Sequence[float],
        current_logic: str,
        target_transformation: str,
        observed_phi: float,
        predicted_phi: float,
    ) -> ManifoldTelemetry:
        """Compute all six dimensions into a single auditable telemetry object."""

        curvature = self.calculate_fisher_curvature(weights)
        chi = self.compute_euler_characteristic(nodes, edges)
        genus_proxy = 1 - chi
        possible = self.check_task_possibility(current_logic, target_transformation)
        free_energy = abs(float(observed_phi) - float(predicted_phi)) + math.log(
            max(float(observed_phi), 0.0) + 1.1
        )
        max_impact = max(
            (self.infer_causal_impact(node_id) for node_id in self.causal_graph),
            default=0.0,
        )
        stability = 1.0 / (1.0 + curvature)
        ricci_curvature = self.calculate_ricci_flow(curvature)
        quantum_metrics = self.compute_quantum_resonance(weights)
        telemetry = ManifoldTelemetry(
            predictive_free_energy=round(max(0.0, free_energy), 6),
            causal_impact=round(max_impact, 6),
            counterfactual_possible=possible,
            euler_characteristic=chi,
            topological_genus_proxy=genus_proxy,
            fisher_curvature=round(curvature, 6),
            geometric_stability=round(stability, 6),
            ricci_flow_curvature=round(ricci_curvature, 6),
            quantum_resonance_gap=quantum_metrics["quantum_resonance_gap"],
            quantum_coherence=quantum_metrics["quantum_coherence"],
        )
        self.state_history.append(telemetry.geometric_stability)
        return telemetry


class ManifoldEngine(IntelligenceManifold):
    """Compatibility alias for production manifold integrations."""

    def ricci_flow_smoothing(self, curvature: float, volume: float) -> float:
        smoothed = self.calculate_ricci_flow(curvature)
        return self.stabilizer.preserve_volume(smoothed, volume)
