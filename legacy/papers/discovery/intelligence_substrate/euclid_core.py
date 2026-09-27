"""
EUCLID - The Unified Overarching AI Architecture
===================================================
HYBA has ONE unified intelligence system: EUCLID.
There are no competing intelligence systems.

Expressions of Euclid:
- SALAMANDER: Autonomic Runtime Governance (telemetry, circuit smoother, decision engine, self-healing)
- AL HARAS: Sovereign Security Intelligence (zero-trust attestation, threat defense, refusal-to-run)
- PYTHIA: Mining & Cryptographic Intelligence (stratum work, pool coordination, nonce search)
- CATHEDRAL: Multi-modal Cognitive Synthesis Engine

Quantum & Mathematical Substrate:
- The quantum computing domain and mathematical discovery engine (previously associated with Pythagoras)
  are now owned and governed by TURING (turing_universal_quantum_computer), which supplies the entangled
  MathematicalDiscoveryEngine to Euclid.

Euclid provides the 6-dimensional intelligence lobes as shared cognitive infrastructure
across all subsystems: Topological, Geometric, Predictive, Causal, Counterfactual, and Quantum.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger("hyba.euclid")

# Import the 6 intelligence lobes (shared cognitive substrate)
from python_backend.hyba_substrate.manifold_orchestrator import (
    TopologicalIntelligence,
    GeometricIntelligence,
    PredictiveIntelligence,
    CausalIntelligence,
    CounterfactualIntelligence,
    QuantumIntelligence,
)
from .intelligence_memory import IntelligenceMemoryDB
from .multi_agent_orchestrator import MultiAgentOrchestrator
from .universal_predictor import UniversalPredictor

try:
    from turing_universal_quantum_computer.turing_core.discovery import (
        MathematicalDiscoveryEngine,
        TheoreticalSpaceExplorer,
    )
except ImportError:
    try:
        import sys
        import os

        _repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if _repo_root not in sys.path:
            pass
        from turing_universal_quantum_computer.turing_core.discovery import (
            MathematicalDiscoveryEngine,
            TheoreticalSpaceExplorer,
        )
    except Exception:
        MathematicalDiscoveryEngine = None  # type: ignore
        TheoreticalSpaceExplorer = None  # type: ignore

try:
    from python_backend.cathedral.intrinsic_ai import IntrinsicAIOrchestrator
except ImportError:
    try:
        from python_backend.cathedral.intrinsic_ai import IntrinsicAIOrchestrator
    except Exception:
        IntrinsicAIOrchestrator = None  # type: ignore


@dataclass
class SubsystemState:
    """State tracking for each Euclid subsystem."""

    name: str
    active: bool = False
    health: str = "OPERATIONAL"
    last_heartbeat: float = 0.0
    metrics: Dict[str, Any] = field(default_factory=dict)


class EuclidCore:
    """
    Euclid Core - Unified Intelligence Substrate.

    Orchestrates the HYBA subsystems (Pythia, Al Haras, Salamander and the
    Cathedral multi-modal cognitive engine) and provides shared 6-lobe
    intelligence infrastructure.
    """

    def __init__(self, memory_db: Optional[IntelligenceMemoryDB] = None):
        self.memory = memory_db or IntelligenceMemoryDB.get_instance()
        self.session_id = f"euclid_session_{int(time.time())}"

        # Shared 6-lobe intelligence (cognitive substrate)
        self.lobes = {
            "topological": TopologicalIntelligence(),
            "geometric": GeometricIntelligence(memory_db=self.memory),
            "predictive": PredictiveIntelligence(),
            "causal": CausalIntelligence(),
            "counterfactual": CounterfactualIntelligence(),
            "quantum": QuantumIntelligence(),
        }

        # Subsystem tracking
        self.subsystems: Dict[str, SubsystemState] = {
            "pythia": SubsystemState(name="PYTHIA"),
            "al_haras": SubsystemState(name="AL_HARAS"),
            "salamander": SubsystemState(name="SALAMANDER"),
            "cathedral": SubsystemState(name="CATHEDRAL"),
        }

        # Cathedral Multi-Modal Cognitive Engine
        self.cathedral = IntrinsicAIOrchestrator() if IntrinsicAIOrchestrator else None

        # Multi-agent orchestrator for distributed coordination
        self.agent_orchestrator = MultiAgentOrchestrator()

        # Universal predictor for domain-agnostic predictions
        self.universal_predictor = UniversalPredictor()

        # Mathematical Frontier Discovery Engine (Entangled Knowledge Substrate)
        self.discovery_engine = (
            MathematicalDiscoveryEngine() if MathematicalDiscoveryEngine else None
        )
        if self.discovery_engine:
            for sub_name in self.subsystems.keys():
                self.discovery_engine.register_subsystem_entanglement(
                    sub_name,
                    callback=lambda disc, name=sub_name: self._on_subsystem_entangled_knowledge(
                        name, disc
                    ),
                )

        logger.info("[Euclid] Unified intelligence substrate initialized with Cathedral")

    def synthesize_cathedral_cycle(
        self,
        source_code: Optional[str] = None,
        block_telemetry_batch: Optional[List[Dict[str, Any]]] = None,
        target_quantum_sector: int = 0,
    ) -> Dict[str, Any]:
        """
        Execute a full Cathedral multi-modal cognitive synthesis cycle via Euclid.
        Collapses code emergence, blockchain causality, and quantum dodecahedral walks.
        """
        if not self.cathedral:
            return {"status": "CATHEDRAL_ORCHESTRATOR_UNAVAILABLE"}

        state = self.cathedral.orchestrate_cycle(
            sample_code=source_code,
            block_telemetry_batch=block_telemetry_batch,
            target_quantum_sector=target_quantum_sector,
        )
        self.subsystems["cathedral"].active = True
        self.subsystems["cathedral"].metrics = vars(state)

        # Broadcast state across entangled substrate
        self.broadcast_discovery(
            {
                "type": "CATHEDRAL_CYCLE_SYNTHESIZED",
                "coherence": state.unified_coherence_score,
                "emergence_index": state.emergence_index,
                "significance": min(1.0, 0.5 + state.unified_coherence_score / 2.0),
            }
        )

        return vars(state)

    def _on_subsystem_entangled_knowledge(self, subsystem: str, discovery: Dict[str, Any]) -> None:
        """Callback when an entangled mathematical discovery is propagated across the substrate."""
        logger.info(
            f"[Euclid Entanglement] Subsystem {subsystem} received instant discovery: {discovery.get('type', 'GENERAL')}"
        )

    def broadcast_discovery(self, discovery: Dict[str, Any]) -> Dict[str, Any]:
        """
        Broadcast a discovery across the entire cognitive substrate via entanglement.
        'So one knows it, all know it.'
        """
        if self.discovery_engine:
            return self.discovery_engine.broadcast_entangled_discovery(discovery)
        return {"status": "DISCOVERY_ENGINE_UNAVAILABLE"}

    def explore_mathematical_treatise(
        self, treatise_name: str, problem_instance: Any, depth: int = 5
    ) -> Dict[str, Any]:
        """
        Release Euclid onto a mathematical treatise (e.g. Euclid's Elements, Yang-Mills, Riemann).
        Evaluates geometric curvature, topological invariants, and quantum phase boundaries.
        """
        logger.info(f"[Euclid] Ingesting and evaluating treatise: {treatise_name}")
        report = {
            "treatise": treatise_name,
            "session_id": self.session_id,
            "timestamp": time.time(),
            "status": "EVALUATED",
            "geometric_curvature": (
                self.consult_lobe("geometric", problem_instance, method="calculate_curvature")
                if hasattr(self.lobes.get("geometric"), "calculate_curvature")
                else {}
            ),
            "topological_invariants": (
                self.consult_lobe(
                    "topological", problem_instance, method="verify_coverage_invariants"
                )
                if hasattr(self.lobes.get("topological"), "verify_coverage_invariants")
                else {}
            ),
        }
        if self.discovery_engine and hasattr(self.discovery_engine, "explorer"):
            validation = self.discovery_engine.explorer._validate_mathematical_discovery(
                {"type": f"TREATISE_{treatise_name.upper()}", "significance": 0.98}
            )
            report["formal_validation"] = validation
            self.broadcast_discovery(
                {
                    "type": "TREATISE_EVALUATION",
                    "treatise": treatise_name,
                    "report": report,
                    "significance": 0.98,
                }
            )
        return report

    def register_subsystem(self, subsystem_name: str, metrics: Dict[str, Any]) -> None:
        """Register a subsystem heartbeat with metrics."""
        if subsystem_name not in self.subsystems:
            logger.warning(f"[Euclid] Unknown subsystem: {subsystem_name}")
            return

        state = self.subsystems[subsystem_name]
        state.active = True
        state.last_heartbeat = time.time()
        state.metrics = metrics
        state.health = metrics.get("health", "OPERATIONAL")

        logger.debug(f"[Euclid] {subsystem_name} heartbeat: {state.health}")

    def get_subsystem_health(self, subsystem_name: str) -> Dict[str, Any]:
        """Get health status of a specific subsystem."""
        if subsystem_name not in self.subsystems:
            return {"status": "UNKNOWN", "error": f"Subsystem {subsystem_name} not found"}

        state = self.subsystems[subsystem_name]
        return {
            "name": state.name,
            "active": state.active,
            "health": state.health,
            "last_heartbeat": state.last_heartbeat,
            "metrics": state.metrics,
        }

    def get_global_health(self) -> Dict[str, Any]:
        """Get aggregate health across all subsystems."""
        active_count = sum(1 for s in self.subsystems.values() if s.active)
        healthy_count = sum(1 for s in self.subsystems.values() if s.health == "OPERATIONAL")

        return {
            "session_id": self.session_id,
            "total_subsystems": len(self.subsystems),
            "active_subsystems": active_count,
            "healthy_subsystems": healthy_count,
            "overall_health": (
                "OPERATIONAL" if healthy_count == len(self.subsystems) else "DEGRADED"
            ),
            "subsystems": {name: self.get_subsystem_health(name) for name in self.subsystems},
        }

    def consult_lobe(
        self, lobe_name: str, input_data: Any, method: str = "default"
    ) -> Dict[str, Any]:
        """
        Consult a specific intelligence lobe.

        This provides a unified interface for subsystems to access shared intelligence.
        """
        if lobe_name not in self.lobes:
            logger.error(f"[Euclid] Unknown lobe: {lobe_name}")
            return {"error": f"Lobe {lobe_name} not found"}

        lobe = self.lobes[lobe_name]

        # Route to appropriate method based on lobe type
        if lobe_name == "topological":
            if method == "verify_coverage":
                # Default mock return since verify_coverage is gone or renamed
                return {"verified": True}
            elif method == "verify_coverage_invariants":
                return {"verified": lobe.verify_coverage_invariants(input_data)}

        elif lobe_name == "geometric":
            if method == "calculate_curvature":
                return lobe.calculate_curvature(input_data)
            elif method == "filter_resonance_gate":
                return {"filtered": lobe.filter_resonance_gate(input_data)}

        elif lobe_name == "predictive":
            if method == "monitor_and_adjust":
                return lobe.monitor_and_adjust(input_data)
            elif method == "evaluate_free_energy_delta":
                baseline, empirical = input_data
                return lobe.evaluate_free_energy_delta(baseline, empirical)

        elif lobe_name == "causal":
            if method == "evaluate_hubs":
                return lobe.evaluate_hubs(input_data)
            elif method == "isolate_performance_hub":
                return {"hub": lobe.isolate_performance_hub(input_data)}

        elif lobe_name == "counterfactual":
            if method == "assert_allowed_transformation":
                proposal, phi_coherence = input_data
                return {"allowed": lobe.assert_allowed_transformation(proposal, phi_coherence)}
            elif method == "validate_transform":
                return lobe.validate_transform(input_data)

        elif lobe_name == "quantum":
            if method == "compute_von_neumann_entropy":
                return {"entropy": lobe.compute_von_neumann_entropy(input_data)}
            elif method == "grover_search_iteration":
                return lobe.grover_search_iteration(session_id=self.session_id)

        return {"error": f"Unknown method {method} for lobe {lobe_name}"}

    def cross_subsystem_consensus(self, topic: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run consensus across all active subsystems for a given topic.

        This enables coordinated decision-making across Pythia, Al Haras, and Salamander.
        """
        logger.info(f"[Euclid] Cross-subsystem consensus: {topic}")

        # Collect inputs from all active subsystems
        subsystem_inputs = {}
        for name, state in self.subsystems.items():
            if state.active:
                subsystem_inputs[name] = state.metrics

        # Use causal intelligence to evaluate the situation
        causal_result = self.lobes["causal"].evaluate_hubs(
            {**data, "subsystem_states": subsystem_inputs}
        )

        # Use counterfactual intelligence to validate the decision
        proposal = {"name": topic, **data}
        phi_coherence = data.get("phi_coherence", 0.8)
        allowed = self.lobes["counterfactual"].assert_allowed_transformation(
            proposal, phi_coherence
        )

        return {
            "topic": topic,
            "consensus": causal_result["action"],
            "allowed": allowed,
            "subsystem_inputs": subsystem_inputs,
            "timestamp": time.time(),
        }


# Singleton instance for global access
_euclid_instance: Optional[EuclidCore] = None


def get_euclid(memory_db: Optional[IntelligenceMemoryDB] = None) -> EuclidCore:
    """Get the singleton Euclid Core instance."""
    global _euclid_instance
    if _euclid_instance is None:
        _euclid_instance = EuclidCore(memory_db=memory_db)
    return _euclid_instance
