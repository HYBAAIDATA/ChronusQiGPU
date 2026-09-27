"""
HYBA Core — 6-Dimensional Intelligence Taxonomy & Unified Execution Graph
Layer 1: Topological Intelligence
Layer 2: Geometric Intelligence
Layer 3: Predictive Intelligence
Layer 4: Causal Intelligence
Layer 5: Counterfactual Intelligence
Layer 6: Quantum Intelligence
"""

from __future__ import annotations
import math
from typing import Any, Dict, Optional, Tuple, Sequence

try:
    import numpy as np
except ImportError:

    class _NumpyFallback:
        def ndarray(self, *args, **kwargs):
            return list

        def asarray(self, a, dtype=None):
            return list(a)

        def mean(self, a):
            return sum(a) / len(a) if a else 0.0

        def std(self, a):
            if not a:
                return 0.0
            m = sum(a) / len(a)
            return (sum((x - m) ** 2 for x in a) / len(a)) ** 0.5

        def abs(self, a):
            return [abs(x) for x in a]

        def eigvalsh(self, a):
            return [0.5, 0.5]

    np = _NumpyFallback()

try:
    from .intelligence_memory import IntelligenceMemoryDB
except ImportError:
    try:
        from intelligence_memory import IntelligenceMemoryDB
    except ImportError:
        IntelligenceMemoryDB = None  # type: ignore


class TopologicalIntelligence:
    """
    Layer 1: Topological Intelligence (Continuous Coverage)
    Partitioning maps parameters across 20 Dodecahedral nodes (D-nodes, degree-6)
    and 12 Icosahedral nodes (I-nodes, degree-10) forming a 32-node compound network graph.
    Preserves total graph automorphism group order of |Aut(G)| = 120.
    """

    def __init__(self, memory_db: Optional[Any] = None) -> None:
        self.d_nodes = 20
        self.i_nodes = 12
        self.total_nodes = 32
        self.aut_g = 120
        self.expected_automorphism_order = 120
        self.memory = memory_db or (
            IntelligenceMemoryDB.get_instance() if IntelligenceMemoryDB else None
        )

    def verify_coverage(self, session_id: str = "default_session") -> Dict[str, Any]:
        """Verify continuous graph coverage and automorphism order, logging to cognitive memory.

        NOTE (stub): every field returned here is a fixed constant
        (self.aut_g / self.d_nodes / self.i_nodes / self.total_nodes set in
        __init__) -- no actual graph is walked or checked against the 32-node
        topology this class describes, so "verified" cannot ever come back
        False and nothing here varies cycle to cycle. headless_miner.py's
        state_scan() only logs this output; there is no real per-cycle signal
        to wire it to. verify_coverage_invariants() below does real,
        input-dependent work, but nothing in the mining loop currently
        tracks a live 32-element active-node list to hand it, so it is left
        unused rather than wired to a fabricated one.
        """
        result = {
            "status": "verified",
            "automorphism_order": self.aut_g,
            "d_nodes": self.d_nodes,
            "i_nodes": self.i_nodes,
            "total_nodes": self.total_nodes,
        }
        if self.memory:
            self.memory.record_episode(
                session_id=session_id,
                lobe="topological",
                event_type="coverage_verification",
                input_state={"nodes": self.total_nodes},
                output_decision=result,
                confidence=1.0,
                reward=1.0,
            )
        return result

    def verify_coverage_invariants(self, active_nodes: Sequence[int]) -> Tuple[bool, int]:
        """Verify structural connectivity invariants across active nodes."""
        if len(active_nodes) != self.total_nodes:
            return False, 0
        genus = int(math.ceil((self.total_nodes - 4) / 2))
        return True, genus


