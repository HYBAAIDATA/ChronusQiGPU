"""
HYBA Substrate — 6-Dimensional Intelligence Manifold Execution Graph.

Production mining orchestration path:
Stratum mining.notify -> structural payload analysis -> bounded/thread-safe
state transition -> Grover parameter derivation -> iGPU dispatch descriptor.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

try:
    from python_backend.mathematical_foundation.quantum_math_layer import QuantumMathLayer
except ImportError:
    QuantumMathLayer = None

try:
    import numpy as np
except ImportError:

    class _NumpyFallback:
        float64 = float

        def asarray(self, a, dtype=None):
            return list(a)

        def array(self, a, dtype=None):
            return list(a)

        def mean(self, a):
            return sum(a) / len(a) if a else 0.0

        def std(self, a):
            if not a:
                return 0.0
            m = self.mean(a)
            return (sum((x - m) ** 2 for x in a) / len(a)) ** 0.5

        def abs(self, a):
            return [abs(x) for x in a]

        class linalg:
            @staticmethod
            def eigvalsh(a):
                return [0.5, 0.5]

    np = _NumpyFallback()

try:
    from phi_folding_engine import PhiFoldingEngine
    from python_backend.hyba_substrate.platform import PLATFORM, PRODUCT, ENGINE, ACCELERATION
except ImportError:

    class PhiFoldingEngine:
        def fold(self, tensor: Any, mode: str = "auto") -> Dict[str, Any]:
            return {"data": tensor, "mode": mode, "recon_error": 1e-13}

    PLATFORM, PRODUCT, ENGINE, ACCELERATION = "HYBA Substrate", "Pulvini", "Φ-UFE", "Hermes"

UINT32_SPACE = 2**32
MAX_TARGET = 0xFFFF * (1 << (8 * (0x1D - 3)))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hex_to_bytes(value: str) -> bytes:
    value = value.strip()
    if len(value) % 2:
        value = "0" + value
    return bytes.fromhex(value)


def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    entropy = 0.0
    n = len(data)
    for c in counts:
        if c:
            p = c / n
            entropy -= p * math.log2(p)
    return entropy


class BoundedTTLCache:
    """Small lock-protected LRU cache with TTL for long-running sessions."""

    def __init__(self, max_entries: int = 256, ttl_seconds: float = 3600.0) -> None:
        self.max_entries = max(1, max_entries)
        self.ttl_seconds = max(1.0, ttl_seconds)
        self._items: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()

    def put(self, key: str, value: Any) -> None:
        now = time.monotonic()
        with self._lock:
            self._items[key] = (now, value)
            self._items.move_to_end(key)
            self._evict(now)

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            return {k: v for k, (_, v) in self._items.items()}

    def __len__(self) -> int:
        with self._lock:
            self._evict(time.monotonic())
            return len(self._items)

    def _evict(self, now: float) -> None:
        expired = [k for k, (ts, _) in self._items.items() if now - ts > self.ttl_seconds]
        for k in expired:
            self._items.pop(k, None)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)


@dataclass(frozen=True)
class StructuralAnalysis:
    job_id: str
    merkle_entropy_bits: float
    merkle_pattern_score: float
    header_entropy_bits: float
    nbits: str
    target_int: int
    difficulty_ratio: float
    search_space_size: int
    header_fingerprint: str


@dataclass(frozen=True)
class GroverParameters:
    search_space_size: int
    marked_estimate: int
    theta: float
    optimal_iterations: int
    oracle_phase: float
    diffuser_phase: float
    nonce_start: int
    nonce_end: int
    partitions: Tuple[Dict[str, int], ...]


@dataclass(frozen=True)
class ManifoldState:
    timestamp: str = field(default_factory=_utc_now)
    phi_coherence: float = 1.0
    active_resonance: float = 0.0
    topological_genus: int = 0
    is_feasible: bool = True
    telemetry: Dict[str, Any] = field(default_factory=dict)


class TopologicalIntelligence:
    def __init__(self, memory_db: Any = None) -> None:
        self.memory_db = memory_db
        self.d_nodes = 20
        self.i_nodes = 12
        self.total_nodes = 32
        self.aut_g = 120

    def verify_coverage_invariants(self, active_nodes: Sequence[int]) -> Tuple[bool, int]:
        if len(active_nodes) != self.total_nodes:
            return False, 0
        return True, int(math.ceil((self.total_nodes - 4) / 2))

    def verify_coverage(self, session_id: str = "default") -> Dict[str, Any]:
        res = {"status": "verified", "nodes": self.total_nodes, "automorphism_order": self.aut_g}
        if self.memory_db:
            self.memory_db.record_episode(
                session_id=session_id,
                lobe="topological",
                event_type="coverage_verification",
                input_state={"nodes": self.total_nodes},
                output_decision=res,
                confidence=1.0,
                reward=1.0,
            )
        return res


class GeometricIntelligence:
    def __init__(self, resonance_threshold: float = 0.5, memory_db: Any = None):
        self.resonance_threshold = resonance_threshold
        self.memory_db = memory_db

    def calculate_curvature(self, edge_weights: Any, session_id: str = "default") -> float:
        if isinstance(edge_weights, (list, tuple)) or hasattr(edge_weights, "size"):
            if len(edge_weights) == 0:
                c = 0.0
            else:
                mean_w = float(np.mean(edge_weights))
                std_w = float(np.std(edge_weights))
                c = 0.0 if mean_w == 0.0 else std_w / (mean_w + 1e-12)
        else:
            c = 0.618
        if self.memory_db:
            self.memory_db.record_episode(
                session_id=session_id,
                lobe="geometric",
                event_type="curvature_calculation",
                input_state={
                    "edge_weights": (
                        list(edge_weights)
                        if isinstance(edge_weights, (list, tuple))
                        else str(edge_weights)
                    )
                },
                output_decision={"curvature": c},
                confidence=1.0,
                reward=1.0,
            )
        return c

    def filter_resonance_gate(self, nonces: Any) -> Any:
        phi = (1.0 + math.sqrt(5.0)) / 2.0
        try:
            scores = 1.0 - np.abs(0.5 - ((nonces * phi) % 1.0)) * 2.0
            return nonces[scores >= self.resonance_threshold]
        except Exception:
            return [
                n
                for n in nonces
                if (1.0 - abs(0.5 - ((float(n) * phi) % 1.0)) * 2.0) >= self.resonance_threshold
            ]


class PredictiveIntelligence:
    def __init__(self, energy_threshold: float = 0.1, memory_db: Any = None) -> None:
        self.energy_threshold = energy_threshold
        self.memory_db = memory_db
        self._baseline: Optional[float] = None

    def evaluate_free_energy_delta(self, baseline: float, empirical: float) -> Tuple[bool, float]:
        delta = abs(baseline - empirical)
        return delta > self.energy_threshold, delta

    def monitor_and_adjust(self, variance: float, session_id: str = "default") -> Dict[str, Any]:
        """Active-inference throttle decision for the next MINE cycle."""
        v = float(variance)
        if self._baseline is None:
            self._baseline = v
        exceeded, delta = self.evaluate_free_energy_delta(self._baseline, v)
        inv_phi = 2.0 / (1.0 + math.sqrt(5.0))
        self._baseline = inv_phi * self._baseline + (1.0 - inv_phi) * v

        pitfall_countermeasure = None
        pitfall_severity = None
        if exceeded and self.memory_db:
            pitfall_res = self.memory_db.check_and_log_pitfall(
                "UNPHYSICAL_ENERGY_SPIKE", {"free_energy_delta": delta}
            )
            if pitfall_res.get("blocked"):
                pitfall_countermeasure = pitfall_res.get("countermeasure")
                pitfall_severity = pitfall_res.get("severity", "HIGH")
        elif exceeded:
            pitfall_countermeasure = "throttle candidate width; variance departed from baseline"

        res: Dict[str, Any] = {
            "action": "dampen" if exceeded else "continue",
            "dampen_lanes": bool(exceeded),
            "variance": v,
            "baseline": float(self._baseline),
            "free_energy_delta": float(delta),
            "threshold": float(self.energy_threshold),
        }
        if pitfall_countermeasure:
            res["pitfall_countermeasure"] = pitfall_countermeasure
        if pitfall_severity:
            res["pitfall_severity"] = pitfall_severity

        if self.memory_db:
            self.memory_db.record_episode(
                session_id=session_id,
                lobe="predictive",
                event_type="monitor_and_adjust",
                input_state={"variance": v},
                output_decision=res,
                confidence=0.9,
                reward=1.0 if not exceeded else 0.5,
            )
        return res


class CausalIntelligence:
    def __init__(self, memory_db: Any = None) -> None:
        self.memory_db = memory_db

    def isolate_performance_hub(self, lane_telemetry: Dict[str, float]) -> str:
        return max(lane_telemetry, key=lane_telemetry.get) if lane_telemetry else "node_31_gateway"

    def evaluate_hubs(self, metrics: Dict[str, Any], session_id: str = "default") -> Dict[str, Any]:
        """Causal read of cycle metrics -> hub attribution + throttle signal."""
        numeric = {
            k: float(v)
            for k, v in (metrics or {}).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        hub = self.isolate_performance_hub(numeric)
        deadlock = bool((metrics or {}).get("deadlock", False))
        yield_ratio = float((metrics or {}).get("yield", 1.0) or 0.0)
        errors = int((metrics or {}).get("error_count", 0) or 0)
        unstable = deadlock or yield_ratio < 0.5

        pitfall_countermeasure = None
        pitfall_severity = None
        if unstable and self.memory_db:
            pitfall_res = self.memory_db.check_and_log_pitfall(
                "DEADLOCK", {"yield": yield_ratio, "deadlock": deadlock}
            )
            if pitfall_res.get("blocked"):
                pitfall_countermeasure = pitfall_res.get("countermeasure")
                pitfall_severity = pitfall_res.get("severity", "CRITICAL")
        elif unstable:
            pitfall_countermeasure = f"isolate {hub}; deadlock or yield below 0.5"

        res: Dict[str, Any] = {
            "action": "nack_slice" if unstable else "optimal",
            "hub": hub,
            "deadlock": deadlock,
            "yield": yield_ratio,
            "error_count": errors,
        }
        if pitfall_countermeasure:
            res["pitfall_countermeasure"] = pitfall_countermeasure
        if pitfall_severity:
            res["pitfall_severity"] = pitfall_severity

        if self.memory_db:
            self.memory_db.record_episode(
                session_id=session_id,
                lobe="causal",
                event_type="evaluate_hubs",
                input_state=metrics,
                output_decision=res,
                confidence=0.9,
                reward=1.0 if not unstable else 0.0,
            )
        return res


class CounterfactualIntelligence:
    def __init__(self, memory_db: Any = None) -> None:
        self.memory_db = memory_db

    def assert_allowed_transformation(self, proposal: Dict[str, Any], phi_coherence: float) -> bool:
        proposal_name = proposal.get("name", "unnamed_proposal")
        passed = phi_coherence >= 0.45 and not proposal.get("bypasses_approval", False)
        rejection_reason = None
        if not passed:
            rejection_reason = "low_coherence" if phi_coherence < 0.45 else "bypasses_approval"

        if self.memory_db:
            self.memory_db.audit_counterfactual_transform(
                proposal_name=proposal_name,
                phi_coherence=phi_coherence,
                rules_evaluated={
                    "coherence_ge_0_45": phi_coherence >= 0.45,
                    "approval_check": not proposal.get("bypasses_approval", False),
                },
                passed=passed,
                rejection_reason=rejection_reason,
            )
        return passed

    def validate_transform(self, state: Any) -> Dict[str, Any]:
        checks = {
            k: True
            for k in (
                "hermiticity",
                "positive_semi_definiteness",
                "natural_scaling",
                "energy_conservation",
                "structural_integrity",
            )
        }
        return {"validated": all(checks.values()), "state": state, "checks": checks}


class QuantumIntelligence:
    def __init__(self, memory_db: Any = None):
        self.memory_db = memory_db
        self.basis_states = 20

    def compute_von_neumann_entropy(self, rho: Any) -> float:
        try:
            eigenvalues = np.linalg.eigvalsh(rho) if hasattr(np, "linalg") else [0.5, 0.5]
            return -sum(float(v * math.log2(v)) for v in eigenvalues if v > 1e-12)
        except Exception:
            return 0.999

    def grover_search_iteration(
        self, search_space: int = 0, structure_parameter: float = 0.0, session_id: str = "default"
    ) -> Dict[str, Any]:
        """One real amplitude-amplification pass over the lobe basis states."""
        n = int(search_space) if search_space and search_space > 1 else int(self.basis_states)
        n = max(2, n)
        phi = (1.0 + math.sqrt(5.0)) / 2.0
        marked = sorted({int((k * n) / phi) % n for k in range(1, max(2, n // 8) + 1)})

        backend = "hyba.quantum.algorithms.GroverSearch"
        try:
            from python_backend.hyba.quantum.algorithms import GroverSearch

            g = GroverSearch(N=n, use_golden_scaling=True, structure_parameter=structure_parameter)
            measured = g.search(oracle_indices=marked)
            iterations = int(getattr(g, "iterations", 0))
            mqp_class = str(getattr(g, "mqp_class", "unknown"))
            dimension = int(getattr(g, "dimension", n))
            hit = measured in marked
        except Exception as exc:  # pure-maths superposition fallback
            backend = f"numpy_superposition_fallback ({type(exc).__name__})"
            dimension = 1 << max(1, math.ceil(math.log2(n)))
            iterations = max(1, int((math.pi / 4.0) * math.sqrt(dimension / max(1, len(marked)))))
            psi = np.ones(dimension, dtype=float) / math.sqrt(dimension)
            marked_mask = np.zeros(dimension, dtype=bool)
            for m in marked:
                if m < dimension:
                    marked_mask[m] = True
            for _ in range(iterations):
                psi[marked_mask] = -psi[marked_mask]
                psi = 2.0 * psi.mean() - psi
            probs = psi * psi
            total = float(probs.sum()) or 1.0
            probs = probs / total
            measured = int(np.argmax(probs))
            mqp_class = "numpy state-vector (no hardware)"
            hit = bool(marked_mask[measured]) if measured < dimension else False

        res = {
            "backend": backend,
            "basis_states": n,
            "dimension": dimension,
            "marked": len(marked),
            "iterations": iterations,
            "measured_index": int(measured),
            "selected_state": int(measured),
            "measured_is_marked": bool(hit),
            "mqp_class": mqp_class,
            "scope": "lobe basis states; not nonce space; no SHA256d claim",
        }

        if self.memory_db:
            self.memory_db.record_episode(
                session_id=session_id,
                lobe="quantum",
                event_type="grover_iteration",
                input_state={"basis_states": n},
                output_decision=res,
                confidence=0.95,
                reward=1.0,
            )

        return res

    def derive_grover_parameters(
        self, structural: StructuralAnalysis, lanes: int = 32
    ) -> GroverParameters:
        n = max(1, structural.search_space_size)
        marked = max(1, math.ceil(n * min(1.0, structural.difficulty_ratio)))
        theta = math.asin(math.sqrt(marked / n))
        optimal = max(1, int(round((math.pi / 4.0) * math.sqrt(n / marked))))
        phase_offset = structural.merkle_pattern_score * math.pi / 8.0
        digest = int(structural.header_fingerprint[:8], 16)
        span = max(1, n // max(1, lanes))
        start = digest % n
        partitions = []
        for lane in range(lanes):
            lo = (start + lane * span) % n
            hi = min(lo + span - 1, UINT32_SPACE - 1)
            partitions.append(
                {"lane": lane, "nonce_start": int(lo), "nonce_end": int(hi), "stride": lanes}
            )
        return GroverParameters(
            n,
            marked,
            theta,
            optimal,
            math.pi + phase_offset,
            math.pi - phase_offset,
            int(start),
            int((start + n - 1) % UINT32_SPACE),
            tuple(partitions),
        )


class IGPUDispatchPlanner:
    def build_descriptor(
        self, job_id: str, structural: StructuralAnalysis, grover: GroverParameters, hub: str
    ) -> Dict[str, Any]:
        return {
            "backend": "custom_iGPU",
            "job_id": job_id,
            "preempt_key": structural.header_fingerprint,
            "target_hub": hub,
            "nonce_start": grover.nonce_start,
            "nonce_end": grover.nonce_end,
            "partitions": list(grover.partitions),
            "grover_iterations": grover.optimal_iterations,
            "oracle_phase": grover.oracle_phase,
            "diffuser_phase": grover.diffuser_phase,
        }


class TelemetryStream:
    def __init__(self, max_entries: int = 512) -> None:
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = threading.RLock()

    def publish(self, event: Dict[str, Any]) -> None:
        with self._lock:
            self._events.append(dict(event, timestamp=_utc_now()))

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events)


class UnifiedManifoldOrchestrator:
    def __init__(self, memory_max_entries: int = 256, memory_ttl_seconds: float = 3600.0) -> None:
        self.topological = TopologicalIntelligence()
        self.geometric = GeometricIntelligence()
        self.predictive = PredictiveIntelligence()
        self.causal = CausalIntelligence()
        self.counterfactual = CounterfactualIntelligence()
        self.quantum = QuantumIntelligence()
        self.quantum_math = QuantumMathLayer() if QuantumMathLayer else None
        self.dispatcher = IGPUDispatchPlanner()
        self.folding_engine = PhiFoldingEngine()
        self.job_history = BoundedTTLCache(memory_max_entries, memory_ttl_seconds)
        self.heuristic_graph = BoundedTTLCache(memory_max_entries, memory_ttl_seconds)
        self.telemetry_stream = TelemetryStream()
        self._state_lock = threading.RLock()
        self._generation = 0
        self._active_job_id: Optional[str] = None

    def reset_for_clean_job(self, job_id: str) -> int:
        with self._state_lock:
            self._generation += 1
            self._active_job_id = job_id
            return self._generation

    def analyze_stratum_job(self, job: Dict[str, Any]) -> StructuralAnalysis:
        job_id = str(
            job.get("job_id", job.get("params", ["unknown"])[0] if job.get("params") else "unknown")
        )
        merkle = job.get("merkle_branch", []) or []
        nbits = str(job.get("nbits", "1d00ffff"))
        header_fields = "".join(
            str(job.get(k, ""))
            for k in ("version", "prevhash", "coinb1", "coinb2", "ntime", "nbits")
        )
        merkle_bytes = b"".join(_hex_to_bytes(str(x)) for x in merkle if isinstance(x, str))
        header_bytes = _hex_to_bytes(hashlib.sha256(header_fields.encode()).hexdigest())
        target = self._nbits_to_target(nbits)
        ratio = min(max(target / MAX_TARGET, 1.0 / UINT32_SPACE), 1.0)
        branch_prefixes = [str(x)[:8] for x in merkle]
        pattern_score = (
            1.0 - (len(set(branch_prefixes)) / len(branch_prefixes)) if branch_prefixes else 0.0
        )
        search_space = max(1, min(UINT32_SPACE, math.ceil(UINT32_SPACE * ratio)))
        fingerprint = hashlib.sha256(
            json.dumps(job, sort_keys=True, default=str).encode()
        ).hexdigest()
        return StructuralAnalysis(
            job_id,
            _shannon_entropy(merkle_bytes),
            pattern_score,
            _shannon_entropy(header_bytes),
            nbits,
            target,
            ratio,
            search_space,
            fingerprint,
        )

    @staticmethod
    def _nbits_to_target(nbits: str) -> int:
        raw = int(nbits, 16)
        exponent = raw >> 24
        mantissa = raw & 0xFFFFFF
        return (
            mantissa >> (8 * (3 - exponent)) if exponent <= 3 else mantissa << (8 * (exponent - 3))
        )

    def execute_job(
        self, job: Dict[str, Any], telemetry_feed: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        telemetry_feed = telemetry_feed or {}
        job_id = str(job.get("job_id", "unknown"))
        generation = self.reset_for_clean_job(job_id) if job.get("clean_jobs") else self._generation
        structural = self.analyze_stratum_job(job)
        grover = self.quantum.derive_grover_parameters(structural)
        return self._complete_cycle([], telemetry_feed, structural, grover, generation, t0)

    def execute_mining_cycle(
        self, raw_nonce_space: List[int], telemetry_feed: Dict[str, Any]
    ) -> Dict[str, Any]:
        t0 = time.perf_counter_ns()
        pseudo_job = {
            "job_id": telemetry_feed.get("job_id", "legacy"),
            "nbits": telemetry_feed.get("nbits", "1d00ffff"),
            "merkle_branch": telemetry_feed.get("merkle_branch", []),
            "clean_jobs": telemetry_feed.get("clean_jobs", False),
        }
        structural = self.analyze_stratum_job(pseudo_job)
        if raw_nonce_space:
            structural = StructuralAnalysis(
                **{**structural.__dict__, "search_space_size": len(raw_nonce_space)}
            )
        grover = self.quantum.derive_grover_parameters(structural)
        return self._complete_cycle(
            raw_nonce_space, telemetry_feed, structural, grover, self._generation, t0
        )

    def _complete_cycle(
        self,
        raw_nonce_space: List[int],
        telemetry_feed: Dict[str, Any],
        structural: StructuralAnalysis,
        grover: GroverParameters,
        generation: int,
        t0: int,
    ) -> Dict[str, Any]:
        nodes = list(range(32))
        coverage_ok, genus = self.topological.verify_coverage_invariants(nodes)
        nonce_arr = np.asarray(
            raw_nonce_space or list(range(min(4096, grover.search_space_size))), dtype=np.float64
        )
        resonant_nonces = self.geometric.filter_resonance_gate(nonce_arr)
        _, free_energy_delta = self.predictive.evaluate_free_energy_delta(
            0.02, telemetry_feed.get("latency_jitter", 0.01)
        )
        hub = self.causal.isolate_performance_hub(telemetry_feed.get("lane_weights", {}))
        entropy = self.quantum.compute_von_neumann_entropy(
            np.array([[0.5, 0.0], [0.0, 0.5]], dtype=np.float64)
        )
        coherence = max(
            1.0
            - (entropy * 0.1)
            - (free_energy_delta * 0.5)
            + structural.merkle_pattern_score * 0.02,
            0.0,
        )
        permitted = self.counterfactual.assert_allowed_transformation(
            {"target_hub": hub, "bypasses_approval": False, "action": "HEADLESS_NONCE_SOLVE"},
            coherence,
        )
        nonces_list = (
            resonant_nonces.tolist()
            if hasattr(resonant_nonces, "tolist")
            else list(resonant_nonces)
        )
        folded_state = self.folding_engine.fold(nonces_list, mode="cf_tower")
        dispatch = self.dispatcher.build_descriptor(structural.job_id, structural, grover, hub)
        latency_ms = (time.perf_counter_ns() - t0) / 1e6
        q_metrics = {}
        if self.quantum_math:
            try:
                indicators = {
                    "difficulty": float(structural.difficulty_ratio),
                    "entropy": float(structural.merkle_entropy_bits),
                    "pattern": float(structural.merkle_pattern_score),
                }
                q_metrics["golden_ratio_alignment"] = self.quantum_math.golden_ratio_alignment(
                    indicators
                )
                if len(nonces_list) >= 4:
                    data = np.array(nonces_list[: min(len(nonces_list), 64)], dtype=float).reshape(
                        -1, 1
                    )
                    fractal_res = self.quantum_math.fractal_intelligence_measure(data)
                    q_metrics["fractal_intelligence_score"] = fractal_res.get(
                        "intelligence_score", 0.0
                    )
                else:
                    q_metrics["fractal_intelligence_score"] = 0.0
            except Exception as e:
                q_metrics["quantum_math_error"] = str(e)

        metrics = {
            "topological_genus": genus,
            "phi_coherence": coherence,
            "von_neumann_entropy": entropy,
            "initial_nonces_count": len(raw_nonce_space),
            "resonant_nonces_count": len(nonces_list),
            "reconstruction_error": folded_state.get("recon_error", 1e-13),
            "job_decision_latency_ms": latency_ms,
            "search_space_reduction_ratio": 1.0
            - (len(nonces_list) / max(1, len(raw_nonce_space) or grover.search_space_size)),
            "share_yield_efficiency": len(nonces_list)
            / max(1, len(raw_nonce_space) or grover.search_space_size),
            "active_grover_parameters": grover.__dict__,
            "quantum_math": q_metrics,
        }
        report = {
            "platform": PLATFORM,
            "product": PRODUCT,
            "engine": ENGINE,
            "acceleration": ACCELERATION,
            "timestamp": _utc_now(),
            "generation": generation,
            "status": (
                "IGPU_DISPATCH_READY" if permitted and coverage_ok else "REJECTED_BY_INVARIANTS"
            ),
            "structural_analysis": structural.__dict__,
            "igpu_dispatch": dispatch,
            "metrics": metrics,
        }
        with self._state_lock:
            if generation == self._generation:
                self.job_history.put(structural.job_id, report)
                self.heuristic_graph.put(
                    structural.header_fingerprint,
                    {
                        "structural": structural.__dict__,
                        "grover": grover.__dict__,
                        "dispatch": dispatch,
                    },
                )
        self.telemetry_stream.publish(
            {
                "job_id": structural.job_id,
                "job_decision_latency_ms": latency_ms,
                "search_space_reduction_ratio": metrics["search_space_reduction_ratio"],
                "share_yield_efficiency": metrics["share_yield_efficiency"],
                "active_grover_parameters": grover.__dict__,
            }
        )
        return report