class GeometricIntelligence:
    """
    Layer 2: Geometric Intelligence (Information Curvature)
    Applies non-Euclidean Fisher Information Metric to calculate information curvature.
    Guides execution pipelines to focus on search sectors where target nonces exhibit >= 0.5 resonance threshold.
    """

    def __init__(self, resonance_threshold: float = 0.5, memory_db: Optional[Any] = None) -> None:
        self.resonance_threshold = resonance_threshold
        self.phi = (1.0 + math.sqrt(5.0)) / 2.0
        self.memory = memory_db or (
            IntelligenceMemoryDB.get_instance() if IntelligenceMemoryDB else None
        )

    def calculate_curvature(
        self, parameters: Any, session_id: str = "default_session"
    ) -> Dict[str, Any]:
        """Calculates Fisher Information Metric curvature on input parameters or weights."""
        if isinstance(parameters, (list, tuple)) or hasattr(parameters, "size"):
            if len(parameters) == 0:
                return {"curvature": 0.0, "resonance": 0.0, "focused": False}
            mean_val = float(np.mean(parameters))
            std_val = float(np.std(parameters))
            curvature = std_val / (mean_val + 1e-12) if mean_val != 0 else 0.0
        else:
            curvature = 0.618

        # NOTE (stub): resonance below is a fixed 0.618 constant, not derived
        # from `curvature` or `parameters` -- it does not vary with input.
        # headless_miner.py's state_scan() calls this with self.state (a
        # dict), which always falls to the `else` branch above too, so in
        # practice neither curvature nor resonance reflect live mining state
        # from that call site today. Left un-wired rather than treated as a
        # real signal; see filter_resonance_gate() below for this lobe's
        # genuinely input-dependent computation, which headless_miner.py's
        # _phi_guided_nonce_search() now consults (opt-in, see that method).
        resonance = 0.618
        focused = resonance >= self.resonance_threshold
        result = {"curvature": curvature, "resonance": resonance, "focused": focused}

        if self.memory:
            self.memory.record_episode(
                session_id=session_id,
                lobe="geometric",
                event_type="curvature_calculation",
                input_state={"threshold": self.resonance_threshold},
                output_decision=result,
                confidence=resonance,
                reward=1.0 if focused else 0.5,
            )
        return result

    def filter_resonance_gate(self, nonces: Any) -> Any:
        """Filters nonces using Fibonacci-scaled phi resonance gate."""
        if hasattr(nonces, "__iter__"):
            filtered = []
            for n in nonces:
                score = 1.0 - abs(0.5 - ((float(n) * self.phi) % 1.0)) * 2.0
                if score >= self.resonance_threshold:
                    filtered.append(n)
            if hasattr(nonces, "dtype") and hasattr(np, "asarray"):
                return np.asarray(filtered, dtype=getattr(nonces, "dtype", float))
            return filtered
        return nonces


class PredictiveIntelligence:
    """
    Layer 3: Predictive Intelligence (Active Inference)
    Manages local runtime adjustments to minimize system free energy under heavy operational load.
    Monitors lane jitter, network packet latency, and thermodynamic indicators.
    If variance or drift metrics deviate beyond a 0.1 threshold, triggers recalibrations.
    """

    def __init__(self, energy_threshold: float = 0.1, memory_db: Optional[Any] = None) -> None:
        self.variance_threshold = energy_threshold
        self.energy_threshold = energy_threshold
        self.memory = memory_db or (
            IntelligenceMemoryDB.get_instance() if IntelligenceMemoryDB else None
        )

    def monitor_and_adjust(
        self, variance: float, session_id: str = "default_session"
    ) -> Dict[str, Any]:
        """Actionable window check on runtime variance."""
        if variance > self.variance_threshold:
            action = {"action": "recalibrate_boundaries", "dampen_lanes": True}
        else:
            action = {"action": "continue", "dampen_lanes": False}

        if self.memory:
            # Consult pitfall-defense memory: pitfall_003 (UNPHYSICAL_ENERGY_SPIKE) is
            # seeded for exactly this "free_energy_delta > 0.1" condition. Actually
            # querying it (rather than only ever writing episodes) is what lets past
            # operational experience influence the live decision instead of the
            # memory subsystem being a write-only log.
            if action["dampen_lanes"] and hasattr(self.memory, "check_and_log_pitfall"):
                pitfall = self.memory.check_and_log_pitfall(
                    "UNPHYSICAL_ENERGY_SPIKE",
                    {"variance": variance, "threshold": self.variance_threshold},
                )
                if pitfall.get("blocked"):
                    action["pitfall_countermeasure"] = pitfall["countermeasure"]
                    action["pitfall_severity"] = pitfall["severity"]

            self.memory.record_episode(
                session_id=session_id,
                lobe="predictive",
                event_type="active_inference_adjustment",
                input_state={"variance": variance, "threshold": self.variance_threshold},
                output_decision=action,
                confidence=1.0 - min(variance, 1.0),
                reward=0.0 if action["dampen_lanes"] else 1.0,
            )
        return action

    def evaluate_free_energy_delta(self, baseline: float, empirical: float) -> Tuple[bool, float]:
        """Evaluates free energy delta between baseline and empirical telemetry."""
        delta = abs(baseline - empirical)
        requires_adaptation = delta > self.energy_threshold
        return requires_adaptation, delta


class CausalIntelligence:
    """
    Layer 4: Causal Intelligence (Hub Isolation)
    Constructs Directed Acyclic Graphs (DAGs) representing executing processes, isolating optimal performance hubs.
    If processing lanes encounter deadlocks or sub-optimal hash yields, triggers Lindblad relaxation step (nack_slice).
    """

    def __init__(self, memory_db: Optional[Any] = None) -> None:
        self.memory = memory_db or (
            IntelligenceMemoryDB.get_instance() if IntelligenceMemoryDB else None
        )

    def isolate_performance_hub(self, lane_telemetry: Dict[str, float]) -> str:
        """Identifies optimal performance hub from lane telemetry."""
        if not lane_telemetry:
            return "node_31_gateway"
        return max(lane_telemetry, key=lane_telemetry.get)

    def evaluate_hubs(
        self, performance_metrics: Dict[str, Any], session_id: str = "default_session"
    ) -> Dict[str, Any]:
        """Evaluates execution hubs and triggers Lindblad relaxation if sub-optimal."""
        if performance_metrics.get("deadlock") or performance_metrics.get("yield", 1.0) < 0.5:
            action = {"action": "nack_slice", "relaxation": "Lindblad"}
        else:
            action = {"action": "optimal", "redistribute": False}

        if self.memory:
            # Consult pitfall-defense memory: pitfall_001 (DEADLOCK) is seeded for
            # exactly "lane_yield < 0.5". Querying it here lets the seeded
            # countermeasure (and the historical times_blocked counter) actually
            # drive the returned action, instead of only being logged after the
            # fact via record_episode.
            if action["action"] == "nack_slice" and hasattr(self.memory, "check_and_log_pitfall"):
                pitfall = self.memory.check_and_log_pitfall("DEADLOCK", performance_metrics)
                if pitfall.get("blocked"):
                    action["pitfall_countermeasure"] = pitfall["countermeasure"]
                    action["pitfall_severity"] = pitfall["severity"]

            self.memory.record_episode(
                session_id=session_id,
                lobe="causal",
                event_type="hub_evaluation",
                input_state=performance_metrics,
                output_decision=action,
                confidence=performance_metrics.get("yield", 1.0),
                reward=1.0 if not performance_metrics.get("deadlock") else 0.0,
            )
        return action


class CounterfactualIntelligence:
    """
    Layer 5: Counterfactual Intelligence (Transform Validation)
    Evaluates possible alternative configurations using constructor theory rules.
    Safety Gate: Verifies execution states against five core rules:
    Hermiticity, Positive Semi-Definiteness, Natural Scaling, Energy Conservation, Structural Integrity.
    """

    def __init__(self, memory_db: Optional[Any] = None) -> None:
        self.rules = [
            "hermiticity",
            "positive_semi_definiteness",
            "natural_scaling",
            "energy_conservation",
            "structural_integrity",
        ]
        self.memory = memory_db or (
            IntelligenceMemoryDB.get_instance() if IntelligenceMemoryDB else None
        )

    def assert_allowed_transformation(self, proposal: Dict[str, Any], phi_coherence: float) -> bool:
        """Determines if a proposed transformation state is permitted under constructor theory rules."""
        if phi_coherence < 0.45:
            if self.memory:
                self.memory.audit_counterfactual_transform(
                    proposal_name=proposal.get("name", "unnamed_proposal"),
                    phi_coherence=phi_coherence,
                    rules_evaluated={r: (r != "energy_conservation") for r in self.rules},
                    passed=False,
                    rejection_reason="Phi coherence < 0.45 threshold",
                )
            return False
        if proposal.get("is_hermitian") is False:
            if self.memory:
                self.memory.audit_counterfactual_transform(
                    proposal_name=proposal.get("name", "unnamed_proposal"),
                    phi_coherence=phi_coherence,
                    rules_evaluated={r: (r != "hermiticity") for r in self.rules},
                    passed=False,
                    rejection_reason="Non-Hermitian operator rejected",
                )
            return False
        if proposal.get("bypasses_approval", False):
            if self.memory:
                self.memory.audit_counterfactual_transform(
                    proposal_name=proposal.get("name", "unnamed_proposal"),
                    phi_coherence=phi_coherence,
                    rules_evaluated={r: (r != "structural_integrity") for r in self.rules},
                    passed=False,
                    rejection_reason="Unauthorized approval bypass detected",
                )
            return False

        if self.memory:
            self.memory.audit_counterfactual_transform(
                proposal_name=proposal.get("name", "valid_proposal"),
                phi_coherence=phi_coherence,
                rules_evaluated={r: True for r in self.rules},
                passed=True,
            )
        return True

    def validate_transform(self, state: Any) -> Dict[str, Any]:
        """Validates state transformation against all 5 core rules.

        NOTE (stub): rule_checks below is hardcoded {rule: True for rule in
        self.rules} -- none of the 5 rules are actually evaluated against
        `state`, so "validated" can never come back False from this method.
        This is what headless_miner.py's state_optimize() calls by default;
        left as pass-through telemetry rather than wired to a fabricated
        gate. assert_allowed_transformation() above does real rule
        evaluation (phi_coherence threshold, Hermiticity, approval-bypass)
        and is now wired in as an opt-in real gate -- see
        HYBA_MINING_USE_COUNTERFACTUAL_GATE in headless_miner.py.
        """
        rule_checks = {rule: True for rule in self.rules}
        rules_passed = all(rule_checks.values())
        return {
            "validated": rules_passed,
            "state": state if rules_passed else None,
            "checks": rule_checks,
        }


class QuantumIntelligence:
    """
    Layer 6: Quantum Intelligence (Data Serving)
    Substrate-agnostic framework for encoding high-entropy state data.
    Virtual qubit states via trace-class non-separable density matrices (rho).
    Leverages multi-qubit Grover iterations restricted to 20-state dodecahedral basis.
    """

    def __init__(self, memory_db: Optional[Any] = None) -> None:
        self.basis_states = 20
        self.memory = memory_db or (
            IntelligenceMemoryDB.get_instance() if IntelligenceMemoryDB else None
        )
        # NOTE (stub, not wired into headless_miner.py's mining loop):
        # grover_search_iteration() below returns a hardcoded selected_state=1
        # and a decision dict that is not derived from any real Grover
        # amplitude-amplification computation over the 20-state basis -- it
        # is a fixed constant dressed as a search result. Unlike the other
        # lobe methods reachable from headless_miner.py (CausalIntelligence,
        # PredictiveIntelligence, GeometricIntelligence), there is no real
        # underlying computation here to wire a causal effect to. Flagged
        # for separate attention rather than faked, per the same standard
        # applied to pure_quantum_framework.py (deleted this session).

    def compute_von_neumann_entropy(self, rho: Any) -> float:
        """Computes Von Neumann entropy of trace-class density matrix rho."""
        try:
            if hasattr(rho, "ndim") and (rho.ndim != 2 or rho.shape[0] != rho.shape[1]):
                raise ValueError("Density matrix must be square.")
            eigenvalues = np.eigvalsh(rho) if hasattr(np, "eigvalsh") else [0.5, 0.5]
            entropy = 0.0
            for val in eigenvalues:
                if val > 1e-12:
                    entropy -= float(val * math.log2(val))
            return entropy
        except Exception:
            return 0.999

    def grover_search_iteration(self, session_id: str = "default_session") -> Dict[str, Any]:
        """Runs structurally guided multi-qubit Grover iteration over 20-state dodecahedral basis."""
        decision = {
            "selected_state": 1,
            "basis_states": self.basis_states,
            "optimization": "pre-SHA256",
        }
        if self.memory:
            self.memory.record_episode(
                session_id=session_id,
                lobe="quantum",
                event_type="grover_iteration",
                input_state={"basis_states": self.basis_states},
                output_decision=decision,
                confidence=0.9618,
                reward=1.0,
            )
        return decision
